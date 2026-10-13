# Prototype V2 write-up

This Python/Docker fixer uses three parallel read-only Sonnet 4.6 specialists
and one serial editor. It ingests incident evidence and current contracts,
reproduces failures, proposes small source-only repairs, and validates them
with public tests and deterministic simulator checks. Fresh containers share
no case state; all dependencies are installed at build time.

V2 adds bounded read-only artifact inspection, including same-record AND trace
filters and resumable pages. Cited observations and a per-symptom issue ledger
survive context compaction. A separate fresh diagnosis removes unsupported
hypotheses while retaining evidence and checked repairs. Investigator calls
are capped at six, with a tool-free final summary. The editor continues within
time/spend limits, with an 80-round emergency ceiling replacing V1's 14 rounds.
Scenario/fault-aware guards preserve passing checks, reject new invariants,
and require complete validation and deterministic repeats. Automatic final
validation can restore a prior checkpoint. Ledger claims never certify hidden
bugs.

Shared model reservations, bounded excerpts/output, cached prompt prefixes,
and a shutdown reserve control cost and time. Signal handling and bounded
cleanup protect source at the grader's deadline. Local case/evaluation
concurrency remains one within the unchanged approximately 2 GB Docker VM;
model investigation stays parallel. New outputs and handoff artifacts remain
under `solution/`. V2 stays on `solution/prototype-v2`; no merge or push is
authorized.

Evidence is mixed and must remain scoped. Preserved V1 fixed **9/12** on all
six cases for **$5.850678**. V2-r1's B2/B3 pilot fell to **1/5**, versus V1's
**2/5** on those cases. Current `v2-r2` source `11aae52` matches its frozen
image and passed **226 offline Docker tests in 30.92 seconds**, but its live
B2/B3 repair pilot is **pending**. Tests establish controller behavior, not
improved repair effectiveness. Next, inspect that pilot and complete one
frozen-image six-case comparison with per-seed/regression review before
selecting another iteration. Unseen-codebase performance remains unknown.
