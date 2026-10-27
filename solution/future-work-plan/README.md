# Future work

Status as of the V3.2 submission; see [../README.md](../README.md). The [V2](v2_architecture.md) and [V3](v3_architecture.md) documents are the original proposals, kept unchanged as background.

## Implemented in V3.x

Hypothesis register with linked experiments, trace queries and stuck-work timelines, replay log signatures, fault-profile probing before editing, probe-based candidate checks, per-report focus rounds, forced residual repair, and forced action after read-only batches.

## Gaps

- No full six-case evaluation of V3.2. Results are single local runs with high variance (B2: 1/3 to 3/3).
- A3 and B1 not rerun on the final build; B3 has no valid run (API 403).
- B1 and B3 diagnoses are not implemented. B1: the commit handler decides a duplicate commit by output equality, not task identity. B3: membership keeps `last_hb_seq` across re-registration and compares worker-clock `sent` with coordinator time.

## Priorities

1. **Measure.** Run the exact image on all six cases, repeated, in Docker mode. Record variance, cost and time.
2. **Reduce variance.** Combine rejected one-sided protocol fixes into two-sided candidates, and cap focus-round cost.
3. **Guard audit.** For every check that ignores or rejects a message, ask whether it can starve a liveness signal.
4. **Persistent guards.** Keep the failing seeds, probed profiles and extra seeds as regression guards for the whole run.
5. **Time.** Skip investigators when the cause is clear, and stop once probes and public checks are clean.
