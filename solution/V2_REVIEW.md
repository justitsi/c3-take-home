# V2 independent reliability review — condensed

## Decision and scope

- **Selected V1: 9/12 across all six official practice cases.** V2 remains experimental; no merge/push or full-suite improvement is claimed.
- R4 uninterrupted A1/B2/B3: **4/6**. Interrupted A2 snapshot separately **2/2**. A3/B1 not run.
- Review covered generic controller/tools, adversarial fixtures and saved autonomous outputs; reviewers injected no practice repairs or extra paid workloads.
- Local [README](../README.md)/[rules](../RULES.md) control limits: 900 seconds, $3 per bug, permitted proxy models, source-only changes, deterministic replay and 20 hidden seeds per credited bug.
- VM stayed ~2 GB; later authorized separate sessions used at most three cases, one grading worker each.
- [Future work](<future work.md>) and [V3 plan](V3_IMPLEMENTATION_PLAN.md) record deferred decisions. Upload cleanup moved raw replay/scratch directories outside the repo; retained summaries, logs, patches and chats preserve review records.

## Frozen checkpoints

| Revision | Exact-image offline tests | Official evidence | Disposition |
| --- | --- | --- | --- |
| V1 | 62; 23.51 s | 9/12, six cases; $5.850678, 991.650 s | Selected |
| R1 `43b6c4c` | 149; 30.44 s | B2 0/3, B3 1/2; $6.061312, 876.019 s | Worse than V1 same-case 2/5 |
| R2 `11aae52` | 226; 30.92 s | B2 2/3, B3 0/2; $4.624972, 817.972 s | Rollback/new-regression failure |
| R3 `2096b49` | 278; 30.87 s | A1 1/1, B2 0/3, B3 1/2; $11.533084, 1,928.950 s | Partial 2/6; no improvement |
| R4 `ac409bf` | 287; 31.00 s | A1 1/1, B2 2/3, B3 1/2; $10.619585, 1,980.916 s | Partial 4/6; not qualified replacement |

- Exact image identities/scorecards: [benchmarks/](benchmarks/). Frozen tags remain distinct; runtime source did not change during evaluation.
- V1's 240 repeated bug-seed pairs were independently audited. Each R1–R4 B-family pilot's 100 pairs had two matching valid trace hashes/no replay errors. R4 A1's 20 and interrupted A2's 40 pairs also matched.
- Summed fixer runtime is not concurrent elapsed time. Baseline-relative regression success allows unrelated original failures; it does not mean every private test passed.

## Acceptance and adversarial coverage

| Obligation | Verified mechanism / fixtures |
| --- | --- |
| Preserve earlier behavior | Complete candidate checks, protected public/ad hoc passes, new-category rejection, exact rollback |
| Distinguish check identity | Seed + scenario + faults; invalid configuration cannot poison registry |
| Handle dependent repairs | Reject unsafe intermediate change; allow coherent combined retry without suppressing checks |
| Retain discovered coverage | Known specifications/passing guards survive restoration; revision-specific results stay distinct |
| Report final state | Automatic required coverage; incomplete/partial not relabelled clean |
| Bound iteration/memory | Continuation beyond V1 limit; factual compaction separate from fresh diagnosis |
| Reject incomplete batches | Truncated/filtered/malformed replies execute no partial mutation; conservative budget settlement |
| Contain tools | Read-only artifacts, traversal/symlink checks, bounded scan/output/cancellation |
| Preserve source on shutdown | Atomic exchange/fallback/emergency recovery, active snapshot, SIGTERM and persistent-failure fixtures |
| Keep runtime generic | Permitted model/proxy; source-only edits; no arbitrary shell or practice-specific recipes |
| Demonstrate effectiveness | Exact-image six-case official comparison; incomplete for every V2 revision |

Tests: `test_v2_*.py`, `test_v3_review.py`, `test_v3_amendments.py`, and baseline harness/model/tools/validation fixtures. Generic services/fake HTTP test controller contracts, not unseen repair success.

## R1: evidence access without productive diagnosis

- Both cases exhausted 80 rounds. B2: nine restarts/no candidate. B3: fourteen restarts/one clock repair.
- Literal multiword filters missed terms in separate JSON fields; prefix-only output hid later events without resumable paging.
- Context growth caused fresh diagnosis/evidence loss. Empty query wording counted as novelty; global novelty survived resets and penalized necessary rereads.
- R2 added same-record AND, paging/time/provenance feedback, complete bounded transport, retained observations/issues, content-based progress and separate compaction/restart policy.
- These are observed general shortcomings, not proven sole causes of each miss.

## R2: better evidence, real bind-mount rollback failure

- **B2:** 2/3; bug-1/bug-3 20/20, bug-2 0/20; 618.410 s/$3.221326. Four retained candidates, 61 rounds/four compactions/no restart. Seven public-template seeds and gates passed.
- Ledger claimed every issue resolved, but forbidden cancellation remained. Public-green was not a protocol certificate.
- **B3:** gated 0/2, despite raw outcomes 16/20 and 20/20; 199.562 s/$1.403646, exit 1, three new baseline regressions.
- Host-bind `renameat2(RENAME_EXCHANGE)` raised ENOTEMPTY (39), absent from fallback whitelist. Both restores failed; rejected heartbeat-sequence edits escaped. Report still said running with one accepted patch/no final validation.
- This was a controller defect, not infrastructure failure. Native-temp tests missed Docker Desktop bind behavior.
- R3 added ENOTEMPTY/EEXIST fallback, real bind cycles, retained active snapshot, fatal failure/stop state and recovery retry. Later actual B3 rejections restored source.

### Public-contract audit, not private patch injection

- Supported B2 changes retried missing ambiguous submits with stable operation ID and forgot completed tasks after exhausted reporting.
- R2 also converted UNKNOWN status to absence when stopping, enabling durable bookkeeping deletion after accepted submit/lost reply/abort/lost status. Static permitted-fault control flow violated ambiguity/cleanup obligations; not a newly observed official capacity leak.
- Worker watermark remained acknowledged, not last-sent; coordinator `max(seen, reply)` did not implement documented reply-as-is reconciliation.
- Refreshing strictly older heartbeat arrivals exceeded the not-older guarantee. Passing finite tests did not prove safety.
- Findings motivated generic review/probes, never embedded case-specific repairs.

## R3: safe restoration without improved repair score

- **B2:** 0/3, 615.874 s/$4.321680; zero edits, 80 rounds/five compactions. All public seeds still failed; partial status was honest.
- Final review truncated; 138-character introductory prose was mistakenly treated as a completed audit.
- **B3:** 1/2, 834.797 s/$4.432996; one clock repair, six safe rejections; final edit denied for reserve. Only accepted removal remained installed.
- Completed reviewer misread source: `fresh=False` did not trigger re-registration; `info is None` did. It also overextended the not-older heartbeat contract.
- Neither B case authored a probe. Available tools are not measured coverage.
- Compaction lost direct rejected-artifact citations; accepted-source evidence was briefly confused with rejected-candidate evidence before rediscovery.

## R4: bounded corrections and partial improvement

- Explicit synthesis completion, one tool-free truncation recovery, rejected trace/summary citations, early review after 12 read-only rounds, audited stop before redundant restart.
- Source `ac409bf`; image `sha256:0c590ba5b53715f361871365a8213ec2a6689eb31a7a57e35c5905f61dda1ba4`; ten context files matched. Tests included real bind recovery/nine amendment cases.

| Case | Credit / seed outcomes | Time / spend | Gates |
| --- | --- | --- | --- |
| A1 | 1/1; 20/20 | 538.803 s / $2.695635 | Public/regression pass, clean exit |
| B2 | 2/3; 20/20, 0/20, 20/20 | 695.563 s / $3.397598 | 29 public + 40 regressions pass |
| B3 | 1/2; 0/20, 20/20 | 746.550 s / $4.526352 | 29 public + 39 regressions pass; one original failure |
| A2, interrupted | 2/2; 20/20 each | 146.047 s / $1.168160 | Gates pass; separate SIGTERM snapshot |

- Completed cases exited zero/no timeout/infra. A2's existing grader finished after user-requested SIGTERM; normal final validation/review did not complete. It is not an uninterrupted controller run.
- B2: three retained candidates, 51 rounds/no restart/three compactions; eleven public-template seeds passed, but official bug-2 failed every seed.
- B3: one retained/four safely rejected candidates, 80 rounds/one restart/five compactions; registration expectation remained, accurately reported partial.
- Truncated B2 specialist synthesis completed on its single retry. Both early review handoffs preserved repairs; both reviews genuinely concluded; B2 avoided redundant audit restart.
- B3 read eight rejected-candidate trace paths 57 times, including after compaction: retained provenance was actually used.
- Neither B run authored a scenario. A1 did after correcting an unsupported inline-fault request; replay success alone does not prove intended transition coverage.
- V1 same-case A1/B2/B3 was 3/6; partial improvement cannot establish full-candidate superiority.

## Remaining risks and disposition

- B2 still misses last-sent/reply-as-is reconciliation, refreshes older heartbeats and omits documented missing-submit retry backoff. R4 avoids R2's unsafe UNKNOWN-to-None shortcut.
- B3 reviewer wrongly blamed timestamp-field removal for stale-epoch re-registration; epoch checking preceded that filter. Completed synthesis is not sound causal proof.
- No complete V2 suite, exhaustive interleaving coverage, broad goodput proof or unseen-service guarantee.
- Fixed reliability findings: lost discovered guards on rollback; missing mandatory coverage masked by extras; SIGTERM restore gap; invalid probes becoming guards; bind portability; misleading review-completion state.
- Preserve V1 9/12. Future work should improve distinguishing evidence/routing, never waive guards or encode practice recipes.
