# V2 bug-class coverage review

- **Status: empirical V2 coverage pending.** This review maps public requirements to implemented mechanisms; it does not certify repairs. V1's recorded result remains **9/12 practice bugs**, not a V2 score.
- Reviewed all six `SYMPTOM.md` files and complete `scenarios/public.yaml` files; both invariant documents; current service design/operational notes; current runtime, GPU, idempotency, and fencing contracts; V1 gaps; and current controller/tools/validation code.
- The three A invariant files are byte-identical; the three B invariant files are byte-identical. Reading the two distinct documents therefore covers the published invariant text for all six cases.
- [Architecture guidance](v2_architecture.md) informs the repair loop. The [challenge README](../README.md) controls actual limits and interfaces. The user-requested runtime keeps three parallel read-only investigators and one serial editor.
- This document contains no case-specific patch recipes, source replacements, or private grading implementation details. No case workload, model call, or Docker job was launched for this review.

## Capability map

“Available” means a mechanism exists in the current source. Every row still needs empirical V2 evaluation. Investigator responsibilities overlap deliberately.

| Broad bug class | Public evidence | Available investigation/evidence | Validation and remaining boundary |
| --- | --- | --- | --- |
| Durable intent, cancellation ordering, restart recovery | A1/A3 incidents; service job lifecycle and persistence contracts | State/recovery specialist; source and current contracts; trace queries linking job, operation, and restart | Outcome, lease, liveness, and scenario checks. Recovery paths are exercised only when selected schedules reach them; there is no general disk-state explorer. |
| Cancellation versus completion; resource cleanup | A3 incidents; GPU terminal-state and asynchronous-release contracts | State/recovery plus delivery specialist; correlate API calls, GPU effects, terminal records, and releases | Outcome/capacity/liveness checks. Public success does not prove every release or late-message ordering was explored. |
| Capacity accounting, reservations, dispatch starvation | A3 incidents; service deployment and dispatch contracts | State/recovery specialist; read scheduler/recovery/accounting source and generated summaries | Capacity and liveness checks; A2 also limits GPU submit `CAPACITY` errors. No generic fairness proof or exhaustive workload sizing. |
| Lease expiry, fencing, pauses, clock assumptions | A2 incidents; A-family lease invariants; runtime/fencing contracts | Lease/membership specialist; inspect source and globally ordered trace events around a time/entity | Public lease/outcome checks plus clock/pause scenarios. Log timestamps are node-local; trace times must not be confused with them. Finite seeds do not prove every timing boundary. |
| Concurrent duplicate commits, speculative races, attempt isolation | B1 incidents; B-family commit/reduce/result invariants | Delivery/commit specialist; inspect competing requests, grants, task/attempt identities, and relevant `await` boundaries | Commit uniqueness, committed-input consistency, independent result checks, and liveness. Rare schedules may remain unobserved. |
| Lost assignments/reports; stale or reordered heartbeat reconciliation | B2 incidents; network, scheduling, and membership contracts | Delivery/commit plus lease/membership specialists; trace message/entity sequences and current contracts | Liveness, commit/result, and selected scenario checks. The harness has no automatic causal message graph or protocol-state model checker. |
| Worker incarnation changes; false failure detection | B3 incidents; registration/fencing and deployment timing contracts | Lease/membership specialist; compare restart, registration, heartbeat, and revocation evidence | Liveness and scenario assertions. B3 explicitly bounds registration RPCs per worker. Healthy-node classification still requires contract/trace reasoning. |
| Ambiguous RPC outcomes, retries, stable idempotency identities | B2 and cross-service contracts | Delivery/commit specialist; read caller/callee code and correlate operation identity with submit/status effects | At-most-once, outcome, result, and liveness checks. No generic automatically generated protocol oracle for an unfamiliar service. |
| Retry/registration amplification and goodput | A3/B3 incidents; idempotency/backoff contracts | All specialists can inspect retry loops, traffic counts, and trace events; delivery specialist leads | A3 bounds registration requests by boot; B3 bounds them by worker. General reference-relative I3 is **not** checked by the runtime without a reference message count. |
| Tenant/key scoping, result integrity, cross-attempt contamination | Service/platform contracts; common and B-family invariants | State/recovery plus delivery/commit specialists; inspect identity derivation and state transitions | Published outcome/result checks cover represented workloads. Unspecified semantics and unrepresented input classes remain outside proven coverage. |

Public source evidence: [A invariants](../practice/A1/INVARIANTS.md), [B invariants](../practice/B1/INVARIANTS.md), [A service contracts](../corpus/build/practice/service/A/design-overview.md), [B service contracts](../corpus/build/practice/service/B/design-overview.md), [runtime](../corpus/build/practice/platform/runtime-v3.md), [GPU](../corpus/build/practice/platform/gpu-api-v3.md), [idempotency](../corpus/build/practice/platform/idempotency.md), [fencing](../corpus/build/practice/platform/leases-and-fencing.md).

## What the public scenarios actually check

- All six public scenarios enforce an action-resolution deadline and `no_unhandled_exceptions`.
- A2 additionally bounds GPU submit `CAPACITY` errors with `rpc_errors_max`.
- A3 additionally bounds worker-to-router registration requests per boot with `rpc_requests_per_group_max`.
- B3 additionally bounds worker-to-coordinator registration requests per worker with `rpc_requests_per_group_max`.
- These are active protocol/traffic checks when the harness runs `sim check`. They must not be described as liveness-only coverage.
- Separately, published I3 compares total messages with a reference run. The runtime invokes `sim check` without `--reference-messages`, so **general reference-relative goodput remains unverified**. Specific scenario bounds do not replace that broader check. Official grading remains necessary.

## V1 gaps addressed in source

- **Generated evidence access:** read-only `artifacts/` aliases expose trace, summary, and replay logs; `inspect_trace` supplies entity/time filters and original line provenance. Bounds: 64 MiB scanned, 256 KiB per trace row, 18,000 output characters; cancellation, malformed rows, and truncation are explicit.
- **Iteration:** the editor can continue beyond V1's fourteen rounds, within shared spend/deadline guards and an eighty-round safety ceiling. Repeated evidence or oversized context can trigger a fresh diagnosis while preserving checked source.
- **Regression coverage:** all declared public seeds are retained. Observed scenario/fault checks are keyed separately and reused as guards; invalid probe requests do not become permanent requirements. Candidate acceptance requires complete checks and a successful determinism repeat.
- **Completion:** automatic final validation covers declared seeds and registered probes; partial or incomplete validation is reported distinctly. A prose completion claim does not certify a repair.
- **Progress accounting:** byte-identical transactions are rejected; mixed transactions omit unchanged files. Different source bytes can still be retained as a preparatory partial repair without proving an additional bug fixed.

Implementation references: [controller](fixer/fix.py), [tools](fixer/tools.py), [trace inspector](fixer/artifacts.py), [validation](fixer/validation.py), [retrieval](fixer/retrieval.py), [model limits](fixer/model.py). Offline tests exercise these mechanisms; they do not establish the number of service bugs repaired.

## Unsupported or incomplete coverage

- **Exploration is finite.** Two controller-selected additional seeds use the existing public scenario. There is no explicit scenario-authoring, systematic fault-combination generation, counterexample minimization, or exhaustive interleaving tool. Registered checks are capped at 32 to keep validation bounded.
- **Diagnosis remains model-dependent.** There is no machine-enforced per-symptom coverage ledger or formal proof that every incident item has a cause and repair. General protocol defects can survive a green public run.
- **Retrieval is selective.** Initial service/platform excerpts and log samples can omit decisive material. Agents can widen lexical searches, but there is no guarantee of complete contract discovery on an unfamiliar service.
- **Evidence can be incomplete.** Trace limits and malformed/oversized rows can hide later or larger events; callers must respect the returned flags. A filtered excerpt is evidence of selected events, not a complete causal proof.
- **Repair scope is constrained.** Exact source edits support Python files and new files; tests/simulator/scenarios remain protected. There is no general file-deletion tool or support for repairing a non-Python build system. Candidate validation is serial in the case workspace with checkpoints, not a parallel candidate search across isolated repair trees.
- **Known-safe is not globally optimal.** Guards prevent demonstrated regressions and new invariant categories, but can require a coherent combined repair when one change exposes another defect. Retained source, accepted patch count, and public-green status must never substitute for official per-bug results.
- **Unseen services remain unproven.** The practice families do not establish coverage for other codebases, workloads, or contracts.

## Evidence required before a V2 coverage claim

- [ ] Freeze one V2 image and verify it matches the reviewed runtime source; record offline test evidence.
- [ ] Run that exact image on all six supplied cases, serially under the agreed Docker resource settings.
- [ ] Record official per-bug results, required seed coverage, regression gates, spend, runtime, and infrastructure outcomes.
- [ ] Inspect residual failures, traffic/protocol assertions, and any truncated/incomplete evidence; distinguish an oracle gap from a failed repair.
- [ ] Compare with measured main/V1 **9/12**, using the same cases and grading workflow. Promote only under the user's improvement rule.
- [ ] Report remaining bug classes honestly. Even a complete practice score would not prove all unseen bugs can be found or repaired.
