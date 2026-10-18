# Local process resource collection

`run` and `smoke --execute` now sample local resources with pinned psutil 7.2.2.
Use `uv sync --locked` / `uv run --locked ...`; the Python runtime is no longer
standard-library-only. No model API SDK has been added.

## Scope

The collector receives explicit process roots, identifies each by PID **and
creation time**, and follows descendants. Previously observed children continue
to be followed after reparenting. It does not enumerate unrelated app command
lines or collect environment variables. The observer process is outside owned
roots, so its own RSS/CPU are not charged to the target process totals.

Roles: `harness`, `mcp`, `bridge`, `browser`, and `browser_launcher`. Role assignment
for discovered descendants uses process names/inheritance; this is a heuristic,
not a claim of perfect executable attribution. Kitsune's web-ext launcher is
reported separately as test infrastructure. Owner tags separate Playwright and
Kitsune even when both have processes alive in the paired setup.

The per-run collector includes Codex and descendants. For Kitsune, it also
receives the separately started private bridge/web-ext process roots. Those
external roots are expected to remain alive until the pair ends, so they are
not mislabeled as leaked processes at the end of an individual agent run.
The pair-level collector measures their full lifecycle and checks final cleanup.

## Files and metrics

Each run and each smoke-pair directory contains:

- `resources.jsonl`: timestamps, phase, PID/creation-time/parent/name/state,
  role/owner, RSS bytes, CPU user/system counters and deltas, one-core CPU
  percentage, and aggregate groups.
- `resource-summary.json`: sampled peak RSS, time-weighted mean RSS,
  observed CPU user/system deltas, peak process count, sample/error counts,
  collector wall-time overhead, and live identities at the end.

Groups include `all`, `owner/<target>`, and `component/<target>/<role>`, plus
`phase/<phase>/<group>`. Per-run phases are `baseline`, `task`, `cleanup`.
Pair phases additionally include `setup`, `ready`, `task_playwright`, and
`task_kitsune`. Phase transitions force boundary samples. Normal interval is
one second; each record has the actual elapsed timestamp.

System context records total/available RAM, swap used, and logical CPU count.
These are machine-wide reference values affected by unrelated applications;
they must not be presented as target-only resource consumption. No dedicated
macOS memory-pressure or compressed-memory metric is collected.

Means use left-rectangle time integration between observations. Per-component
means cover observed component windows, not a complete inferred process lifetime.
Existing processes' CPU counters are baselined when first observed; a newly born
process's initial observed CPU is included. The `cpu_percent_one_core` value
may exceed 100% for multithreaded work.

## Interpretation and limits

- **Summed RSS can double-count shared memory.** It is not PSS, USS, or macOS
  physical footprint. Use absolute bytes/MiB rather than RAM percentage as the
  primary metric.
- Peaks are **sampled peaks**, not guaranteed instantaneous maximums.
- Short-lived children and final CPU tails between observations may be missed.
  New orphaned children that were never observed cannot be recovered reliably.
- Sampling permission/race failures are exposed as counters; do not treat a
  degraded measurement as complete resource coverage.
- CPU percentages and totals are local. Remote GPT inference RAM/CPU/GPU is
  not measured.
- End-of-run live process lists are observations, not automatic proof of a
  leak. Externally managed roots are listed explicitly. Final pair cleanup is
  the relevant leak check for the private Kitsune browser/bridge.
- Pair-level `all` includes idle Kitsune resources while Playwright executes.
  For target comparisons use each **per-run** summary or filter by owner.
- Timing/startup asymmetry and fixed order from the smoke experiment remain;
  resource collection does not turn that experiment into a fair leaderboard.

## First real validation

Actual paired GPT-6.1-Sol smoke with collection:

`artifacts/smoke/20261018T080844Z-2d61acf8c1/`

Both runs completed unscored. The pair captured 64 boundary/periodic samples,
reported zero sampling errors, and no unexpected live processes at final stop.
All expected component groups were present, including the separately started
Kitsune bridge/browser/launcher. These numbers are setup validation, not a
resource efficiency ranking.

## Tests

```sh
uv run --locked python -m unittest discover -s tests -v
```

Coverage includes time weighting, CPU baselines, PID reuse, owner separation,
process-name attribution, permission failures, actual child-process sampling,
private file modes, and exclusion of the observer process.
