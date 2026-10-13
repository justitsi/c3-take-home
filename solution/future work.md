# Future work — wrap-up checkpoint

- **Selected version:** preserved V1 final, **9/12 across all six practice cases**. Local tag `c3-fixer-prototype:best-verified` points to the exact verified `v1-final` image. See [selection manifest](benchmarks/selected-version.json).
- **Reason:** V2 has useful reliability improvements and promising partial results, but no complete six-case evaluation establishes that it beats V1. Do not substitute the experimental `solution/fixer/` tree for the selected V1 source.
- **Stop boundary:** user requested wrap-up on 2026-10-13. No further cases, paid repair iterations, or architecture changes will start. A2 received SIGTERM; its already-running grader completed, but an interrupted snapshot is not an uninterrupted R4 evaluation. A3/B1 were not started. All task-related Docker containers have exited. No merge, push or external submission performed.
- **Honesty:** 100% effectiveness is not demonstrated. Even 12/12 practice bugs would not establish correctness on unseen codebases.

## Evidence preserved

- V1: [complete scorecard](benchmarks/v1-final-evaluation.json), **9/12**, **$5.850678**, **991.650 s** summed fixer runtime. All credited bugs passed 20/20 targeted seeds; all 240 repeated trace pairs were independently audited. Public/baseline-relative regression gates passed; no timeout or infrastructure failure.
- V2-r1: B2/B3 **1/5**; worse than V1 on that subset.
- V2-r2: B2/B3 **2/5**, but B3 rollback failure/new regressions make it nonpromotable.
- V2-r3: A1/B2/B3 **2/6**; incomplete suite, not an improvement.
- Frozen V2-r4: source `ac409bf`, image `sha256:0c590ba5b53715f361871365a8213ec2a6689eb31a7a57e35c5905f61dda1ba4`; **287 offline tests passed**, including real bind-mount rollback. This certifies tested controller behavior, not repair success.
- Uninterrupted R4 A1/B2/B3: **4/6**, **$10.619585**, **1,980.916 s**; [partial scorecard](benchmarks/v2-r4-partial.json). V1 scored 3/6 on these same cases. R4's other cases remain uncertified; never combine revisions to claim a full score.
- Interrupted R4 A2 snapshot: **2/2**, both 20/20, public/regression gates passing, **$1.168160**, **146.047 s**; [separate evidence](benchmarks/v2-r4-interrupted-A2.json). SIGTERM prevented normal automatic final validation/review completion; this does not establish the behavior of an uninterrupted controller run. Total actual R4 practice spend, including that snapshot, is **$11.787745**; not an account-balance claim.
- Source, logs, rejected candidates, scorecards, image tar and redacted build-chat snapshots remain preserved under `solution/`; original V1 artifacts are untouched. Latest chat export has an explicit cutoff and does not claim to include later bookkeeping.

## P0 — complete before considering a replacement for V1

- **Finish an exact-image, uninterrupted six-case evaluation after renewed authorization.** Reuse the frozen R4 image for comparability; rerun interrupted A2 from a fresh workspace, run A3/B1, and decide whether fresh all-six replication is warranted. Do not relaunch completed cases merely because a wrapper is quiet.
  - Pros: answers whether measured subset improvement generalizes. Cons: requires additional time/model spend; results can vary.
  - Owner: lead schedules; independent validation/evidence agents audit. Keep unchanged ~2 GB Docker VM, at most three active case sessions, one evaluation worker each, and monitor memory.
  - Gate: complete case coverage; coherent bug IDs/counts; every credited bug 20/20; public/regression gates, determinism and clean exits; exact source/image identity. Compare against V1 **9/12**, not no-op. An improvement does not authorize merge/push/submission.

- **Resolve remaining supplied bug mechanisms generically, not with practice-specific patches.**
  - Selected V1 still misses B2 forbidden-cancellation/reconciliation behavior, B2 ambiguous-submit liveness, and B3 registration amplification.
  - R4 repairs B2 bug-1/bug-3 but still fails bug-2 on all 20 seeds despite clean public checks. Public contract review identified remaining sent-versus-acknowledged watermark/authority concerns, older-heartbeat handling and retry-backoff obligations. These are diagnosis evidence, not a private answer to embed in the harness.
  - R4 retains B3's clock fix but fails registration-count bug-1 on all 20 seeds. Four later candidates were safely rejected. Its completed reviewer also made an unsupported stale-epoch inference: completion is not correctness.
  - Pros: directs effort at observed failures. Cons: the harness must generalize to unfamiliar services; hard-coded case recipes would invalidate the approach.
  - Gate: source/contract-backed causal explanation, discriminating replay, minimal autonomous patch, then official targeted-seed and regression proof.

- **Reduce cost and ineffective investigation.** R4 A1 took 538.803 s/$2.695635 versus V1's 240.468 s/$1.019304. More rounds/agents are not automatically better.
  - Measure repeated reads, ledger closure, rejected edits, phase cost and useful new observations. Distinguish context compaction from fresh diagnosis; preserve the best validated source.
  - Pros: protects time for repair/validation. Cons: premature stopping can miss dependent fixes.
  - Gate: better repaired-bug score first; lower time/cost second; no weakened coverage or shutdown reserve.

## P1 — V3 strategy increments, planning only

Detailed agent ownership, dependencies, pros/cons, timeboxes and milestones are in [V3_IMPLEMENTATION_PLAN.md](V3_IMPLEMENTATION_PLAN.md). Preserve the supplied [V3 proposal](v3_architecture.md).

1. **Competing hypotheses:** bounded 2–3 alternatives only for ambiguous causes; contract/source citations, distinct predicted observations, cheapest distinguishing query/replay. Skip obvious causes; track contradicted/inconclusive predictions explicitly.
2. **Failure-aware routing:** separate syntax/import errors, persistent reproducer, regression/new invariant, distinct interleaving and exhausted allowance. Staged checks may reject early but must never retain a partially checked candidate as verified.
3. **Mechanism-diverse testing:** separate known failures, protected passes and bounded exploration; use supported fault profiles/immutable derived probes. New seeds alone do not demonstrate new failure mechanisms.
4. **Failure signatures and counterexample minimization:** normalize incidental IDs/times without merging distinct causes; retain scenario/fault/seed/revision provenance and all passing guards. Minimize only when replayed behavior remains equivalent.
5. **Measured allocation:** derive phase time/spend and marginal information first; trial one adaptive policy within shared reservations and final-validation floor.
6. **Progressive retrieval:** exact identifiers, bounded caller/callee/state-write neighborhoods, adjacent current contracts; refresh on hypothesis changes. Trial lazy selective FTS5 only after a measured lexical gap. Defer vectors, full-corpus startup indexing, orchestration frameworks and custom model checking.

- Pros: diagnosis becomes falsifiable and test effort targets mechanisms. Cons: schemas, extra prompts and scheduling can increase overhead or encode bad assumptions.
- Implementation order: agree small interfaces; one controller owner; tools and validation agents work in parallel on isolated modules/fixtures; independently review each increment; freeze and measure before adding another.
- Milestones: proposal mapping → one bounded implementation → adversarial offline tests → exact-image pilot → complete comparable six-case run → honest selection/artifact handoff. Preserve the last verified version at each boundary.

## P1 — remaining reliability and verification work

- **Prove intended probe events occurred.** R4 A1 authored/replayed a restart probe successfully; a passing probe alone does not prove the desired crash/order boundary happened. Assert observed transitions and record inconclusive probes.
- **Broaden exploration safely.** Systematic bounded fault/workload combinations, ambiguity/loss, reordered messages, stale incarnations, cancellation/cleanup and liveness—only where the supplied schema supports them. Unsupported controls must remain explicit.
- **Strengthen review quality.** Bounded synthesis recovery/incomplete status now have tests and live evidence; independently test source-supported findings and false theories. Reject unsupported extra edits, not just malformed output.
- **Complete rejected-candidate provenance.** R4 preserves artifact citations and actually used them after compaction; retain the exact rejected diff/check context as well, with immutable revision labels and bounded storage.
- **Extend adversarial interfaces as code evolves.** Budget/deadline races, malformed/truncated replies, probe identity/containment, deterministic repeats, real host-bind restoration and persistent rollback failure must remain tested. Offline fixtures cannot substitute for paid end-to-end evidence.
- **Evaluate optional Jev only if justified.** It remains deferred; require a measurable cost/quality advantage and keep permitted proxy routes/model limits. No new dependency without a clear benefit.

## P2 — final packaging and decision work not yet authorized/completed

- Complete missing R4 evidence and full comparison; no claim that R4 is submission-ready or better overall.
- If a candidate truly wins, freeze its source/image, independently audit all 240 repeated trace pairs and regression details, export/hash image and chats, refresh concise write-up/selection manifest, and obtain explicit authorization before changing main or submitting.
- Latest R4 chat snapshot stops at **2026-10-13 22:02:36 UTC**; refresh it if later discussion needs inclusion. Existing exports remain intact.
- Keep reproducibility metadata: exact image/source, source-only patch hashes, per-seed outcomes, gates, actual proxy spend, stop/interruption reasons and export cutoff. Do not conceal failed pilots or pool best per-case scores from different images.

## Safe restart instructions

- Start by reading this file, `STATUS.md`, the selection manifest, and V2/V3 review documents; verify live state before repeating commands.
- Current work branch is `solution/prototype-v2`; main remains finalized V1 `96e06b2`. Current `solution/fixer/` is experimental R4. Selected V1 source is separately archived at `solution/results/selected-v1-source.tar`; selected image is `c3-fixer-prototype:best-verified`/`v1-final`.
- Ask for additional evaluation time/spend and desired scope. Preserve `.env` confidentiality, supplied grader/tests/simulator/corpus, user edits and all frozen tags. Keep every new repository artifact under `solution/`.
