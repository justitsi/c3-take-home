# V2 bug-class coverage review

- **Closed at the user's request; no further evaluations. Selected result: preserved V1/main, fully validated at 9/12.** R1 measured 1/5, r2 2/5 and r3 2/6 on their partial case sets. R4 verified A1 1/1; A2's interrupted snapshot later graded 2/2 separately, A3/B1 were not run, and B2/B3 grading was already in progress at closeout. There is **no complete r4 score or V2 promotion**. Implemented mechanisms are not repair certification.
- Reviewed all six `SYMPTOM.md` files and complete `scenarios/public.yaml` files; both invariant documents; current service design/operational notes; current runtime, GPU, idempotency, and fencing contracts; V1 gaps; and current controller/tools/validation code.
- The three A invariant files are byte-identical; the three B invariant files are byte-identical. Reading the two distinct documents therefore covers the published invariant text for all six cases.
- [Architecture guidance](v2_architecture.md) informs the repair loop. The [challenge README](../README.md) controls actual limits and interfaces. The user-requested runtime keeps three parallel read-only investigators and one serial editor.
- This document contains no case-specific patch recipes, source replacements, or private grading implementation details. This reviewer launched no case workload, model call, or Docker job; pilot observations came from the lead's frozen run and read-only inspection of its saved evidence.

## Capability map

“Available” describes frozen r4, including inherited r2/r3 mechanisms. Measured results below do not certify broad classes or establish a six-case r4 score. Investigator responsibilities overlap deliberately.

| Broad bug class | Public evidence | Available investigation/evidence | Validation and remaining boundary |
| --- | --- | --- | --- |
| Durable intent, cancellation ordering, restart recovery | A1/A3 incidents; service job lifecycle and persistence contracts | State/recovery specialist; source and current contracts; trace queries linking job, operation, and restart | Outcome, lease, liveness, and scenario checks. Recovery paths are exercised only when selected schedules reach them; there is no general disk-state explorer. |
| Cancellation versus completion; resource cleanup | A3 incidents; GPU terminal-state and asynchronous-release contracts | State/recovery plus delivery specialist; correlate API calls, GPU effects, terminal records, and releases | Outcome/capacity/liveness checks. Public success does not prove every release or late-message ordering was explored. |
| Protocol authority and forbidden side effects | Current service/platform contracts distinguish permitted participants and operation ownership | Independent post-repair contract reviewer; original-to-current diff; targeted authored workload and schema-supported traffic assertions | A green public template can miss an authority violation. Probe assertions must express the actual obligation; there is no automatic complete protocol oracle. |
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
- **Iteration:** the editor can continue beyond V1's fourteen rounds, within shared spend/deadline guards and an eighty-round safety ceiling. R1 showed that more rounds alone do not ensure progress; r2 changes evidence retention and restart control, and r3 adds independent contract review and targeted probes.
- **Regression coverage:** all declared public seeds are retained. Observed scenario/fault checks are keyed separately and reused as guards; invalid probe requests do not become permanent requirements. Candidate acceptance requires complete checks and a successful determinism repeat.
- **Completion:** automatic final validation covers declared seeds and registered probes; partial or incomplete validation is reported distinctly. A prose completion claim does not certify a repair.
- **Progress accounting:** byte-identical transactions are rejected; mixed transactions omit unchanged files. Different source bytes can still be retained as a preparatory partial repair without proving an additional bug fixed.

Implementation references: [controller](fixer/fix.py), [tools](fixer/tools.py), [probe authoring](fixer/probe_authoring.py), [trace inspector](fixer/artifacts.py), [validation](fixer/validation.py), [retrieval](fixer/retrieval.py), [model limits](fixer/model.py). Offline tests exercise these mechanisms; they do not establish the number of service bugs repaired.

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

These are observed, general interface/controller failure mechanisms, not proof of the sole cause of every unresolved service bug.

## R2 capabilities implemented in response

- **Explicit filtering:** legacy `query` remains one literal substring. Optional `all_terms` requires every term in the same JSON record; it combines with literal and time filters. Lists are bounded to eight terms of at most 256 characters. Clipped records retain relevant term excerpts.
- **Navigation and feedback:** `start_line`/`next_line` pagination resumes the first unreturned row without skipping output-capped evidence. Results expose returned/matched counts, a returned time range, scan-limit status, and actionable zero-match/truncation hints. The 64 MiB scan bound includes skipped lines.
- **Complete trace transport:** the controller allows up to 20,000 characters for read-tool responses, carrying an inspector page capped at 18,000 characters without discarding its cursor or hints. Inspector bounds, cancellation, and containment remain enforced.
- **Evidence-aware progress:** empty searches/scans are not progress; successful evidence is fingerprinted by content, including clipped term excerpts, rather than query spelling or regenerated artifact paths.
- **Retained facts and issue tracking:** a bounded observation buffer and per-symptom issue ledger survive context rebuilding. Observations carry provenance/revision information; ledger hypotheses and resolution claims remain unverified model statements. Fresh diagnosis omits prior hypotheses while retaining cited observations.
- **Separate compaction/restart policy:** context compaction preserves working state; actual fresh restarts reset per-diagnosis novelty and receive a six-round grace period. Investigation checkpoints encourage testing a supported candidate. The editor ceiling remains eighty rounds.

## Measured R2 pilot: progress and remaining failures

Frozen source `11aae52`, image `sha256:13ef71ea43ff…`; **226 offline tests passed**. [Recorded official pilot](benchmarks/v2-r2-pilot.json):

| Scope | Credited bugs | Model spend | Fixer runtime |
| --- | --- | --- | --- |
| B2 | 2/3 | $3.221326 | 618.410 s |
| B3 | 0/2 | $1.403646 | 199.562 s |
| Two-case total | **2/5** | **$4.624972** | **817.972 s** |

- B2 used same-record AND, pagination and RPC-identity correlation to reach decisive later events. Four retained candidates passed its declared public and additional-seed checks; the editor completed after 61 rounds, four context compactions and **zero fresh restarts**. Two credited targets passed 20/20 official seeds each.
- Nevertheless, one B2 target passed **0/20**: public-green status did not establish the relevant protocol/authority obligation. This is evidence for contract-led targeted probes, not an instruction to encode grading answers.
- B3 terminated early when rejection rollback's Linux directory exchange raised `ENOTEMPTY` on the real bind-mounted workspace. Both restore attempts failed; the controller exited nonzero with status `running`, and the case regression gate failed. A target passing 20/20 seeds did **not** receive credit through that failed gate.
- These observations separate repair effectiveness from rollback reliability. R2 improved B2 evidence use, but **2/5 is not a six-case score, an improvement over main, or a promotion result**. Four cases were not run; no timeout was recorded.
- Minor observed inspection limitation: pretty-printed JSON sent to the JSONL inspector can yield all-malformed/zero-event output with an inappropriate filtering hint. Summaries remain readable through `read_file`/`search`; this usability issue is not claimed fixed in r3.

## R3 capabilities and measured partial evaluation

- **Bounded targeted scenario authoring:** editor-only `create_probe` clones a supplied scenario into an owned, write-once `artifacts/probes/` file. Mapping overrides merge; lists/scalars replace. Safe parsing rejects executable YAML tags, duplicate keys, cycles and nonfinite data. Node classes must come from the supplied base. Bounds: 32 expanded nodes, 500 expanded actions, virtual `end_at` ≤600 seconds, serialized scenario ≤64 KiB.
- **Protected evidence:** provided scenarios/faults remain untouched. Relative base fault paths are resolved under protected `scenarios/`; optional fault changes select supplied files, not arbitrary inline fault programs. Authored aliases are registered with content hashes and containment checks. The controller automatically replays a created probe before recording its counterexample as a future guard. Creation itself is not validation.
- **Independent post-repair review:** a fresh read-only reviewer receives the trusted original-to-current source diff, current contracts and checked evidence. Its remit includes both ends of changed protocols, ordering/incarnation/clock assumptions and durable cleanup. Recommendations remain hypotheses; the editor must verify them through code/contracts and supported probes.
- **Bounded source audit:** `source_diff()` accepts no model-selected paths; the controller supplies the original trusted checkpoint. It reports service-source additions/deletions/changes within an 18,000-character output bound, with containment, input-size and cancellation guards.
- **Rollback hardening:** the platform-specific directory-exchange failure now has a recoverable fallback and explicit failed-rollback handling; offline verification includes a real host bind mount. This addresses the observed reliability mechanism, not the unresolved service bug by itself.
- **Frozen verification:** source `2096b49`, image `sha256:639f4282de7d…`; **278 offline tests passed in 30.87 seconds**, with all ten build-context files matching. [Image/test evidence](benchmarks/v2-r3-image.json). Separate case sessions used one grading worker each and the unchanged Docker VM allocation; the lead increased the active-case cap from two to three after observing memory headroom.
- **Measured partial result:** A1 **1/1**, B2 **0/3**, B3 **1/2**; total **2/6**, **$11.533084**, **1,928.950 seconds** summed fixer runtime. Public/regression gates passed; no recorded infrastructure errors or timeouts. A2/A3/B1 were not run on r3, so this is not a complete-suite result or promotion evidence. [Official partial results](benchmarks/v2-r3-partial.json).

## R4 partial closeout: A1 verified; A2 interrupted

- **Freeze:** source `ac409bf`, image `sha256:0c590ba5b537…`; **287 offline tests passed in 31 seconds**, including real bind-mounted restoration, and all ten build-context files match. [Image/test evidence](benchmarks/v2-r4-image.json). The full batch uses separate case sessions, at most three active, one grading worker each; Docker VM allocation remains unchanged.
- **Controller refinements:** rejected-check observations now preserve trace/summary aliases; investigator/reviewer synthesis has more bounded output allowance and explicit completion status. Truncated reviewer synthesis receives a short, tool-free retry; an incomplete review is not returned as a completed audit. Read-only diagnosis can hand off early to independent review. These are workflow corrections, not new service-specific repair rules.
- **A1 official result:** **1/1 credited, 20/20 required seeds**, public and regression gates passed, fixer exit 0, no timeout or infrastructure error. Spend **$2.695635**, official fixer wall time **538.803 seconds**. Independent read-only verification found all **20 repeated trace pairs present and hash-identical**. [Official result](results/v2-r4-cases/A1-session/A1/result.json).
- **A1 runtime evidence:** one retained candidate; completed independent review; successful source diff and authored-probe replay; final coverage complete/all passed with no restoration. An invalid inline-fault request was rejected, then corrected to a supplied fault file. The final guard set included the authored probe. Its pass alone does not prove every intended transition occurred; the official target result supplies the measured repair credit.
- **A2 interrupted snapshot, separately verified:** the user requested immediate wrap-up; A2's fixer log confirms `SIGTERM` after **145.23 seconds**, one retained candidate, and no automatic final-validation event. The already-running grader subsequently credited that source snapshot **2/2**, each **20/20 required seeds**; public/regression gates passed, exit 0, no timeout or infrastructure/evaluation error. Independent read-only audit found all **40 repeated trace pairs present and hash-identical**, and `patch.diff` SHA-256 matched the recorded `9a2d999571c58f4bdd8bafbf8232e7d6868884f5d15c58e428b87de863cbbd1b`. Only two service-source files changed; no dropped files/symlinks. Official wall time **146.047 seconds**, reported spend **$1.168160**. [Separate interrupted-snapshot evidence](benchmarks/v2-r4-interrupted-A2.json). This is a verified snapshot result, **not an uninterrupted/full-controller run or complete r4 score**; in-flight model reservation is not added to settled spend.
- **Uncompleted scope:** A3/B1 were not run on r4. B2/B3 had already reached grading at wrap-up; any terminal results belong to their recorded partial evaluation, not an inferred complete-suite score. No further case or model workload is authorized by this closeout.
- **Selection:** retain V1/main **9/12** as the best fully validated six-case result. Preserve V2 source, frozen image identities, partial evidence and future-work notes separately; no V2 merge/promotion is claimed.

## Unsupported or incomplete coverage

- **Exploration is finite.** R3 authors small targeted workloads and selects supplied fault profiles; it does not systematically generate every fault combination, minimize counterexamples or explore all interleavings. Two additional controller seeds still use the public template. Registered checks are capped at 32.
- **Diagnosis remains model-dependent.** The issue ledger and independent reviewer supply claims, not semantic proofs linking every incident item to a valid repair. Probe strength depends on choosing a distinguishing workload and correct assertion. General protocol defects can survive public and authored green runs.
- **Retrieval is selective.** Initial service/platform excerpts and log samples can omit decisive material. Agents can widen lexical searches, but there is no guarantee of complete contract discovery on an unfamiliar service.
- **Evidence can be incomplete.** Pagination handles ordinary output truncation, but trace scan limits and malformed/oversized rows can still hide events. The bounded observation buffer may evict useful facts. A filtered excerpt is selected evidence, not a complete causal proof.
- **Continuity remains bounded.** R3 B3 compaction lost direct rejected-replay aliases, leading the editor to reason on retained-source evidence before rediscovering rejected artifacts. R4 now preserves those aliases in rejected-check observations, but a bounded buffer can still evict evidence. A retained-source diff is not the rejected candidate's diff.
- **A reviewer may not finish.** R3 B2 review hit its output token limit and retained only a 138-character earlier utterance. R4 records completion explicitly and retries truncated synthesis; A1's review completed. Deadlines, budgets and truncation still limit coverage, so invoking a reviewer never substitutes for checking its actual outcome.
- **Repair scope is constrained.** Exact source edits support Python files and new files; tests/simulator/scenarios remain protected. There is no general file-deletion tool or support for repairing a non-Python build system. Candidate validation is serial in the case workspace with checkpoints, not a parallel candidate search across isolated repair trees.
- **Known-safe is not globally optimal.** Guards prevent demonstrated regressions and new invariant categories, but can require a coherent combined repair when one change exposes another defect. Retained source, accepted patch count, and public-green status must never substitute for official per-bug results.
- **Unseen services remain unproven.** The practice families do not establish coverage for other codebases, workloads, or contracts.

## Deferred gates; not authorized continuation work

- [x] Freeze a distinct r4 image and verify its reviewed source/offline tests. Earlier revisions' repair scores are not r4 results.
- [ ] With renewed authorization only, complete an exact-image six-case evaluation under bounded per-case sessions and Docker resources. The interrupted/absent cases are not successes.
- [ ] Record official per-bug results, required seed coverage, regression gates, spend, runtime, and infrastructure outcomes.
- [ ] Inspect residual failures, traffic/protocol assertions, and any truncated/incomplete evidence; distinguish an oracle gap from a failed repair.
- [ ] Compare with measured main/V1 **9/12**, using the same cases and grading workflow. Promote only under the user's improvement rule.
- [ ] Report remaining bug classes honestly. Even a complete practice score would not prove all unseen bugs can be found or repaired.
