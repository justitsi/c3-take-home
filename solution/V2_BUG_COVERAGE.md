# V2 bug-class coverage review — condensed

## Scope and selection

- **Selected V1: 9/12, all six cases.** V2 has no complete comparison/promotion.
- R4 uninterrupted A1/B2/B3 **4/6**; interrupted A2 snapshot separately **2/2**; A3/B1 not run. See [scorecards](benchmarks/), [review](V2_REVIEW.md), [future work](<future work.md>).
- Reviewed six incidents/public scenarios, both distinct invariant documents, current contracts, runtime and saved autonomous outputs. No injected practice repairs/private answers.
- “Available” describes experimental R4, not selected V1 or universal proof. Three read-only specialists feed one serial editor.

## Capability map

| Bug class | Investigation available | Coverage boundary |
| --- | --- | --- |
| Durable intent, cancellation/restart recovery | Recovery specialist, persistent state/contracts, operation/restart traces | Reached outcome/lease/liveness schedules only; no disk-state explorer |
| Completion versus cancellation, cleanup | Recovery + delivery; API effects, terminal records/releases | Finite late-message/release orderings |
| Protocol authority/forbidden side effects | Independent diff/contract review, derived workloads/traffic assertions | Public templates can miss authority; no complete protocol oracle |
| Reservations/capacity/starvation | Scheduler/recovery/accounting source and summaries | Capacity/liveness, not fairness proof |
| Leases/fencing/pauses/clocks | Membership, current contracts, ordered traces | Finite boundaries; local logs are not global trace time |
| Duplicate commit/speculation/attempt isolation | Delivery; competing requests/grants/identities/awaits | Commit/input/result checks; rare schedules may be missed |
| Lost assignment/report, reordered heartbeat | Delivery + membership, both protocol ends | No automatic causal graph/state model checker |
| Incarnation/false failure detection | Membership; restart/register/heartbeat/revocation | Liveness and selected registration counts |
| Ambiguous RPC/retry/idempotency | Caller/callee state, stable operation identity | Semantic interpretation remains model-dependent |
| Amplification/goodput | Traffic counts, backoff/current contracts | Specific bounds active; general reference-relative I3 unverified |
| Tenant/key/result scoping | Identity derivation/state transitions | Represented inputs only |

Sources: [A invariants](../practice/A1/INVARIANTS.md), [B invariants](../practice/B1/INVARIANTS.md), [A design](../corpus/build/practice/service/A/design-overview.md), [B design](../corpus/build/practice/service/B/design-overview.md), [runtime](../corpus/build/practice/platform/runtime-v3.md), [GPU](../corpus/build/practice/platform/gpu-api-v3.md), [idempotency](../corpus/build/practice/platform/idempotency.md), [fencing](../corpus/build/practice/platform/leases-and-fencing.md).

## What checks establish

- All public scenarios check action-resolution deadline/no unhandled exceptions.
- A2 bounds submit CAPACITY errors; A3 bounds router registrations per boot; B3 bounds coordinator registrations per worker. Active traffic/protocol checks are not merely liveness.
- Runtime check lacks reference-message count: broader reference-relative I3 goodput remains unverified.
- Replay success only establishes execution; invariants/expectations must also pass.
- Official per-bug 20-seed evidence establishes practice credit; public-green, ledger claims and accepted patch count do not.

## Capabilities after V1

- **Contained evidence:** read-only trace/summary/log aliases; traversal/symlink/edit rejection. Bounds: 64 MiB scan, 256 KiB row, 18,000 output characters; explicit cancellation/malformed/truncated state.
- **Navigation:** same-record AND, literal/time filters, line paging and count/time/provenance feedback; complete bounded controller transport.
- **Continuation/memory:** up to 80 total editor rounds within spend/time, versus V1 fourteen. Facts/issues survive compaction; fresh diagnosis drops hypotheses, preserves repairs/guards and resets novelty. Empty reads/no-op edits are not progress.
- **Guards/final state:** every declared seed and observed seed/scenario/fault identity; complete checks, protected passes, new-category rejection, deterministic repeat; invalid configurations cannot poison registry; partial/incomplete final status explicit.
- **Derived probes:** editor-only clones of supplied scenarios; safe parsing, write-once hashes, verified aliases, automatic replay/registration. Provided scenarios/faults untouched.
- **Bounds:** base node-class allowlist, 32 nodes/500 actions/end time ≤600/64 KiB; faults select supplied files, not inline programs.
- **Independent review:** original-to-current trusted diff, current contracts and evidence; findings remain hypotheses.
- **Recovery:** real host-bind fallback, retained active snapshot/fatal rollback state, bounded synthesis retry and completion flag.
- **R4 continuity:** rejected artifacts survive compaction; early review preserves validated repairs; cited completed audit stops without redundant restart.

Code: [controller](fixer/fix.py), [tools](fixer/tools.py), [artifacts](fixer/artifacts.py), [probes](fixer/probe_authoring.py), [validation](fixer/validation.py), [retrieval](fixer/retrieval.py), [model](fixer/model.py).

## Measurements and lessons

| Scope | Credit | Spend / summed fixer time | Observation |
| --- | --- | --- | --- |
| R1 B2/B3 | 1/5 | $6.061312 / 876.019 s | Filter mismatch, prefix pressure, evidence loss/restarts |
| R2 B2/B3 | 2/5 | $4.624972 / 817.972 s | Better correlation; B3 rollback/regression failure |
| R3 A1/B2/B3 | 2/6 | $11.533084 / 1,928.950 s | Safe restore; no B2 edits/truncated review |
| R4 A1/B2/B3 | 4/6 | $10.619585 / 1,980.916 s | Better workflow, residual protocol/registration bugs |
| R4 A2 interrupted | 2/2 | $1.168160 / 146.047 s | Snapshot after SIGTERM, not normal completion |

- Offline counts 149→226→278→287 test controller contracts, not service bug counts.
- R1 multiword literal filters missed terms across JSON fields; later AND/paging addressed expression/navigation. Content-based novelty and distinct compaction reduced empty rediscovery.
- R2 B2 public/extra seeds passed despite official bug-2 0/20. B3 ENOTEMPTY bind failure leaked rejected source; raw scenario successes received no credit through failed regression gate.
- R3 verified bind recovery. B2 spent 80 rounds without edits; truncated review retained introductory prose. B3 safe rejections still left registration bug.
- R4 genuinely completed synthesis/reviews and used rejected citations after compaction. Eleven public-template B2 seeds still missed authority/protocol bug-2.
- R4 B3 safely rejected four candidates but completed reviewer made unsupported causal inferences. Neither B case authored a scenario.
- A1 authored/replayed a probe after correcting inline-fault misuse; retained repair/final coverage/review passed, official 1/1 with 20 matching trace pairs. Probe success does not prove intended events occurred.
- A2 SIGTERM after 145.23 s, one retained patch/no normal final-validation event. Existing grader verified 2/2, 40 matching trace pairs, 27 public/53 regression passes, exact source-only patch hash.
- R4 B2 2/3 and B3 1/2: all 100 repeated pairs audited, gates pass/clean exits/no timeout/infra. V1 same-case 2/5, but no full R4 comparison.

## Residual gaps and future gates

- Selected V1 misses forbidden-cancellation reconciliation, ambiguous-submit liveness and registration amplification.
- R4 repairs ambiguous-submit behavior but still misses last-sent/reply-as-is heartbeat authority; B3 registration remains 0/20.
- Finite exploration: no systematic fault product/interleaving search/counterexample minimizer; registry cap 32.
- Diagnosis/assertions/review remain model-dependent. A cited claim or completed review may be wrong.
- Selective retrieval can miss contracts. Pretty JSON passed to JSONL inspection can yield misleading malformed/empty feedback; ordinary summary reads still work.
- Scan/output/memory bounds can hide/evict evidence; accepted-source diff is not rejected-candidate diff.
- Tools repair Python/source, not arbitrary build systems/general deletion; mutation/validation is serial.
- Guards protect demonstrated behavior, not every unseen case; dependent repairs may need a coherent transaction.
- Renew authorization/time/spend before continuation; complete comparable exact-image suite, verify discriminating probe events, audit hashes/gates/costs.
- Require improvement over full V1 9/12 before considering replacement, with separate merge/submission authority. Report uncertainty even at 12/12.
