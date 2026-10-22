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
| **v0.3.0** | `99a90d2` (tag); `d616c50` = v0.3.0 + docs/agents only (`server.py` comment change) | Opus full suite (2026-10-23, running), 2026-10-22 rerun, disclosure, target view, Sonnet/Opus, integrated startup, tool usage |
| v0.2.1 → v0.3.0 (main) | `9d36c57`, `1045a5e`, `cf24851`, `56bd5d9`, `753406b` | 2026-10-21 personal 24, token efficiency, gallery |
| v0.1.0 → v0.2.0 (main) | `967dfdf`, `68f7e97` | 2026-10-18 smoke and MiniWoB, 2026-10-19 personal pilots |

No report ran on exactly the v0.1.0, v0.2.0 or v0.2.1 tags.

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
