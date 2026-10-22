# Disclosure and expect: pre-execution experiment plan

Written before new model runs. Exploratory mechanism study, not a leaderboard.

## Questions

Does richer UI observation reduce model requests, and do action-specific expect
instructions reduce error/wait overhead? Is there evidence worth pursuing an
adaptive disclosure selector (possibly a small model)? No selector model is
chosen or invoked here; the operator's `jev-like` label remains unspecified.

## Prior observations (not treatment results)

The 24-task bare v0.3.0 run has 195 Kitsune vs 168 Playwright model requests.
Kitsune/PW: 37/12 adjacent read-only requests, 45/81 requests with multiple tool
calls, 17/16 requests immediately following an error. Reads here mean inventory
list and page observations, not tab select/new/close. These categories overlap;
sequence adjacency is not evidence of unnecessary calls or causal attribution.

## Design

2 x 2 factorial, Kitsune only:

- **A native:** native observation, original prompt.
- **B rich:** richer observation, original prompt.
- **C expect:** native observation, appended action-specific expect guidance.
- **D rich-expect:** both treatments.

Fixed: clean Kitsune v0.3.0 `99a90d22c83d6e931814b3c3dadd96c08c633820`,
explicit lean, Claude Code 2.1.303 / claude-haiku-5-5 / medium, claude-api bare,
Firefox build 1553, original tools/graders and variant 0. No Playwright reruns
are necessary to isolate within-Kitsune effects. Original task and tab-preservation
requirements remain intact; v1 and v2 scores both retained.

Six tasks, selected before execution for read/write diversity and prior
read/error sequences: `pb-current-01`, `pb-current-02`, `pb-tabs-01`,
`pb-research-01`, `pb-account-01`, `pb-handoff-01`. Three repetitions per task,
four arms per block: **72 runs / 18 matched task-repetition blocks**.
Order uses rotating Williams sequences (A B D C; B C A D; C D B A; D A C B),
indexed by task index + repetition. This reduces order bias but 18 blocks is
not exactly balanced across all four sequences. Fresh browser/profile/fixture
per run; no parallel browser work. There is no controllable model sampling seed.

## Response intervention, no semantic model

Same tool definitions in every arm; changes only at the experimental relay:

1. Agent `browser_tabs(action=list)` uses `include_active=True`.
2. Agent `browser_snapshot` uses `text=True`, preserving requested subtree/depth.
3. Successful agent `browser_page_text` retains its original result and appends
   a native `browser_snapshot(text=False)` for the same tab (actionable refs).

This is a **richer-observation bundle**, not a comparison of token count alone.
Additional snapshot calls, their latency and response size are recorded under a
separate `disclosure` role and charged to treatment execution; not hidden setup.
Native text cap/truncation remain. No JS/source/cookie/evaluator access, no new
agent tool capability, no fixture-answer extraction. Supplemental snapshot
failure is marked, not turned into success or a retry of a write. Rich snapshots
can replace ref generations, a known semantic side effect to audit.

Expect guidance adds correct value/selector, same-URL save and new-tab examples,
plus inspect-before-replaying a dispatched write. No forced timeout reduction,
no deletion of agent expect arguments. It is a **prompt-policy intervention**,
not proof of a schema implementation fix; its input-token overhead is measured.

## Budget and stopping

Client-estimated total cap **$2**, per-run cap $0.50, timeout 180 seconds. Before
each run reserve its full cap against estimated cumulative spend; missing cost
counts as the cap. Stop on unscorable/setup failure, changed pinned revision,
or budget exhaustion. No automatic retry/model fallback. Persist each run and
schedule before proceeding; never silently replace a failed attempt.

## Analysis registered before execution

- Primary: total model requests, instrumented elapsed and input tokens, with
  functional success, safety and v1/v2 outcomes alongside them.
- Secondary: client-estimated cost, output/cache tokens, native call time,
  enrichment overhead, response bytes, expect use/validation/timeouts,
  adjacent read-only requests and parallel tool-call requests.
- Matched A→B and C→D disclosure effects; A→C and B→D guidance effects.
  Report per-task consistency and paired differences, not only pooled totals.
- Report all-run results and fixed within-comparison jointly successful blocks.
- Small-model case: calculate incremental observed cost/time budget left after
  treatment overhead. A positive rich-observation result supports disclosure
  exploration, **not** the need for a learned router. Mixed task effects may
  motivate a rule-based router, which must beat simple fixed policies before
  a paid model. No post-hoc best-arm-per-task result is a validated router.
- Single model, six selected synthetic tasks, three repeats: no general ranking
  or broad confidence claim. Any further experiment needs a separate stated plan.
