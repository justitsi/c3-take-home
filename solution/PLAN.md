# Assessment completion plan

- **Deadline:** tomorrow. **Work window:** 2–3 hours; schedule targets three hours, including evaluation waits.
- **Local Docker constraint:** keep the VM around 2 GB. Run practice cases serially with `--concurrency 1 --eval-workers 1`; retain three parallel read-only model investigators inside each case.
- **Objective:** submit an autonomous fixer for unfamiliar distributed Python services. Maximize bugs fixed; runtime breaks ties.
- **Development:** AI agents implement, review, test, and package the fixer under your supervision. Work proceeds in short iterations with evidence-backed milestones.
- **Submitted fixer:** three parallel read-only Sonnet specialists, one serial repair agent, a Python controller, targeted corpus search, iterative repairs, simulator checks, and rollback. Hidden evaluation runs autonomously, without human supervision.
- **Basis:** assessment README, rules, examples, simulator CLI, and grader. Current implementation and evaluation evidence is tracked in `solution/STATUS.md`.

## Requirements

- Hidden evaluation: 12 cases across unseen codebases C/D/E; fresh container and no carried-over state.
- Per case: 900 seconds, $3 per bug, 2 CPUs, 4 GB RAM. Read actual paths/budgets from environment.
- Allowed runtime models: Sonnet 4.6 and optional Jev through the supplied proxy; no other network access.
- Only `src/` edits count. Preserve simulator, tests, grader, and deterministic service behavior.
- Each bug must pass its targeted scenario on all 20 hidden seeds; some repairs depend on earlier fixes.
- Breaking baseline-passing public/private regression tests zeroes the case. Public tests already pass before repair.
- Submit: `linux/amd64` image ≤4 GB, fixer source/Dockerfile, build chat logs, half-page write-up. No-argument entry point; Python ≥3.12, PyYAML, pytest, dependencies installed during build.

## Agent roles and supervision

- Use a lead/integration agent plus up to three specialist agents. The lead also implements code; coordination must not consume the development window.
- Development agents can use available development tools/models. The submitted fixer remains subject to the assessment's Sonnet/Jev runtime restrictions.

| Role | Ownership | Deliverables |
| --- | --- | --- |
| Lead/integration agent | `fix.py`, `model.py`, prompts, shared interfaces, `solution/STATUS.md` | Working loop, integration, priorities, milestone reports, final candidate selection |
| Tools/retrieval agent | `tools.py`, `retrieval.py`, associated tests | Bounded inspection/search/edit tools; current-contract retrieval with citations |
| Validation/reliability agent | `validation.py`, controller reliability tests | Baselines, checkpoint/rollback, deadline handling, regression and determinism checks |
| Evaluation/packaging agent | `Dockerfile`, `run.sh`, fixer README/write-up, evaluation summaries | Environment checks, image builds, graded results, submission artifacts |

- **You supervise:** review milestone summaries, inspect representative diagnoses/patches, redirect priorities, and make unresolved scope/spend/submission decisions. Agents should make results understandable enough for you to explain in the interview.
- **Lead coordinates:** assign bounded tasks with interfaces, owned files, acceptance checks, dependencies, and time limits. Reserve three worker slots; reuse them as tasks finish.
- **Parallel work:** tools/retrieval, validation, and packaging scaffolds can proceed together once interfaces are agreed. Integration and edits to shared files remain sequential.
- **Interface checkpoint:** before parallel coding, agree tool request/result schemas, model response/tool-call handling, validation reports, and checkpoint operations. Include success/failure status, bounded output, elapsed time, and artifact paths; develop against fake responses until dependencies are ready.
- **Shared-workspace discipline:** one owner per file; agents request interface changes through the lead. No overwriting another agent's work or changing practice sources to manufacture a score. Use fresh grader workspaces for experiments.
- **Handoff format:** changed files; behavior added; checks and artifact paths; remaining failures; next recommendation. The lead inspects the actual diff/results before integrating.
- **Review:** a non-author agent reviews meaningful patching/budget/checkpoint changes; the lead resolves findings and reruns affected checks. Review must fit the timebox.
- **Checkpoint communication:** report completed evidence, open problems, remaining time/credit, and the next iteration. Routine work continues within the agreed scope; ask you when a missing choice changes scope, cost limits, or the submission outcome.
- **Human review opportunities:** M0 architecture, M2 working repairs, M3 candidate freeze, M5 handoff. Prepare concrete results before asking for decisions. Do not add a mandatory approval pause to every edit or test.
- **Pros:** parallel implementation and independent review; visible progress and clear accountability.
- **Cons:** interface conflicts, integration overhead, duplicated investigation. Mitigate with file ownership, small tasks, and a single integration owner.

## Decisions and tradeoffs

- **Several development agents; three investigators and one editor in the submitted runtime.**
  - **Pros:** concurrent hypotheses across recovery, leases/membership, and delivery/commit; shared findings inform one coherent repair sequence.
  - **Cons:** duplicated retrieval and simultaneous model reservations can consume budget; merging hypotheses adds context.
  - **Choice:** run read-only specialists in parallel, share deadline/spend accounting, and serialize all edits/checkpoint decisions. Defer Jev until measured benefit justifies it.
- **Small Python implementation; standard-library HTTP.**
  - **Pros:** builds on the example; few dependencies; explicit proxy/timeouts.
  - **Cons:** tool parsing, usage tracking, and retries need custom code.
  - **Choice:** one proxy format and compact tools; avoid framework migration.
- **Lexical search, prioritizing current contracts.**
  - **Pros:** fast, inexpensive, explainable; avoids loading the approximately 26M-token corpus.
  - **Cons:** keyword searches can miss paraphrases or dependencies.
  - **Choice:** expand queries using events, RPC names, invariants, and neighboring sections; search research papers only when needed.
- **Focused patches with validated checkpoints.**
  - **Pros:** protects earlier repairs and passing tests; limits unrelated changes.
  - **Cons:** validation costs time; conservative acceptance can discard promising candidates.
  - **Choice:** retain supported partial fixes; compare failures by issue/seed rather than raw violation counts.
- **Progressive validation: failing seed → broader checks → image grader.**
  - **Pros:** quick feedback before expensive evaluation; verifies packaging.
  - **Cons:** public seeds cannot prove hidden correctness.
  - **Choice:** report official practice scores and their limits.
- **Freeze early; reserve submission time.**
  - **Pros:** leaves room for evaluation and artifacts before tomorrow.
  - **Cons:** fewer tuning opportunities.
  - **Choice:** improve only when sufficient time remains to regrade the final artifact.

## Iteration protocol

- Use short build–measure–review cycles, generally 15–25 minutes inside the schedule below. A cycle ends with runnable evidence or a documented failing check, not a progress claim alone.
- **Choose:** lead selects the highest-impact observed gap: infrastructure, missing capability, regression, retrieval failure, or repair weakness. Record a hypothesis and success criterion before editing.
- **Delegate:** assign independent tasks and identify integration dependencies. Prefer one measurable improvement per task.
- **Implement:** agents make scoped changes and run focused checks; report blockers early while continuing independent work.
- **Integrate:** lead inspects patches, resolves interface mismatches, and runs the combined controller.
- **Measure:** compare with the previous checkpoint using tests, simulator outcomes, grader scores, elapsed time, and spend. Change one major strategy at a time where practical.
- **Review:** another agent checks the evidence and risky logic. Present meaningful findings to you; distinguish proven improvement from a hypothesis.
- **Checkpoint:** retain the candidate if it preserves passing behavior and improves the intended capability; otherwise restore the previous implementation or narrow the change. Update status and choose the next cycle.
- **Stop rules:** do not repeat identical failed experiments without a changed hypothesis. Escalate missing credentials, unavailable Docker, ambiguous requirements, or exhausted credit. Freeze when remaining time only covers final verification and packaging.
- **Pros:** catches mistaken assumptions early and turns evaluation failures into specific work.
- **Cons:** repeated runs consume time/credit; use cheap local checks before paid grading.

## Three-hour schedule

### 1. Setup and baseline — minutes 0–15

- **Owners:** lead defines interfaces and assignments; packaging agent checks environment; other agents inspect contracts and prepare scaffolds.
- Create a virtual environment; install PyYAML/pytest. Earlier checks found these missing; recheck first.
- Configure supplied key in ignored `.env`; verify proxy health and Docker daemon. Never print credentials.
- Run no-op on A2: expect `0/2` fixes, zero spend, no infrastructure error.
- Run minimal LLM example once on A2; capture comparison score, runtime, spend, and patch.
- Inspect `result.json`, `eval.json`, `patch.diff`, `fixer.log`. Confirm real proxy use; the wrapper can fall back to a stub.
- **Gate:** functioning proxy, grader, Docker. Ask immediately if credentials or Docker access are missing; continue independent controller work.
- **Checkpoint M0:** baseline artifacts, recorded environment gaps, agreed agent ownership, and an initial status entry. You can redirect architecture or priorities here.
- **Pros:** detects infrastructure failures early. **Cons:** uses development time and some practice credit.

### 2. Iteration 1: smallest complete repair loop — minutes 15–50

- **Owners:** lead builds model/orchestration; tools agent builds inspection/retrieval; validation agent builds baseline/checkpoint interfaces; packaging agent prepares the image and run scripts.
- Implement under `solution/fixer/`; retain this plan at `solution/PLAN.md`.
- Use small modules: `fix.py` orchestration, `model.py` proxy, `tools.py` inspection/edits/checks, `validation.py` checkpoints. Add `run.sh` and `Dockerfile` early.
- Read `C3_WORKSPACE`, `C3_CORPUS`, `C3_DEADLINE`, `C3_BUDGET_USD`, and proxy settings. Discover package/service names dynamically.
- Gather ticket, README, invariants, metadata, relevant logs, source layout. Establish tests and failing replay/check baselines.
- Begin corpus discovery at `INDEX.md`; retrieve service design/runbooks and current platform contracts. Return bounded excerpts with paths/line numbers; prefer current over superseded versions.
- Expose local tools: list, read ranges, search, patch source, test, replay, check, finish. Bound output and execution time.
- Prompt sequence: reproduce → trace failing transition → read contract → repair → validate → inspect remaining issues.
- Maintain an evidence/repair/verification checklist. Tickets may hide multiple bugs; continue after the first improvement.
- **Gate:** a fresh case performs an autonomous inspect/edit/check cycle and uses results to decide its next action.
- **Checkpoint M1:** integrated fixer, a recorded tool-call/replay/check cycle, baseline tests, source snapshot, and a concise gap list. A proposed patch alone does not satisfy the gate.
- **Pros:** delivers scoring capability early. **Cons:** initial prompts/retrieval remain simple.

### 3. Iteration 2: repair quality and reliability — minutes 50–80

- **Owners:** validation agent leads failure handling; lead integrates; tools agent fixes observed retrieval/editing gaps; packaging agent starts A1/B1 pilots when the loop is runnable.
- Resolve edits beneath `src/`, including symlink checks; reject traversal. Match expected old text, stage replacements, support new source files.
- Save original/latest validated source. Treat related multi-file edits as one candidate; compile/test before retaining it. Restore the checkpoint after failure.
- Run `sim check` after replay: replay exit zero means simulation ran, not that invariants passed.
- Preserve baseline-passing tests and earlier repairs. Accept supported partial fixes while unrelated original bugs remain.
- Bound model requests/subprocess groups; handle malformed responses, transient failures, HTTP 402, SIGTERM. Avoid repeated permanent errors.
- Track conservative spend, including cache writes/output; account for proxy cost reservations when choosing prompt size and `max_tokens`.
- Initially reserve 60–90 seconds per case for final checks/restoration; tune from observed duration. Track elapsed time monotonically.
- Test containment, rollback, exhaustion, shutdown using fake responses. Log evidence, checks, runtime, spend; omit secrets.
- **Gate:** later failed candidates preserve earlier validated fixes; time/spend exhaustion exits cleanly.
- **Checkpoint M2:** controller failure-path tests, actual A1/B1 pilot results when available, representative repair diff, remaining issues, and cumulative spend. You review the evidence and can redirect the final improvement cycle.
- **Pros:** reduces zero-score regressions and damaged deadline output. **Cons:** consumes diagnosis time.

### 4. Iteration 3: targeted improvement, image, freeze — minutes 80–100

- **Owners:** lead chooses one improvement from M2 evidence; relevant agent implements it; a different agent reviews; packaging agent builds and smoke-tests the candidate image.
- Use A1/B1 pilot evidence across both services; inspect contracts, diagnosis, diffs, runtime, spend. Rerun affected pilots after a meaningful change rather than duplicating unchanged checks.
- Fix controller/integration failures; keep practice-specific answers and grader internals out of runtime inputs.
- Build amd64 image with Python, PyYAML, pytest, required tools. Include only fixer/dependencies; read mounted corpus at runtime.
- Verify no-argument startup, arbitrary workspace paths, image size/architecture, read-only corpus, restricted-network/resource compatibility.
- Freeze candidate; launch full image grading by minute 100, earlier if possible. Avoid scheduling a fresh architectural rewrite here.
- **Gate:** candidate image starts and runs through the grader.
- **Checkpoint M3:** frozen source snapshot, image identity, controller tests, image smoke result, known limitations, and final suite handle/output directory. Present the candidate to you; preserve it while evaluation runs.
- **Pros:** catches container differences early. **Cons:** short pilots may miss complex multi-bug weaknesses.

### 5. Final evaluation and conditional iteration — minutes 100–160

- **Owners:** packaging agent monitors the specific live grader process and records results; validation agent investigates failures; tools agent prepares documentation evidence; lead manages remaining time and candidate selection.
- Grade six practice cases: A1 (1 bug), A2 (2), A3 (3), B1 (1), B2 (3), B3 (2): 12 total.
- Run one case and one evaluation worker at a time (`--concurrency 1 --eval-workers 1`) within the requested approximately 2 GB Docker VM. Each fixer remains within the assessment's individual resource allocation.
- Record fixes, tests/regressions, runtime, spend, timeouts, infrastructure failures. Inspect per-bug seed results in `eval.json`.
- Within the fixer: failing seed first, then public/additional seeds and relevant fault profiles; small determinism check. Use supplied scenario templates for targeted reproduction when necessary.
- Aim for 12/12 practice bugs; distinguish infrastructure problems from repair failures. Practice success does not establish hidden performance.
- Improve only if there is time to rebuild and grade the changed image. Every submitted image needs its own complete suite; unchanged-case results from another image are insufficient.
- Keep the M3 image intact while testing any new candidate. Use a new version tag and output directory; never mix results or overwrite evidence from different builds.
- Prepare documentation while evaluations run.
- **Gate:** inspected results for all cases on the exact final image; remaining failures documented.
- **Checkpoint M4:** six-case scorecard tied to one image, public/private regression outcomes, spend/runtime, infrastructure status, and reviewer findings. Retain the best fully evaluated candidate, not merely the latest code.
- **Pros:** measures the actual submission. **Cons:** grading may exceed this slot; prioritize finishing evaluation/packaging over more edits.

### 6. Handoff — minutes 160–180

- **Owners:** packaging agent assembles artifacts; lead and a second agent audit them; you inspect the final handoff and decide how to submit it.
- Record image identity; export tarball or supply registry reference. Include source/Dockerfile.
- Export actual lead and specialist build chat logs; runtime logs supplement them. Include a short manifest identifying each agent's role and relevant artifacts.
- Write half a page: mechanism, retrieval, validation/rollback, measured results, limitations, next improvements.
- Include reproduction commands and saved evaluation artifacts.
- **Gate:** requested artifacts exist; reported scores/cost/runtime match saved outputs.
- **Checkpoint M5:** image export/reference, matching source/Dockerfile, build chats, half-page write-up, reproduction instructions, and final status. Uploading or sending the submission remains a separate user-directed action.
- **Pros:** reproducible, reviewable handoff. **Cons:** requires protected time.

## Checkpoint contents and milestone tracking

- Maintain `solution/STATUS.md` during implementation; the lead owns it. Start every resumed agent task by reading the current status and inspecting relevant files/results.
- Track each milestone as **pending**, **running**, **verified**, or **blocked**, with timestamp, owner, evidence paths, remaining issues, next action, and remaining development time/credit.
- Store development checkpoints in ignored `evidence/checkpoints/<milestone-or-iteration>/`: source snapshot or exact version reference, diff, file hashes, configuration/prompt version, check outputs, image identity when available, and evaluation paths.
- Keep paid run outputs in unique `results/<run-id>/` directories. Never reuse another build's score without identifying its source/image version.
- Preserve existing user changes. Local checkpoint commits are optional; source snapshots do not require committing, resetting, or cleaning the repository.
- A milestone is **verified** only when its gate has direct evidence. If a check is still running, mark it running and retain its process/session handle. If it fails, capture the failure and assign the next investigation.
- Never restart an evaluation merely because its output is temporarily quiet. Inspect its live handle and state first.
- Keep credentials out of checkpoint metadata, logs, images, and chat exports; preserve requested build chats with secrets redacted if necessary.
- **Pros:** recoverable progress, clear supervision, reliable handoffs between agents.
- **Cons:** snapshot/log overhead; keep artifacts compact and outside the image build context.

| Milestone | Target minute | Evidence needed |
| --- | --- | --- |
| M0: ready to build | 15 | Proxy/grader plumbing, environment status, ownership/interfaces |
| M1: complete loop | 50 | Integrated autonomous tool/edit/check cycle and baseline evidence |
| M2: reviewed pilot | 80 | Failure-path tests, pilot findings/results, repair diff, next hypothesis |
| M3: frozen image | 100 | Source snapshot, image ID, smoke checks, final suite started |
| M4: evaluated candidate | 160 | All six inspected results tied to the final image |
| M5: handoff ready | 180 | All submission artifacts and matching, evidence-backed write-up |

- Targets are planning estimates; unmet gates remain visible. If final evaluation overruns, stop tuning, finish independent packaging work, and report actual status to you. Do not claim the assessment is ready while required verification is incomplete.

## Runtime iteration and checkpointing

- Start with three parallel read-only investigators: `state-recovery`, `leases-membership`, and `delivery-commit`. Give them distinct focus areas and the same bounded case context; merge evidence before editing.
- The submitted fixer repeats its own autonomous loop within each 900-second case: gather evidence → diagnose an issue → retrieve contract → patch → validate → checkpoint or rollback → inspect remaining issues.
- Cap the initial prototype at six model calls per investigator and fourteen editor rounds, with shared budget reservations. Keep repair edits serialized; parallel discovery does not authorize concurrent source mutation.
- Cap investigation reservations at 45% of the shared budget and stop discovery after 35% of initial usable time, preserving editor allowance. Baseline and candidate checks use up to two public seeds; reject new invariant categories relative to each retained seed result.
- Track each issue separately; later repairs must preserve earlier successful ones, including prerequisite fixes in chained cases.
- Before accepting a candidate, verify syntax, baseline-passing tests, original failing-seed behavior, and relevant previous repair checks. Broaden seeds/faults and run determinism checks as time allows.
- Persist the latest validated `src/` snapshot in case-local scratch storage; track applied files, unresolved issues, checks, remaining budget, and deadline allowance.
- Keep staged edits separate until ready to apply; handle interrupted multi-file candidates by restoring the validated checkpoint where time permits. Keep final source valid throughout the run.
- Stop proposing new edits before the measured shutdown allowance; finish checks or restore the last supported candidate and exit before the deadline.
- Runtime checkpoints exist only within that fresh case; carry no case data or learned patches into another evaluation case.
- **Pros:** multiple repair attempts with protected partial progress. **Cons:** checking and checkpointing consume runtime; prioritize checks by affected behavior and retain the final reserve.

## Commands and spend

```sh
docker build --platform linux/amd64 -t c3-fixer-main-baseline:noop fixers/examples/noop
./solution/grade-docker.sh --fixer c3-fixer-main-baseline:noop --cases practice \
  --concurrency 1 --eval-workers 1 --out results/prototype-main-baseline
docker build --platform linux/amd64 -t c3-fixer-prototype:v2 solution/fixer
./solution/grade-docker.sh --fixer c3-fixer-prototype:v2 --cases practice \
  --concurrency 1 --eval-workers 1 --keep --out results/prototype-v2-all
docker image inspect c3-fixer-prototype:v2 --format '{{.Os}}/{{.Architecture}} {{.Size}} {{.Id}}'
docker save -o c3-fixer-prototype-v2.tar c3-fixer-prototype:v2
```

- Six case budgets total **$36 maximum per full suite**; actual usage determines spend. Pack allowance: $150; verify remaining credit before repeats.
- Initial development caps: $15 setup, $45 development, $45 final evaluation/repeats, $45 contingency. Runtime case limits remain separate.
- The lead maintains one spend ledger across all agents/runs. Development-agent calls may have separate billing from the supplied proxy credit; report them separately when available and avoid duplicated paid experiments.
- **Pros:** protects final evaluation capacity. **Cons:** limits speculative experiments; adjust using measured costs.
- If only two hours are available: limit development to two iterations, target image freeze by minute 60, then overlap final evaluation with documentation/export. Preserve reliability, full image evaluation, and required artifacts; actual completion still depends on measured evaluation duration.
- If fewer development worker slots are available, combine tools/retrieval and validation roles; retain lead ownership and independent review where possible. Runtime investigation remains parallel as requested.
- **Uncertainty:** grading/model/build duration is unmeasured. Start long checks early; never report unfinished checks as passed.
