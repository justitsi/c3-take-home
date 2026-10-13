# Prototype v1 final checkpoint

- Branch: `solution/prototype-v1`; comparison target: `main` at `2b9066c`.
- Main contains no submitted fixer. The provided no-op image is the measured comparison baseline: **0/12 bugs across all six cases**, public/regression gates passed. The first parallel baseline encountered an infrastructure OOM on B2; a successful serial, single-worker retry completed the evidence.
- Current milestone: **v1 finalized at the user's request**; no further paid sweep or v2 implementation started.
- M0 complete: real Docker proxy/key plumbing verified, branch created, agent ownership assigned. Credentials remain ignored and are not included in images.
- M1 complete: three specialists genuinely overlap; checked edits, rollback, shared spending, deadline and SIGTERM behavior have Docker-backed tests. Final safety suite: **45 passed in 22.72 seconds**, Python 3.12 in Docker, networking disabled. The descendant-process cleanup race is fixed; failed edit transactions restore the checkpoint, and candidates require complete seed checks and a successful determinism repeat.
- M2 pilot: immutable `c3-fixer-prototype:v1` fixed **2/2 bugs** (A1 and B1), each verified by the official grader on all 20 hidden practice seeds, with public/private regression gates passing. Spend: **$1.649673**. Raw evidence: `results/prototype-v1-pilot/`.
- Final image: `c3-fixer-prototype:v1-final`, `linux/amd64`; manifest/index identity `sha256:38219577c596f30f84ebdc58bf1ec8b27f941545a61a86fcd78e2b6b94f3c6b3`. It contains safety changes after the paid pilot and **has not had paid reevaluation**. Do not attribute the pilot's score to this final image.
- Evidence summaries: [main baseline](benchmarks/main-baseline.json), [v1 pilot](benchmarks/v1-pilot.json), and [final image/test checkpoint](benchmarks/v1-final.json). Raw official results remain under ignored `results/` directories.
- Promotion: **not performed**. The six-case, same-frozen-candidate comparison gate is incomplete; `main` remains at `2b9066c`. The implementation is saved on `solution/prototype-v1`.
- Runtime design amendment: three parallel read-only Sonnet specialists, one serial repair editor, shared model budget, validated source checkpoints, deadline/SIGTERM cleanup.
- Development agents: lead owns orchestration/model/status; tools agent owns tools/retrieval; reliability agent owns validation; packaging agent owns images/runner/docs.
- Docker VM remains at its current approximately 2 GB allocation. All subsequent practice cases run serially with `--concurrency 1 --eval-workers 1`; model investigators within a case remain parallel.
- Promotion rule: commit candidate to its branch; merge into main only if the same six-case Docker evaluation fixes strictly more bugs than the measured main baseline, without infrastructure failures.

## Inputs for the next planning session

- Four practice cases remain unmeasured on any prototype: A2, A3, B2 and B3. No evidence yet supports an all-bugs claim.
- Evaluate the exact frozen candidate serially across all six cases before promotion; diagnose each remaining per-bug failure rather than infer success from public unit tests.
- Public validation currently gates candidates on the first two seeds and repeats the first for determinism. The editor can request more seeds, but those ad hoc passing checks are not yet retained as regression guards. Automatic final full-public-seed coverage is also not implemented.
- Model failures stop the affected agent without blind retries; large/malformed provider responses and fault-specific scenario generation remain areas for later hardening.
- Preserve the approximately 2 GB Docker VM, serial case evaluation, shared model budget, and parallel read-only investigators.
- [PLAN.md](PLAN.md) is left available for the user's version-two amendment; this closeout does not silently replace it with a new plan.
