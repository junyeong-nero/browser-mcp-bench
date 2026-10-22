# MiniWoB++ external-task pilot

[Documentation index](README.md) · [Running guide](running.md) ·
[Historical MiniWoB result](results/2026-10-18-miniwob.md)

**Scope:** only `click-test-2`, seed 42, is wired into this adapter. This is not
a runner for the entire MiniWoB++ suite. For the current product-oriented work
on existing tabs, sessions and safe drafts, use the separate
[personal browsing track](personal-browsing.md).

## Why this environment first

WebArena-Verified requires a substantial self-hosted Docker environment. This
machine currently has no Docker CLI/engine; it has not been installed implicitly.
MiniWoB++ provides a small original HTML task/reward runtime that can be hosted
locally and exercised in the already isolated Firefox configurations.

This is an **external source/task/evaluator integration**, not a standard
MiniWoB++ leaderboard submission. It uses Codex + Firefox + native MCP UI tools,
not the standard Chrome/Selenium/Gym action/observation interface.

## Pinned source and experiment

Configuration: `configs/benchmarks/miniwob.json`.

- Source: https://github.com/Farama-Foundation/miniwob-plusplus
- Revision: `33c3b4ddef8c6eb67c57a29663d844b1eda7e614`.
- Original task: `miniwob/html/miniwob/click-test-2.html`.
- Original reward runtime: `miniwob/html/core/core.js`.
- Seed:42, applied through `Math.seedrandom(String(seed))` before episode generation.
- Episode budget:120000ms; upstream HTML defaults to10000ms. This explicit
  difference prevents treating the measurements as standard default-budget scores.
- Agent wall-clock limit:180 seconds per target.
- Configured model: `gpt-6-luna`, reasoning `medium`, Codex CLI0.163.0.
  Historical pilot results used `gpt-6.1-sol`; see the
  [dated result report](results/2026-10-18-miniwob.md). The current model setting
  has not been re-evaluated on this MiniWoB task.
- First pilot: one task/seed, one attempt per target, Playwright first.

The vendor checkout lives under gitignored `artifacts/vendor/miniwob`. Its HEAD
must match the pin and its working tree must be clean. Task HTML hash and source
revision are recorded. The upstream license remains in that checkout; source is
not redistributed as part of this project's tracked files.

## Installation and commands

```sh
uv sync --locked
npm ci --ignore-scripts --no-audit --no-fund
npm run setup:firefox

# Source download only; does not invoke a model.
uv run --locked python -m kitsune_benchmark benchmark --fetch

# Plan only; does not start browsers, Codex, or inference.
uv run --locked python -m kitsune_benchmark benchmark

# Actual paired trial; consumes ChatGPT subscription quota.
uv run --locked python -m kitsune_benchmark benchmark --execute
```

Provide `--kitsune-project /absolute/path/to/kitsune` if the source is not the
sibling checkout. Each execution uses fresh private browser profiles, bridge
ports/home/token, and a localhost-only benchmark HTTP server. No normal Zen
profile or default Kitsune bridge port is used.

## Task setup and reset

Each target receives a new trial token and page with the same original task and
seed. The prompt says to open that page, click START exactly once, and follow
its visible instruction. For this task, click ONE rather than TWO. Each trial
has independent load/start/result counters. A new page/profile plus seeded
original `genProblem()` is the reset boundary for this limited task.

The original files are not edited. The HTTP response adds an instrumentation
script before `</body>` that:

1. Seeds the existing RNG and sets the declared episode duration.
2. Calls the original `core.startEpisodeReal`, then records the episode start.
3. Calls the original `core.endEpisode`, then forwards the original
   `WOB_RAW_REWARD_GLOBAL`, `WOB_REWARD_GLOBAL`, and reason if it ended an active
   episode. It does not replace the task's click handlers or generate rewards.

The localhost server accepts bounded event payloads for active trials, validates
seed/task/time budget and finite reward values, records only the first terminal
result, and rejects malformed/duplicate results. Reloads or extra episode starts
invalidate a trial. The discounted reward remains the upstream computation;
raw reward1 indicates the successful click in this selected binary task.

## Evaluation and execution are separate

`evaluation.json` contains the original terminal reward, trial load/start counts,
telemetry errors, `scorable`, and `task_success`. The model's final text is never
used as a success signal. Execution audits must pass before a trial is scorable.
A valid started episode with no terminal reward at model completion is not a
success. Authentication/transport/audit failures are not silently turned into
ordinary task failures.

The generic Codex execution status may remain `completed_unscored`: that describes
completion of the execution adapter, before its external evaluator. The separate
`benchmark_evaluation` object and `evaluation.json` are the task verdict. A valid
external pair may exit0 even if an actual task fails; an invalid/unscorable pair
exits3. Do not infer task success from process exit alone.

## Tool policy and integrity limits

This pilot's explicit native-tool allowlists exclude `browser_js`,
`browser_evaluate`, `browser_run_code`, workflows, batch/parallel commands,
filesystem, shell, and raw-code/network entry points. Observation/click/type/
keyboard/select tools remain native to each server; they are not translated to
a synthetic common API. Observed tool names and unsafe navigation schemes are
audited after execution.

Why the restriction: MiniWoB rewards are client-side JavaScript state. An agent
with arbitrary page JS could call `core.endEpisode` or alter reward globals
instead of solving the task. The full-native smoke remains a separate track;
its tool configuration is not interchangeable with this UI-only pilot.

**This is not a hardened anti-cheating boundary.** Reward telemetry comes from
browser-side upstream code, not a privileged independent service. A malicious
agent exploiting an unexpected tool/browser surface could still forge it. The
recorded integrity label explicitly states that limitation. Do not use this
pilot for adversarial agent evaluation or claim a standard MiniWoB score.

## Artifacts and resources

Outputs: `artifacts/miniwob/<pair-id>/` (private/gitignored).

- `pair-manifest.json`: pins, source state, tool policy, extension patch, ports.
- `pair-summary.json`: execution results with attached external verdicts.
- `benchmark-summary.json`: benchmark configuration, original task hash, results.
- Per-run `evaluation.json`, Codex logs/final text, and resource files.
- Pair-level `resources.jsonl` / `resource-summary.json` across setup through cleanup.

Per-run resource metrics include owned client-side processes, not the model
server or benchmark HTTP environment thread in the observer process. Shared RSS
can be counted more than once; short-lived CPU/process peaks can be missed.
Kitsune's web-ext launcher is test infrastructure reported separately. See
[resources](resources.md) before interpreting RAM/CPU values.

## Actual validation and next steps

The first real pair completed with original raw reward1 for both targets,
zero tool/audit/telemetry/sampling errors, and no unexpected survivors:
[result report](results/2026-10-18-miniwob.md).

Still needed before a meaningful comparison: more task types/seeds, repeated
and counterbalanced runs, matched effective viewport and startup policy, controlled
cache effects, failure taxonomy, and confidence intervals. WebArena-Verified
remains a separate future adapter after its environment is provisioned.

References:

- https://miniwob.farama.org/
- https://github.com/Farama-Foundation/miniwob-plusplus
- https://github.com/ServiceNow/webarena-verified
