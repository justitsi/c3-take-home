# V3 proposal review and implementation plan

- **Scope:** local review of all 205 lines of [v3_architecture.md](v3_architecture.md), current controller code, and saved evaluation evidence. Preserve the supplied proposal unchanged.
- **Now:** bounded R4 corrections under lead ownership; major architecture changes below are **planning only**. They are not authorized implementation, a new branch, or a merge/push request.
- **Objective:** more correctly repaired bugs per allowed run, then lower runtime/cost. Neither public checks nor this plan guarantee every supplied or unseen bug will be fixed.
- **Evidence boundary:** V1 remains the complete baseline: **9/12**, $5.850678. R1's B2/B3 pilot scored **1/5**; R2 scored **2/5**, but B3's rollback failure/new regressions make it nonpromotable. Frozen R3 `2096b49` passed **278 offline tests**; its inspected B2 result is **0/3**, no retained patch, exit 0, passing baseline-relative gates. That one case is not a complete R3 score.
- **Sources:** [local assessment README](../README.md), [RULES.md](../RULES.md), [V1 scorecard](benchmarks/v1-final-evaluation.json), [R2 pilot](benchmarks/v2-r2-pilot.json), [R3 image/tests](benchmarks/v2-r3-image.json), [R3 B2 result](results/v2-r3-cases/B2-session/B2/result.json). Proposal paper links are unverified background, not evidence of benefits here.

## Contract and operating limits

- Read actual workspace/corpus/deadline/budget environment settings; maximum **900 seconds per case**, **$3 per bug**, **2 CPUs/4 GB per fixer**. Runtime models: Sonnet 4.6 and optional Jev, through the supplied proxy only.
- Only `src/` changes count. Preserve provided tests, simulator, scenarios, corpus and grader. A credited bug passes its targeted scenario on **all 20 hidden practice seeds**; new baseline-passing test failures can zero its case. Determinism remains mandatory.
- Submission image: `linux/amd64`, no-argument entry point, Python >=3.12/PyYAML/pytest installed during build, <=4 GB. Fresh case containers; no cross-case repair state.
- Local VM remains **1,973 MiB/4 CPUs**. Latest schedule: at most **three separate active case sessions**, one case/evaluation worker each; monitor measured memory. Runtime read-only investigators remain parallel; source mutations remain serialized.
- New repository code, logs, scorecards, chat exports and image artifacts stay under `solution/`. Preserve existing V1 artifacts and frozen candidate tags. No V2/V3 main merge, push or submission without a new user request.

## Already present: retain and measure

- **Decision: extend the current harness, avoiding a parallel replacement architecture.**
  - Evidence/issue ledgers, revision labels, compaction and fresh diagnosis: `Harness.remember_evidence`, `update_issues`, `editor_messages` in [fix.py](fixer/fix.py).
  - Protected public/scenario/fault registry, passing guards, invariant categories, deterministic repeats and final restoration: `required_specs`, `apply_candidate`, `final_validation`.
  - Bounded trace AND/paging: [artifacts.py](fixer/artifacts.py). Trusted original-to-current `source_diff`: [tools.py](fixer/tools.py); model cannot select its checkpoint path.
  - Write-once hashed derived probes: [probe_authoring.py](fixer/probe_authoring.py); scenario identity/hash checked before replay. Read-only independent contract review and bounded editor follow-up already exist.
  - Shared budget reservations, output bounds, truncated-reply rejection and bounded transient retries: [model.py](fixer/model.py). Targeted current-contract lexical retrieval: [retrieval.py](fixer/retrieval.py).
  - **Pros:** preserves tested containment/rollback and avoids duplicated work. **Cons:** existing ledgers, review and higher round limits have not established a better complete score; mechanical presence is not empirical success.

## Minor R4 work: current window only

- **Decision: recover from truncation with an explicit completion flag.** Lead owns implementation in `model.py`/`fix.py`; independent reviewer owns adversarial checks.
  - Preserve the rule that partial/truncated tool calls never execute. Return an explicit complete/incomplete outcome; retry narrowly with shorter output while accounting for the charged response and remaining allowance.
  - Distinguish provider output truncation from locally clipped evidence; preserve evidence handles/paging instead of treating clipped JSON as complete.
  - **Pros:** prevents a supported repair from dying on response shape/output size. **Cons:** retries consume tokens and may repeat truncation; cap attempts and never waive parsing/validation.
- **Decision: retain rejected counterexample citations through compaction.** Store bounded invariant/check identity, observed revision, trace/summary aliases and rejection reason beside the candidate.
  - Keep rejection evidence after restoring source; mark it as evidence from the rejected revision. Do not replace current passing guards with that revision's results.
  - **Pros:** later diagnosis can investigate the actual rejection. **Cons:** historical artifacts can mislead or fill context; keep revision labels and bounded excerpts.
- **Decision: request early independent review after 12 read-only rounds without a candidate.** Reuse the existing read-only reviewer; bounded trigger, shared budget/deadline, no new swarm.
  - **Pros:** challenges unsupported theories before the initial 55-round allowance is consumed. **Cons:** reviewer overhead/anchoring may remain; require contract citations and a concrete discriminating probe.
- **Decision: check audited completion before a fresh restart.** First test current revision's required coverage, issue evidence and completed audit; a stale/claimed issue status cannot certify completion.
  - **Pros:** avoids resetting a completed investigation. **Cons:** an overbroad completion flag can hide residual symptoms; final deterministic validation and explicit unresolved status remain required.
- **Timebox/checkpoint:** about 10–15 minutes of focused implementation/review, then lead-serialized offline Docker checks and a new frozen R4 tag. These changes are **in progress/planned**, not covered by R3's 278-test evidence. Do not disturb confirmed live R3 sessions or mix their scores with R4.
- **Current stop rule:** protect the user's 30–60-minute deadline. No major work below in this window. Keep incomplete case coverage visibly pending; complete official checks/artifacts when time permits and report exact remaining gaps.

## Major work: future implementation decisions

### P1 — competing hypotheses with discriminating predictions

- **Decision:** add a small optional hypothesis list to each ambiguous issue: 2–3 alternatives, source/contract citations, expected distinguishing observation, cheapest check specification, result and revision.
- Skip the comparison phase when existing evidence supports one clear cause; do not generate speculative alternatives to fill a quota.
- Prefer a bounded source/trace query over a replay when it can distinguish the alternatives. Choose experiments with different predicted outcomes; duplicate tests do not discriminate.
- Record unsupported, contradicted and inconclusive predictions separately. Model confidence is not acceptance evidence. On a changed theory, retrieve the relevant current contract again.
- **Pros:** makes diagnosis falsifiable and reduces unsupported patch churn. **Cons:** extra schema/prompt/context cost; wrong predictions or absent trace events can mislead.
- **Dependencies/owner:** lead extends issue/controller state; tools agent supplies evidence handles. Preserve existing ledger compatibility and scope limits.
- **Timebox/gate:** 25–35 active minutes for a first bounded implementation after authorization; tests for obvious-cause bypass, competing predictions, stale revisions and inconclusive evidence. Then measure changed diagnosis/repair behavior on a frozen candidate.

### P1 — outcome routing and staged validation

- **Decision:** use explicit observed outcomes instead of only retry/round counts. Proposed routing:
  - Malformed/truncated reply: execute nothing; narrow output/recover locally.
  - Syntax/import failure: restore failed candidate; request a mechanical correction.
  - Original reproducer persists: revise predictions or obtain missing evidence.
  - Previous pass regresses/new invariant appears: restore checkpoint; inspect diff/contract and preserve the rejection counterexample.
  - New mechanism fails: record a distinct failure and targeted hypothesis; retain existing guards.
  - Public checks pass: independent review, distinguishing probes, then final required coverage.
  - Insufficient allowance: stop new edits, validate/restore best supported source, report partial/incomplete coverage honestly.
- Order fast diagnostic checks before broad checks to reject bad candidates sooner. **Do not weaken retention:** full required check execution, passing public tests, deterministic-repeat gate, previous passes and invariant-category protections remain mandatory. Supported partial repairs can retain unrelated original failures; they are not full fixes.
- Preserve the **best validated checkpoint**, accumulated evidence and protected checks during fresh diagnosis. Never blindly reset to original source and erase valid repairs.
- **Pros:** cheap corrections stay cheap; diagnosis changes follow evidence. **Cons:** misclassified outcomes can cause loops or suppress a real new failure; expose routing reasons and use a conservative unknown branch.
- **Dependencies/owner:** lead owns routing/types; validation agent supplies structured outcomes and acceptance tests. Coordinate interface changes before parallel edits.
- **Timebox/gate:** 25–40 active minutes; adversarial outcome/rollback/partial-fix tests and ordering tests that prove acceptance requirements remain unchanged. No promising-but-partially-checked candidate is promoted to a verified checkpoint.

### P2 — mechanism-diverse exploration and failure signatures

- **Decision:** maintain known failing reproductions, protected passing regressions and bounded exploration as separate scheduling pools. All remain revision/scenario/fault aware.
- Build signatures from available invariant, operation/transition, role and a bounded causal excerpt; store seed/scenario/fault/revision provenance separately. Normalize incidental IDs/times, but keep distinct operations/mechanisms separate; missing fields mean unknown, not identical cause.
- Choose exploration from **supported** scenario schema, provided fault profiles and constrained derived probes. Examples to consider only when available: crash/restart boundaries, ambiguity/loss, duplication/order, stale incarnations, cancellation/cleanup and liveness. Unsupported controls are recorded, not invented.
- Retest original failures and every protected pass for candidate acceptance. New seeds alone do not establish mechanism diversity; deduplicate repeated signatures without deleting their regression guards.
- **Pros:** targets untested causal boundaries and avoids repeated diagnosis. **Cons:** signature collisions, scenario-construction errors and exploration cost; cap registry, artifact size and runs.
- **Dependencies/owner:** tools agent owns generic signature/scheduler helpers; validation owns scenario identity/replay; lead selects next checks. Reuse immutable probes, not practice-specific repair knowledge.
- **Timebox/gate:** 30–45 active minutes; schema/unsupported-fault tests, collision/unknown-field fixtures, preserved reproducer/pass coverage and deterministic probes. Measure marginal new failures per replay-second, then official repaired bugs.

### P2 — measured adaptive time/spend allocation

- **Decision:** instrument phase/model/tool durations, actual/estimated cost, cache tokens, useful observations, rejected candidates, repeated signatures and final-validation time before changing allocation.
- Start with retrospective summaries from existing logs. Later prefer the cheapest supported next action: reproduce an unknown fault; test a discriminating prediction; patch an evidenced cause; broaden a promising repair; seek independent review after unproductive repetition.
- Keep shared concurrent reservations, proxy limits, uncertain-charge accounting and a hard final-validation floor. Adapt within those constraints; do not turn estimated success-per-second into a correctness claim.
- **Pros:** replaces arbitrary phase fractions with observed costs. **Cons:** noisy estimates and instrumentation overhead; a bad allocator can starve validation or overreward cheap irrelevant work.
- **Dependencies/owner:** packaging/evidence agent derives metrics; lead implements one allocation change only after outcome/scheduler data exists.
- **Timebox/gate:** 15–25 active minutes for metrics first; allocation is a separate later checkpoint. Reject policies that reduce protected coverage or increase deadline/budget failures.

### P3 — progressive structural retrieval; selective FTS experiment

- **Decision:** expand exact identifiers/log/API searches into bounded caller/callee, state-write and adjacent-contract neighborhoods before broad retrieval. Refresh contract queries when the hypothesis changes.
- Retain filename/section/line/version status and source revision. Dynamic calls or incomplete indexes require lexical/manual fallback; an absent edge is not evidence of no dependency.
- **Pros:** higher-signal context and fewer missed boundaries. **Cons:** Python dynamic dispatch and broad call graphs can inflate context; cap depth/files and request explicit widening.
- **Owner/dependencies/timebox:** tools/retrieval agent, after hypothesis/query metrics; 20–30 active minutes for one structural level plus synthetic renamed-service fixtures.
- **Decision:** only after a measured lexical retrieval gap, trial lazy SQLite FTS5 over selected current service/platform documents. Check image support, cap index build/time/size, keep it case-local and use lexical fallback. Do not index the entire 26M-token corpus at startup.
- **Pros:** local, inspectable ranking with no embedding service. **Cons:** indexing startup cost, FTS availability and lexical misses; metadata ranking still determines authority.
- **Gate:** a small retrieval query set improves citation relevance/recall within bounds, followed by a frozen-image repair comparison. Defer vectors, embeddings, orchestration frameworks and corpus-wide indexing absent measured benefit.

## Agent ownership and sequencing

- **Lead/integration:** controller, hypothesis/outcome schema, budget policy, freeze/version selection. One owner for `fix.py`; integration changes are sequential.
- **Tools/retrieval specialist:** signature/probe selection and structural retrieval modules with focused fixtures; no independent controller edits.
- **Validation/reliability specialist:** complete execution/guard/rollback/outcome tests; independent review of lead acceptance and deadline changes.
- **Packaging/evidence specialist:** reproducible image/case sessions, metrics, comparison scorecards, source/image hashes, README/write-up/chat handoff.
- Agree small schemas first; parallelize implementation and independent fixtures, not source mutation or uncontrolled Docker workloads. Handoffs: files, observed behavior, checks/artifacts, limits, next experiment. Reuse agents; avoid duplicated paid runs.
- Major timeboxes above are **future estimates**, not a promise to fit all features into the current deadline. Change one major strategy per measured checkpoint; stop or narrow an unproductive experiment, preserving the last verified version.

## Checkpoints and empirical gates

1. **C0 — proposal mapped:** this plan, local contract, current-source/evidence gaps. Proposal/research claims remain distinct from implementation proof.
2. **C1 — minor R4 frozen:** focused/adversarial Docker checks, real host-bind rollback, truncation/complete flags, rejection citations, review trigger and audited-stop behavior; exact source/image identity. R3 evidence cannot certify R4.
3. **C2 — bounded pilot:** inspect official per-bug seeds, gates, exit/timeout/infra, patches, final coverage, cost/time and stop reasons. Partial pilots diagnose weaknesses; they do not establish full promotion.
4. **C3 — future major increment:** one hypothesis, change, independent review and offline acceptance proof; preserve prior candidate. Separate diagnosis quality metrics from repaired-bug score.
5. **C4 — full comparison:** all six cases on one exact image; every credited bug 20/20 targeted seeds, no new baseline-passing regressions, comparable bug/seed sets, clean exits/timeout/infra, internally consistent scores. Never combine R3/R4/later case scores to fabricate one candidate.
6. **C5 — handoff:** source/Dockerfile/image identity/export, scorecards, observed gaps, explicit incomplete gates and redacted build chats with cutoff/hash manifest, all new artifacts under `solution/`. Remain on the requested branch; quality evidence does not authorize merge/push.

- Freeze early enough for actual evaluation and artifacts; simulation/build duration is variable. Preserve confirmed live session handles, poll them instead of restarting on quiet output, and report unfinished checks as unfinished.
- Keep whichever fully evaluated candidate best satisfies the user's objective. Higher test counts, more agents, more hypotheses, or longer investigation are not evidence of improved repair success.
