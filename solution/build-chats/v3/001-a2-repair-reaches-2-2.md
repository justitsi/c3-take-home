<overview>
The user asked to improve the experimental fixer because its local grader score was low, with the goal of reliably fixing all provided cases. After approving an implementation plan and selecting paid A1/A2/A3 evaluations, the user explicitly asked to stop Docker grading and focus on getting A2 to 2/2 before continuing. A2 now scores 2/2 in non-Docker local mode; the next planned work is to evaluate A1 and A3 in local mode only.
</overview>

<history>
1. The user asked for a plan to improve the low-scoring fixer.
   - Inspected the repository, its existing dirty changes, historical 9/12 V1 score, and partial V3 grader results.
   - Found the initial experimental V3 results: A1 1/1, A2 0/2, A3 0/3.
   - Asked what paid evaluation scope was authorized. The user selected A1, A2, and A3.
   - Created the session plan and todos, then received plan approval.

2. Implemented controller improvements and offline tests.
   - Preserved rejected edit payloads and bounded validation evidence, including baseline/candidate trace paths.
   - Added follow-up after narrative-only rounds and action escalation when unresolved candidates only receive read-only investigation.
   - Added an edit-only turn after two experiments fail to resolve a candidate.
   - Added a resource-release investigator for services containing both capacity and releaser modules, and routed follow-up to supported hypotheses not covered by an accepted candidate.
   - Added corresponding controller tests and updated the solution README.

3. The user interrupted the A1–A3 Docker evaluation and asked to stop Docker and achieve A2 2/2 first.
   - Stopped the active grading shell and its A1/A2/A3 grader/proxy containers. Did not restart Docker afterward.
   - Inspected the partial A2 evidence. The first attempted fix prevented expired lease reports but exposed a capacity counterexample; subsequent rounds lacked an effective repair.
   - Switched to the repository’s non-Docker `grade.sh --mode local` path and focused only on A2.
   - A2 attempts scored 0/2, 0/2, 1/2, then 2/2. The user’s requested A2 threshold was achieved.

4. Current point.
   - The latest A2 run fixed both bugs on all 20 hidden seeds, with tests and regression gates passing.
   - The latest accepted A2 patch changes only the temporary grader workspace’s `executor.py` and `releaser.py`; those are not edits to the repository’s practice case.
   - The assistant said it would resume the authorized A1/A3 runs in local mode only. No A1/A3 rerun has happened yet.
</history>

<work_done>
Repository files modified by this task:
- [solution/fixer/fix.py](/Users/h/Development/c3-take-home/solution/fixer/fix.py): bounded rejected-candidate context, trace evidence, narrative-only retry, read-only-batch escalation, edit-only escalation after two experiments, capability-selected resource-release investigator, and supported-hypothesis follow-up.
- [solution/tests/test_harness.py](/Users/h/Development/c3-take-home/solution/tests/test_harness.py): tests for retained candidate evidence, action escalation, resource profile selection, unaddressed supported hypotheses, and corrected seed fixtures for existing controller tests.
- [solution/README.md](/Users/h/Development/c3-take-home/solution/README.md): documents the controller changes and historical partial V3 evaluation. **Its evaluation statement is now stale**: it says A2 0/2, but the latest A2 local run is 2/2.

Plan/tracking:
- Plan: [plan.md](/Users/h/.copilot/session-state/d978be55-4b4c-48d6-b5d2-31063885c7ec/plan.md)
- SQL todos: diagnosis and implementation marked done; testing is in progress; selected-case evaluation remains pending.

Validation:
- Latest macOS-compatible offline run: **74 passed, 1 deselected**. The deselected test is Linux-specific process-group behavior that fails on macOS with `PermissionError`.
- Earlier Linux-container run (before the most recent additions): **72 passed**.
- `git diff --check` passed.
- A2 local run r6: **2/2 bugs fixed**, each with 20/20 hidden seeds; `tests_ok=true`, `regression_ok=true`, no infrastructure errors.
- No Docker grading containers were launched after the user requested stopping Docker. Latest container listing showed only an unrelated `api-api-1` service.

Grader artifacts:
- Latest verified A2 result: [result.json](/Users/h/Development/c3-take-home/results/v3.1-a2-local-r6/A2/result.json)
- Accepted A2 patch evidence: [patch.diff](/Users/h/Development/c3-take-home/results/v3.1-a2-local-r6/A2/patch.diff)
- Earlier attempts are under `results/v3.1-a2-local-r3`, `-r4`, and `-r5`; they scored 0/2, 0/2, and 1/2 respectively.
</work_done>

<technical_details>
- The practice A2 lease issue was in `LeaseExecutor._report`: the loop checked the lagging `lease.lost` flag rather than checking `lease.valid()` immediately before sending a report.
- The independent release issue was in `ReleaseManager._run`: it freed router capacity right after the GPU accepted a release request, before observing `ReleaseComplete`. The successful generated A2 patch moved `_on_freed` until after the completion message or `status.released` was observed.
- Candidate-level checks alone could falsely signal completion when public seeds passed but independent supported hypotheses remained. The controller now records hypotheses covered by accepted edits and prompts follow-up for supported hypotheses that remain unaddressed.
- The initial no-action retry alone was insufficient: the model kept making read-only calls. The controller now escalates after two read-only batches on an unresolved candidate, then restricts tools to experiments/edits; after two experiments, it restricts the next turn to `apply_edits`.
- Resource-release investigation is selected by source capability (presence of `capacity.py` and `releaser.py`), not by hard-coded A2 bug fixes.
- The A2 paid runs were performed with `./grade.sh --mode local` and case `practice/A2`, not Docker. Each run had a $6 case budget; the latest successful run spent $1.77.
- The worktree was already dirty before this task in `solution/fixer/Dockerfile`, `tools.py`, `validation.py`, tests, docs, and `solution/run-v3.sh`. Those pre-existing changes were preserved.
- Do not inspect or modify private grading material; analysis used public case files, public contracts, and the grader’s aggregate result output.
</technical_details>

<important_files>
- [solution/fixer/fix.py](/Users/h/Development/c3-take-home/solution/fixer/fix.py)
  - Main controller implementation; latest changes preserve failed patch/check evidence, force productive follow-up, and route resource-release investigation.
- [solution/tests/test_harness.py](/Users/h/Development/c3-take-home/solution/tests/test_harness.py)
  - New deterministic tests for controller progression and supported-hypothesis coverage; existing candidate fixtures were corrected to model their intended seeds.
- [solution/README.md](/Users/h/Development/c3-take-home/solution/README.md)
  - Documentation update exists, but update the V3 results section after A1/A3 reruns to reflect the newer A2 2/2 result.
- [practice/A2/src/jobrouter/releaser.py](/Users/h/Development/c3-take-home/practice/A2/src/jobrouter/releaser.py)
  - Public A2 source reviewed to understand the independent capacity-release issue; not modified.
- [corpus/build/practice/service/A/operational-notes.md](/Users/h/Development/c3-take-home/corpus/build/practice/service/A/operational-notes.md)
  - Current contract states capacity remains reserved until ReleaseComplete.
- [results/v3.1-a2-local-r6/A2/result.json](/Users/h/Development/c3-take-home/results/v3.1-a2-local-r6/A2/result.json)
  - Authoritative latest A2 result: 2/2.
- [results/v3.1-a2-local-r6/A2/patch.diff](/Users/h/Development/c3-take-home/results/v3.1-a2-local-r6/A2/patch.diff)
  - Shows the two successful generated changes from the latest run.
</important_files>

<next_steps>
- Continue the originally authorized evaluation of **A1 and A3 only**, using `./grade.sh --mode local`; do not launch Docker.
- Inspect results and adjust the controller if either case underperforms.
- Update [solution/README.md](/Users/h/Development/c3-take-home/solution/README.md) with the verified A1/A2/A3 results, clearly distinguishing current experimental results from the historical V1 9/12 baseline.
- Rerun the macOS-compatible offline suite and `git diff --check` after any further code changes.
- Mark the remaining SQL testing/evaluation todos complete only after A1/A3 results and documentation are verified.
</next_steps>