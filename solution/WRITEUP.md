# Final write-up — autonomous repair prototype

The selected deliverable is **V1**, `c3-fixer-prototype:v1-final`, also tagged `c3-fixer-prototype:best-verified`. It fixed **9 of 12 practice bugs across all six cases**, spending **$5.850678** with **991.650 seconds** summed fixer runtime. Every credited bug passed its targeted scenario on all 20 hidden practice seeds. Public and baseline-relative regression gates passed; independent review checked all 240 repeated trace pairs for determinism. These results do not guarantee unseen-service performance.

The fixer is a small Python controller packaged in a `linux/amd64` Docker image. Dependencies are installed during build; the no-argument entry point reads workspace, corpus, deadline, budget and proxy settings from the environment. Fresh case containers share no repair state. Runtime uses permitted Sonnet 4.6 through the supplied proxy.

Three parallel read-only specialists investigate recovery, leases/membership and delivery/commit. They gather bounded source, incident and current-contract evidence; one editor makes serialized repairs. Candidate validation checks syntax, baseline-passing tests, simulator invariants and deterministic replay. Rejected/interrupted candidates restore validated source. Shared model reservations, bounded subprocesses and shutdown reserve protect spend/deadline. V1's finite editor and seed coverage remains a limitation.

The remaining practice bugs concern heartbeat/forbidden-cancellation reconciliation, ambiguous-submit liveness and registration amplification. Public tests did not expose every protocol obligation.

V2 experiments added contained trace inspection, retained evidence, broader guards, derived probes and independent contract review. They also exposed and fixed a bind-mount rollback defect. Frozen R4 passed 287 offline controller tests and scored 4/6 on three uninterrupted cases; a separately interrupted A2 snapshot scored 2/2. A3/B1 were not evaluated. This is not a complete improvement comparison, so V1 remains selected; V2 source and failed/partial results are preserved transparently.

Next work would prioritize falsifiable hypotheses, mechanism-diverse probes with verified events, failure-aware routing and lower diagnosis overhead, followed by a complete exact-image comparison. The upload includes matching V1 source/Dockerfile, the preserved image, evidence and redacted public build chats. [Future work](<future work.md>) records unfinished tasks.
