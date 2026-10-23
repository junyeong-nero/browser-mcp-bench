# Result reports

[Documentation index](../README.md) · [Running guide](../running.md)

Reports are dated records of actual executions. **Changing the configured model
does not change the model used in an older report.** Different tasks, models,
tool policies and instrumentation are not a single comparable leaderboard.
For the same reports grouped by Kitsune revision, see
[results by Kitsune version](kitsune-versions.md).

| Date | Report | Model | Scope and outcome |
| --- | --- | --- | --- |
| 2026-10-23 | [Opus full suite, Kitsune v0.3.1](2026-10-23-opus-full-v0.3.1.md) | `claude-opus-5-5`, medium (Claude Code API, bare) | `taskset-v1.2` (same 23-tool allowlist), 398 scorable runs, $31.67: personal 72/72 PW vs 71/72 Kitsune; crowded 63/63 vs 61/63, isolated 62/63 vs 60/63; Kitsune 1.3–1.7× calls on joint successes; snapshot lacks text/link URLs, Playwright selector syntax unsupported, hover does not scroll |
| 2026-10-23 | [Opus full suite, Kitsune v0.3.0](2026-10-23-opus-full-v0.3.0.md) | `claude-opus-5-5`, medium (Claude Code API, bare) | `taskset-v1`, 398 scorable runs, $27.98: personal 67/72 PW vs 68/72 Kitsune; gallery crowded 63/63 vs 60/63, isolated 63/63 vs 57/63; Kitsune cost ×0.67 on crowded; snapshot drops `img`, lean lacks keypress; two grader defects |
| 2026-10-22 | [Tool usage inventory](2026-10-22-tool-usage.md) | Offline, 196 existing Kitsune runs | 2,084 agent calls; exposure-aware counts and error categories; status/page-info candidates for default-surface ablation, not API removal |
| 2026-10-22 | [Sonnet / Opus targeted follow-up](2026-10-22-sonnet-opus-target-view.md) | Sonnet 5.5 / Opus 5.5, medium (Claude Code API, bare) | 16 scorable runs in 4m37s; catalog requests −13.8% / −11.8%, elapsed −8.5% / −17.3%, but cost +15.1% / +13.5%; no-model probe confirms video screenshot(ref) failure |
| 2026-10-22 | [Target/action view A/B](2026-10-22-target-view-ab.md) | `claude-haiku-5-5`, medium (Claude Code API, bare) | 60 scorable runs; native/catalog both 28/30 strict, requests −2.2% but input +6.0%, elapsed +2.9%, cost +10.0%; chart assets absent from source snapshot, video crop divergence; no global-default adoption |
| 2026-10-22 | [Disclosure × expect A/B](2026-10-22-disclosure-ab.md) | `claude-haiku-5-5`, medium (Claude Code API, bare) | 72 scorable Kitsune runs, 2×2 factorial: rich-only requests +3.0%; combined −7.9% with task-sensitive timing; no-model probes confirm ref invalidation and ungrounded expect selectors; paid selector not justified yet |
| 2026-10-22 | [Kitsune 0.3.0 rerun](2026-10-22-kitsune-0.3.0.md) | `claude-haiku-5-5`, medium (Claude Code API, bare/full descriptions) | 96 scorable runs; bare PW/Kitsune 22/24 vs 23/24, full 23/24 vs 19/24 (Kitsune v2: 22/24); Kitsune input +4.2% / +16.2%; default now lean |
| 2026-10-21 | [Component gallery](2026-10-21-gallery.md) | `claude-haiku-5-5`, medium (Claude Code API) | 21 tasks × 2 layouts: crowded 20/21 Playwright vs 15/21 Kitsune (3.23× input on joint successes); isolated 21/21 vs 18/21 (1.88×); Kitsune fails shadow DOM, iframe, native video |
| 2026-10-21 | [Token efficiency analysis](2026-10-21-token-efficiency.md) | `claude-haiku-5-5`, medium (Claude Code API, `--bare`) | 24 pairs, 23/24 each, $0.099; Kitsune +30.5% input, all from the fixed prefix (tool definitions × requests); client truncates descriptions; savings estimates |
| 2026-10-21 | [All 24 personal tasks, Claude Code](2026-10-21-personal-24-claude-haiku.md) | `claude-haiku-5-5`, medium (Claude Code) | 24 variant-0 pairs / 48 agent runs, all scorable; 21/24 Playwright vs 23/24 Kitsune; Kitsune 1.69× input on the 20 jointly successful tasks |
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
per MCP**. The later reports include 24-task model evaluations. No real-account experiment,
repeated/counterbalanced comparison or WebArena result has been recorded. Native-browser
fixture tests and the TTL cache intervention use no model and must not be counted
as LLM benchmark runs. See [optimization findings](../optimization-findings.md)
for the evidence and precise observability limits.
