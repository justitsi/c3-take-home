# C3 parallel repair prototype v1

This directory contains the first implementation of the assessment plan: a
Docker-packaged, autonomous repair harness for unfamiliar Python services. The
development process uses AI agents under human supervision; each graded run
operates without human input. This is a prototype to measure and improve, not a
claim of a final submission score.

Read the repository's [assessment brief](../README.md) and [rules](../RULES.md)
for the authoritative contract. [PLAN.md](PLAN.md) describes the development
milestones. [STATUS.md](STATUS.md) records checkpoints, validation evidence,
practice scores, and remaining work.

Version 1 is finalized as `c3-fixer-prototype:v1-final`. Evidence and limits:

- Main's no-op baseline fixed **0/12 bugs across all six cases**. An initial B2
  infrastructure failure was resolved by a serial, single-worker retry.
- The immutable pilot image `c3-fixer-prototype:v1` repaired **2/2 bugs across
  A1 and B1**, spending **$1.649673**. Both cases passed public and private
  regression checks; raw evidence is in `results/prototype-v1-pilot/`.
- `v1-final` contains later safety hardening and has a separate image identity
  from that pilot. Its changed source has **not been reevaluated with paid
  model calls**. There is no final six-case score and the merge condition has
  not been demonstrated. Remaining case coverage is work for the next version.
- Final offline Docker safety suite: **45 passed**. Image runtime source was
  checked byte-for-byte against the source saved on `solution/prototype-v1`.
  Evidence summaries are in [benchmarks/](benchmarks/); the local handoff image
  is [results/prototype-v1-final.tar](../results/prototype-v1-final.tar), with
  its SHA-256 recorded in [v1-final.json](benchmarks/v1-final.json).

## How it works

- A Python controller reads the ticket, case metadata, invariants, source
  layout, logs, and the corpus index. Paths come from the grader's environment.
- Several Sonnet 4.6 specialist agents investigate different distributed
  failure classes in parallel. Their tools inspect files, search documentation,
  and gather evidence; they cannot edit service files.
- The controller combines their findings for a repair agent. Source edits and
  validation are serialized so investigators cannot race to overwrite a patch.
- The repair agent makes small edits, runs public tests and deterministic
  replay/check commands, and uses the feedback to investigate remaining bugs.
  Passing unit tests alone do not prove a bug is fixed: the original tests
  already pass before repair.
- Validation retains source checkpoints and restores a validated version when
  a candidate breaks passing checks. Accepted changes remain available if a
  later investigation runs out of time or model budget.
- Each case starts fresh. The image contains the harness, not practice-case
  repairs, expected answers, hidden grading data, credentials, or prior runs.

The model client uses standard-library HTTP and the supplied proxy. Runtime
calls use only the permitted Sonnet model. Jev is an optional future experiment,
not a dependency of this prototype. Local tools perform retrieval and simulator
commands; no provider web search or server-side tools are needed.

The initial specialist profiles and controller limits are constants in
`fixer/fix.py`; request handling and budget accounting live in `fixer/model.py`:

- `state-recovery`: durability, restart/cancellation, capacity accounting,
  release, and idempotency.
- `leases-membership`: fencing, worker incarnations, heartbeat ordering, clock
  drift, and pauses.
- `delivery-commit`: ambiguous RPC outcomes, retry/backoff, acknowledgments, and
  speculative commit races.
- Each investigator has at most six model calls with `max_tokens=1800`; the
  integrating editor has at most fourteen rounds with `max_tokens=3800`.
  These are ceilings, not allocations that must be exhausted.
- One shared `Budget` reserves a conservative estimate before each concurrent
  request, then settles against reported usage/cost. Missing or uncertain usage
  is charged conservatively internally; the supplied proxy enforces the actual
  spend limit. Internal estimates and the grader's measured spending are
  distinct.
- Investigation reservations are capped at 45% of the shared case budget.
  Investigation also ends at 35% of the initial usable time after subtracting
  the shutdown reserve. This preserves allowance for the integrating editor.
- Initial validation runs syntax checks, public tests, and up to two public seeds.
  Each candidate checks public tests and up to two public seeds, repeating the
  first replay for trace-hash determinism when enough time remains. It protects
  previously passing seeds and rejects newly appearing invariant categories
  relative to each seed's retained result. Original invariant failures can
  remain after a partial repair; related prerequisite repairs may need one
  coherent candidate. This limited public validation does not replace the
  official 20-seed, per-bug grader.

## Runtime limits and shutdown

The grader provides `C3_WORKSPACE`, `C3_CORPUS`, `C3_DEADLINE`,
`C3_BUDGET_USD`, and per-case proxy settings. The normal maximum is 900 seconds,
2 CPUs, 4 GB RAM, and $3 of model budget per bug. The actual deadline and budget
are authoritative; the harness must not assume that every run receives a full
15 minutes or a fixed dollar allocation.

The controller shares its time and spending limits across all agents, bounds
tool and HTTP work, and reserves 75 seconds for final validation/rollback under
the normal allowance. For shorter runs, the reserve is 10% of the initial
remaining time, bounded between 5 and 75 seconds. It exits
when work is complete or the remaining limits cannot support useful work; it
does not sleep to fill the allowance. The shell entry point uses `exec`, allowing
SIGTERM to reach Python directly. The external grader sends SIGTERM at the
deadline and SIGKILL five seconds later. Checkpointed, valid `src/` is therefore
the output that matters, including during interruption.

Only edits inside the case's `src/` count. Tests, simulator, scenarios, corpus,
and grader are evidence, not repair targets. Official grading checks each bug
against 20 hidden seeds and can zero a case if a patch breaks baseline-passing
public or private regression tests.

## Token and cost discipline

- Search before reading: bounded, line-numbered excerpts from source and corpus
  replace full-file or full-corpus prompts.
- Give specialists distinct responsibilities and a compact shared case summary
  to reduce duplicate investigation.
- Bound agent rounds and generated output; retain concise findings with file
  references instead of repeatedly copying raw logs.
- Keep repeated prompt prefixes stable for the proxy's automatic prompt cache.
- Reserve budget across concurrent requests; treat HTTP 402 as exhaustion and
  preserve the last validated source rather than retrying indefinitely.

These controls constrain waste, not repair quality. Simulator feedback and
relevant contract retrieval remain part of the repair loop.

## Build and test in Docker

Run commands from the repository root. Docker must be running. Dependencies are
installed while building, before the grader restricts runtime networking.
Keep the Docker VM at the requested approximately 2 GB. Run practice cases
serially with one evaluation worker; the three model investigators within a
case still operate in parallel. The official grader's per-fixer resource limits
remain separate from the VM's total allocation.

```sh
docker build --platform linux/amd64 -t c3-fixer-prototype:v1-final solution/fixer

docker image inspect c3-fixer-prototype:v1-final \
  --format '{{.Os}}/{{.Architecture}} {{.Size}} {{.Id}}'

docker run --rm --network none --platform linux/amd64 \
  --entrypoint python3 \
  -e PYTHONPATH=/fixer \
  -v "$PWD/solution:/solution:ro" \
  c3-fixer-prototype:v1-final -m pytest -q /solution/tests
```

The required image is `linux/amd64` and must be no larger than 4 GB. The image
has Python 3.12, PyYAML, pytest, and a no-argument entry point. Building the image
does not contact a model. Unit tests exercise the controller with fake model
responses; they do not establish a real repair score.

## Run the provided practice cases

`solution/grade-docker.sh` runs the supplied grader and proxy in a development
container, then the unmodified grader launches the fixer image in a separate
container with the assessment mounts, resource limits, proxy isolation, and
termination behavior. Docker is the only host dependency. The development
image contains Python 3.12, PyYAML, pytest, and a Docker client; it is separate
from the submitted fixer image.

Place the supplied `OPENROUTER_API_KEY` in the repository's ignored `.env`
without committing or printing it. The development entry point starts the real
proxy, checks that a key loaded, and requests `--proxy http` so a dead proxy is
an infrastructure failure. Model requests are paid; no-op baseline runs do not
call a model. The wrapper defaults to `--concurrency 1 --eval-workers 1` to keep
benchmarks serial within the requested VM memory allocation.

The following are reproduction commands for a future evaluation session. No
further paid grading is part of this v1 finalization.

```sh
# Zero-spend Docker baseline; main initially has no solution fixer.
docker build --platform linux/amd64 -t c3-fixer-main-baseline:noop \
  fixers/examples/noop
./solution/grade-docker.sh --fixer c3-fixer-main-baseline:noop --cases practice \
  --concurrency 1 --eval-workers 1 \
  --out results/prototype-main-baseline

# Optional paid checkpoint for the changed final image.
./solution/grade-docker.sh --fixer c3-fixer-prototype:v1-final --cases practice/A2 \
  --concurrency 1 --eval-workers 1 --keep --out results/prototype-v1-final-A2

# Measure the exact frozen image across all six provided cases.
./solution/grade-docker.sh --fixer c3-fixer-prototype:v1-final --cases practice \
  --concurrency 1 --eval-workers 1 --keep \
  --out results/prototype-v1-final-all
```

If main later contains a fixer, build and grade that exact main implementation
as the baseline using the same cases and grading configuration. A no-op run
would then cease to represent main. Keep each experiment's output directory
distinct to avoid overwriting earlier evidence.

For each case, inspect `result.json` (`bugs_fixed`, spending, elapsed time),
`eval.json` (seed outcomes), `patch.diff`, and `fixer.log`. Report fixed bugs and
total available bugs, not model diagnoses or a count of changed lines. Record
infrastructure failures separately from a valid score of zero. No score is
claimed until the official runner finishes against the actual image.

The controller writes JSON event lines to `fixer.log` and a detailed report to
both temporary scratch `fixer-report.json` and the case workspace's ungraded
`.c3-fixer-report.json`. Use `--keep` as above to retain grader workspaces under
`results/.scratch/` for report and source inspection. The report includes
specialist findings, accepted/rejected candidate checks, and internal budget
estimates; the official result/ledger remains authoritative for score and cost.

The Docker wrapper builds its development image using Docker's build cache.
It mounts the repository at the same absolute path on host and container and
places grader workspaces under `results/.scratch/`, so nested Docker bind
mounts resolve correctly. Proxy state lives in the named Linux volume
`c3-prototype-proxy-state`, mounted at its daemon-visible absolute path. This
allows the supplied grader's sidecar to bind the proxy Unix socket on Docker
Desktop, where a socket in a macOS bind mount would not work. Each invocation
gets a separate proxy state directory and writes proxy logs/spending to
`results/.runner/<run-id>/`. No upstream credential is passed to fixer images;
the grader supplies fresh per-case proxy tokens.

The runner uses the host Docker socket. Override `C3_DEV_IMAGE` or
`C3_DEV_PROXY_VOLUME` if needed to choose development image/volume names. It
retains the volume for later runs
and stops its proxy on normal completion. The fixer itself has access only to
the proxy network namespace, its case workspace, and the read-only corpus.

Alternatively, if the host has Python 3.12+, PyYAML, and pytest, use the original
`./grade.sh --fixer c3-fixer-prototype:v1-final --cases practice/A2 --concurrency 1 --eval-workers 1`.
Passing an image
still runs the assessed harness in Docker. That wrapper may fall back to a stub
without a configured key/proxy; a stub run does not establish a live repair
score. The fully containerized runner above checks the real proxy explicitly.

## Iterative development and branch gate

The following gate applies to future promotion. Finalizing this v1 snapshot
does not imply that its hardened image has passed the complete comparison.

1. Establish main's baseline and save its score artifacts.
2. Build one runnable prototype, run controller checks in Docker, then grade one
   practice case. Inspect actual diagnoses, patches, failures, time, and spend.
3. Record a checkpoint and a hypothesis for the next small improvement. Change
   one major strategy at a time; repeat the relevant checks before a full sweep.
4. Grade the candidate image on all six practice cases. Save source and an
   evidence summary on a dedicated Git branch.
5. Integrate into main only when the measured total of fixed bugs strictly
   exceeds main's comparable score. Otherwise retain the candidate branch and
   explain the observed gap. Equal scores do not satisfy this merge condition.

Human review centers on checkpoint evidence and priorities. The lead agent
coordinates file ownership, integration, and git operations; specialist agents
implement and independently review bounded pieces of work. Real credentials,
large generated result trees, and model ledgers do not belong in commits.

## Layout and next work

- `fixer/`: controller, model client, local tools, retrieval, validation, Docker
  build context, and executable `run.sh`.
- `tests/`: offline reliability tests for the harness, separate from service
  tests supplied in each case.
- `dev/` and `grade-docker.sh`: Docker-hosted official grader/proxy runner.
- `PLAN.md`: supervised, iterative development plan and milestone gates.
- `STATUS.md`: measured checkpoints, score comparison, and open limitations.
- `WRITEUP.md`: short architecture and next-steps explanation for handoff.

Practice results guide the next iteration; unseen hidden codebases remain the
target. Favor general contract retrieval, evidence-driven repairs, deadline
reliability, and meaningful validation over case-specific shortcuts. Preserve
the development chat logs for the required submission handoff.
