# Browser MCP Bench

Compare **Playwright MCP vs Kitsune MCP** with a fixed Codex/model configuration,
external task evidence, and local process resource measurements.

## Current state

- **Harness:** Codex CLI `0.163.0`, existing ChatGPT subscription login.
- **Model:** `gpt-6.1-sol`, reasoning `medium`; no direct model API integration or
  API-key fallback. Execution consumes subscription quota.
- **Browser:** isolated Firefox 156 profiles using the same private-cache binary.
- **Resources:** one-second process sampling, including separately started
  Kitsune bridge/browser roots; setup/task/cleanup phases and private artifacts.
- **External pilot:** pinned MiniWoB++ `click-test-2`, seed 42, original reward
  evaluation. Both MCPs have completed one actual pilot episode successfully.
- **Not yet a benchmark suite:** no multi-task/repeated randomized experiments,
  WebArena deployment, full prompt/catalog attestation, or token-budget stopping.

MiniWoB results are a **Firefox MCP UI-only pilot**, not the standard Chrome/Gym
leaderboard. The configured episode budget is 120 seconds instead of upstream's
10-second HTML default. Do not generalize one episode into a success-rate ranking.

## Setup

Requires Python 3.11+, uv, Node/npm, a supported Codex ChatGPT login, and the
Kitsune source checkout (normally the sibling `../kitsune`).

```sh
uv sync --locked
npm ci --ignore-scripts --no-audit --no-fund
npm run setup:firefox
```

Python dependencies are pinned by `uv.lock` (psutil 7.2.2; no model SDK). npm tools
are pinned by `package-lock.json` (Playwright MCP 0.0.83, web-ext 10.8.0).
The Firefox setup helper uses `artifacts/browsers` and disables shared-cache GC.
No everyday browser profile is used by the automated pair runner.

## Inspect without using the model

```sh
uv run --locked python -m browser_mcp_bench doctor --json
uv run --locked python -m browser_mcp_bench smoke
uv run --locked python -m browser_mcp_bench benchmark
uv run --locked python -m unittest discover -s tests -v
```

`doctor` checks Codex version/help/login only. It flags API credential environment
variables in the caller's environment; actual runs use a restricted child
environment that omits those variables. The runner discovers an unambiguous
nvm Codex installation or accepts explicit `--codex /path/to/codex`.

## Run the isolated smoke pair

```sh
uv run --locked python -m browser_mcp_bench smoke --execute
```

Uses `configs/experiments/smoke.json`: read the Example Domain page in a new tab.
The final answer is not an external success label, so smoke executions remain
`completed_unscored`. Artifacts go to private, gitignored `artifacts/smoke/`.

The pair runner starts private HTTP/WS bridge ports and a temporary Firefox
profile for Kitsune using a copy of its extension. Only the copy's WebSocket
endpoint changes; the original extension and normal Zen profile are untouched.
Use `--kitsune-project /absolute/path/to/kitsune` for a non-sibling checkout.

## Run the external MiniWoB++ pilot

```sh
# Fetch pinned upstream source; no inference without --execute.
uv run --locked python -m browser_mcp_bench benchmark --fetch

# Actual quota-consuming paired task with original reward telemetry.
uv run --locked python -m browser_mcp_bench benchmark --execute
```

Configuration: `configs/benchmarks/miniwob.json`. Source revision:
`33c3b4ddef8c6eb67c57a29663d844b1eda7e614` from Farama-Foundation/miniwob-plusplus.
The source must remain clean. Original task files are served locally without
modifying the checkout. Response-layer instrumentation seeds randomness, sets
the documented episode budget, and forwards original `core.endEpisode` rewards.

This track exposes UI observation/interaction tools only; JS execution, workflows,
and batch/raw-code tools are not exposed. Each target gets one seeded episode;
restarts/reloads, malformed reward events, and execution audit failures are
not scorable. Grading uses original reward events, **not the model's answer**.
It is client-side telemetry, not a hardened anti-cheating boundary.

Artifacts go to private `artifacts/miniwob/`; per-run `evaluation.json` and
pair-level `benchmark-summary.json` retain the verdict and its limitations.
Generic execution status remains separate from task success.

## Individual runs and configurations

`plan`/`run` also accept explicit server/task JSON and `--model gpt-6.1-sol`.
See [Codex integration](docs/codex-harness.md) before using generic `run`, which
requires an operator-confirmed isolated browser and does not provision one.

- `configs/servers/playwright.json`: generic pinned package configuration.
- `configs/servers/kitsune.example.json`: replace its local checkout path.
- `configs/local/`: gitignored machine-specific configuration.
- `enabled_tools`: optional native-tool allowlist; the full native toolset is
  used when omitted, while the external UI pilot has an explicit restricted set.

## Resource measurement

Each run and pair writes `resources.jsonl` and `resource-summary.json`.
Measurements include RSS bytes, observed CPU user/system deltas, one-core CPU
percent, process count/status/identity, and system RAM/swap reference values.
Groups separate owner, component, and lifecycle phase. Final live processes are
recorded; per-run externally managed roots are not mistaken for pair-end leaks.

**Summed RSS is not unique physical RAM** and can double-count shared pages.
Peaks are sampled; short-lived children and final CPU tails can be missed.
Remote GPT inference resources are not measured. System memory includes unrelated
apps. Kitsune's web-ext launcher is test infrastructure and is reported separately.
See [resource measurement details](docs/resources.md).

## Reports and documentation

- [First smoke pair](docs/results/2026-10-18-smoke.md)
- [MiniWoB pilot with resource measurements](docs/results/2026-10-18-miniwob.md)
- [Codex integration and safety](docs/codex-harness.md)
- [Resource collection and interpretation](docs/resources.md)
- [MiniWoB setup, instrumentation, and evaluator](docs/miniwob.md)
- [Additional browser MCP candidates and comparison cohorts](docs/comparison-candidates.md)

## Fairness, safety, and remaining work

The evaluation unit is **model + Codex + MCP configuration**, not an intrinsic
model/server score. Fix versions, instructions, task seeds/state, budgets, and
evaluator before comparing. Preserve native schemas rather than normalizing away
tool design. Match browser/viewports and counterbalance run order; repeat tasks.

Current pilots have one fixed-order pair, shared prompt-cache effects, and
startup asymmetry: Kitsune's browser/bridge start outside the timed agent run,
while Playwright may start its browser inside a timed tool call. The pair-level
resource trace records setup separately but does not remove that asymmetry.

Use test accounts/controlled sites for mutations. MCP servers are trusted code;
Codex's read-only workspace sandbox does not make browser actions read-only.
Raw logs can contain page data, screenshots, or reasoning: keep them private and
review/redact before sharing. Credentials, browser profiles, downloaded source,
and generated artifacts are gitignored. No user authentication config is edited.

WebArena-Verified remains a future target: this machine currently has no Docker
CLI/engine. Its self-hosted environment and independent deterministic evaluator
must be provisioned before claiming WebArena results.
