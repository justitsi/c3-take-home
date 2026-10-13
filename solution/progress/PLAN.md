# Assessment completion plan — condensed record

Original V1 development plan; not authorization to resume. Selected deliverable: [V1 source](../fixer/), V1 **9/12**. Actual status: [STATUS.md](STATUS.md). Deferred work: [future roadmap](../future-work-plan/README.md).

## Objective and constraints

- Build an autonomous fixer for unfamiliar distributed Python services; maximize repaired bugs, then minimize runtime.
- Development: AI agents under user supervision. Graded runtime: hands-off, fresh container, no cross-case state.
- Per case: 900 seconds, $3 model spend per bug, 2 CPUs/4 GB; actual environment settings control.
- Runtime models: Sonnet 4.6 and optional Jev through supplied proxy only. Never expose credentials.
- Only service `src/` edits count; preserve provided tests/scenarios/simulator/corpus/grader.
- Credit: each targeted bug scenario passes all 20 hidden seeds; prerequisite fixes may be required. New baseline-passing regression failures can zero the case. Replays must be deterministic.
- Deliver: amd64 image ≤4 GB, matching source/Dockerfile, public build chats and short write-up. No-argument entry point; Python ≥3.12, PyYAML/pytest installed at build time.
- Local VM stays ~2 GB. Original serial schedule was later amended to at most three measured separate sessions, one evaluation worker each. No runs remain active.

## Ownership and supervision

| Owner | Scope | Handoff |
| --- | --- | --- |
| Lead | Controller/model/interfaces, integration, priorities, version choice | Integrated behavior, checks, remaining risks |
| Tools/retrieval | Bounded inspection/edit tools, current-contract discovery | Evidence paths, fixtures, limits |
| Validation | Baselines, checkpoints, rollback, guards, deadlines | Independent failure-path review |
| Packaging | Docker/runner, official evidence, artifacts/docs | Source/image hashes, scores, reproduction |

- Agree schemas before parallel coding; one owner per shared file. Serialize integration/source mutation.
- Handoffs identify files, behavior, checks/artifacts, failures and next experiment. Lead inspects actual evidence.
- User reviews architecture, working repairs, freeze and handoff. Ask about material scope/spend/submission choices, not every routine edit.
- Pros: concurrent implementation and independent review. Cons: interface conflicts, duplicate work, coordination cost.

## Decisions and trade-offs

- **Three read-only investigators, one editor:** recovery, leases/membership and delivery/commit evidence feeds coherent serialized patches.
  - Pros: parallel perspectives, clear checkpoint ownership. Cons: repeated context and budget pressure.
- **Small Python controller, standard-library HTTP.**
  - Pros: few dependencies, explicit proxy/timeouts. Cons: custom parsing/accounting/recovery.
- **Selective lexical retrieval:** index → identifiers/RPCs/invariants → adjacent current contracts.
  - Pros: cheap cited context without loading ~26M tokens. Cons: missed paraphrases/dependencies.
- **Minimal patches and validated checkpoints.**
  - Pros: protects earlier repairs/passes. Cons: check cost; dependent bugs may require combined transactions.
- **Progressive checks, then exact-image grading.**
  - Pros: cheap rejection before paid evaluation. Cons: public seeds cannot prove hidden correctness.
- **Early freeze, preserve prior candidate.**
  - Pros: protects evaluation/artifact time. Cons: fewer tuning attempts; newest is not necessarily best.

## Iteration protocol

1. Choose one observed gap; record hypothesis and measurable success criterion.
2. Delegate isolated implementation/independent fixtures with explicit interfaces.
3. Integrate sequentially; inspect diffs and focused checks.
4. Measure behavior, repaired bugs, actual time/spend; change one major strategy at a time.
5. Independently review patching/budget/checkpoint risks.
6. Retain supported improvements; otherwise restore/narrow and record next experiment.

- Stop repeated identical failures without changed evidence. Freeze when only verification/packaging time remains.
- Missing credentials/Docker, exhausted credit or material scope choices require user direction.
- Pros: failures become actionable. Cons: grading repeats cost time/money; use offline fixtures first.

## Original three-hour milestone schedule

Planning estimates, not claims that the actual work fit the window.

| Milestone | Target | Evidence gate |
| --- | --- | --- |
| M0 — environment | 0–15 min | Proxy/key/Docker, no-op/one-shot baselines, interfaces/ownership |
| M1 — complete loop | 15–50 min | Autonomous inspect/edit/replay/check, baseline tests, source snapshot |
| M2 — reliable pilot | 50–80 min | Containment/rollback/budget/SIGTERM tests, actual A1/B1 results and diff |
| M3 — freeze | 80–100 min | Measured improvement, independent review, amd64 startup/identity, suite handle |
| M4 — evaluate | 100–160 min | Six cases on one image; per-bug seeds, gates, determinism, actual cost/time |
| M5 — handoff | 160–180 min | Selected image, matching source, chats, write-up, limits/reproduction |

- M0 detects infrastructure problems but uses some credit.
- M1 delivers scoring capability early but starts with simple retrieval/prompts.
- M2 protects partial repairs but consumes diagnosis time.
- M3 catches packaging differences; short pilots miss complex dependencies.
- M4 measures the actual artifact; grading can exceed estimates. Never restart a quiet live session without checking its handle.
- M5 makes work reviewable but needs protected time. Upload/push remains user-directed.
- Two hours means fewer improvements and earlier freeze, not fabricated verification.

## Runtime loop

- Read incident/source/invariants/metadata/logs/contracts; establish test/replay/check baselines.
- Three specialists share bounded context; editor cycles evidence → cause → contract → patch → check → retain/rollback → remaining issue.
- V1 limits: six calls per investigator, fourteen editor rounds; investigation reservations ≤45% of budget and 35% of initial usable time.
- V1 candidate checks use up to two public seeds, protect baseline passes, reject new invariant categories and require a determinism repeat. Broader checks are model-selected; do not attribute V2 automatic full-public coverage to V1.
- Contain edits beneath `src/`; reject traversal/symlinks; require expected old text and stage related changes together.
- Replay success is not invariant success; run `sim check`.
- Keep latest validated source in case-local scratch. Rejected/interrupted edits restore it; bounded requests/process groups and shutdown reserve protect source/deadline.
- Prose claims/public-green/patch count do not certify hidden repairs.
- Pros: protected iterative progress. Cons: finite checks and conservative guards can miss/reject dependent changes.

## Evidence and spending

- Record milestone status, owner, timestamp, source/image identity, checks, artifacts, risks and next experiment.
- Unique tags/output directories; never pool successes across images.
- Report actual proxy spend separately from development-agent billing. Full practice budgets total at most $36; $150 account allowance is not a verified remaining balance.
- Initial envelopes: $15 setup, $45 development, $45 final evaluation/repeats, $45 contingency; actual limits/user direction take precedence.
- Preserve source/image/chat hashes and redacted provenance. Upload retains summaries/logs/patches; bulky scratch/replay traces are recoverably archived outside the repo.
- Select the best **fully evaluated** candidate: V1 complete 9/12. No V2 revision completed a comparable six-case run.
- No 100% or unseen-case guarantee. Future V3 work requires renewed authorization.
