# Result reports

[Documentation index](../README.md) · [Running guide](../running.md)

Reports are dated records of actual executions. **Changing the configured model
does not change the model used in an older report.** Different tasks, models,
tool policies and instrumentation are not a single comparable leaderboard.

| Date | Report | Model | Scope and outcome |
| --- | --- | --- | --- |
| 2026-10-19 | [Six-task personal pilot](2026-10-19-personal-six-task.md) | `gpt-6-luna`, medium | Six variant-0 pairs / 12 agent runs, all scorable; current grader 3/6 Playwright vs 4/6 Kitsune; cache intervention and format/safety caveats documented |
| 2026-10-19 | [Personal current-page pair](2026-10-19-personal-current-page.md) | `gpt-6-luna`, medium | `pb-current-01`, variant 0; one attempt per MCP; both externally scorable, functionally successful and safety-passing |
| 2026-10-18 | [MiniWoB++ pilot](2026-10-18-miniwob.md) | `gpt-6.1-sol`, medium | Only `click-test-2`, seed 42; both passed original reward evaluation in a non-standard Firefox/MCP track |
| 2026-10-18 | [Read-only smoke](2026-10-18-smoke.md) | `gpt-6.1-sol`, medium | One Example Domain pair; execution completed, no external task-success label |

## Evidence standard

Each new report should identify:

- Exact selected task(s), variant/seed, repetitions, order and stopping policy.
- Requested model/effort, Codex and MCP/browser pins, source cleanliness/hashes.
- Initial/reset state, tool allowlist and external success/safety checks.
- Scorable vs ordinary task failure vs execution/setup error.
- Reported usage fields, cache accounting, agent calls and hidden harness work.
- Instrumented timing/resource scope and important confounders.
- Reproduction command and private artifact identifiers, without publishing
  credentials, session tokens, real page contents or unreviewed raw logs.

The six-task personal pilot is recorded, **only for variant 0 with one attempt
per MCP**. No 24-task model evaluation, real-account experiment, repeated/
counterbalanced comparison or WebArena result has been recorded. Native-browser
fixture tests and the TTL cache intervention use no model and must not be counted
as LLM benchmark runs. See [optimization findings](../optimization-findings.md)
for the evidence and precise observability limits.
