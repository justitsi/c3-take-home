# C3 repair prototype V2

This branch develops an autonomous Docker fixer with AI-assisted implementation
under human supervision. Graded runs remain hands-off. The active branch is
`solution/prototype-v2`, based on finalized V1 `96e06b2`. **Do not merge or push
V2 without a new user request.**

The repository [assessment brief](../README.md) and [rules](../RULES.md) are
authoritative. [V2_PLAN.md](V2_PLAN.md) defines the iteration gates;
[STATUS.md](STATUS.md) and [V2_REVIEW.md](V2_REVIEW.md) record evidence and review.

## Current checkpoints

| Checkpoint | Official practice evidence | Meaning |
| --- | --- | --- |
| Preserved V1 final | **9/12**, all six cases; **$5.850678**, **991.65 s** fixer time | Current complete comparison baseline |
| V2-r1 | **1/5** on B2/B3; **$6.061312**, **876.019 s** | Setback: V1 fixed **2/5** on those same cases |
| V2-r2 | **Repair score pending**; B2/B3 serial pilot in progress | Implemented and tested controller, unproven repair effectiveness |

[V1's scorecard](benchmarks/v1-final-evaluation.json) remains intact: A1 1/1,
A2 2/2, A3 3/3, B1 1/1, B2 1/3, B3 1/2. Every credited bug passed all 20 hidden
practice seeds, with public and baseline-relative regression gates passing.
Its separate image is `c3-fixer-prototype:v1-final`. Historical
[no-op](benchmarks/main-baseline.json), [V1 pilot](benchmarks/v1-pilot.json), and
[one-shot A2 reference](benchmarks/minimal-reference-A2.json) evidence is retained;
those runs are not substitutes for the current V1 comparison.

The [R1 pilot](benchmarks/v2-r1-pilot.json) scored B2 0/3 and B3 1/2, with no new
baseline-passing regressions, timeout, or infrastructure failure. Both cases
exhausted the 80-round ceiling; repeated investigation and resets did not
produce enough repairs. Additional controller features alone did not improve
the measured result.

The current frozen candidate is `c3-fixer-prototype:v2-r2`, source `11aae52`.
[Image/test evidence](benchmarks/v2-r2-image.json) records `linux/amd64`,
47,638,807 bytes, all nine build-context files matching the image, and
**226 offline Docker tests passed in 30.92 seconds**. Its recorded image identity
is `sha256:13ef71ea43ffb4005fc0b7015bbe778c062c6b94e3e46d640d79009a3ae2c7ba`.
Offline tests verify controller behavior; they do not establish a repair score.
R2 has no completed six-case comparison or demonstrated improvement yet.

## How the current harness works

1. **Reproduce and retrieve.** Read the ticket, invariants, source layout, logs,
   case metadata, and corpus index. Run syntax/public tests and every declared
   public seed. Retrieve bounded source and contract excerpts instead of loading
   the approximately 26M-token corpus.
2. **Investigate in parallel.** Three read-only Sonnet 4.6 specialists cover
   `state-recovery`, `leases-membership`, and `delivery-commit`. Each has at most
   six model calls; the sixth is tool-free so it can summarize the strongest
   evidence. They cannot modify source.
3. **Inspect generated evidence.** Read/search/list tools expose a contained,
   read-only `artifacts/` namespace for simulator traces and summaries.
   `inspect_trace` supports one literal `query`, same-record AND via
   `all_terms`, optional time windows, and resumable `start_line`/`next_line`
   pages. It reports line numbers, returned time ranges, truncation, malformed
   rows, and scan limits. Empty or clipped output is not proof that no event
   occurred.
4. **Retain facts and issue state.** A bounded observation ledger keeps cited
   tool results, unsuccessful queries, and source revisions. A per-symptom
   `update_issues` ledger records hypotheses, citations, next steps, and
   verification plans. Old source excerpts are marked historical.
   `claimed-resolved` is a model claim, never hidden-bug certification.
5. **Repair iteratively.** One integrating editor makes small, serialized
   candidates. Context compaction preserves cited observations and recorded
   issue hypotheses. A separate fresh diagnosis drops prior hypotheses while
   keeping factual evidence and the latest validated source. Repeated empty
   reads do not count as useful progress. Stagnation, budget, deadline, and
   completion checks control continuation; **80 rounds is an emergency ceiling,
   replacing V1's 14-round cap**, not a requirement to spend all 80.
6. **Validate and checkpoint.** Candidate checks cover public tests, every
   declared public seed, and registered `(seed, scenario, faults)` probes.
   Preserve previously passing checks, reject newly introduced invariant
   categories, and require complete execution plus a repeated-trace determinism
   check before retaining a candidate. Roll back rejected or interrupted edits.
   Related prerequisite repairs can form one coherent candidate; original
   unrelated failures may remain after a partial repair.
7. **Finish with evidence.** Run automatic final validation over the required
   public/probe registry and restore a supported checkpoint after demonstrated
   regressions. Reports distinguish verified public coverage, known remaining
   failures, and incomplete validation. Public coverage does not certify hidden
   bug scenarios.

For example, a trace request can combine an entity and event in separate JSON
fields:

```json
{"path":"artifacts/replay-example/trace.jsonl",
 "all_terms":["job-17","rpc"],"start_line":1,"limit":30}
```

Use a real returned artifact path. If `next_line` is returned, keep the filters
and request that next page. The inspector returns at most 100 events/18,000
characters and scans at most 64 MiB, including skipped prefix lines; oversized
or malformed evidence is explicitly partial.

The model client uses standard-library HTTP and the supplied proxy. Runtime
uses only permitted Sonnet 4.6; Jev is deferred. Local tools provide retrieval
and validation. No practice-specific patches, grader data, credentials, or
cross-case state are embedded in the fixer image. Only case `src/` edits count.

## Time, spend, and shutdown

- Read `C3_WORKSPACE`, `C3_CORPUS`, `C3_DEADLINE`, `C3_BUDGET_USD`, and proxy
  settings. Actual supplied limits take precedence over defaults.
- Assessment maximum: 900 seconds, $3 **per bug**, 2 CPUs, and 4 GB per fixer.
  Keep the existing approximately 2 GB local Docker VM unchanged. Run cases
  serially with one evaluation worker; model investigators remain parallel.
- Share conservative request reservations across all agents. Investigation is
  capped at 45% of case budget and 35% of initial usable time. Investigator/editor
  output limits are 1,800/3,800 tokens per call.
- Reserve 75 seconds under the normal allowance; shorter runs use 10% of initial
  remaining time, bounded between 5 and 75 seconds. Bound HTTP/tools and stop
  new edits while enough allowance remains for validation.
- Reject truncated or malformed model replies before executing partial tools.
  The editor retries transient transport/rate-limit failures within bounded attempts
  and remaining allowance; permanent rejection or exhaustion preserves source.
- Use targeted excerpts, stable cached prefixes, concise observations, and
  context compaction to reduce repeated input. Validation and relevant
  contract retrieval remain mandatory.
- The entry point uses `exec` so signals reach Python directly. SIGTERM requests
  shutdown; a watchdog cancels work and restores valid source, with bounded
  fallback cleanup. The external grader sends SIGTERM at the deadline and
  SIGKILL five seconds later. Exit when useful work is finished rather than
  sleeping to fill the allowance.

## Build and run in Docker

Run from the repository root. These commands are examples, not evidence that a
new run has completed. Keep frozen tags/artifacts intact; after runtime changes,
use a new candidate tag and unique output directory.

```sh
docker build --platform linux/amd64 -t c3-fixer-prototype:v2-r2 solution/fixer

docker image inspect c3-fixer-prototype:v2-r2 \
  --format '{{.Os}}/{{.Architecture}} {{.Size}} {{.Id}}'

docker run --rm --platform linux/amd64 --network none --cpus 2 --memory 1g \
  --mount "type=bind,source=$PWD/solution,target=/solution,readonly" \
  --entrypoint python c3-fixer-prototype:v2-r2 \
  -m pytest -q -p no:cacheprovider /solution/tests
```

Python 3.12, PyYAML, and pytest are installed at image build time. The image has
a no-argument entry point and needs no dependency downloads at runtime. Offline
tests use controlled/fake model responses, not paid model calls.

`solution/grade-docker.sh` runs the supplied grader/proxy in a development
container and assessed fixer images in separate containers. Docker is the only
host dependency for those grading commands. The ignored repository `.env`
holds the supplied upstream key; the runner checks that the real proxy loaded
it without printing it. Each fixer receives a fresh per-case proxy token,
not the upstream credential.

The R2 pilot is already running. Do not launch a duplicate. For later
reproduction, use a fresh output directory and one case workload at a time:

```sh
# Paid B2/B3 reproduction after the active pilot finishes.
./solution/grade-docker.sh --fixer c3-fixer-prototype:v2-r2 \
  --cases practice/B2 practice/B3 --concurrency 1 --eval-workers 1 --keep \
  --out solution/results/v2-r2-pilot-repeat

# Full comparison, once the pilot has been inspected.
./solution/grade-docker.sh --fixer c3-fixer-prototype:v2-r2 \
  --cases practice --concurrency 1 --eval-workers 1 --keep \
  --out solution/results/v2-r2-all
```

The active pilot's output is `solution/results/v2-r2-pilot/`. For each run,
inspect `result.json` (credited bugs, actual spend/time, gates), `eval.json`
(per-bug seed outcomes), `patch.diff`, and `fixer.log`. Count official fixes,
not diagnoses. A credited bug must pass all 20 hidden practice seeds. A patch
that breaks baseline-passing public/private tests can zero its case.

## Artifact paths and comparison policy

New repository artifacts stay under `solution/`:

- `results/<run>/`: official results, logs, patches, and retained evaluation work.
- `results/.scratch/`: grader workspaces; `--keep` retains case reports.
- `results/.runner/<run-id>/`: proxy log and actual spending ledger.
- `results/.grader-cache/`: overlay for the unmodified grader's cache.
- `benchmarks/`: sanitized scorecards and image/source/test identities.
- `evidence/build-chats/`: new redacted public chat exports with role/hash manifest.
  Existing V1 artifacts under root `results/` and `evidence/` remain preserved.

The wrapper validates `--out`, `--tmp`, and optional `C3_RESULTS_ROOT` to remain
under `solution/`, including symlink resolution. It mounts the repository at
the same absolute host/container path for nested case mounts. Linux proxy
socket/state stays in the existing named Docker volume, mounted at its
daemon-visible path for Docker Desktop compatibility. The grader's cache
overlay protects the original cache; no supplied grader code is changed.

The controller writes JSON events to `fixer.log` and a detailed
`.c3-fixer-report.json` in the ungraded case workspace. It includes candidate
decisions, issue/evidence state, coverage, stop reasons, and internal budget
estimates. Official results and the proxy ledger determine scores and cost.

`benchmark.py` requires both complete six-case reports, comparable bug/seed
coverage, internally coherent credited flags and scores, and strict improvement.
Every candidate case must pass public/regression gates, exit zero, and avoid
timeout/infrastructure errors, including cases with zero fixes. Partial pilots
cannot satisfy that full comparison. Compare V2 against V1's **9/12**, not the
historical no-op score. A favorable comparison does **not** authorize a V2
merge, push, or external submission.

```sh
# Read-only comparison after the complete R2 scorecard has been collected.
docker run --rm --network none \
  --mount "type=bind,source=$PWD/solution,target=/solution,readonly" \
  --entrypoint python c3-fixer-prototype:v2-r2 /solution/benchmark.py compare \
  /solution/benchmarks/v1-final-evaluation.json \
  /solution/benchmarks/v2-r2-evaluation.json
```

## Handoff and next evidence

`fixer/` contains runtime code/build context; `tests/` holds offline harness
checks; `dev/` and `grade-docker.sh` provide the Docker grader environment.
`WRITEUP.md` is the short design/results account. `export_build_chats.py`
exports public user/assistant messages and linked tool evidence with credential
redaction and hashes; analysis, system/developer context, and inherited parent
history are excluded. No credential file is read by that exporter.

R2's remaining gate is empirical: inspect the live pilot, then evaluate one
frozen image on all six cases and audit seed/regression outcomes. Preserve
checkpoints and identify a changed hypothesis before another iteration.
The target is 12/12 supplied bugs; neither that target nor unseen-case
correctness is presently demonstrated. Prioritize observed repair failures
over additional orchestration complexity.
