# V2 implementation and verification

- Branch: `solution/prototype-v2`, based on finalized V1 `96e06b2`. Do not merge or push V2 without a new user request.
- Preserve V1 images, scores, source and chat artifacts. New repository files, run outputs and handoff artifacts belong under `solution/`.
- Baseline: V1 **9/12**, $5.850678, 991.65 seconds. Target: **12/12 supplied bugs**, no baseline-passing regressions, all 20 hidden practice seeds per credited bug. Unseen-case perfection is unproven, not a permissible claim.
- Authoritative limits: repository README/RULES; 900 seconds per case, $3 **per bug**, 2 CPUs/4 GB per fixer. Keep the actual approximately 2 GB Docker VM unchanged. Latest user amendment: separate evaluation sessions per case, initially two and now **at most three sessions** after measured usage remained around 400 MiB. One case/one grading worker per session; monitor memory before increasing load.

## Architecture guidance: adopted and adapted

- Adopt failure-driven evidence, bounded trace inspection, explicit check provenance, counterexample-guided repair, fresh diagnosis and automatic final validation.
  - Pros: addresses V1's observed workflow failures; makes completion verifiable.
  - Cons: more check bookkeeping and validation time; test rollback/identity boundaries independently.
- Retain three parallel read-only investigators and one serial editor; do not add debates or parallel edits.
  - Pros: preserves proven V1 discovery diversity and safe source ownership.
  - Cons: duplicated context/spend; keep shared caps and measure cost/cache rates.
- Replace the 14-round editor limit with time/budget-aware continuation, a high emergency ceiling, bounded stagnation and fresh-context diagnosis.
  - Pros: uses remaining allowance for supported unresolved bugs.
  - Cons: runaway loops/context growth; bound rounds, retries, output and final reserve.
- Preserve passing `(seed, scenario, faults)` checks and invariant-category guards; allow supported partial fixes and coherent prerequisite repair.
  - Pros: prevents "improve one seed, break another" acceptance.
  - Cons: broader checks cost time; record incomplete coverage honestly and rollback rather than silently drop guards.
- Defer embeddings, Jev routing, large frameworks, automatic unrestricted scenario synthesis and full research-benchmark ablations until measured evidence justifies them.
  - Pros: concentrates effort on observed gaps.
  - Cons: these capabilities may help unseen cases; record them as limitations rather than claim universal effectiveness.
- The supplied architecture document remains unchanged. Its single-agent recommendation and numerical assumptions are suggestions, not overrides of measured evidence or the local rules.
- R3 adds bounded, immutable scenarios derived from supplied templates and a fresh read-only contract review before the final repair phase.
  - Pros: targets symptoms that aggregate public seeds can miss; checks sender/receiver and unintended changes independently.
  - Cons: model-generated probes are not trusted oracles; limit schema/classes/resources, retain all guards, reserve review/repair time, and use official scoring as the outcome evidence.
- User-requested per-case sessions replace the earlier serial-only evaluation schedule.
  - Pros: reduces wall-clock time and isolates logs/process handles.
  - Cons: the unchanged VM is small; cap at three concurrent sessions after live memory checks, one evaluation worker each, and inspect actual memory/process state.

## Ownership and milestones

- Lead: orchestration, budgets, validation integration, status, branch and frozen-image selection.
- Tools agent: bounded artifact namespace/trace inspection and focused tests.
- Independent validation agent: adversarial policy/model tests, safety review, final per-seed evaluation audit and gap report.
- Packaging agent: solution-local outputs/cache, image/runner checks, documentation/handoff review.
- One owner per file; source edits and actual Docker case workloads are serialized. No changes to supplied cases, simulator, tests or grader.

1. **M0: scope verified** — architecture read fully; local rules and V1 failures inspected; new branch created.
2. **M1: feedback loop repaired** — artifact access; adaptive editor; scenario-aware guards; final validation; model response safety and bounded tool logs. Gate: offline adversarial tests pass in Docker.
3. **M2: targeted pilots** — frozen `v2-r1` image on B2/B3, serially; inspect actual missing-bug seeds, regressions, cost and stop reasons. Change generic capabilities only, never insert practice fixes.
4. **M3: full coverage** — all six cases on one exact frozen image, plus independent deterministic/seed/gate audit. If not 12/12, classify gaps, implement one evidence-backed change, rebuild under a new tag and repeat relevant/full checks.
5. **M4: handoff** — branch commits, source/image identity, solution-local image export/build chats, README/write-up, V1 comparison, demonstrated bug classes and residual gaps. No all-unseen-bugs claim.

## Verification scope

- Containment: workspace/corpus/artifact roots, traversal, symlinks, oversized/malformed traces, cancellation, bounded output.
- Repair policy: all declared public seeds; ad hoc scenario/fault identity; previous passes; new invariants; incomplete checks/determinism; failed transactions; prerequisite fixes; final-sweep rollback.
- Model/control: malformed/truncated replies; permanent/transient errors; shared spend; context restart; useful continuation beyond 14 rounds; stagnation; deadline/SIGTERM during tools and HTTP.
- Empirical: all supplied bug types and targeted hidden-seed scenarios, public/private baseline-relative gates, repeated trace hashes; additional seed/fault checks when useful. Practice outcomes do not prove unseen correctness.
