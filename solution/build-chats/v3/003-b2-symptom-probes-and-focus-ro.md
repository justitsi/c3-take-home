<overview>
The user wants the experimental V3.x fixer in `solution/fixer` to solve every practice case reliably against the local grader. A1, A2 and A3 now pass (1/1, 2/2, 3/3 in local mode). The latest instruction is: "drill down on B2 and get that passing with 3/3; we'll work on the other ones later." Constraints: use only public case files, contracts and aggregate grader results (no private grading material); keep fixes generic with no case-specific repairs; run grading only with `./grade.sh --mode local` (no Docker); avoid regressions on the A cases. I'm working in a directed way: diagnose first, add generic harness capabilities, then verify with offline tests and local grading runs.
</overview>

<history>
1. Earlier turns (see prior checkpoints): improved the controller (rejected-candidate retention, forced-action escalation, resource-release investigator, ticket-report investigators). A2 reached 2/2.
   - A3 initially scored 1/3, then 3/3 once the ticket-report parser was fixed (r7: $2.36).
   - A2 re-verified at 2/2 (`results/v3.1-a2-local-r8`, $1.84).
   - README updated with these results.

2. The user asked for a git checkpoint on a new branch "v3.2".
   - I created `solution/prototype-v3.2` from `solution/prototype-v3.1` and committed `b08c6f2`. The commit included the previously uncommitted Dockerfile, tools and validation changes and `solution/run-v3.sh`.

3. The user asked to run the B cases and solve them one by one, as with the A cases.
   - The baseline in `results/v3.2-b-local-r1` was B1 1/1 ($1.35), B2 1/3 ($2.60), B3 0/2 ($2.85).
   - I diagnosed B2 (details in the technical notes) and committed `4be839f`: forced investigator conclusion, `log_signatures`, probe deltas, `trace_query`.
   - After those commits B2 swung between 1/3 and 2/3 across runs (r2–r7). I paused and offered the user a choice of continuing B2 or moving to B3.

4. The user said: drill down on B2 and get 3/3; the other cases come later. All work after `4be839f` is uncommitted.
   - The B2 runs after that commit were r8 1/3, r9 0/3 (empty patch), r10 2/3, r11 2/3.
   - r10 fixed bugs 2 and 3. r11 fixed bugs 2 and 3. Bug 1 failed in both.
   - I was mid-diagnosis of bug 1 when context ended.
</history>

<work_done>
Committed:
- `b08c6f2`: V3.2 base, per-report investigators and forced-action escalation (branch `solution/prototype-v3.2`).
- `4be839f`: forced investigator JSON conclusion, `log_signatures` in replay results, scenario probe baselines and deltas, `trace_query`.

UNCOMMITTED changes (on top of `4be839f`), all in `solution/fixer/fix.py`:
- `ticket_signatures(workspace)` plus `SIGNATURE_TOKEN`: parses `field=value` tokens (outcome, reason, code, state, verdict, cause) from `SYMPTOM.md`. In practice only B2 contains one (`outcome=missing_from_heartbeat`). `self.symptom_targets` and `self.symptom_evidence` are set in `__init__`.
- `Harness.probe_symptom()`, called from `run()` after the baseline and before the investigators; its output is appended to the shared `context`.
  - It runs every `scenarios/faults/*.yaml` profile (excluding `public.yaml`) once on `self.seeds[0]`.
  - It records profiles where the ticket-named token occurs and profiles with invariant violations ("latent failures").
  - It pins the top 2 symptomatic profiles (ranked by fewest violations, then highest count) plus up to 3 violating profiles as probes (`remember_probe(..., pinned=True)`).
  - The evidence text includes a `trace_query` timeline of the first symptom occurrence, a generic reordering/sent-vs-acked hint, and the list of latent-failure profiles.
  - It logs `symptom_probe` and `latent_failures` events.
- `remember_probe` now takes `pinned`. `probe_deltas` uses up to 5 pinned probes plus the 3 most recent unpinned ones, and adds `symptom_count_before_after`.
- `apply_candidate` now computes `probe_deltas` before the accept decision.
  - It rejects a candidate if any probed profile gains violations (`probe_regressions`).
  - It grants "resolved" credit through `resolved["ticket-symptom"]` and `resolved["fault-profile-violations"]` when the symptom count drops to 0 or profile violations drop.
  - `record["probe_deltas"]` uses the precomputed value.
- Per-report focus rounds:
  - `self.total_rounds` is `min(DIAGNOSIS_ROUNDS + 1, 4)` (so 4) when the ticket has at least 3 items, else 3.
  - `edit()` uses `self.total_rounds` instead of `DIAGNOSIS_ROUNDS`, and `_base_followup_directive` combines in the last round (`round_number == self.total_rounds`).
  - `followup_directive` prepends "ROUND FOCUS: repair ONLY ticket report N" for rounds ≤ number of items and < `total_rounds`.
- Prompt additions (BASE_SYSTEM and editor system prompt): the probe_deltas / signature guidance and the producer-consumer note.

Tests: `solution/tests` has 83 passing with `--deselect solution/tests/test_harness.py::test_sigterm_process_group`. `test_exited_parent_does_not_hang_on_inherited_stdout` is flaky on macOS (PermissionError in a process-group race). New tests have been added for the forced conclusion, `log_signatures`, `trace_query`, and the probe-baseline logic. There are NO tests yet for `ticket_signatures`, `probe_symptom`, the focus rounds, or the profile-violation credit.

Not yet rerun after the uncommitted changes: A1, A2, A3 and B1 (regression checks are required). README not updated for the V3.2 B-case work. A scratch debug copy of B2 with the r11 patch is at `/tmp/b2r11-6974`; it contains a DBG log line and is not part of the repo.
</work_done>

<technical_details>
- Run command: `C3_GRADER_PYTHON="$PWD/venv/bin/python" ./grade.sh --fixer solution/fixer --cases practice/B2 --mode local --concurrency 1 --eval-workers 1 --keep --out results/<new-dir>`. The output dir must not already exist. A B2 run takes about 4–5 minutes and costs about $3–4. Tests: `venv/bin/python -m pytest -q solution/tests --deselect solution/tests/test_harness.py::test_sigterm_process_group`.
- To find a run's report: take the `harness_done` event in `results/<dir>/B2/fixer.log`, whose `report` field is `/tmp/c3-fixer-*/fixer-report.json`. It contains `candidates` (with `probe_deltas`), `hypotheses`, `hypothesis_assessments` and `experiments`. Per-bug results are in `results/<dir>/B2/eval.json` (`bugs[].fixed`, `seeds_passed`).
- B2 ticket (`practice/B2/SYMPTOM.md`), three independent bugs:
  1. After a ~4 s coord/worker blip, single-shard jobs get stuck (MAPPING, committed=0, never re-dispatched).
  2. On the jittery profile, coord requeues still-running tasks (`task_finished outcome=missing_from_heartbeat`).
  3. With packet loss, jobs hang for good (some in REDUCING) after `gpu_submit_unknown`, followed only by status polls.
- Bug 3 fix (found by agents in most runs): in `gpu_client.py` `submit()`, the inner `while True` loop after `gpu_submit_unknown` polls forever on NOT_FOUND. It must break out so the outer loop resubmits with the same op_id.
- Bug 2 fix (verified manually in a scratch copy: all `missing_from_heartbeat` counts drop to 0 under reorder, stragglers and network). It needs TWO coordinated edits:
  - `worker.py`: the assign reply must report the highest heartbeat seq SENT (a `hb_sent` counter set in `_main`), not `self.hb_seq` (the last acked).
  - `scheduler.py` line ~249: use `t.ack_seq = int(r["hb_seq"])` instead of `min(seen, ...)`.

  Either edit alone leaves the count unchanged. The agents repeatedly tried the one-sided variants `max()` and `>=`.
- Bug 1 (V1 solved it with these two changes): remove the `if fresh` gate in `coordinator.py` heartbeat (`abort = self.sched.on_heartbeat(...) if fresh else []`), and in `worker.py` `_run_batch` delete finished tasks from `self.tasks` regardless of whether `_report` returned True.
- Public seeds 1, 3, 5, 6, 7 pass invariants even with bug 2 present, which is why a symptom/profile probe is needed. Baseline fault-profile results on seed 1: `network.yaml` has 22 violations (3 missing_from_heartbeat), `lossy.yaml` 10, `partitions.yaml` 2; `reorder.yaml` and `stragglers.yaml` have 0 violations but 5 and 1 missing_from_heartbeat.
- The probes are the key signal. In r10, probes plus per-report rounds fixed bug 2 (the symptom went 5→0). In r11, after all accepted candidates, `partitions.yaml` still had 2 violations. That is the unresolved bug 1 signal.
- Current debugging state for bug 1 (r11 patch applied in `/tmp/b2r11-6974`, `partitions.yaml` seed 1, stuck job `A:q35`):
  - The task failed on worker-1 at t≈34.6, and the report RPC attempts were dropped by the partition.
  - `batch_report_abandoned` was logged at t≈37.8, and the worker deleted the task from `self.tasks`.
  - After the partition healed, heartbeats from worker-1 arrived normally from t=38.5.
  - The DBG instrumentation in `Scheduler.on_heartbeat` shows the coordinator-side task stays `state=running` with `ack_seq=60`, `hb` increasing (61…227) and `inrun=True` on every heartbeat, even after the worker deleted the task. So the worker's heartbeat `running` list still contained the task.
  - Conclusion: the worker still lists the failed task, so the deletion-after-report path isn't running. Likely candidates are an unpatched path in `worker.py` (in r11 the 4 worker edits may not include removal of the task, or the task is re-added/held elsewhere) or a different stuck-task cause. This is not yet confirmed. The next step is to inspect where `self.tasks` is cleaned in the r11 patch and why `running` still contains the task.
- Known behavior: the editor tends to bundle fixes into one big rejected candidate, or to stack one-sided variants. Per-report focus rounds partly fixed this (r10).
- Agents never called `trace_query` unprompted (0 uses). The harness now injects a timeline itself.
- The investigators' hypothesis ids collide across agents ("H1"). Known limitation; not changed.
- `A1/A2` have no numbered ticket items (0 items). A3 has 3 and B2 has 3. B1 has 0 and B3 has 2 (`total_rounds` stays 3 for B3).
- Risks of the uncommitted changes: pinned fault-profile probes and the profile-violation credit also apply to the A cases (those cases have fault profiles that may already have violations). A regression is possible, and A1/A2/A3 plus B1 must be rerun.
- Constraints: no case-specific fixes; don't read private grading material; don't launch Docker; a `rm -rf` command was denied by permissions, so use fresh temp directories instead of deleting.
</technical_details>

<important_files>
- `/Users/h/Development/c3-take-home/solution/fixer/fix.py`
  - Main controller. All uncommitted work is here:
    - `ticket_signatures` / `SIGNATURE_TOKEN` (before `symptom_profile`);
    - `probe_symptom`, `remember_probe`, `probe_deltas` (near the `assess_hypothesis` area, ~lines 450–560);
    - the `apply_candidate` probe credit/regression logic;
    - `followup_directive` / `_base_followup_directive` focus rounds (~line 293+);
    - `edit()` using `self.total_rounds`;
    - `run()` calling `probe_symptom`.
  - `investigate` has the forced-conclusion step. `TRACE_QUERY_SCHEMA` is wired into the investigator and editor loops.
- `/Users/h/Development/c3-take-home/solution/fixer/validation.py`
  - `log_signatures()` and `Validation.trace_query()` (committed).
  - `replay_check` returns `log_signatures`.
- `/Users/h/Development/c3-take-home/solution/fixer/model.py`: `Client.complete(... tool_choice=...)`.
- `/Users/h/Development/c3-take-home/solution/tests/test_harness.py`, `test_validation.py`, `test_model.py`: offline tests (83 passing).
- `/Users/h/Development/c3-take-home/practice/B2/`: `SYMPTOM.md`, `scenarios/faults/*.yaml`, `src/shardmr/{scheduler,worker,coordinator,gpu_client,membership,config}.py`.
- `/Users/h/Development/c3-take-home/results/v3.2-b2-local-r10` and `r11`: latest B2 results (2/3).
- `/Users/h/Development/c3-take-home/results/prototype-v1-final-all/B2/patch.diff`: V1's bug-1 fix reference.
- `/Users/h/Development/c3-take-home/solution/README.md`: needs a V3.2 results update (it currently covers A1/A2/A3 only).
</important_files>

<next_steps>
Immediate:
1. Finish diagnosing bug 1 (partitions.yaml seed 1 stuck task). Check why the worker's heartbeat `running` list still includes the failed task after `batch_report_abandoned`: read `worker.py` `_run_batch`, `_report` and `tasks` handling in the r11-patched scratch copy at `/tmp/b2r11-6974`.
2. Derive a generic harness improvement from this so agents can reach the bug-1 fix. Options: strengthen the latent-failure evidence (give a `trace_query` timeline for the first stuck/unresolved action in the pinned violating profile, not only for the symptom token); give the final/integration round an explicit "profiles still violating after accepted candidates" directive so the editor keeps working on `partitions.yaml`/`network.yaml` until it reaches 0 violations; and require the remaining-violations list in directives. No case-specific patches.
3. Add offline tests for `ticket_signatures`, `probe_symptom` (probe pinning and ranking), the focus-round directive, and the profile-violation credit. Rerun the full suite.
4. Rerun B2 (aim for 3/3, ideally on more than one run, since variance is high). Note that each run costs about $3–4.
5. Regression checks in local mode: A1 (1/1), A2 (2/2), A3 (3/3), and B1 (1/1). If any regress, scope the new probe/credit/focus logic more tightly.
6. Commit as the next V3.2 checkpoint on `solution/prototype-v3.2`, with the Co-authored-by trailer, after `git diff --check`.
7. Update `solution/README.md` with verified local results (single runs, separate from the V1 baseline) and the new controller behaviors (forced conclusion, log signatures, probe deltas and symptom/latent-failure probing, per-report focus rounds, trace_query).
8. B3 (0/2) and the remaining B cases are deferred until B2 is solved, per the user.
</next_steps>