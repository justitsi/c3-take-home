# Prototype V2 write-up

**Selected deliverable: preserved `c3-fixer-prototype:v1-final`, 9/12 across
all six cases for $5.850678**, also tagged `c3-fixer-prototype:best-verified`.
The user ended work before R4's full evaluation;
the following describes the experimental V2 branch, not a promoted replacement.

This Python/Docker fixer uses three parallel read-only Sonnet 4.6 specialists
and one serial editor. It retrieves incident/code/contract evidence, reproduces
failures, and validates source-only repairs with public tests and deterministic
simulation. Fresh cases share no state; dependencies are installed at build time.

Bounded trace inspection supports same-record AND filters and paging. Cited
observations and an issue ledger survive compaction; independent diagnosis
drops hypotheses while retaining evidence. Investigators have at most seven
attempts, with at most five tool-enabled. R3 adds immutable hashed derived scenarios, trusted
`source_diff`, and independent read-only contract review. Up to 55 initial
editor rounds leave review/follow-up allowance within 80 total rounds.
Scenario-aware guards preserve passes, reject new invariants, and require
complete checks and deterministic repeats. Final validation can restore unsafe
candidates. R3 adds real bind-mount rollback fallback and explicit fatal
restoration status. Model claims do not certify hidden bugs.

R4 adds bounded truncation recovery/completion state, retained rejection
counterexample citations, early independent review after 12 candidate-free
read-only rounds, and audited completion before a fresh restart. Major V3
architecture changes remain planning only.

Shared budgets, cached excerpts, shutdown reserves and bounded signal cleanup
control cost/time. Evaluations used at most three active case sessions, one
case/evaluation worker each, on the unchanged 1,973 MiB/4-CPU Docker VM. New
artifacts stay under `solution/`; V2 stays on its branch without merge/push.

Preserved V1 fixed **9/12** across six cases for **$5.850678**. R1's B2/B3
pilot scored **1/5**, versus V1's **2/5** there. R2 scored **2/5**, but B3's
rollback failure, exit 1 and new regressions make it nonpromotable. R3 source
`2096b49` scored **2/6** on A1/B2/B3 for **$11.533084**, **1,928.95 s**; it was
not a complete six-case run. Frozen R4 source `ac409bf` passed **287 exact-image
offline tests in 31.00 seconds**, including real bind recovery. Its evaluation
was **partial/interrupted**: completed A1 1/1, B2 2/3 and B3 1/2 total **4/6**,
**$10.619585**, **1,980.916 s**, versus V1's 3/6 on those same cases. This is not
a full six-case improvement. A2 was SIGTERM-stopped and is separate interrupted
evidence; A3/B1 never launched. No further runs are queued. Controller
tests do not establish repair effectiveness; unseen-codebase performance is unknown.
