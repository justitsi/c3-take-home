# Prototype V2 write-up

This Python/Docker fixer uses three parallel read-only Sonnet 4.6 specialists
and one serial editor. It retrieves incident/code/contract evidence, reproduces
failures, and validates source-only repairs with public tests and deterministic
simulation. Fresh cases share no state; dependencies are installed at build time.

Bounded trace inspection supports same-record AND filters and paging. Cited
observations and an issue ledger survive compaction; independent diagnosis
drops hypotheses while retaining evidence. Investigators have at most six
calls, ending tool-free. R3 adds immutable hashed derived scenarios, trusted
`source_diff`, and independent read-only contract review. Up to 55 initial
editor rounds leave review/follow-up allowance within 80 total rounds.
Scenario-aware guards preserve passes, reject new invariants, and require
complete checks and deterministic repeats. Final validation can restore unsafe
candidates. R3 adds real bind-mount rollback fallback and explicit fatal
restoration status. Model claims do not certify hidden bugs.

Shared budgets, cached excerpts, shutdown reserves and bounded signal cleanup
control cost/time. The latest schedule permits three active case sessions, one
case/evaluation worker each, on the unchanged 1,973 MiB/4-CPU Docker VM. New
artifacts stay under `solution/`; V2 stays on its branch without merge/push.

Preserved V1 fixed **9/12** across six cases for **$5.850678**. R1's B2/B3
pilot scored **1/5**, versus V1's **2/5** there. R2 scored **2/5**, but B3's
rollback failure, exit 1 and new regressions make it nonpromotable. Frozen R3
source `2096b49` passed **278 offline tests in 30.87 seconds**, including real
bind recovery; its live B2/B3 repair results remain **pending**. Controller
tests do not establish repair effectiveness. Complete the six-case frozen-image
comparison and seed/regression audit next. Unseen-codebase performance is unknown.
