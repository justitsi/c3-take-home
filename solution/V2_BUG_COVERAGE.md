# V2 bug-class coverage review

- **Status: V2-r1 measured 1/5 bugs in a two-case pilot; V2-r2 repair coverage pending.** V1/main remains the **9/12** six-case baseline. Implemented mechanisms are not repair certification.
- Reviewed all six `SYMPTOM.md` files and complete `scenarios/public.yaml` files; both invariant documents; current service design/operational notes; current runtime, GPU, idempotency, and fencing contracts; V1 gaps; and current controller/tools/validation code.
- The three A invariant files are byte-identical; the three B invariant files are byte-identical. Reading the two distinct documents therefore covers the published invariant text for all six cases.
- [Architecture guidance](v2_architecture.md) informs the repair loop. The [challenge README](../README.md) controls actual limits and interfaces. The user-requested runtime keeps three parallel read-only investigators and one serial editor.
- This document contains no case-specific patch recipes, source replacements, or private grading implementation details. This reviewer launched no case workload, model call, or Docker job; pilot observations came from the lead's frozen run and read-only inspection of its saved evidence.

## Capability map

“Available” describes the current r2 implementation. The measured pilot below ran the earlier frozen r1 image; it does not certify these broad classes or establish an r2 score. Investigator responsibilities overlap deliberately.

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
- **Iteration:** the editor can continue beyond V1's fourteen rounds, within shared spend/deadline guards and an eighty-round safety ceiling. R1 showed that more rounds alone do not ensure progress; r2 changes evidence retention and restart control below.
- **Regression coverage:** all declared public seeds are retained. Observed scenario/fault checks are keyed separately and reused as guards; invalid probe requests do not become permanent requirements. Candidate acceptance requires complete checks and a successful determinism repeat.
- **Completion:** automatic final validation covers declared seeds and registered probes; partial or incomplete validation is reported distinctly. A prose completion claim does not certify a repair.
- **Progress accounting:** byte-identical transactions are rejected; mixed transactions omit unchanged files. Different source bytes can still be retained as a preparatory partial repair without proving an additional bug fixed.

Implementation references: [controller](fixer/fix.py), [tools](fixer/tools.py), [trace inspector](fixer/artifacts.py), [validation](fixer/validation.py), [retrieval](fixer/retrieval.py), [model limits](fixer/model.py). Offline tests exercise these mechanisms; they do not establish the number of service bugs repaired.

## Measured V2-r1 pilot and observed failure mechanisms

The completed pilot used source `43b6c4c` and immutable image `c3-fixer-prototype:v2-r1` (`sha256:9e3f6911690…`). [Recorded official results](benchmarks/v2-r1-pilot.json):

| Scope | Bugs fixed | Model spend | Fixer runtime |
| --- | --- | --- | --- |
| B2 | 0/3 | $3.011534 | 418.027 s |
| B3 | 1/2 | $3.049778 | 457.992 s |
| Two-case total | **1/5** | **$6.061312** | **876.019 s** |

- The credited bug passed 20/20 required seeds. Public tests and regression gates passed; there were no infrastructure errors or timeouts.
- Four cases were not run in this pilot, so there is **no six-case V2-r1 score**. V1 fixed 2/5 on this same two-case subset; r1 did not improve on it and does not meet the promotion rule.
- **Literal-filter mismatch:** seven observed multi-word trace queries returned zero records after scanning the full 5,488,195-byte / 32,944-row saved trace. Independent same-record term checks found relevant records whose values lived in separate JSON fields. The tool accepted the requests but did not express the model's intended AND search.
- **Prefix pressure:** one broad entity query reached the output bound after 50 records, covering only a short early time interval. R1 had time filters but no resumable line cursor; the agent repeatedly failed to reach later evidence efficiently.
- **Compaction and evidence loss:** B2 exhausted 80 editor rounds with nine fresh restarts and no candidate patch. Source/summary facts and action-to-entity mappings were rediscovered after resets. Context growth was treated like a fresh investigation, discarding useful observations along with hypotheses.
- **Progress bookkeeping:** differently worded empty queries could count as progress. Conversely, the global novelty set survived fresh restarts, so required rereads could trigger another restart after only a few rounds. This produced repeated investigation rather than a checked repair.

These are observed, general interface/controller failure mechanisms, not proof of the sole cause of every unresolved service bug. Their correction still needs measured r2 evaluation.

## R2 capabilities implemented in response

- **Explicit filtering:** legacy `query` remains one literal substring. Optional `all_terms` requires every term in the same JSON record; it combines with literal and time filters. Lists are bounded to eight terms of at most 256 characters. Clipped records retain relevant term excerpts.
- **Navigation and feedback:** `start_line`/`next_line` pagination resumes the first unreturned row without skipping output-capped evidence. Results expose returned/matched counts, a returned time range, scan-limit status, and actionable zero-match/truncation hints. The 64 MiB scan bound includes skipped lines.
- **Complete trace transport:** the controller allows up to 20,000 characters for read-tool responses, carrying an inspector page capped at 18,000 characters without discarding its cursor or hints. Inspector bounds, cancellation, and containment remain enforced.
- **Evidence-aware progress:** empty searches/scans are not progress; successful evidence is fingerprinted by content, including clipped term excerpts, rather than query spelling or regenerated artifact paths.
- **Retained facts and issue tracking:** a bounded observation buffer and per-symptom issue ledger survive context rebuilding. Observations carry provenance/revision information; ledger hypotheses and resolution claims remain unverified model statements. Fresh diagnosis omits prior hypotheses while retaining cited observations.
- **Separate compaction/restart policy:** context compaction preserves working state; actual fresh restarts reset per-diagnosis novelty and receive a six-round grace period. Investigation checkpoints encourage testing a supported candidate. The editor ceiling remains eighty rounds.

R2 tests and pilots must establish whether these changes improve repairs. This document asserts no r2 score or all-bugs result.

## Unsupported or incomplete coverage

- **Exploration is finite.** Two controller-selected additional seeds use the existing public scenario. There is no explicit scenario-authoring, systematic fault-combination generation, counterexample minimization, or exhaustive interleaving tool. Registered checks are capped at 32 to keep validation bounded.
- **Diagnosis remains model-dependent.** R2 adds an issue ledger, but its hypotheses, citations, and statuses are model claims, not a semantic proof linking every incident item to a valid repair. General protocol defects can survive a green public run.
- **Retrieval is selective.** Initial service/platform excerpts and log samples can omit decisive material. Agents can widen lexical searches, but there is no guarantee of complete contract discovery on an unfamiliar service.
- **Evidence can be incomplete.** Pagination handles ordinary output truncation, but trace scan limits and malformed/oversized rows can still hide events. The bounded observation buffer may evict useful facts. A filtered excerpt is selected evidence, not a complete causal proof.
- **Repair scope is constrained.** Exact source edits support Python files and new files; tests/simulator/scenarios remain protected. There is no general file-deletion tool or support for repairing a non-Python build system. Candidate validation is serial in the case workspace with checkpoints, not a parallel candidate search across isolated repair trees.
- **Known-safe is not globally optimal.** Guards prevent demonstrated regressions and new invariant categories, but can require a coherent combined repair when one change exposes another defect. Retained source, accepted patch count, and public-green status must never substitute for official per-bug results.
- **Unseen services remain unproven.** The practice families do not establish coverage for other codebases, workloads, or contracts.

## Evidence required before a V2-r2 promotion claim

- [ ] Freeze a distinct r2 image and verify it matches the reviewed runtime source; record its own offline test evidence. Do not reuse r1's image or score.
- [ ] Run that exact image on all six supplied cases, serially under the agreed Docker resource settings.
- [ ] Record official per-bug results, required seed coverage, regression gates, spend, runtime, and infrastructure outcomes.
- [ ] Inspect residual failures, traffic/protocol assertions, and any truncated/incomplete evidence; distinguish an oracle gap from a failed repair.
- [ ] Compare with measured main/V1 **9/12**, using the same cases and grading workflow. Promote only under the user's improvement rule.
- [ ] Report remaining bug classes honestly. Even a complete practice score would not prove all unseen bugs can be found or repaired.
