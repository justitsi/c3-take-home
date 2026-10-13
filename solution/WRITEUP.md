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

Main's no-op baseline fixed 0/12 bugs after a successful serial B2 retry. The
immutable `c3-fixer-prototype:v1` pilot fixed 2/2 bugs across A1 and B1, passed
their public/private regression checks, and spent $1.649673. The finalized
`c3-fixer-prototype:v1-final` image contains later safety hardening and has a
different image identity. That changed source has not had another paid model
evaluation; the pilot score does not establish its six-case score or merge gate.
Local benchmarks run one case and one evaluation worker at a time within the
requested approximately 2 GB Docker VM, while model investigation stays parallel.

Version 1 is frozen on its development branch under human supervision; further
paid evaluation is deferred. `STATUS.md` records evidence and artifact identity.
Next work should evaluate all six cases on one frozen image, then improve
retrieval, investigation efficiency, and seed/fault coverage from observed
failures. Promotion requires a measured improvement over main on the complete
comparison. Preserve development chats for the eventual submission.
