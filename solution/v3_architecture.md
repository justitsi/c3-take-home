# Improvements to the C3 Agentic Bug-Fixer Plan

**Goal:** Improve hidden-case bug-fixing success and runtime efficiency without overengineering the harness.

**Main finding:** The current approach emphasises generating and testing patches, but needs a stronger mechanism for establishing the root cause before editing code.

> No approach can guarantee correct repairs for every unseen bug. These changes aim to improve the likelihood of correct diagnosis, reduce wasted iterations and catch incorrect patches.

## Improvements ranked by impact

| Priority | Improvement | Rationale |
|---|---|---|
| 1 | Hypothesis-driven debugging | Reduces incorrect patches and wasted retries. |
| 2 | Adaptive simulator testing | Explores more distinct failure scenarios within the same budget. |
| 3 | Failure-aware agent control | Responds to what actually failed instead of arbitrary retry counts. |
| 4 | Semantic patch verification | Reduces fixes that pass visible tests but violate the intended contract. |
| 5 | Hierarchical code and documentation retrieval | Improves diagnosis while limiting context and token usage. |
| 6 | Evidence-based budget allocation | Directs computation towards the most informative next step. |

## 1. Add hypothesis-driven debugging before patching

**Current workflow:**

```text
Observe failure -> Retrieve code -> Generate patch -> Test
```

**Improved workflow:**

```text
Observe failure -> Generate hypotheses -> Test hypotheses -> Patch -> Verify
```

Have Claude propose **two or three plausible root causes**, together with the observable result expected if each is true. For example:

| Hypothesis | Discriminating evidence |
|---|---|
| Duplicate delivery triggers double processing | The same request ID reaches the commit operation twice. |
| Acknowledgement occurs before durable commit | A crash between acknowledgement and commit loses the work. |
| A retry reads stale state | The trace shows the retry observing an outdated version. |

Choose the **cheapest available experiment** that distinguishes the hypotheses. Depending on what the challenge simulator allows, this might be a particular seed, targeted logging, or fault injection.

Do **not** impose an expensive hypothesis phase on obvious failures. If the root cause is already well supported, patch immediately.

**Benefit:** Fewer patch attempts based on faulty assumptions, and a clearer audit trail explaining *why* each change was made.

## 2. Replace undirected random-seed testing with adaptive testing

Maintain three pools of tests:

1. **Known failing seeds** — reproducible examples of the original defect; always retest them.
2. **Regression seeds** — scenarios that passed before a patch and must remain correct.
3. **Exploration seeds** — new and varied scenarios, ideally selected to expose failure mechanisms the harness has not yet checked.

If the simulator provides relevant controls, bias exploration toward the suspected mechanism: process crashes near acknowledgements, duplicated messages, message reorderings, or competing updates.

Record a **failure signature** for each distinct failure (first violated invariant, operation, relevant stack or trace excerpt). Avoid repeatedly paying to diagnose an already-understood failure.

The objective is **coverage of different failure mechanisms**, not merely running the largest number of random seeds.

This follows the reproducible, deterministic-simulation principles employed in distributed-systems testing such as FoundationDB's testing framework. See [FoundationDB: Simulation and Testing](https://apple.github.io/foundationdb/testing.html).

## 3. Make the agent controller failure-aware

A rule such as “start a fresh diagnosis after every third failed patch” is arbitrary. Instead, route on the observed outcome:

| Validation outcome | Next action |
|---|---|
| Compilation or syntax failure | Correct the patch mechanically; avoid an expensive new diagnosis. |
| Original failure persists | Reconsider the root cause or look for missing evidence. |
| A previously passing test regresses | Inspect the violated contract, revert or revise the candidate. |
| A new seed reveals a distinct failure | Investigate the new event interleaving or failure mechanism. |
| All visible tests pass | Broaden validation and review semantic correctness. |

Keep **local repair** and **fresh diagnosis** as separate operations. A fresh diagnosis should start from the original code (or a known-good checkpoint) with the accumulated evidence, not from a chain of failed patches.

**Benefit:** Trivial errors get cheap corrections; flawed theories don't consume the whole budget.

## 4. Add semantic verification of candidate patches

Passing visible tests is **necessary but not sufficient** to establish correctness. Automated program repair is prone to test overfitting; see [Invalidator](https://arxiv.org/abs/2301.01113) for work on identifying semantically incorrect patches.

For promising patches, run a short independent review of the **diff, incident report, original failure evidence and relevant contracts**. Ideally, the reviewer should not see the original patch author's justification.

Ask the reviewer to check whether the patch:

- Corrects the cause rather than suppressing a symptom or disabling a check.
- Preserves both **safety** properties (nothing bad happens) and **liveness** properties (required progress remains possible).
- Handles retries, crashes and concurrent execution consistently.
- Relies on undocumented assumptions.

This review is a supplement to simulator tests, **not a proof** of correctness. Prioritise concrete counterexamples and contract violations over an ungrounded “looks correct” verdict.

## 5. Improve code and documentation retrieval

Use progressively broader searches rather than always loading large volumes of source or documentation:

| Level | Retrieval method |
|---|---|
| **1. Exact evidence** | Search identifiers, exception names, log strings, API names and referenced functions. |
| **2. Structural neighbourhood** | Follow callers and callees, state writes, dependency boundaries and directly referenced contracts. |
| **3. Broad search** | Use wider keyword or semantic retrieval only when focused searches fail. |

A lightweight local search index such as **SQLite FTS5** may be sufficient for a supplied document corpus; evaluate it before adding a vector database.

Preserve the **source path and section** of retrieved passages so the agent can assess which rule is authoritative and avoid mixing unrelated documentation.

Most importantly, **retrieve relevant contracts again when the working hypothesis changes**. A single retrieval pass at the start may miss the rule that determines the correct fix.

## 6. Make time and model-cost allocation adaptive

Do not assume a fixed fraction of the time belongs to diagnosis, patch generation or testing. Instead, log time and cost spent in each phase and make the next decision based on current evidence:

| Current state | Priority |
|---|---|
| No reproducible failure | Investigation and exploratory simulation. |
| Root cause supported by clear evidence | Produce a minimal candidate patch. |
| Candidate passes the original reproducer | Expand regression and robustness testing. |
| Repeated attempts support the same unsuccessful theory | Restart diagnosis or collect discriminating evidence. |

Reserve adequate time and budget for final validation. Generally run the **fastest, most diagnostic test first**, followed by broader suites. Estimate which available test is most likely to reveal a new defect *per second*.

Regression test selection is an established optimisation topic in automated program repair; the specific benefits depend on the simulator and case characteristics.

## 7. Revised controller pseudocode

```python
def repair(case, budget):
    evidence = investigate(case)
    hypotheses = diagnose(evidence)

    best = None

    while budget.can_attempt():
        hypothesis = choose_hypothesis(hypotheses)

        if hypothesis.needs_evidence:
            evidence += run_discriminating_test(hypothesis)
            hypotheses = update_hypotheses(evidence)
            continue

        candidate = generate_patch(hypothesis, evidence)

        result = staged_validation(
            candidate,
            known_failures=evidence.failures,
            held_out_seeds=select_diverse_seeds(),
        )

        if result.improves_without_regression:
            best = checkpoint(candidate)

        if result.justifies_broad_validation:
            if validate_semantics_and_regressions(candidate):
                return candidate

        evidence += result.counterexamples
        hypotheses = update_hypotheses(evidence)

    return best
```

**Important implementation caveat:** This is conceptual pseudocode, not a complete safe acceptance policy. In the real implementation:

- Track validation status **per immutable patch/checkpoint**.
- Do not equate a partially validated candidate with a verified fix.
- Revert failed edits before exploring a different hypothesis.
- Preserve the original reproducer and all known regression tests.
- Respect the actual challenge time, memory and token limits.
- Define a final return policy that does not submit an unverified partial patch as a confirmed fix.

## 8. Suggested implementation order

Start with these three changes:

1. **Hypothesis-driven debugging** with cheaply testable predictions.
2. **Adaptive seed selection**, keeping reproducible counterexamples and distinct failure signatures.
3. **Failure-aware retry routing**, distinguishing syntax errors, persistent failures, regressions and new interleavings.

Next add a short **independent patch review** and more advanced retrieval **only if measured practice-case performance warrants them**.

Do not start by implementing multi-agent orchestration, a vector database or a full custom model checker. These add cost and complexity without guaranteed benefit.

## 9. Prerequisite: verify C3's actual challenge contract

The recommendations above assume a simulator-driven repair task. Before tuning the system, confirm the following in the [C3 take-home repository](https://github.com/c3-research/c3-take-home):

- Exact execution time, token/model-spend, CPU and memory limits.
- The runtime interface and supported tools.
- Simulator commands, seed semantics and fault-injection controls.
- Whether instrumentation, local indexing, parallel executions and worktrees are permitted.
- The scoring rules and what constitutes a successful repair.

The preceding discussion could not independently verify the repository's contents; numerical limits previously mentioned must **not** be treated as confirmed.

## Bottom line

**Optimise for correctly diagnosed failures, not patches generated.** The main upgrade is to create an explicit cycle of *hypothesis → discriminating evidence → minimal patch → targeted and broad verification*. Measure each addition against the practice cases and retain only improvements that raise the full-case success rate without unacceptable runtime cost.

## References

- [C3 take-home repository](https://github.com/c3-research/c3-take-home) — authoritative source for challenge rules; verify locally.
- [FoundationDB: Simulation and Testing](https://apple.github.io/foundationdb/testing.html) — deterministic failure reproduction and simulation.
- [Invalidator: automated detection of incorrect program repairs](https://arxiv.org/abs/2301.01113) — motivation for semantic checks beyond passing tests.
