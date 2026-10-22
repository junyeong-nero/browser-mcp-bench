# Target/action view: pre-execution A/B plan

Written before inference. This experiment tests **representation**, not a new
retrieval or enrichment policy. Prior rich observations introduced extra native
snapshots and ref invalidation; this experiment must not do that.

## Arms

- A: native Kitsune MCP results.
- B: the same native results, with existing snapshot strings reorganized into
  **INTERACTIONS / MEDIA / CONTEXT**. Preserve every original line once, original
  line order through explicit line numbers, indentation, parent relationships,
  refs, names, values, flags, truncation markers and all other result fields.
  Add only deterministic role-derived candidate-action hints, not inferred
  task importance or new browser facts. Disabled/read-only flags override hints.

Both arms use the same relay, unchanged tool schemas, arguments, prompts and
native request count per agent call. No extra snapshot, page read, screenshot,
DOM inspection, selector generation, JS, model, or task-answer access. Binary
media is untouched. Transform snapshots inside inventory/action results too;
other observations (e.g. page_text/forms) remain native. The experiment cannot
expose assets that were absent in the native snapshot.

Classification is presentation only: an asset can have a clickable control
represented elsewhere using the existing parent/ref relationships. Ordinary
snapshot structure is recoverable by sorting line numbers. Candidate hints
such as click/type/choose are role-derived, not verified actionability claims.
Do not infer scroll/drag capability from arbitrary containers. Scroll/drag
support itself is outside this representation-only experiment.

## Fixed conditions

Kitsune clean v0.3.0 `99a90d22c83d6e931814b3c3dadd96c08c633820`, lean, same
14-tool UI allowlist; Claude Code 2.1.303, Haiku 5.5 medium, claude-api bare;
private Firefox build 1553. No expect guidance from the preceding experiment.

Ten task/layout units, chosen before execution:

- Personal, variant 0: pb-current-01, pb-current-02, pb-tabs-01,
  pb-research-01, pb-account-01, pb-handoff-01.
- Gallery, variant 0, crowded: ui-select, ui-rowmenu.
- Gallery, variant 0, isolated: mm-chart, mm-video.

Three repeats each, two arms: **60 runs / 30 matched blocks**. Alternate AB/BA
by (task index + repeat) parity. Thus 15 AB and 15 BA blocks, fresh profile and
fixture each run, no concurrent browser activity. Sampling seed and cache state
are not controllable. Task prompts and graders stay unchanged; report v1 and
v2 cleanup separately.

## Validation gates

Before inference: test lossless reconstruction, ref equality, parent mapping,
disabled/readonly flags, escaped names, media classification, malformed/empty
snapshot fallback, nested snapshots, untouched error and image payloads,
unchanged schema/arguments, and exactly one native call per agent call.
Real-Firefox no-model probes must show unchanged page/tab state and that an old
ref still works after **formatting only**. Inspect a crowded gallery snapshot
and ensure media and repeated control labels retain their context. Any formatter
fallback is recorded. Core personal/gallery behavior remains unchanged.

## Budget and stopping

$2 cumulative client-estimated cost, $0.50 cap per run, configured agent
timeouts of 180 seconds for personal and 240 seconds for gallery. Reserve a full per-run cap before launching each run; unknown
cost counts as the cap. Stop on changed source/experiment code, execution/setup
failure or externally unscorable run; no automatic retry or model substitution.
Ordinary scorable task failures do not stop the schedule. Persist every attempt.
If stopped, report partial coverage rather than a 60-run result.

## Analysis

- Per arm: success, functional/safety and v2 outcomes; requests, input/output,
  cost, elapsed, agent calls/errors, screenshot use, snapshot use, result bytes,
  formatter coverage/expansion/time, media entries presented and fallbacks.
- Paired differences within task/repetition. Split personal / crowded UI /
  isolated media results; do not equate their different grading contracts.
- All-run and within-comparison joint-success results. Task-level consistency,
  median paired latency, exploratory task-cluster bootstrap intervals; 10 task
  units and 3 repeats do not establish general significance.
- Manually trace failures or regressions involving targeting/context/media.
- A direction is promising only if it preserves success/safety and improves
  task-level effort; smaller output is not required, but extra output must earn
  its cost. Small-model routing, asset extraction quality, drag/scroll target
  discovery and real web generalization are **not** measured here.
