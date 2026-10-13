# Future work plan

These are proposals, not features of the selected V1 image. The supplied
[V2 architecture](v2_architecture.md) and [V3 architecture](v3_architecture.md)
are copied unchanged from `solution/prototype-v2`. Their suggestions are
guidance; the assessment rules and measured results take precedence. The original
proposals are exempt from the limits on rewritten, authored write-ups.

V1 remains the selected fully evaluated version: **9/12**. V2 implementation and
partial evaluation history remain on the V2 branch; no full V2 comparison or
unseen-case guarantee is claimed.

## Priorities and checkpoints

1. **Evidence access and continuation:** bounded trace inspection, retained
   observations and passing guards; stop from evidence/time/budget, not only
   round count. Pros: less rediscovery, protected progress. Cons: context and
   validation overhead.
2. **Hypothesis-driven diagnosis:** compare a few plausible causes using the
   cheapest distinguishing query/probe. Skip this step for clear causes.
   Pros: falsifiable reasoning. Cons: extra prompts can delay simple repairs.
3. **Mechanism-diverse tests:** preserve original failures and known passes;
   explore supported crash/retry/reordering boundaries and verify the intended
   events occurred. Pros: stronger coverage. Cons: finite budgets and imperfect
   probe selection; more seeds alone do not prove diversity.
4. **Outcome-aware routing and independent review:** distinguish syntax errors,
   unchanged failures, regressions and new counterexamples. Review both ends of
   changed protocols. Pros: targeted follow-up. Cons: reviewers can still err.
5. **Measured selection:** freeze one change, run adversarial offline checks,
   pilot the exact image, then grade all six cases and audit every credited
   20-seed result, regression gate, hash, cost and timeout. Replace V1 only after
   a comparable improvement; never pool scores across images.

Use separate owners for controller, tools, validation and packaging; serialize
shared edits. Preserve the last verified candidate at every checkpoint. Further
implementation/paid evaluation needs renewed user direction; no push or external
submission is authorized here.

Historical working notes are in [progress/](../progress/README.md).
