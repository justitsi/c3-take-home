# V2 independent reliability review

Owner: reliability/evaluation agent. Scope: adversarial tests and evidence review;
runtime implementation belongs to the lead and tools agents. No paid model calls,
Docker workloads, grading runs, or practice-case patches are made by this review.

## Authoritative constraints

- Follow the local assessment `README.md` and `RULES.md` when the supplied
  architecture note disagrees: 900 seconds per case, **$3 per bug**, 20 hidden
  seeds **per bug**, permitted runtime models, source-only grading, and exit
  before `C3_DEADLINE`.
- Preserve the user's parallel investigators, supervised development, Docker
  execution, serial evaluation within the existing approximately 2 GB Docker VM,
  and conditional branch promotion.
- Use the architecture note for failure-driven diagnosis, contract retrieval,
  counterexamples, validated checkpoints, independent diagnosis, bounded tools,
  final verification, and explicit provenance. Its research links and suggested
  allocations are guidance, not measured performance guarantees.
- Fresh diagnosis must preserve validated repairs and regression evidence. An
  independent original-source candidate may be explored separately; resetting
  the submitted source must not silently discard already verified repairs.

## V1 evidence that motivates this revision

- Frozen v1 fixed 9/12 practice bugs, with every credited bug passing 20/20 seeds.
  All baseline-relative public/regression gates passed; no final-suite timeout or
  infrastructure failure occurred. See `benchmarks/v1-final-evaluation.json`.
- B2 retained one repair but left two bug scenarios failing all 20 seeds: forbidden
  worker-to-GPU cancellation requests and unresolved/late jobs. B3 retained the
  clock fix while a registration-count scenario failed all 20 seeds.
- B2 stopped after 14 editor calls at 133 seconds and about $1 of its $9 allowance.
  Its last notes repeatedly requested trace inspection. Generated traces existed
  under scratch, while inspection tools accepted only workspace/corpus paths.
- B3 safely rejected a later candidate because seed 12 gained an unresolved-job
  invariant, although seed 11 passed. The editor round ceiling prevented a further
  dependency repair. This supports improving continuation, not weakening rollback.
- All 190 requests in the final v1 ledger succeeded. No editor reply reached its
  3,800-token limit. Four investigator replies reached 1,800 tokens, but finish
  reasons were not recorded. Truncation is a handling gap to test, **not a proven
  cause of the measured missed bugs**.

## Acceptance checklist and required evidence

| Requirement | Adversarial evidence required | Current review state |
| --- | --- | --- |
| Preserve known good behavior | A later patch improves the initial seeds but breaks an ad hoc passing seed or alternate scenario/fault; reject and restore exact prior source | Synthetic 226-test suite passed; real bind-mount rollback failure found in r2 B3, hardening pending |
| Keep identities distinct | Same seed under different scenario/fault configurations remains separate evidence; rechecking one cannot overwrite the other | Passed, including invalid-probe isolation |
| Handle prerequisite repairs | Reject a new invariant, retain earlier repair, then allow a coherent combined retry to repair both without suppressing checks | Passed in 226-test r2 offline suite |
| Final coverage | Exercise every configured public seed automatically; incomplete execution must not be reported as complete or clean | Passed, including rollback guard preservation |
| Adaptive continuation | Continue past the v1 round ceiling when useful and affordable; stop or restart repeated no-progress attempts | Passed in 226-test r2 offline suite |
| Fresh diagnosis | Reset model context from concise evidence without dropping source checkpoints, observed failures, or passing guards | Passed, including separate compaction, retained facts, and omitted unsupported hypotheses |
| Preserve shutdown allowance | Stop model/edit activity before final-validation reserve; deadline, cancellation, and budget exhaustion retain valid source | Synthetic atomic/fallback/SIGTERM cases passed; persistent restore failure on host bind mount needs new verification |
| Handle incomplete model replies | Truncated/filtered/malformed replies cannot execute a partial mutation; budget reservations settle and recovery/stop is explicit | Passed in 226-test r2 offline suite |
| Structured observability | Actor/tool/candidate/check identities, outcomes, timings, and source revision are correlated; logs are bounded and omit secrets | Passed in 226-test r2 offline suite |
| Inspect generated evidence safely | Read/search generated trace and summary through contained bounded tools; reject traversal, symlink escapes, and artifact edits | Passed, including same-record terms, pagination, and complete bounded metadata transport |
| Maintain runtime contracts | Only permitted model, no arbitrary shell tool, no practice-specific fixes, source-only mutation, deterministic service behavior | Generic runtime audit passed; generated B2 patch has public-contract risks detailed below |
| Measure actual improvement | Frozen image, all six official cases, 20 seeds per bug, regression gates, cost/runtime, clean infrastructure, comparison against v1 | R2 pilot 2/5 ties v1 on those cases; B3 regression gate and rollback failed. No promotion evidence |

## Review limits

- A synthetic test proves its stated controller contract, not unseen repair
  performance. The exact frozen Docker image still needs the official full suite.
- No v2 behavioral requirement is marked verified from intended code or green
  unrelated tests. Results will be added after the lead's serialized test runs.
- Runtime code must remain generic. V1 failure categories may guide controller
  capabilities and fixtures; private scenarios/patches are never runtime inputs.

## Independent tests authored

- `tests/test_v2_artifacts.py`: generated absolute paths and aliases, read-only
  artifacts, traversal/symlink/sibling-prefix containment, literal/time-filtered
  trace provenance, malformed and oversized records, bounded output, cancellation.
- `tests/test_v2_model.py`: truncated/filtered replies, finish metadata versus
  provider message schema, malformed response envelopes and tool batches, local
  limit enforcement, HTTP 402, conservative transport accounting.
- `tests/test_v2_guards.py`: all configured seeds, scenario/fault identity,
  persistent ad hoc passing checks, registry isolation, coherent prerequisite
  retry, preserved partial repairs, omitted guards, final coverage/rollback,
  deadline and cancellation, invalid-probe isolation versus genuine runtime
  failure retention.
- `tests/test_v2_iteration.py`: useful repair progress beyond 14 editor rounds,
  unsupported completion claims, independent context restart without source
  regression, stagnant loops, truncation recovery, final time reserve, exhausted
  budget, and unavailable proxy after a supported repair.
- `tests/test_v2_observability.py`: correlated actor/tool/call/timing/revision
  records, bounded redacted diagnostics, distinct outcome digests, and provider
  finish-reason evidence.
- `tests/test_v2_restore.py`: native atomic directory exchange, forced fallback
  recovery in the source-directory gap, installation/recovery failures, and
  actual SIGTERM while final rollback holds the edit lock.
- `tests/test_v2_memory.py` (verified in r2 offline suite): semantic rather than
  argument novelty, empty-result stagnation, factual memory versus unsupported
  hypotheses, compaction versus independent diagnosis, source-revision
  provenance, bounded/redacted issue claims, same-record term queries and
  pagination, enforced final investigator synthesis, and full trace metadata
  transport to the next model turn.
- `tests/test_v2_bind_restore.py` (new hardening, verification pending): native
  exchange errors 39/17, real Docker host-bind restore cycles, exact source
  scope, and persistent rollback failure retaining checkpoints and reporting
  an explicit fatal status rather than an accepted revision.

These tests use generic fixtures and mocked model HTTP; they do not encode
practice-case fixes. The lead's latest serialized offline Docker runs reported:

- Mounted r2 source with r1 dependencies: **226 passed in 31.56 seconds**,
  session `83239`, exit 0.
- Fresh exact `c3-fixer-prototype:v2-r2` image: **226 passed in 30.92 seconds**,
  session `49931`, exit 0.

Both include the independent r2 memory, investigator synthesis, and full trace
transport tests, plus the existing invalid-probe, atomic exchange, fallback
recovery, and real SIGTERM interleaving cases. They supersede the earlier
149-test r1 run (`27943`, 30.58 seconds) for current source. This review starts
no workloads itself.

The fresh r2 image build completed in session `35076`, exit 0, index
`sha256:13ef71ea43ffb4005fc0b7015bbe778c062c6b94e3e46d640d79009a3ae2c7ba`.
The lead verified amd64 architecture, 47,638,807 image bytes, and exact byte
matches for all nine build-context files. The official r2 two-case pilot is
reviewed below; passing offline reliability tests did not prevent its real
bind-mount rollback failure.

The fresh image build completed successfully in session `22941`:
`c3-fixer-prototype:v2-r1`, index
`sha256:9e3f69116902207ff4bc54b10a73ee6026fd788feac280b8643b33aad6abd1b7`.
The pilot used frozen source checkpoint `43b6c4c`. Its terminal evidence is
reviewed below. A two-case pilot alone cannot establish improvement over the
fully evaluated 9/12 v1 baseline or satisfy promotion. R2 changes and new memory
tests are separate from this frozen r1 image. Their offline verification has
passed as recorded above. Neither the r1 nor r2 pilot is a full-suite result.

## Frozen r1 official pilot: independent evidence audit

Evidence: `benchmarks/v2-r1-pilot.json` and
`results/v2-r1-pilot/{B2,B3}/{result.json,eval.json,patch.diff,fixer.log}`.
The lead's serialized grader session `15146` exited 0. This was intentionally
only B2/B3; the benchmark correctly reports `complete: false` and the four
omitted cases. It is **not** a 1/12 full-suite result.

| Case | Credited bugs | Bug-seed scores | Fixer wall time | Cost | Submitted patch |
| --- | --- | --- | --- | --- | --- |
| B2 | 0/3 | 0/20, 0/20, 0/20 | 418.027 s | $3.011534 | None |
| B3 | 1/2 | 0/20, 20/20 | 457.992 s | $3.049778 | `src/shardmr/membership.py` |
| Pilot | 1/5 | 20/100 credited seed outcomes | 876.019 s | $6.061312 | One retained repair |

- Independently grouped all 200 replay summaries by case/bug/seed: all **100
  bug-seed pairs** have exactly two runs and matching `trace_sha256`, with no
  replay error. This includes all 60 B2 pairs. The official grader annotates
  invariant results on the first run and uses the second as the determinism
  repeat; absence of an invariant field on a repeat is not a passing check.
- Every checked B3 bug-2 seed has an empty invariant list, matching its 20/20
  credit. Every other bug has checked failures on all 20 seeds. B2 failures
  include unresolved/late jobs and forbidden worker-to-GPU cancellation;
  B3 bug-1 fails the per-worker registration-count expectation.
- Each case passes all 29 public tests and its baseline-relative regression
  gate. B2 has 37 passing regressions and three pre-existing failures; B3 has
  39 passing and one pre-existing failure. No new baseline regression, grader
  infrastructure error, fixer timeout, or nonzero fixer exit was reported.
- B2 finishes at the 80-round safety ceiling after nine diagnosis restarts,
  **zero edit attempts**, and 172 successful tool results (103 file reads,
  55 trace inspections, 14 listings). Its empty patch is a pre-patch diagnosis
  failure, not evidence that regression guards rejected a useful repair.
- B3 retains one edit, then finishes at the same ceiling after 14 restarts.
  Its 166 successful tool results contain 68 file reads, 76 trace inspections,
  20 listings, one search, and one edit. No tool-result error was recorded.
  Restarts become approximately three rounds apart late in the run. The
  membership edit removes a cross-clock heartbeat-age rejection; no second
  candidate is attempted for the remaining symptom.
- Both controllers report complete final public coverage with remaining
  failures and status `partial-known-failures`. Public controller status does
  not certify hidden bug credit; the independent official scores above do.
- V1 scored 2/5 on these same two cases. R1's **1/5 is a measured setback**,
  despite its offline reliability tests. It must not replace v1 on this
  evidence. Raising the editor ceiling alone did not produce useful repairs.

## R2 hypotheses and verification boundary

- The r1 log combines context-size resets and stagnation under one restart
  reason. Source review confirms that the old restart discarded inspected
  facts except aggregate checks; this is consistent with repeated reading but
  does not prove the sole cause of missed repairs.
- Separate compaction from independent diagnosis: preserve bounded cited
  facts, current/historical revision labels, attempted-repair outcomes, and a
  per-symptom claim ledger. True independent diagnosis omits specialist and
  ledger hypotheses; the ledger cannot erase deterministic failures or guards.
- Count new nonempty semantic evidence as progress. Changed arguments, fresh
  artifact paths, timing noise, and zero-result queries are not new findings.
  Give a fresh diagnosis enough rounds to inspect a causal chain before
  restarting again.
- Preserve literal query semantics, add same-record AND terms and bounded
  line pagination, and transport the parser's complete bounded JSON response.
  Otherwise late `next_line` metadata can be lost by a smaller outer cap.
- Require the final investigator call to synthesize with tools disabled;
  asking for a conclusion in prose alone does not enforce an actual finding.
- Current-source read-only review confirms the r2 code implements these
  interfaces, including the sixth-call `tools=[]`, 20k read-tool transport for
  an 18k trace bound, refreshed same-key observation provenance, and explicit
  compaction/restart events. The new independent tests passed in both serialized
  226-test offline runs, including the exact fresh r2 image. The measured r2
  pilot below supports improved B2 behavior, but cannot isolate the causal
  contribution of an individual controller change and does not justify
  promotion after the B3 rollback failure.

## Frozen r2 official pilot: independent evidence audit

Frozen source `11aae52`; exact r2 image index recorded above. Evidence:
`results/v2-r2-pilot/{B2,B3}/{result.json,eval.json,patch.diff,fixer.log}`,
plus retained `.c3-fixer-report.json` files in
`results/.scratch/c3grade-B2-r1-s2s4n_br/workspace/` and
`results/.scratch/c3grade-B3-r1-nft6vsx1/workspace/`. These are read-only
observations of autonomous output, not human-injected practice patches.

| Case | Credited bugs | Raw bug-seed outcomes | Fixer wall time | Cost | Gates / execution |
| --- | --- | --- | --- | --- | --- |
| B2 | 2/3 | 20/20, 0/20, 20/20 | 618.410 s | $3.221326 | 29 public + 40 regression tests pass; exit 0 |
| B3 | 0/2 | 16/20, 20/20 | 199.562 s | $1.403646 | 29 public pass; three new regression failures; exit 1 |
| Pilot | 2/5 | Raw outcomes are not gated bug credit | 817.972 s | $4.624972 | Not promotable |

- Independently verified all **100 bug-seed pairs**: exactly two replay
  summaries each, valid non-null 64-hex hashes, matching hashes within every
  pair, and no replay error. B2's 60 checked first runs contain 40 clean
  results, all bug-1/bug-3; B3's 40 contain 36 clean results. B3 bug-2's 20/20
  raw scenario result earns **no credit** because its baseline-relative
  regression gate fails. This must not be relabelled 3/5.
- B2 improves from v1's 1/3 and r1's 0/3 to 2/3. Its remaining official
  bug-2 scenario fails all 20 seeds on forbidden worker-to-GPU cancellation.
  No new regression, timeout, infrastructure error, or nonzero exit occurs.
- B2 retains four candidates, finishes after 61 editor rounds, four context
  compactions and zero diagnosis restarts, and stops with
  `public-and-additional-checks-passed`. All seven final public/probe seeds
  (1, 3, 5, 6, 7, 108, 218) pass at revision 4. Final coverage is complete,
  with no rollback; status is explicitly `public-verified`, not hidden-bug
  certification.
- The B2 final ledger has four `claimed-resolved` entries with citations and
  revision 4. The ticket-2 claim is nevertheless disproved by official
  evidence: aggregate clean public seeds did not verify that symptom's
  ordering contract. No alternative scenario or fault specification appears
  in the final check registry. The ledger is useful retained reasoning, not
  a certificate that every issue was repaired.
- B2 completes 121 tool results with no logged tool errors: 67 file reads,
  33 trace inspections, five listings, five searches, four edits, six ledger
  updates, and one validation. Trace inspection actually uses `all_terms`
  22 times and line pagination 20 times; 28 results are nonempty and five
  empty. The final two editor responses have stop finish reasons; the other
  59 use tools. No truncation event is logged.
- B3 aborts after 12 editor rounds, one recorded accepted candidate and a
  second unrecorded rejected candidate. `renameat2(RENAME_EXCHANGE)` returns
  `ENOTEMPTY` (39); both the normal rollback and exception-handler retry
  raise. The final report says `status: running`, `patches_accepted: 1`, and
  `final_validation: {}`. Actual source still contains the second candidate's
  heartbeat-sequence reset, so it is **not the recorded accepted checkpoint**.
  Zero diagnosis restarts/compactions occurred before this runtime failure.
- B3's official regression failures are new: fault profile crashes seed 8,
  soak seed 106, and soak seed 107. Its raw bug-1 failures include unresolved
  jobs. This is a confirmed rollback/controller defect and failed behavior
  gate, not a grader infrastructure failure; `infra_error` is null and no
  timeout occurred.
- R2's gated 2/5 ties v1's same-case 2/5 and improves on r1's 1/5, but the
  changed distribution and B3 failure prevent a promotion claim. Four cases
  remain unmeasured for this image. More paid repair evaluation must wait for
  portable, fail-closed checkpoint recovery verification.

### Generated B2 patch: public-contract audit

This review used only the actual diff, generated source and current public
service/platform documents. It did not run extra model, Docker or simulator
workloads and did not inject a case fix.

- **Supported changes:** retrying a missing ambiguous GPU submit with the
  same operation id follows `runbooks/unknown-submit-outcome.md` and GPU API
  v3 sections 3.2/4. Forgetting finished batch tasks after exhausted report
  attempts follows `runbooks/undelivered-reports.md`. These are distinct
  from the extra cancellation behavior below.
- **Confirmed unsafe source path, not an observed official capacity leak:**
  generated `gpu_client.py:43–49` returns `None` when a status reply times
  out and `should_stop()` is true. `submit()` passes that value to
  `executor.py:58–61`, which deletes the durable operation record and exits
  without releasing it. An accepted submit with lost reply, followed by
  abort and a lost status reply, therefore turns UNKNOWN into absence. GPU
  API v3 section 4 forbids dropping bookkeeping for an ambiguous outcome;
  section 3.4 requires release of every accepted operation. This is a
  concrete permitted-fault counterexample from static control flow, not a
  newly reproduced grader failure. The added early stop in `settled_absent`
  also bypasses the prior delayed recheck after `NOT_FOUND`.
- **Confirmed retained protocol gap:** `runbooks/lost-tasks.md` section 1
  requires `assign.hb_seq` to be the last heartbeat **sent**, acknowledged or
  not, and requires the coordinator to use that reply number as-is. The
  generated worker still updates `self.hb_seq` only after a reply
  (`worker.py:78–86`), while `assign` returns that acknowledged counter.
  Changing scheduler acknowledgement to `max(seen, reply)` does not implement
  the documented protocol. The official 0/20 bug-2 result confirms that the
  attempted repair does not resolve the measured symptom; source review
  identifies a public-contract gap without using a private reference patch.
- **Unsupported extra behavior, not a reproduced failure:** the membership
  edit refreshes the silence timer even for strictly older sequence numbers.
  `operational-notes.md` section 9 guarantees refresh for not-older arrivals;
  it does not justify this broader change. Delayed old heartbeats can now
  postpone failure detection. The finite passing tests do not establish
  that this additional behavior is safe.

### Portable rollback hardening: pending evidence

- The native-temp offline suite did not reproduce Docker Desktop's actual
  host-bind filesystem behavior. The new independent tests inject exchange
  errors 39 and 17, and require a real bind-root restore smoke via
  `C3_TEST_BIND_ROOT`, preserving all unrelated files across three cycles.
- Persistent restoration failure must retain the active validated snapshot
  and prior revision/registries, stop further mutations, return a fatal
  rollback result, and report `rollback-failed` rather than `running` or
  `public-verified`. Finalization must retry recovery and raise explicitly
  if it still fails. Independent fixtures are written to this contract;
  the lead owns runtime changes and serialized verification. No hardening
  test result or new image repair score is claimed yet.

## Findings and dispositions

- **Final rollback dropped later-discovered guards:** confirmed from source;
  the lead now preserves the union of known scenario/fault specifications and
  passing guards while restoring revision-specific results. The independent
  rollback-guard fixture passed in the latest offline suite.
- **Mandatory public checks could be silently filled by the extra-check phase:**
  the existing incomplete-seed fixture caught this during the first integration
  run. The lead restricted extras to ad hoc specifications; the latest suite passed.
- **SIGTERM could exit during an unguarded final-restore rename gap:** confirmed
  from the restore/watchdog interleaving. The lead added restore locking,
  active-checkpoint tracking, native atomic exchange, and emergency source
  recovery. Native exchange, forced-fallback recovery, failed recovery, and actual
  SIGTERM while the restore owner is blocked all passed in the latest suite.
- **Invalid replay invocations could become permanent guards:** the lead added
  path/name validation and rejection of unregistered configuration-error results.
  Independent fixtures require genuine runtime failures to remain diagnostic
  evidence and previously passing guards to survive a later configuration error.
  These fixtures passed in the latest suite.
- **Reviewer fixture artifact-name collision:** four initial failures came from
  clearing the fixture's call log and reusing replay directory names. A monotonic
  artifact counter fixed the fixture without changing behavioral assertions.
