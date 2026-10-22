# Results by Kitsune version

[Documentation index](../README.md) · [All result reports](README.md)

The same reports as the [dated list](README.md), grouped by the Kitsune source
each run used. Revisions come from each report and its `kitsune_source`
artifact; `git describe` is relative to the
[Kitsune tags](https://github.com/junyeong-nero/kitsune/tags). Reports within
one version still differ in model, harness, tasks and tool policy, so they are
not one leaderboard. Comparing across versions only isolates the Kitsune change
when model, harness and tasks match.

| Kitsune | Revisions | Reports |
| --- | --- | --- |
| **v0.3.0** | `99a90d2` (tag); `d616c50` = v0.3.0 + docs/agents only (`server.py` comment change) | Opus full suite (2026-10-23, running; `taskset-v1`), 2026-10-22 rerun, disclosure, target view, Sonnet/Opus, integrated startup, tool usage |
| v0.2.1 → v0.3.0 (main) | `9d36c57`, `1045a5e`, `cf24851`, `56bd5d9`, `753406b` | 2026-10-21 personal 24, token efficiency, gallery |
| v0.1.0 → v0.2.0 (main) | `967dfdf`, `68f7e97` | 2026-10-18 smoke and MiniWoB, 2026-10-19 personal pilots |

No report ran on exactly the v0.1.0, v0.2.0 or v0.2.1 tags.

## Frozen taskset

Version comparisons only mean something on an unchanged taskset. The current
one is frozen as git tag **`taskset-v1`** of this repository (`f1ff9fa`).
Every v0.3.0 report from the 2026-10-23 Opus suite on uses it; earlier reports
predate the tag and ran on earlier task/grader code.

Frozen in `taskset-v1`:

- Personal: `tasks/personal/catalog.json`, `kitsune_benchmark/personal_fixtures.py`,
  `personal.py` and `personal_session.py` (fixtures, variants and graders).
- Gallery: `kitsune_benchmark/gallery.py`, `gallery_static/`, `gallery_media.py`.
- MiniWoB: `configs/benchmarks/miniwob.json` (upstream revision, task, seed).
- Harness: Claude Code `2.1.303`, Playwright MCP `0.0.83`, UI tool allowlists,
  per-run timeouts in `configs/benchmarks/`.

Rules:

- Do not change frozen files on `main` for a v1 run. A grader bug fix becomes
  `taskset-v1.1`; rerun the Kitsune versions being compared on it, and never
  compare scores across taskset versions.
- Model, effort and per-run cap may vary per run (`--claude-model`,
  `--max-budget-usd-per-run`); report them, and compare versions only at the same
  model.
- Each report names its taskset tag next to the Kitsune revision.
- A full-suite run on one Kitsune revision is an **observation**. Under the
  [workflow](https://github.com/junyeong-nero/kitsune/blob/main/docs/workflow.md) it can motivate a `hypothesis` issue but is not that
  hypothesis's baseline: baseline and candidate are re-run together on the same
  taskset tag, model, attempts and counterbalanced order. A reproducible Kitsune
  failure (same task failing on every variant) is filed as a Kitsune `bug`, and a
  grader or fixture defect as a taskset change here.

### Upgrading with the next Kitsune release

v1 has a ceiling: Haiku already reaches 23/24 personal and 21/21 isolated gallery,
and there is one attempt per task in a fixed order. Introduce `taskset-v2`
together with the next Kitsune release:

1. Run the new release on `taskset-v1` first, for continuity with this table.
2. Freeze `taskset-v2` (harder tasks, repeated trials, counterbalanced order).
3. Run both the previous release and the new one on `taskset-v2`, so the new
   taskset has its own baseline.

Steps 1 and 3 are observations; a claim that the release is better on some metric
still goes through a `hypothesis` issue.

## v0.3.0

`99a90d22c83d6e931814b3c3dadd96c08c633820`, default tool preset **lean** (14 tools).

| Date | Report | Model / harness | Kitsune revision | Notes |
| --- | --- | --- | --- | --- |
| 2026-10-23 | Opus full suite (in progress; artifacts in `artifacts/opus-full/`) | `claude-opus-5-5`, Claude Code API bare | `d616c50` (`v0.3.0-4`) | Personal 24 × 3 variants, gallery 21 × 3 variants × 2 layouts, MiniWoB; $100 cap |
| 2026-10-22 | [Tool usage inventory](2026-10-22-tool-usage.md) | Offline | v0.3.0 | 196 existing v0.3.0 runs |
| 2026-10-22 | [Sonnet / Opus targeted follow-up](2026-10-22-sonnet-opus-target-view.md) | Sonnet 5.5 / Opus 5.5, API bare | `99a90d2` | 16 runs, lean |
| 2026-10-22 | [Target/action view A/B](2026-10-22-target-view-ab.md) | Haiku 5.5, API bare | `99a90d2` | 60 runs |
| 2026-10-22 | [Disclosure × expect A/B](2026-10-22-disclosure-ab.md) | Haiku 5.5, API bare | `99a90d2` | 72 Kitsune-only runs |
| 2026-10-22 | [Integrated Opus startup](2026-10-22-integrated-startup.md) | Opus 5.5, API | `99a90d2` | Harness-error diagnostic, not a score |
| 2026-10-22 | [Kitsune 0.3.0 rerun](2026-10-22-kitsune-0.3.0.md) | Haiku 5.5, API bare / full | `99a90d2` | Personal 24; compares against `1045a5e` |

## v0.2.1 → v0.3.0 (pre-release main)

| Date | Report | Model / harness | Kitsune revision | Notes |
| --- | --- | --- | --- | --- |
| 2026-10-21 | [Component gallery](2026-10-21-gallery.md) | Haiku 5.5, API | `56bd5d9` (`v0.2.1-134`) | No-model re-check of failures on `753406b` (`v0.2.1-164`) |
| 2026-10-21 | [Token efficiency analysis](2026-10-21-token-efficiency.md) | Haiku 5.5, API bare | `1045a5e` pairs 1–16, `cf24851` pairs 17–24 (`v0.2.1-132/133`) | Checkout moved mid-suite; led to the revision guard |
| 2026-10-21 | [All 24 personal tasks](2026-10-21-personal-24-claude-haiku.md) | Haiku 5.5, Claude Code subscription | `9d36c57` (`v0.2.1-37`) | |

## v0.1.0 → v0.2.0 (pre-release main)

| Date | Report | Model / harness | Kitsune revision | Notes |
| --- | --- | --- | --- | --- |
| 2026-10-19 | [Six-task personal pilot](2026-10-19-personal-six-task.md) | `gpt-6-luna`, Codex | `68f7e97` (`v0.1.0-5`) | |
| 2026-10-19 | [Personal current-page pair](2026-10-19-personal-current-page.md) | `gpt-6-luna`, Codex | `68f7e97` (`v0.1.0-5`) | |
| 2026-10-18 | [MiniWoB++ pilot](2026-10-18-miniwob.md) | `gpt-6.1-sol`, Codex | `967dfdf` (`v0.1.0-2`) | |
| 2026-10-18 | [Read-only smoke](2026-10-18-smoke.md) | `gpt-6.1-sol`, Codex | `967dfdf` (`v0.1.0-2`) | |

## Adding a report

Record the full Kitsune revision and `git -C <kitsune> describe --tags` in the
report, then add a row under that version. `scripts/run-full-suite.py` writes both
to `suite-manifest.json`.
