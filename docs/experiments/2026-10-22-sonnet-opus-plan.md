# Sonnet / Opus targeted representation follow-up

Pre-execution plan. The operator requests two stronger models in parallel and
completion within approximately 30 minutes, using only problematic cases.

## API check

Authenticated free GET of the configured Anthropic models endpoint returned
`claude-sonnet-5-5` (Claude Sonnet 5.5, created 2026-09-28) and
`claude-opus-5-5` (Claude Opus 5.5, created 2026-09-21), alongside Haiku 5.5.
No inference was used for this check; no API key/workspace identifiers published.
An initial incorrectly appended pagination query returned HTTP 400; the existing
configured URL already includes `limit=1000`. The corrected request succeeded,
`has_more=false`. No model substitution is allowed.

## Fixed design

Reuse the exact native A / target-view B formatter, task prompts, variant 0,
Kitsune v0.3.0 clean pinned revision, lean tools, Claude Code 2.1.303, bare API
harness, effort medium and Firefox binary of the preceding experiment. Only the
requested model changes. The formatter remains frozen, including its known
context/omission-marker limitations; do not repair it during this test.

Four task/layout units chosen from prior regressions:

1. pb-research-01 (personal): additional requests/context in the catalog arm.
2. ui-rowmenu (crowded gallery): context costs around repeated row controls.
3. mm-chart (isolated gallery): guessed crop selectors, extra verification.
4. mm-video (isolated gallery): page-vs-asset screenshot selection.

One A/B attempt per unit/model: **8 runs per model, 16 total**. Sonnet orders
AB/BA/AB/BA, Opus uses the opposite orders. Model workers run in parallel;
within each model, runs are sequential. Profiles, ports, fixtures, log/output
folders and processes are separate. Shared host/API capacity can affect elapsed,
so timing is not a clean intrinsic model-speed ranking.

Haiku reference = the same four units from the already recorded 3-repeat cohort.
Compare A/B effects *within* each model first, and use Haiku historical means
only as contextual evidence. No contemporaneous Haiku control and one repeat
for stronger models: no causal attribution to model capacity or significance
claim. No bootstrap/confidence interval for four one-shot stronger-model pairs.

## Bounds

- Execution window: **18 minutes from parallel worker launch**, enforced by a
  coordinator that cleans up owned descendant processes on expiry. Reserve
  180 seconds before starting another run; no automatic retries.
- Agent timeout: **120 seconds** for both tracks (shorter than earlier 180/240 s).
  Report any timeout/unscorable run and incomplete coverage; never count it as
  a normal task failure or silently rerun it.
- Client-estimated budget: **$4/model, $8 total**, $0.50 per-run cap. Reserve
  the full cap before each run; missing cost counts as the cap. This is not an
  independently verified invoice or a check of remaining account credits.
- Stop a worker on revision/code change, execution/setup or unscorable failure;
  no alternate model. The other worker may finish within its own bounds.
- Keep initial API checks, implementation and final analysis bounded so the
  operator's approximately 30-minute goal remains practical.

## Questions / analysis

- Does the stronger model improve targeting or avoid premature submissions in B?
- Does it crop video/recognize missing chart asset information instead of guessing?
- Does B still increase context/cost at the same task outcome?
- Per model and task: scorable/success/v1/v2, requests, input/output, cost,
  elapsed, errors, screenshot scope/dimensions and wrong attempts.
- Match source/tool schemas and formatter hashes; include raw evidence paths.
- Conclude separately: model-sensitive behavioral mistakes vs unchanged tool
  coverage/contract gaps. A model can work around missing asset identities,
  but cannot make a formatter expose information absent in its input.
