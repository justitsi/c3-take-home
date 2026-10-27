# Write-up: autonomous bug fixer (V3.2)

**Overview.** A Python controller that repairs distributed services without human input. It edits only `src/` and uses Claude Sonnet 4.6 through the supplied proxy.

**How it works**
1. *Probe.* Run public tests, then replay every fault profile. Profiles that violate invariants or show a ticket-named log token become pinned probes, since public seeds can pass while the reported bug does not.
2. *Investigate.* Read-only investigators (one per numbered ticket report, plus recovery, membership and delivery) register hypotheses, run replay experiments and end with a structured conclusion.
3. *Edit.* One editor makes small edits in rounds: a focus round per report, then residual rounds that must submit a candidate while violations remain. Harness-built timelines show what state stuck work left behind.
4. *Verify.* Each candidate must pass syntax, tests, invariants and determinism, and is replayed on the probes. It is rejected if a probe gains violations. Rejected edits are rolled back.

Budget reservations and timeouts bound cost and time. The image contains no case-specific repairs.

**Results.** The earlier V1 build was fully evaluated at 9/12 practice bugs. V3.2 targets V1's weaknesses: early-stopping investigators, one-sided fixes to two-sided protocols, and bugs the public seeds do not expose. Local single runs: A1 1/1, A2 2/2, A3 3/3 (on V3.1); B2 ranged from 1/3 to 3/3. A3 and B1 were not rerun on the final build and B3 had no valid run, because the model API returned HTTP 403. There is no full six-case result for V3.2 and no claim about unseen cases. 88 offline tests pass.

**Next steps**
1. Run the exact image on all six cases, repeated, to measure variance.
2. Implement the B1 diagnosis (commit decided by output equality, not task identity) and the B3 one (heartbeat sequence kept across restarts; cross-clock staleness check).
3. Keep multi-seed regression guards for the whole run.
4. Audit every "ignore this message" check for liveness starvation, and test two-sided protocol changes together.
