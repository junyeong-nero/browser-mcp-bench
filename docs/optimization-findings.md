# Token and latency investigation: findings and optimization targets

[Documentation index](README.md) · [Six-task evidence](results/2026-10-19-personal-six-task.md) ·
[Personal protocol](personal-browsing.md)

## Bottom line

**Do not optimize from the first simple task alone.** In the six-task variant-0
pilot, Kitsune's total input was only **0.61% higher**, its non-cached input was
**25.79% lower**, and it made **46 vs 51** agent calls. Total instrumented elapsed
was **121.323 vs 111.536 seconds** (Kitsune vs Playwright).

The strongest demonstrated avoidable delay is **tab-readiness polling against
Kitsune's five-second cached tab list**. Bigger schema metadata and the split
between readable content and actionable refs are separate input/round-trip
optimization candidates. They have not yet been isolated in model-based A/B runs.

No production Kitsune source or task grader was changed. This investigation
added diagnostic logging, an offline analyzer, tests and an isolated no-model
cache probe. The probe changes only its owned temporary bridge.

## Evidence and priority

| Priority | Finding | Confidence | Target and recommended change |
| --- | --- | --- | --- |
| **P0** | Setup repeatedly receives stale tab metadata after asynchronous tab creation | Source, RPC logs and TTL intervention confirm it | Fresh/event-invalidated `getTabs`; navigation-ready acknowledgement; remove polling against known cached results |
| **P0 evaluation** | Product-name exact-string grading and all-starting-URL preservation affect score interpretation | Direct trace and saved-state review | Version/clarify prompt/grader contract before ranking or optimization A/B |
| **P1** | Page facts and refs often require separate observations | Source and six no-model observation checks confirm missing paragraph fact | Bounded combined readable text + relevant refs, ideally as an observation mode rather than another overlapping tool |
| **P1** | Enabled Kitsune schema metadata is about 50% larger | Direct metadata measurement; exact provider token contribution unknown | Lean personal capability preset; trim redundant descriptions/defaults/examples and overlapping low-use tools |
| **P2** | Post-action ref invalidation produced a recoverable stale-ref call | One observed Kitsune error, documented source behavior | Clear fresh-ref contract, stable/bounded refs where safe, consistent error flags |
| Not first | Raw HTTP/bridge call speed or blanket response compression | Kitsune RPC/text totals were lower in this pilot | Profile longer/live tasks before micro-optimizing transport or discarding useful context |

## 1. Tab freshness and readiness: confirmed bottleneck

Source locations below refer to the clean sibling Kitsune checkout at
`68f7e979dcda9a982f8f3781841ecc6b26d7b3ee`, not files vendored into this project:

- `../kitsune/src/kitsune/bridge.py:110`: `CACHE_TTL = 5`.
- `bridge.py:135–154`: read cache and clear operations.
- `bridge.py:1641–1650`: `handle_tabs()` caches `getTabs` and marks reused results
  `_cached: true`.
- `bridge.py:1696–1718`: mutation handlers invalidate cache **before** dispatch;
  this does not handle subsequent asynchronous browser tab updates.
- `../kitsune/extension/background/background.js:387–398`: browser tab query.
- `background.js:449–456`: `createTab()` returns an ID immediately after
  `browser.tabs.create()`, without waiting for the new URL/page to settle.
- `browser_mcp_bench/personal_session.py`, `wait_inventory()`/`prepare()`: the
  benchmark polls at 100 ms until seeded URLs/selected tab match.

Mechanism:

```text
newTab starts navigation and returns an ID
  → getTabs sees a transient URL list and caches it
  → browser navigation completes, but no tab-event cache invalidation occurs
  → readiness checks receive the cached list for almost five seconds
  → TTL expires, a fresh list matches, setup finally completes
```

Measured across six model tasks: **236 cached setup tab reads**, **25.614 seconds
of readiness sleep**, and **31.958 seconds** of Kitsune setup vs **10.379 seconds**
for Playwright. The setup gap is larger than the entire total elapsed gap.
This setup is hidden harness work, not extra model context or agent operations.

**Intervention:** three fresh isolated instances per condition, TTL 5 vs TTL 0,
no model calls. Median setup fell from **5.273 to 0.332 seconds**; every seeded
state still verified. See the [raw measurement table](results/2026-10-19-personal-six-task.md#cache-mechanism-and-independent-intervention).
The first TTL-0 run was 1.532 seconds; do not promise one constant savings value.

### Preferred fix

1. Avoid caching cheap browser tab inventories, or invalidate them on relevant
   browser `onCreated`/`onUpdated`/`onActivated`/`onRemoved` events.
2. If caching remains, expose explicit freshness/generation semantics for
   orchestration; do not repeatedly poll a response known to be cached.
3. Offer a bounded `newTab` navigation-ready result with tab ID, actual URL and
   load state. Preserve an immediate mode when the caller explicitly wants it.
4. Benchmark **warm-ready agent work** separately from provisioning, while still
   publishing end-to-end setup cost. Merely deleting setup from the headline
   without fixing correctness would hide a real product issue.

**Do not ship global `CACHE_TTL=0` as the only fix.** Page-text caching may have
separate value. The probe establishes causality; it is not production guidance
to disable every cache.

Acceptance checks: delayed navigation, redirect, externally changed tab URL,
selection, close/reopen and fresh-profile initialization must not wait for a
five-second TTL or report stale protected-tab state. Include both cache-enabled
and fresh-read scenarios. Keep normal user profiles untouched during tests.

## 2. Observation design: content and refs are split

`../kitsune/extension/content/content.js:387–594`, `getSnapshot()`, includes
semantic headings/landmarks and controls but filters ordinary paragraph-only
subtrees from useful/selected entries. This is a compact DOM-semantic view,
not a full platform accessibility tree. `../kitsune/src/kitsune/server.py:213`
exposes separate readable text, while `server.py:252` exposes snapshot refs.

In **all six cache-probe sessions**, the current-page snapshot omitted the exact
cancellation deadline and `browser_page_text` included it. To read a fact and
then edit a field, the agent can need text + snapshot, whereas the Playwright
snapshot in the same fixture includes paragraph facts and input refs together.
The current task used **five agent calls vs three** in this full pilot.

This is not universal: Kitsune can read non-active tabs via `tab_id` without
switching, saving calls on the product comparison and cross-tab tasks. It made
fewer calls and returned less result text across the full pilot. Do not replace
that advantage with unconditional full-page dumps.

### Candidate fix and validation

Add a bounded reading-oriented observation mode that includes relevant visible
text, URL/title/tab identity, links and actionable refs in one response. Keep an
interaction-only compact mode for large pages. Reuse post-action observations
when sufficient, rather than reflexively reading the page again. Enforce
sensitive-field redaction, truncation markers and stable ref semantics.

A/B on identical content/model/policy should compare **same-task success and
safety**, agent-call count, non-cached + total input and elapsed/setup separately.
Character savings alone do not establish token or latency savings. This candidate
has not yet had a model-based before/after test.

## 3. Tool catalog size: real difference, not exact token attribution

Native metadata matched to the configured allowlist:

| Metric | Playwright | Kitsune |
| --- | ---: | ---: |
| All native tools returned | 25 | 30 |
| Config-enabled definitions | 15 | 19 |
| Enabled compact JSON characters | 11,260 | 16,869 |
| Enabled UTF-8 bytes | 11,260 | 16,875 |
| MCP initialize instructions characters | 0 | 0 |

The enabled serialized definitions are **49.8% larger** in Kitsune. Larger
Kitsune definitions include scroll (1,510 chars), keypress (1,444), screenshot
(1,411), snapshot (1,368), and type (1,241). Parameter alternatives, defaults,
descriptions and overlapping observation/action entry points contribute.

**Do not charge all 30 tools to model input:** Codex is configured with an
allowlist of 19 native definitions. These logs capture the native catalog, not
Codex's exact provider tool envelope; the final conversion/tokenizer is not
observed. Nor does a 49.8% character gap imply a 49.8% total token increase.
The six-task total input gap was only 0.61%, affected by caching, batching,
agent choices and number of model/context iterations.

A lean personal preset could combine overlapping read tools, remove rarely
needed dev-oriented UI inspection/resize/screenshot variants for an explicitly
labeled cohort, and shorten repeated descriptions/examples while preserving
meaningful parameter documentation. Review capability equivalence and failure
rates; silently removing functionality to win a token count is not a fair test.

## 4. Error/ref contract and evaluation alignment

One Kitsune account lookup reused a stale ref and received JSON
`{"error": "stale ref, call browser_snapshot again"}`. One Playwright handoff
used an invalid ref/selector syntax and retried. Both are extra agent work, not
slow successful RPC. Kitsune snapshots and post-action snapshots advance a ref
generation; the documented invalidation rule can require extra observations.

Prefer an explicit fresh-observation contract and bounded stable element refs
where safe. Return MCP `isError` for actual operation errors instead of only
embedding an error in normal JSON. The new offline analyzer detects both forms;
existing generic audit flags alone do not count every JSON-wrapped error.

Before interpreting scores, resolve two benchmark issues in a **new version**:

- Product request: either explicitly demand *only* the product name or grade a
  structured answer that can include valid supporting facts. Playwright's saved
  explanation named the correct product but failed exact-string matching.
- Preservation policy: decide whether personal browsing means preserving
  **protected unrelated tabs** or every working tab's URL at every checkpoint.
  The present protocol explicitly chooses the latter; both agents violated it
  on research/orders, despite restoring state and saving correct values. Do not
  retrospectively call those runs passing without labeling a different policy.

Do not silently alter the old catalog/hash, grader or report to improve scores.

## Logs now available

All are private, gitignored files; keep modes `0600` and review before sharing.

| File | Answers |
| --- | --- |
| `runs/<id>/events.jsonl` | Agent tool names/arguments/results, reasoning/final events and final reported `usage` |
| `runs/<id>/summary.json`, `evaluation.json` | Execution validity, usage, external functional/safety verdict |
| `{target}-session-evidence.json` | Verified initial tabs and per-call sampled inventories, harness totals |
| **`{target}-native-rpc.jsonl`** | Each upstream RPC start/completion, UTC/monotonic offsets, agent vs harness role, duration, result size, cache flag, setup/readiness spans |
| **`{target}-native-metadata.json`** | Native initialize payload, full tools/list pages and configured enabled-tool list |
| `diagnostic-analysis.json` | Offline per-run and same-success-subset aggregates, schema sizes and recovered errors |
| `bridge.log`, `runs/<id>/stderr.log` | Private server/bridge diagnostics; not all extension internals are traced |
| `resources.jsonl`, `resource-summary.json` | Local CPU/RSS and cleanup observations, not model/network resources |

The new RPC log stores **timing/size metadata, not full tool payloads**; agent
payloads already live in Codex events. The native catalog file contains schemas,
not provider prompts. Added log serialization/file I/O itself has some overhead;
timings are not a zero-overhead profiler.

### Offline analysis: no new quota

```sh
uv run --locked python -m browser_mcp_bench.personal_analysis \
  artifacts/personal/20261019T104926Z-ef986c9a42/suite-summary.json \
  --output artifacts/personal/20261019T104926Z-ef986c9a42/analysis-review.json
```

Choose a new output path; overwrite is refused. Old runs without the new native
logs produce missing/null diagnostic fields, not invented measurements. Check
`diagnostic_runs` before interpreting partial aggregate totals.

### Cache intervention: browsers, but no model calls

```sh
uv run --locked python scripts/probe-personal-cache.py --repeats 3
```

This development utility reuses the native integration-test private-browser
setup. It creates six separate temporary Kitsune instances, sets TTL only on
those owned bridges, and records measurements/observations in a new private
`artifacts/personal/cache-probe-<timestamp>/` directory. It never invokes Codex
inference, edits Kitsune source, or changes a normal shared bridge's TTL.

### Remaining observability gaps

Codex JSONL here reports **final turn-total usage**, not per-provider-request
input, exact serialized model prompts, TTFT, network vs inference latency or
subscription billing. The analyzer labels unaccounted elapsed as residual
Codex/model/network/startup/cleanup/logging, **not pure model time**. It also
avoids adding readiness sleep and RPC durations on top of setup, where they
are already included. Precise token attribution or claimed optimization savings
needs provider-level telemetry or a controlled new cohort, not guessed token
counts from characters or a single subtraction.
