# Final write-up — autonomous bug fixer (V1)

This program repairs distributed Python services without human input during a run. It receives an isolated service workspace, an incident report, logs, public tests, a deterministic simulator and read-only documentation describing the service's intended behavior. Its output is changes to the service's `src/` directory—not changes to tests or the simulator.

## How a repair works

1. **Establish the starting state.** The controller runs public tests and simulator checks, then gathers relevant source, log excerpts and current contracts. Public tests can already pass while the reported bug remains.
2. **Investigate in parallel.** Three read-only Sonnet 4.6 agents examine recovery, leases/membership and message delivery/commit. They return suspected causes, supporting evidence and suggested repairs; they cannot change source.
3. **Repair sequentially.** One editor checks those hypotheses against the code, proposes small exact-text changes and uses test/simulation feedback to address remaining issues.
4. **Keep or undo each candidate.** The controller checks Python syntax, public tests and up to two configured public simulator seeds, repeating one replay to compare trace hashes. It rejects incomplete checks, demonstrated regressions and newly introduced invariant categories. Accepted changes become saved source checkpoints; rejected changes restore the previous checkpoint. Partial repairs can be retained while original failures remain.

## Code and execution

`fixer/fix.py` coordinates agents, edits and checkpoints. `retrieval.py` selects bounded documentation excerpts; `tools.py` exposes contained reads/searches and source-only edits; `validation.py` runs checks and restores source; `model.py` handles the proxy and shared model budget.

The no-argument Docker entry point reads workspace, corpus, deadline and budget settings from the environment. Shared spending reservations, subprocess timeouts and a shutdown reserve limit resource use. Cases start fresh and carry no repairs between runs. The image contains no practice-specific answers; dependencies are installed at build time.

## Results and limitations

The selected `c3-fixer-prototype:v1-final` image fixed **9/12 practice bugs across all six cases**, costing **$5.850678** with **991.650 seconds** summed fixer runtime. Each credited bug passed all 20 targeted hidden practice seeds. Public/baseline-relative regression gates passed; reviewers audited all 240 repeated trace pairs. The offline suite passed 62 tests.

Three bugs remain: heartbeat/cancellation reconciliation, ambiguous-submit liveness and registration amplification. V1's fourteen editor rounds and limited seed coverage can stop useful investigation early; its inspection tools cannot read generated scratch traces.

V2 experiments added stronger diagnostics, broader guards and independent review, but did not complete a comparable six-case evaluation. V1 therefore remains selected. Next steps are distinguishing protocol probes, evidence-driven continuation and complete exact-image evaluation. Unseen-service correctness is not guaranteed.
