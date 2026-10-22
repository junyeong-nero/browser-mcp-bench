# Integrated Opus benchmark — proposed corpus, $30 cap approved

## Status

Corpus research and native tool inventory complete. The operator approved a
**$30 total estimated API-cost cap**. **No integrated paid run has started.** Online subset candidates below have not yet passed browser preflight;
public availability, selectors and independent grading remain to be validated.
Do not describe this plan as implemented online evaluation or completed tests.

## Existing coverage: correct the MiniWoB scope

The repository integrates only MiniWoB++ `click-test-2`, seed 42, not the full
MiniWoB++ benchmark. Keep it as an upstream-runtime smoke control. The custom
tracks are distinct: personal browsing has 24 tasks; component gallery has 21
tasks in two layouts. Proposed online additions are 20 tasks (17 primary and
3 conditional UI regressions).

| Track | Task definitions | Task/layout units per target | Share of planned units |
| --- | ---: | ---: | ---: |
| MiniWoB++ pilot | 1 | 1 | 1.1% |
| Custom personal browsing | 24 | 24 | 27.6% |
| Custom component gallery | 21 | 42 | 48.3% |
| Korean live-web candidates | 20 | 20 | 23.0% |
| **Total** | **66** | **87** | **100%** |

Kitsune + Playwright, one attempt each = **174 planned target runs**. Actual
online coverage depends on preconditions; never silently remove blocked cases
from the reported coverage denominator. The three conditional cases are separate
from primary task success. Report four track scores, not one raw pooled score
that lets 42 gallery variants dominate. This is broad coverage, not repeated
statistical confirmation. More MiniWoB tasks/seeds would require additional work.

## Model and tool scope

Pin `claude-opus-5-5`, medium, Claude Code 2.1.303, same API harness and Firefox
build for both targets. Use native responses, not the experimental formatter.
Keep the Kitsune source unchanged during execution, and record exact revision,
source hashes, profile configuration, tool definitions and allowed tools.

Free tools/list inspection of pinned v0.3.0 confirmed:

- `KITSUNE_TOOL_PRESET=full`, `KITSUNE_CAPS=core`: **30 published tools**.
- `KITSUNE_TOOL_PRESET=full`, `KITSUNE_CAPS=all`: **96 published tools**. Explicitly
  named-only capabilities are not necessarily included by `all`.
- 31 source-level core declarations include an alias not published in the list.

Recommended primary configuration: **full-core-derived UI surface (27 tools)**,
excluding `browser_js`, `browser_workflow`, `browser_workflows` under the existing
UI-only integrity policy. Exclude the corresponding arbitrary-code interfaces
from Playwright. Do not call this an unrestricted full-native evaluation.

Reason: synthetic reward state is browser-accessible, so arbitrary code could
alter the evaluator rather than solve the task. On live sites, the primary
measurement should likewise require real UI interaction rather than constructing
an apparent result. Devtools/storage/network/history/parallel capability groups
are not covered by this UI cohort and must not receive “unused” deprecation votes.
Some advertised UI tools still lack an opportunity in the current fixtures
(e.g. file upload): count exposure separately from task opportunity.

Do not change to a reduced 12-tool default before collecting this broader
baseline. Record per-tool calls, used/exposed runs, task family, error category,
recovery and role-separated harness/enrichment calls.

## Online source and deduplication

Source: https://huggingface.co/datasets/junyeong-nero/korean-online-mind2web

The dataset has 400 train / 50 dev / 50 test rows. Select **15 from test only**;
add **5 issue-derived cases**. Repository revision observed during selection:
`b6d39b3ebf5749f4cb0f68c59ae378ddfb4581aa`. Raw dataset-server response and source
metadata are retained privately; pin candidate row content hashes before
execution. Do not assume dataset-server cached rows are revision-pinned merely
because repository metadata has a SHA.

Issue: https://github.com/junyeong-nero/kitsune/issues/200 (body and both comments
archived before selection).

Selection principles:

- Prefer multi-constraint, multi-state and evidence-rich tasks, not repeated
  keyword substitutions in “search and open the first result”.
- At most two tasks per exact product/site; repeated corporate ownership (Naver)
  is distinct from repeated interaction patterns. Selected candidates span
  19 product/site entry points, with two different Naver Map tasks.
- Merge issue-derived map checks into dataset map tasks; do not add another
  near-duplicate map route task to inflate counts.
- Keep public information access, visual/spatial state, filtering, form state,
  changing panels and conditional overlays represented.
- The supplied difficulty labels are source metadata, not proof of present-day
  difficulty. Public availability and task ambiguity need preflight.
- If browser preflight finds a case impossible, record it as blocked. No silent
  replacement based on model performance; any replacement must be selected and
  frozen before paid target runs, with the changed ratios documented.

## Proposed online manifest

### Dataset-derived primary cases (15)

| Source task ID | Scenario | Required evidence / non-duplicated purpose |
| --- | --- | --- |
| `kr-naver-finance-025` | Domestic equity fund return ranking, top five managers | Category + ranking state; five fund/manager pairs, timestamp; do not hardcode changing rank values |
| `kr-yanolja-014` | Haeundae family room, next month, 2 adults + 1 child | Freeze one-night dates and child age before execution; verify destination/date/occupancy and room/rate; never book |
| `kr-naver-map-002` | Seoul Station → Incheon Airport, three route modes | Confirm actual origin/destination selections and result changes per mode; preserve genuine no-route states |
| `kr-naver-map-009` | Olympic Park satellite view and major facilities | Actual selected map mode plus visual spatial evidence; text label presence alone is insufficient |
| `kr-kakao-map-010` | Gangnam → Pangyo cycling route and stops | Autocomplete selection must commit places; verify route result, not only field text; supported stops only |
| `kr-gmarket-012` | Segway electric scooter, brand filter and safety certification | Verify selected filter and real detail tab/certification evidence; no purchase |
| `kr-gov24-017` | Land register viewing versus issuance procedures | Public procedure comparison with both source sections; never request a certificate |
| `kr-wanted-007` | Security engineer position preferring security certification | Evidence matching role and preference, plus application method; never apply |
| `kr-tving-009` | Seojin's program seasons and first episode | Actual program identity, season state and episode metadata; no subscription/login/paywall bypass |
| `kr-naver-webtoon-013` | Sports genre → soccer work → synopsis | Evidence for genre, subject and selected work rather than a single matching search term |
| `kr-nhis-003` | General health screening eligibility and examinations | Public policy sections for both requested fields; no personal medical records |
| `kr-naver-021` | 黎明: meaning, pronunciation, synonyms and examples | Four distinct requested fields, handling dictionary sections/tabs |
| `kr-kocw-002` | Operating-systems lecture, title and institution | Lower-depth cross-domain educational control; actual lecture detail and provider |
| `kr-zigbang-013` | Gangdong district housing result and basic details | Correct committed geographic state and property detail; no agent contact or inquiry |
| `kr-daum-008` | Secondary-battery news and related companies | Verify available news/related-company section; unsupported or obsolete features are not invented |

The hotel task is underspecified as supplied (exact dates, stay length, child
age). Resolve these in the frozen adaptation manifest, not differently per agent.
Likewise freeze route endpoint disambiguation and the number/type of requested
facts. Record original and adapted prompts separately. These are **derived
benchmark cases**, not an unchanged official Mind2Web score.

### Issue-derived primary cases (2)

- **Danawa:** search Mac mini → ascending price → 16GB RAM filter. Verify active
  sort, checked filter and results update/removal control. Rental listings may
  occur; this is UI correctness, not a purchasing recommendation or static price
  accuracy test.
- **Kyobo:** search `불변의 법칙` → correct book detail → book-information tab /
  contents expansion. Do not assume a new tab. Verify selected tab, viewport or
  expanded content change, not a pre-existing hidden/visible element alone.

### Issue-derived conditional regressions (3)

- **CGV:** close an actually visible promotion dialog; use as the previously
  successful close-action control. Confirm gone/hidden state after action.
- **SSG:** close an actually visible top advertisement banner; compare target
  identification, dispatch and actual disappearance. Do not click “hide today”.
- **CHZZK:** if the ad-block notice is naturally present, close its confirmation
  dialog and verify text disappearance. Do not install blockers, change browser
  security, modify account state or manufacture the notice. Original report used
  logged-in Zen with signed extension; private Firefox is not the same context.

Absent popup = **precondition absent**, not success. Login-required CHZZK
reproduction = **auth/context blocked**, not an Opus failure. Exact Zen/signed
extension reproduction is a separate operator-authorized diagnostic.

Excluded duplication: other simple promotion-close controls (Megabox/Everland)
and repeated first-result keyword variants. Issue #200 does not establish one
common root cause for all sites; do not convert its unfinished cases into known
failures or assume `isTrusted` is the cause.

## Live-web safety, scoring and scheduling

Default: fresh isolated **logged-out** profiles; no normal browser profile or
personal account tokens. Read/search/filter/inspect only. No purchases, bookings,
applications, posts, messages, certificate requests, or external submissions.
Do not bypass CAPTCHA, login gates or anti-bot restrictions. Redact personal
information and keep screenshots/session traces private.

This tests realistic **public-web interaction**, not fully personalized signed-in
workflows. Existing local personal fixtures retain coverage of tab preservation,
state and safe drafts. A dedicated authorized signed-in profile would be a
separate follow-up, never an implicit reuse of the user's everyday browser.

The dataset contains tasks/URLs/difficulty, **not executable success labels**.
Before execution implement per-case milestones and independent evidence capture.
Final model text alone cannot determine success. Retain intermediate states,
final page evidence, selected controls, screenshots where needed, source URLs
and observation times. Judge facts against contemporaneous page evidence rather
than fixed prices/ranks. Mark unverifiable outcomes as unscorable, not successful.

Report separately: verified success, partial/task failure, tool error,
environment/auth/CAPTCHA block, absent precondition, execution/audit failure and
unverifiable evidence. Never infer success from process exit or dispatched=true.

Run each live-site pair close in time with counterbalanced target order; one
active visit per site, no aggressive concurrency. Keep model, parameters,
viewport and dates matched. Freeze selection before outcome-dependent analysis.
Use bounded per-run/overall cost and time, no automatic retries/model fallback.

## Implementation gates before paid runs

1. Overall cost cap confirmed: **$30**, including any #69 revision-control runs;
   this is an estimated API-spend ceiling, not a completion or invoice guarantee.
2. Freeze actual source revision, tool policies and the adapted online manifest.
3. Validate protected evaluators and new online evidence/status handling.
4. Browser preflight without inference; retain blocked/conditional coverage.
5. Run a bounded paid pilot; stop on protocol or grading errors rather than
   spending the full budget on invalid runs.
6. Complete eligible fixed-suite runs within budget, then aggregate per-track
   outcomes and per-tool usage. Report incomplete coverage if a cap is reached.

## Additional requirement: Kitsune #69 action error contract

Source: https://github.com/junyeong-nero/kitsune/issues/69, archived privately as
`issue-69.json`. This is an evaluation requirement, not an assumption that errors
have been fixed. Record the exact tested revision; #69 names
`68f7e979dcda9a982f8f3781841ecc6b26d7b3ee` as the comparison baseline.

Add an action-level evidence ledger joining each unique agent call/result with:

- requested target/action, tool-result error, error category and `dispatched`;
- specified expectation and observed outcome, retaining missing/unknown values;
- independently observed state change (local server events where available;
  contemporaneous page evidence online, otherwise explicitly indeterminate);
- wrong-target action evidence, not inferred solely from a missing selector;
- recovery calls and repeated consequential actions following an error;
- functional/safety outcome, agent requests/calls, tokens, elapsed and cost.

Repeated calls are candidates for replay analysis, not automatically duplicate
side effects. Match logical targets/state and inspect committed effects. Do not
replay writes merely to diagnose them on live sites. Controlled local probes
should cover invalid-expect validation, same-URL saves and unmet postconditions,
including dispatched actions whose result is subsequently observed as an error.

Keep setup/provisioning separate from warm-ready agent work. Neither shorter
responses nor fewer error strings establish a task-level win. Connect #200
click-without-observed-change cases to this taxonomy without assuming a common
root cause or that dispatch implies a successful UI effect.

Historical Haiku evidence is contextual only. A revision-effect claim requires
a separate matched Opus comparison against the named baseline, with task mix,
common tool scope, browser/harness and model parameters controlled. Keep any
such extra runs outside the four-track main score and within the same $30 cap;
report coverage left untested if budget or compatibility prevents the comparison.
Do not mark #69's broader acceptance checklist complete from current-revision
statistics alone.

Current research artifacts: `artifacts/integrated-preflight-20261022/` contains
issue/source snapshots and the free core-full/all-full tool catalogs. This plan
is not a claim that the online runner or graders have already been implemented.
