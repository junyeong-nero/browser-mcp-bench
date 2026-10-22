"""Sample explicitly owned process trees, never machine-wide command lines.

RSS is not unique physical memory. CPU counters and sampled peaks may miss
short-lived processes. Remote model compute is outside the measurement scope.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import json
import os
from pathlib import Path
import threading
import time
from typing import Any

import psutil


@dataclass(frozen=True)
class ResourceRoot:
    pid: int
    component: str
    owner: str
    externally_managed: bool = False


def component_for(name: str, inherited: str) -> str:
    name = name.lower()
    if inherited == "browser" or any(s in name for s in (
        "firefox", "nightly", "web content", "isolated web", "plugin-container",
        "socket process", "rdd process", "utility process", "webextensions",
        "privileged content", "gpu process",
    )):
        return "browser"
    if inherited == "harness" and (name == "node" or name == "uv" or "python" in name or name == "kitsune"):
        return "mcp"
    return inherited


class ProcessProbe:
    def __init__(self) -> None:
        self.roots: dict[tuple[int, float], dict] = {}
        self.known: dict[tuple[int, float], dict] = {}
        self.errors = 0

    def register(self, root: ResourceRoot) -> None:
        try:
            process = psutil.Process(root.pid)
            key = (root.pid, process.create_time())
            meta = {"component": root.component, "owner": root.owner,
                    "externally_managed": root.externally_managed}
            self.roots[key] = meta
            self.known[key] = meta
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            self.errors += 1

    def capture(self) -> tuple[list[dict], dict]:
        # Continue observing known children after reparenting. New children are
        # discovered only below verified identities; do not adopt a recycled PID.
        for key, meta in list(self.known.items()):
            try:
                parent = psutil.Process(key[0])
                if parent.create_time() != key[1]:
                    continue
                for child in parent.children():
                    child_key = (child.pid, child.create_time())
                    if child_key not in self.known and child.pid != os.getpid():
                        self.known[child_key] = {
                            **meta, "component": component_for(child.name(), meta["component"])}
            except psutil.NoSuchProcess:
                continue
            except psutil.AccessDenied:
                self.errors += 1
        # Breadth-first discovery to include descendants born between samples.
        seen: set[tuple[int, float]] = set()
        pending = list(self.known)
        processes = []
        while pending:
            key = pending.pop(0)
            if key in seen or key[0] == os.getpid():
                continue
            seen.add(key)
            meta = self.known[key]
            try:
                p = psutil.Process(key[0])
                with p.oneshot():
                    if p.create_time() != key[1]:
                        continue
                    cpu = p.cpu_times()
                    processes.append({"pid": p.pid, "create_time": key[1], "ppid": p.ppid(),
                        "name": p.name(), "status": p.status(), "rss_bytes": p.memory_info().rss,
                        "cpu_user_sec": cpu.user, "cpu_system_sec": cpu.system, **meta})
                    for child in p.children():
                        child_key = (child.pid, child.create_time())
                        if child_key not in self.known:
                            self.known[child_key] = {**meta, "component": component_for(child.name(), meta["component"])}
                        if child_key not in seen:
                            pending.append(child_key)
            except psutil.NoSuchProcess:
                continue
            except psutil.AccessDenied:
                self.errors += 1
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()
        system = {"total_memory_bytes": memory.total, "available_memory_bytes": memory.available,
                  "swap_used_bytes": swap.used, "logical_cpu_count": psutil.cpu_count()}
        return processes, system


class ResourceCollector:
    def __init__(self, directory: Path, *, interval_sec: float = 1.0,
                 roots: tuple[ResourceRoot, ...] = (), probe: Any = None) -> None:
        if not 0.05 <= interval_sec <= 60:
            raise ValueError("Resource interval must be between 0.05 and 60 seconds.")
        self.directory = Path(directory)
        self.interval = interval_sec
        self.probe = probe if probe is not None else ProcessProbe()
        for root in roots:
            self.probe.register(root)
        self.phase = "baseline"
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._file = None
        self._started = 0.0
        self._wall_started = 0.0
        self._previous: dict | None = None
        self._identities: dict[tuple[int, float], dict] = {}
        self._buckets: dict[str, dict] = defaultdict(lambda: {
            "samples": 0, "sampled_peak_rss_bytes": 0, "rss_byte_seconds": 0.0,
            "duration_sec": 0.0, "observed_cpu_user_sec": 0.0,
            "observed_cpu_system_sec": 0.0, "peak_process_count": 0})
        self._errors = 0
        self._samples = 0
        self._overhead = 0.0
        self.summary: dict = {}

    def __enter__(self) -> ResourceCollector:
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._file = (self.directory / "resources.jsonl").open("x")
        os.chmod(self._file.name, 0o600)
        self._started = time.monotonic()
        self._wall_started = time.time()
        self.sample()
        self._thread = threading.Thread(target=self._loop, name="resource-sampler", daemon=True)
        self._thread.start()
        return self

    def register(self, root: ResourceRoot) -> None:
        with self._lock:
            self.probe.register(root)
            self.sample()

    def set_phase(self, phase: str) -> None:
        with self._lock:
            self.sample()
            self.phase = phase
            self.sample()

    def _loop(self) -> None:
        while not self._stop.wait(self.interval):
            self.sample()

    @staticmethod
    def _groups(processes: list[dict]) -> dict[str, dict]:
        groups: dict[str, dict] = {}
        for p in processes:
            for key in ("all", "owner/" + p["owner"], "component/" + p["owner"] + "/" + p["component"]):
                group = groups.setdefault(key, {"rss": 0, "count": 0, "user": 0.0, "system": 0.0})
                group["rss"] += p["rss_bytes"]
                group["count"] += 1
                group["user"] += p["cpu_user_delta_sec"]
                group["system"] += p["cpu_system_delta_sec"]
        groups.setdefault("all", {"rss": 0, "count": 0, "user": 0.0, "system": 0.0})
        return groups

    def sample(self) -> None:
        with self._lock:
            if self._file is None:
                return
            before = time.monotonic()
            try:
                processes, system = self.probe.capture()
            except (OSError, psutil.Error):
                self._errors += 1
                return
            elapsed = time.monotonic() - self._started
            for p in processes:
                key = (p["pid"], p["create_time"])
                previous = self._identities.get(key)
                born_during = p["create_time"] >= self._wall_started
                p["cpu_user_delta_sec"] = max(0.0, p["cpu_user_sec"] - (
                    previous["cpu_user_sec"] if previous else (0.0 if born_during else p["cpu_user_sec"])))
                p["cpu_system_delta_sec"] = max(0.0, p["cpu_system_sec"] - (
                    previous["cpu_system_sec"] if previous else (0.0 if born_during else p["cpu_system_sec"])))
                dt = elapsed - previous["elapsed_sec"] if previous else elapsed
                p["cpu_percent_one_core"] = ((p["cpu_user_delta_sec"] + p["cpu_system_delta_sec"]) / dt * 100
                                              if dt > 1e-6 else None)
                self._identities[key] = {**p, "elapsed_sec": elapsed}
            groups = self._groups(processes)
            if self._previous:
                dt = max(0, elapsed - self._previous["elapsed_sec"])
                # Left-rectangle time integration; phase boundaries force a
                # sample before and after transition to avoid phase mixing.
                for group, value in self._previous["groups"].items():
                    for bucket_key in (group, "phase/" + self._previous["phase"] + "/" + group):
                        bucket = self._buckets[bucket_key]
                        bucket["rss_byte_seconds"] += value["rss"] * dt
                        bucket["duration_sec"] += dt
            for group, value in groups.items():
                for bucket_key in (group, "phase/" + self.phase + "/" + group):
                    bucket = self._buckets[bucket_key]
                    bucket["samples"] += 1
                    bucket["sampled_peak_rss_bytes"] = max(bucket["sampled_peak_rss_bytes"], value["rss"])
                    bucket["peak_process_count"] = max(bucket["peak_process_count"], value["count"])
                    bucket["observed_cpu_user_sec"] += value["user"]
                    bucket["observed_cpu_system_sec"] += value["system"]
            row = {"elapsed_sec": elapsed, "phase": self.phase, "processes": processes,
                   "system": system, "groups": groups}
            self._file.write(json.dumps(row) + "\n")
            self._file.flush()
            self._previous = row
            self._samples += 1
            self._overhead += time.monotonic() - before

    def __exit__(self, exc_type, exc, tb) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
        with self._lock:
            self.sample()
            alive = [p for p in (self._previous or {}).get("processes", [])
                     if p["status"] not in {"zombie", "dead"}]
            metrics = {}
            for key, bucket in self._buckets.items():
                duration = bucket["duration_sec"]
                metrics[key] = {**{k: v for k, v in bucket.items() if k != "rss_byte_seconds"},
                    "time_weighted_mean_rss_bytes": bucket["rss_byte_seconds"] / duration if duration else None}
            self.summary = {
                "schema_version": 1, "backend": "psutil", "interval_sec": self.interval,
                "samples": self._samples, "sampling_errors": self._errors + self.probe.errors,
                "sampler_wall_overhead_sec": self._overhead, "metrics": metrics,
                "alive_at_stop": [{k: p[k] for k in ("pid", "create_time", "name", "component", "owner", "externally_managed")}
                                  for p in alive],
                "unexpected_alive_at_stop": [p["pid"] for p in alive if not p["externally_managed"]],
                "limitations": ["Summed RSS can double-count shared memory; not physical footprint/PSS.",
                    "Peaks and CPU deltas are sampled; short-lived/unobserved orphan processes may be missed.",
                    "CPU percent uses a one-core basis and may exceed 100%.",
                    "System context includes unrelated apps; sampler process is excluded from owned roots.",
                    "No remote model inference memory, GPU, or CPU is measured.",
                    "Time-weighted component means cover observed component windows, not missing lifetime tails."],
            }
            path = self.directory / "resource-summary.json"
            with path.open("x") as stream:
                json.dump(self.summary, stream, indent=2)
                stream.write("\n")
            path.chmod(0o600)
            self._file.close()
            self._file = None
