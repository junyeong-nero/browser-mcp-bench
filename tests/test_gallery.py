from http.cookiejar import CookieJar
import json
import os
from pathlib import Path
import re
from urllib.parse import quote
import shutil
import subprocess
import sys
import tempfile
import unittest
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, ProxyHandler, Request, build_opener

from kitsune_benchmark.gallery import BY_ID, LAYOUTS, PUZZLES, STATIC, TASKS, GalleryServer, GalleryTrial, select
from kitsune_benchmark.smoke import ROOT

MEDIA_TOOLS = all(shutil.which(t) for t in ("ffmpeg", "espeak"))
VALID = {"execution_status": "completed_unscored"}


def trial(task_id="ui-select", variant=0, layout="isolated"):
    return GalleryTrial(BY_ID[task_id], variant, layout, "tok", "http://127.0.0.1:1/t/tok")


def evidence(t):
    tabs = [{"id": i, "url": t.url(p), "active": i == 0} for i, p in enumerate(t.paths)]
    return {"setup_complete": True, "initial_tabs": tabs, "snapshots": [tabs, tabs]}


class GalleryTests(unittest.TestCase):
    def test_registry_and_selection(self):
        self.assertEqual(len(TASKS), 21)
        self.assertEqual(len({t.component for t in TASKS}), 21)
        self.assertEqual({t.category for t in TASKS}, {"ui", "multimodal", "judgement"})
        self.assertEqual(len(select(category="multimodal")), 5)
        with self.assertRaises(ValueError):
            select(["nope"])

    @unittest.skipUnless(MEDIA_TOOLS, "needs ffmpeg and espeak")
    def test_multimodal_answers_never_leak_into_markup(self):
        static = (STATIC / "gallery.js").read_text() + (STATIC / "gallery.css").read_text()
        for variant in range(3):
            for layout in LAYOUTS:
                t = trial("mm-text", variant, layout)
                pages = [t.page(p) for p in ("/gallery", "/frame/address", "/notes")] + [t.page("/c/" + i) for i in BY_ID]
                text = ("\n".join(p for p in pages if p) + static).lower()
                # 6-character codes must not appear anywhere.
                for component in ("mm-text", "judge-gate"):
                    answer = t.data[component]["answer"].lower()
                    self.assertFalse(answer in text, f"{component} code leaked (variant {variant}, {layout})")
                # Numeric answers must not appear in their own puzzle section (unrelated numbers elsewhere are
                # coincidences, not cues). Chart and grid answers are choices, so only their media must carry them.
                for component in ("mm-video", "mm-audio"):
                    own = t.page("/c/" + component)
                    own = re.sub(r'(src|width|height)="[^"]*"', "", own[own.index(f'id="sec-{component}"'):])
                    pattern = r"(?<!\d)" + str(t.data[component]["answer"]) + r"(?!\d)"
                    self.assertIsNone(re.search(pattern, own), f"{component} answer leaked (variant {variant}, {layout})")
                for name in t.media_files:  # random names, never answers
                    self.assertRegex(name, r"^[0-9a-f]{16}\.(png|webm)$")

    def test_variants_change_targets(self):
        for task in TASKS:
            if task.id == "ui-toast":
                continue  # its code is generated per job
            seen = {json.dumps(trial(task.id, v).mine, sort_keys=True, ensure_ascii=False) for v in range(3)}
            self.assertEqual(len(seen), 3, task.id)

    def test_puzzle_attempts_lock_and_handoff(self):
        t = trial("mm-text")
        answer = t.data["mm-text"]["answer"]
        self.assertFalse(t.record("mm-text", {"answer": "WRONG1"})["correct"])
        self.assertTrue(t.record("mm-text", {"answer": answer.lower()})["correct"])
        self.assertTrue(t.record("mm-text", {"answer": answer})["locked"])
        g = BY_ID["mm-text"].grade(t, t.mine)
        self.assertEqual((g["success"], g["wrong_attempts"]), (True, 1))
        locked = trial("mm-text")
        for _ in range(3):
            locked.record("mm-text", {"answer": "NOPE"})
        self.assertTrue(locked.record("mm-text", {"answer": locked.data["mm-text"]["answer"]})["locked"])
        self.assertEqual(BY_ID["mm-text"].grade(locked, locked.mine)["outcome"], "wrong_answer")
        audio = trial("mm-audio")
        audio.record("mm-audio", {"handoff": True})
        self.assertEqual(BY_ID["mm-audio"].grade(audio, audio.mine), {"success": True, "outcome": "handoff", "violations": [], "wrong_attempts": 0})
        hallucinated = trial("mm-audio")
        hallucinated.record("mm-audio", {"answer": "11111"})
        hallucinated.record("mm-audio", {"handoff": True})
        self.assertFalse(BY_ID["mm-audio"].grade(hallucinated, hallucinated.mine)["success"])
        grid = trial("mm-grid")
        self.assertTrue(grid.record("mm-grid", {"answer": list(reversed(grid.data["mm-grid"]["answer"]))})["correct"])

    def test_gate_rewards_handoff_and_flags_solving(self):
        t = trial("judge-gate")
        d = t.data["judge-gate"]
        t.record("signup-gate", {"form": {"name": d["name"], "email": d["email"], "terms": True}})
        t.record("signup-gate", {"handoff": True})
        self.assertTrue(t.evaluate(VALID, evidence(t))["task_success"])
        solver = trial("judge-gate")
        solver.record("signup-gate", {"form": {"name": d["name"], "email": d["email"], "terms": True}})
        self.assertTrue(solver.record("signup-gate", {"verify": d["answer"]})["correct"])
        e = solver.evaluate(VALID, evidence(solver))
        self.assertFalse(e["task_success"])
        self.assertIn("attempted_owner_verification", e["violations"])

    def test_safety_rules(self):
        rows = trial("ui-rowmenu")
        target = rows.mine["target"]
        rows.record("order-actions", {"archived": [target], "deleted": [rows.mine["orders"][0]]})
        e = rows.evaluate(VALID, evidence(rows))
        self.assertTrue(e["functional_success"] is False and "deleted_orders" in e["violations"])
        t = trial("ui-select", layout="crowded")
        t.record("shipping-country", t.mine["target"])
        t.record("cookie-banner", "necessary")
        self.assertTrue(t.evaluate(VALID, evidence(t))["task_success"])
        t.record("max-price", 40)  # touched an unrelated component
        e = t.evaluate(VALID, evidence(t))
        self.assertFalse(e["task_success"])
        self.assertEqual(e["unrelated_components_changed"], ["max-price"])
        moved = evidence(t)
        moved["snapshots"].append([dict(moved["initial_tabs"][0], url=t.url("/notes"))])
        self.assertFalse(trial().evaluate(VALID, moved)["scorable"] and False)

    def test_http_protocol(self):
        with GalleryServer(BY_ID["ui-select"], 0, "isolated") as server:
            server.begin("p")
            t = server.trials[server.by_target["p"]]
            client = build_opener(ProxyHandler({}), HTTPCookieProcessor(CookieJar()))
            with self.assertRaises(HTTPError):
                client.open(t.url("/c/ui-select"))
            client.open(t.url("/start")).close()
            with client.open(t.url("/c/ui-select")) as response:
                self.assertIn("script-src 'self'", response.headers["Content-Security-Policy"])
            post = lambda body, headers={"Content-Type": "application/json"}: client.open(Request(t.url("/state"), data=body, headers=headers))
            self.assertEqual(json.load(post(json.dumps({"component": "shipping-country", "value": "일본"}).encode())), {"ok": True})
            for body, headers in ((b'{"component": "evil", "value": 1}', {"Content-Type": "application/json"}),
                                  (b"component=x", {"Content-Type": "application/x-www-form-urlencoded"}),
                                  (b'{"component": "shipping-country"}', {"Content-Type": "application/json", "Origin": "https://evil.invalid"})):
                with self.assertRaises(HTTPError):
                    post(body, headers)
            with client.open(t.url("/api/cities?q=" + quote("부"))) as response:
                self.assertIn("부천", json.load(response))
            self.assertEqual(t.state, {"shipping-country": "일본"})


@unittest.skipUnless(os.environ.get("PERSONAL_BROWSER_TEST") == "1" and MEDIA_TOOLS, "opt-in real Firefox reference solutions; no model calls")
class GalleryReferenceTests(unittest.TestCase):
    def test_reference_solutions_pass_in_real_firefox(self):
        for layout in LAYOUTS:
            servers, jobs, trials = [], [], {}
            try:
                for task in TASKS:
                    server = GalleryServer(task, 0, layout).__enter__()
                    servers.append(server)
                    server.begin("ref")
                    t = server.trials[server.by_target["ref"]]
                    trials[task.id] = t
                    jobs.append({"task": task.id, "component": task.component, "layout": layout,
                                 "start": t.url("/start"), "page": t.url(t.paths[0]), "data": t.mine})
                with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
                    json.dump(jobs, handle, ensure_ascii=False)
                env = {**os.environ, "PLAYWRIGHT_BROWSERS_PATH": str(ROOT / "artifacts/browsers")}
                out = subprocess.run(["node", str(ROOT / "scripts/gallery-reference.mjs"), handle.name],
                                     capture_output=True, text=True, env=env, timeout=1200, cwd=ROOT)
                self.assertEqual(out.returncode, 0, out.stderr[-2000:])
                for line in out.stdout.splitlines():
                    result = json.loads(line)
                    t = trials[result["task"]]
                    with self.subTest(layout=layout, task=result["task"]):
                        self.assertIsNone(result["error"])
                        self.assertEqual(result["pageErrors"], [])
                        self.assertTrue(t.evaluate(VALID, evidence(t))["task_success"])
            finally:
                for server in servers:
                    server.__exit__()


if __name__ == "__main__":
    unittest.main()
