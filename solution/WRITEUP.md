# Prototype v1 write-up

This Python prototype runs as a Linux/amd64 Docker image against a fresh service
workspace and read-only corpus. Three parallel Sonnet 4.6 investigators inspect
source, logs, invariants, and targeted documentation for recovery, membership,
and delivery/commit failures. A repair agent combines their evidence, edits only
`src/`, and iterates using public tests and deterministic simulator replay/check
feedback. Edits and validation are serialized; checkpoints protect useful
earlier repairs when a later candidate fails or resources run out.

Standard-library HTTP, bounded retrieval, compact findings, cached prompt
prefixes, and shared budget reservations control overhead. Timeouts, a shutdown
reserve, SIGTERM handling, and an `exec` entry point support the grader's deadline
contract. Dependencies are installed at build time. Cases share no runtime
state; the image contains no practice-specific patches or grading data.

The frozen `c3-fixer-prototype:v1-final` image fixed 9/12 practice bugs: A1 1/1,
A2 2/2, A3 3/3, B1 1/1, B2 1/3, B3 1/2. Each credited bug passed all 20 hidden
practice seeds. All baseline-relative test/regression gates passed, with no
timeout or infrastructure error. Cost was $5.850678 and total fixer runtime
991.65 seconds; 84.4% of input tokens were cached. This exceeds original main's
no-op baseline of 0/12 and satisfies the conditional integration gate. Cases
and evaluation workers ran serially on the unchanged approximately 2 GB Docker
VM; model investigation remained parallel. The offline suite passed 62 checks.

Three misses remain, so this is not an all-bugs claim. Next, expose bounded
access to generated traces: current inspection tools cannot read scratch
artifacts. Replace the fixed editor-round stop with a time/budget-aware repair
allowance, preserving rollback; B3 correctly rejected a new invariant failure
but had no rounds left to repair dependencies. Retain additional passing seeds
as regression guards and improve final seed/fault coverage. The image tarball,
source/Dockerfile, redacted public build chats from all four agents, and measured
scorecards are preserved locally. Unseen-codebase performance remains unknown.
