<overview>
The user wants the experimental V3.1 fixer in `solution/fixer` to solve all practice cases reliably against the local grader. They said A2 must reach 2/2 before anything else, and then (latest instruction) to fix A3 without regressions, to understand why A3 fails before changing anything, and to work in a directed way. They also said to use MCPs and web search if needed, and to check V1's performance on A3 and borrow what worked. Approach so far: diagnose from public artifacts only (no private grading material), keep fixes generic with no case-specific repairs, run paid grading only with `./grade.sh --mode local` (no Docker), and verify with offline tests.
</overview>

<history>
1. Original task: improve the low-scoring fixer.
   - Earlier work (see the checkpoint) added controller improvements: rejected-candidate evidence retention, narrative-only retry, read-only-batch escalation, an edit-only turn after two experiments, a resource-release investigator, and supported-hypothesis follow-up.
   - The user then asked to stop Docker and get A2 to 2/2. A2 reached 2/2 in local mode.

2. A1/A3 local evaluation (`results/v3.1-focused-local-final`).
   - A1 scored 1/1. A3 scored 0/3 with an empty patch: the editor repeatedly read files and narrated, and never ran an experiment or edit.
   - I added generic controller fixes:
     - `Client.complete` takes a `tool_choice` argument ("auto" by default; "required" when escalating).
     - After 2 read-only editor batches with no action, the editor is restricted to edit, replay and compare tools with `tool_choice="required"`.
     - The edit-only lock after two experiments applies only when no candidate has been accepted yet, or in the final round when the round has produced no candidate.
     - `action_specs` is now `[apply_edits, replay_check, compare_traces]`.
   - A3 reruns r2–r5 all scored 1/3. Every one fixed only the `granted=False` bug in `router.py`.
   - A2 re-verified at `results/v3.1-a2-local-final`: 2/2, $1.82.

3. The user's latest instruction: verify A2, then focus on A3 without regressions, understand the failure first, check V1, and incorporate what V1 did right.
   - V1's A3 result is in `results/prototype-v1-final-all/A3`: 3/3 for $1.07 in 170 s. Its patch had four changes:
     - `router.py`: remove `job["granted"]=False` in `_note_boot` and `_lease_monitor`.
     - `recovery.py`: iterate over ALL ops with `rel == REL_RELEASING` and restart the releaser for each, not just `current_op_id`. After a FAILED report `attempt` is incremented, so the original code missed the previous attempt's releasing op. That leaked capacity, and B jobs then stayed queued forever.
     - `config.py`: `HELLO_BACKOFF_MAX_S = 2.0` instead of `= HELLO_TIMEOUT_S`. The runbook `worker-registration.md` says the cap is its own constant, 4× the hello timeout. This caused the registration flood and the "rpc requests per boot: 54 > 34" expect failure.
   - V1 found these by reading the corpus runbooks.
   - Root cause of the V3.1 A3 failure, from the report in `/tmp/c3-fixer-90paaulv/fixer-report.json`: all four investigators anchored on the first ticket item (`granted`). None investigated the other two ticket reports, recovery, or the config constants. The editor then tried a wrong `worker.py` `_register` change that regressed things.

4. Implemented the "ticket-report" investigators.
   - `ticket_items(workspace)` parses the numbered reports in `SYMPTOM.md`.
   - One `ticket-report-N` investigator is added per report when there are at least 2 items (cap 5). Each owns only its report and is told to check boot recovery of every persisted record, config constants against documented runbook values, and the corpus contract.
   - `followup_directive` is now a wrapper that appends the ticket list, the files changed by accepted candidates, and an instruction to address unexplained reports first. The original logic moved to `_base_followup_directive`.
   - Added test `test_numbered_ticket_reports_get_dedicated_investigators`.
   - The first parser version split on blank lines, but A3's `SYMPTOM.md` items are consecutive lines with no blank lines between them. The r6 run (2/3) therefore ran with only 4 investigators and did NOT use the new profiles. Its recovery fix was luck.
   - Rewrote the parser to match lines starting with `\d+\.\s+\S`, with indented continuation lines. Verified: A1 gives 0 items, A2 gives 0, A3 gives 3. Offline suite: 79 passed (macOS, deselecting `test_sigterm_process_group`).
   - `git diff --check` passed earlier. It has not been rerun since the parser rewrite.
</history>

<work_done>
Files modified this task (on top of pre-existing dirty files `solution/fixer/Dockerfile`, `tools.py`, `validation.py`, `solution/tests/test_tools.py`, `test_validation.py`, `solution/future-work-plan/README.md`, and untracked `solution/run-v3.sh`, which were preserved):
- `solution/fixer/fix.py`: `import re`; `SYMPTOM_PROFILE_LIMIT`, `ticket_items`, `symptom_profile`; `Harness.ticket_items` and the extended `self.profiles`; `followup_directive` wrapper and `_base_followup_directive`; read-only-batch escalation (`read_only_batches`, `batch_read`) with `tool_choice="required"` when `action_only` or `repair_only`; the narrowed repair-only lock (`final_candidate_required`, only if no accepted candidate exists or this is the final round with no candidate); `action_specs` reduced to edit, replay and compare.
- `solution/fixer/model.py`: `tool_choice` parameter on `Client.complete`.
- `solution/tests/test_model.py`, `solution/tests/test_harness.py`: new tests for read-only escalation, accepted-repair keeping reads available, the final-round candidate requirement, and ticket-report investigators.
- `solution/README.md`: NOT yet updated. Its V3 results paragraph is stale: it says A2 0/2 and A3 0/3 and describes only the older controller.

Grading results (local mode, no Docker):
- A1: 1/1 (`results/v3.1-focused-local-final`).
- A2: 2/2 (`results/v3.1-a2-local-final` and r6).
- A3: r2 1/3, r3 1/3, r4 1/3, r5 1/3, r6 2/3 (accidental; bugs 1 and 2 fixed, bug 3 `hello` backoff not). None of these used the working ticket-report profiles.

Current state: the parser fix is in and the offline tests pass, but A3 has NOT been rerun with the working per-report investigators. A2 and A1 have not been rerun since the ticket-report change either. A1 and A2 produce 0 ticket items, so their behavior is unchanged by it.
</work_done>

<technical_details>
- Run command (no Docker): `C3_GRADER_PYTHON="$PWD/venv/bin/python" ./grade.sh --fixer solution/fixer --cases practice/A3 --mode local --concurrency 1 --eval-workers 1 --keep --out results/<new-dir>`. Check that the output dir doesn't exist first. Use `venv/bin/python -m pytest -q solution/tests --deselect solution/tests/test_harness.py::test_sigterm_process_group`.
- Fixer reports are written to `/tmp/c3-fixer-*/fixer-report.json`. The path is in the `harness_done` event in `fixer.log`. Use that path, not the newest by mtime. `investigator_count` in the `harness_start` event shows whether the new profiles are active (4 means they are not; 7 expected for A3).
- A3 ticket: 3 independent bugs. (1) `granted` cleared on expiry/revocation, so a cancel takes the `cancel_queued` fast path (billing dispute); (2) recovery restarts the releaser only for the current attempt's op, which leaks capacity and leaves B jobs stuck; (3) `HELLO_BACKOFF_MAX_S` mis-set to the hello timeout, which causes the registration flood. Hidden grading uses 20 seeds per bug (1001+, 2001+, 3001+). Bug 3 is judged by expect checks: `worker_register_retry` at most 50, and `hello` RPCs per boot at most 52.
- Do not "fix" `worker.py` `_register` by returning on RpcError. That made seed 11 worse and was wrongly accepted or rejected by the editor in earlier runs.
- The investigators' hypothesis ids collide across agents (several use "H1"). `outstanding_supported_hypotheses` therefore can't distinguish them. This is a known limitation and was not changed.
- The investigation budget is capped at 45% of spend (`spend_cap`) and runs until `investigation_until` (35% of the time budget). More parallel investigators cost roughly $0.2 each. A3 total spend has been about $2–2.5 of $9.
- A1/A2 SYMPTOM.md files have no numbered lists, so ticket profiles don't apply to them.
- The Linux-only test `test_sigterm_process_group` fails on macOS with PermissionError, so it is deselected.
- Constraints: don't read private grading material; use only the public case files, contracts and aggregate grader results.
</technical_details>

<important_files>
- `/Users/h/Development/c3-take-home/solution/fixer/fix.py`: main controller; contains `ticket_items`/`symptom_profile` (near the top, after the profile constants), the `Harness.__init__` profile selection, `followup_directive`/`_base_followup_directive`, `investigate`, `apply_candidate`, and the `edit` loop with its escalation logic.
- `/Users/h/Development/c3-take-home/solution/fixer/model.py`: `Client.complete(... tool_choice="auto")`.
- `/Users/h/Development/c3-take-home/solution/tests/test_harness.py` and `test_model.py`: offline tests for the controller behaviors above.
- `/Users/h/Development/c3-take-home/solution/README.md`: needs a results update (the V3.1 paragraph near the end).
- `/Users/h/Development/c3-take-home/results/prototype-v1-final-all/A3/patch.diff`: the reference V1 3/3 patch.
- `/Users/h/Development/c3-take-home/results/v3.1-a3-local-r6/A3/`: latest A3 result, 2/3 (with a patch touching `recovery.py` and `router.py`).
- `/Users/h/Development/c3-take-home/practice/A3/SYMPTOM.md` and `practice/A3/src/jobrouter/{router,recovery,config,worker}.py`: public A3 sources and ticket.
- `/Users/h/Development/c3-take-home/corpus/build/practice/service/A/` runbooks: contain `worker-registration.md`, `cancellations.md` and `operational-notes.md`, the contracts V1 relied on.
</important_files>

<next_steps>
Immediate:
1. Run `git diff --check`, then rerun A3 locally into a new output dir, e.g. `results/v3.1-a3-local-r7`. Confirm `investigator_count` is 7 in the log and inspect which hypotheses the `ticket-report-*` agents produced (especially report 3 and the config constant) and the patch.
2. If A3 is still below 3/3, analyze why from the report. Ideas: make the config-constant check more explicit (e.g. a general instruction to grep the runbooks for each config constant named in the report); make sure the editor does not get stuck; and check that `HELLO_BACKOFF_MAX_S` is surfaced.
3. Do not add case-specific fixes; keep them generic.
4. After A3 improves, rerun A2 (must stay 2/2) and A1 (1/1) in local mode only, to confirm there are no regressions. Re-run the offline suite after any code change.
5. Update `solution/README.md` with verified A1/A2/A3 results, clearly separated from the historical V1 9/12 baseline, and describe the new controller behaviors (ticket-report investigators, forced-action escalation).
6. Mark the remaining SQL todos (testing, selected-case evaluation) done only after A1/A2/A3 results and the docs are verified. Don't launch Docker.
</next_steps>