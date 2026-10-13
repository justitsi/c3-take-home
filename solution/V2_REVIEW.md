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
| Preserve known good behavior | A later patch improves the initial seeds but breaks an ad hoc passing seed or alternate scenario/fault; reject and restore exact prior source | Passed in 149-test offline suite |
| Keep identities distinct | Same seed under different scenario/fault configurations remains separate evidence; rechecking one cannot overwrite the other | Passed, including invalid-probe isolation |
| Handle prerequisite repairs | Reject a new invariant, retain earlier repair, then allow a coherent combined retry to repair both without suppressing checks | Passed in 149-test offline suite |
| Final coverage | Exercise every configured public seed automatically; incomplete execution must not be reported as complete or clean | Passed, including rollback guard preservation |
| Adaptive continuation | Continue past the v1 round ceiling when useful and affordable; stop or restart repeated no-progress attempts | Passed in 149-test offline suite |
| Fresh diagnosis | Reset model context from concise evidence without dropping source checkpoints, observed failures, or passing guards | Passed in 149-test offline suite |
| Preserve shutdown allowance | Stop model/edit activity before final-validation reserve; deadline, cancellation, and budget exhaustion retain valid source | Passed, including atomic/fallback recovery and real SIGTERM during final rollback |
| Handle incomplete model replies | Truncated/filtered/malformed replies cannot execute a partial mutation; budget reservations settle and recovery/stop is explicit | Passed in 149-test offline suite |
| Structured observability | Actor/tool/candidate/check identities, outcomes, timings, and source revision are correlated; logs are bounded and omit secrets | Passed in 149-test offline suite |
| Inspect generated evidence safely | Read/search generated trace and summary through contained bounded tools; reject traversal, symlink escapes, and artifact edits | Passed in 149-test offline suite |
| Maintain runtime contracts | Only permitted model, no arbitrary shell tool, no practice-specific fixes, source-only mutation, deterministic service behavior | Offline tests and source audit; exact final image still requires grading |
| Measure actual improvement | Frozen image, all six official cases, 20 seeds per bug, regression gates, cost/runtime, clean infrastructure, comparison against v1 | V2 official results pending; no improvement claim yet |

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

These tests use generic fixtures and mocked model HTTP; they do not encode
practice-case fixes. The lead's latest serialized offline Docker run reported
**149 passed in 30.58 seconds**, session `27943`, exit 0. It includes the new
invalid-probe, atomic exchange, forced-fallback recovery, and actual SIGTERM
interleaving tests. The earlier 135-test run is superseded for current source.
This review starts no workloads itself.

The fresh image build completed successfully in session `22941`:
`c3-fixer-prototype:v2-r1`, index
`sha256:9e3f69116902207ff4bc54b10a73ee6026fd788feac280b8643b33aad6abd1b7`.
The lead will finish source/image byte checks and commit the frozen checkpoint.
Official v2 grading remains pending. A two-case pilot alone cannot establish
improvement over the fully evaluated 9/12 v1 baseline or satisfy promotion.

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
