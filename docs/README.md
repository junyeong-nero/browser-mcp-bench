# Documentation

This project compares **native browser MCP configurations under a fixed Codex
model**, with externally checked task outcomes and local resource measurements.
The current product-oriented focus is **personal browsing**: continuing work in
already-open tabs and a pre-established test session.

## Start here

1. [Run safely](running.md): setup, plan-only checks, one-pair execution, quotas,
   tests and where results are written.
2. [Personal browsing taskset](personal-browsing.md): the 24-task catalog,
   six implemented tasks, session/reset protocol, grading and limitations.
3. [Latest six-task result](results/2026-10-19-personal-six-task.md): all six
   implemented tasks, variant 0, with token/time breakdown and grading caveats.
4. [Optimization findings](optimization-findings.md): confirmed tab-cache delay,
   observation/schema opportunities, diagnostic logs and no-quota analysis commands.
5. [All result reports](results/README.md): dated evidence with the model and
   scope of each experiment. Historical reports are not relabeled to today's model.

## Tracks and current evidence

| Track | Purpose | Implementation | Observed evidence |
| --- | --- | --- | --- |
| **Personal browsing** | Existing tabs, test sessions, lookup, drafts and safe mutations | 24 original specifications, all runnable local fixtures, each with three data variants | 24 variant-0 pairs on Claude Code + `claude-haiku-5-5`: 21/24 Playwright vs 23/24 Kitsune, 2026-10-21; six-task Codex `gpt-6-luna` pilot 3/6 vs 4/6, 2026-10-19 |
| **MiniWoB++ UI pilot** | Small upstream-task/original-reward integration check | Only `click-test-2`, seed 42; not the complete MiniWoB++ suite | One pair passed with historical `gpt-6.1-sol`, 2026-10-18 |
| **Read-only smoke** | Browser/MCP connectivity and native-tool smoke | Example Domain task; no external task-success grader | One completed historical `gpt-6.1-sol` pair, 2026-10-18 |
| **WebArena / live personal accounts** | Future realistic/multi-step tracks | Not provisioned or implemented | No results |

Current execution configs request **`gpt-6-luna`, reasoning `medium`, Codex CLI
`0.163.0`**. Model availability and quota can change. A completed simple task
pair is not a general success rate, tool ranking or security certification.

## Guides and source of truth

| Document or file | Owns |
| --- | --- |
| [Running guide](running.md) | Operational sequence, command selection, cost boundaries, exit codes |
| [Personal browsing protocol](personal-browsing.md) | Personal-session task design, provenance, fixture/evaluation/reset contract |
| [Component gallery](gallery.md) | Modern components, multimodal puzzles and a hand-off judgement task on one local page |
| [Personal-state track](personal-state.md) | Specification only: tasks that need a personal profile's history, bookmarks or logins |
| [Task catalog](../tasks/personal/catalog.json) | Per-task requests, initial state, success/safety criteria, implementation status |
| [Personal execution config](../configs/benchmarks/personal.json) | Model/pins, default pilot selection and wall-clock budget |
| [Codex integration](codex-harness.md) | Authentication, isolation, native tool policy, process lifecycle and trace audit |
| [Local resource methodology](resources.md) | CPU/RSS sampling scope, attribution and interpretation |
| [Optimization findings](optimization-findings.md) | Causal cache evidence, token/observation candidates, native diagnostic logging and offline analysis |
| [MiniWoB++ integration](miniwob.md) | Pinned upstream task, reward instrumentation and non-standard track limits |
| [MCP comparison candidates](comparison-candidates.md) | Future MCP/browser cohorts; not benchmark task sources or measured adapters |
| [Results index](results/README.md) | Dated observations and evidence references |

The task catalog and execution configs are executable inputs. Guides describe
their protocol. Dated reports describe what was actually run, not everything
currently possible. Raw JSONL, session state, profiles and resource logs stay in
private, gitignored `artifacts/`; published reports contain reviewed summaries.

## Reading results correctly

- Read **external `task_success` and `scorable`**, not only CLI exit status or
  the agent's final answer. Generic `completed_unscored` can have an attached
  successful external evaluation.
- Input tokens **already include cached input**. No subscription-billing or
  dollar-cost estimator is implemented; missing usage is not zero cost.
- Personal-track time includes hidden setup/readiness/inventory calls, recorded
  separately from agent calls. Do not compare it directly with uninstrumented
  MiniWoB timings.
- Keep model, tool policy, task variant, browser, startup policy and order visible.
  Current fixed-order, single-attempt reports do not justify general rankings.
- All personal fixtures are synthetic local apps. Real logins, durable profile
  history, live-web reliability and prompt-injection robustness remain untested.
