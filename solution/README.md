# C3 repair prototype handoff

**Selected deliverable: preserved `c3-fixer-prototype:v1-final`, verified 9/12
across all six cases.** The user ended the session before R4's full evaluation.
R4 is an incomplete experiment, not a replacement. No further case runs are queued.

For upload, use [UPLOAD.md](UPLOAD.md) and the exact selected
[V1 source directory](submission/README.md), not experimental `fixer/`.

[future work.md](<future work.md>) lists every unfinished evaluation, architecture
increment and verification task. [Selection manifest](benchmarks/selected-version.json)
records the chosen deliverable and verified hashes.

The convenience tag `c3-fixer-prototype:best-verified` points to that same V1 image,
identity `sha256:38219577c596f30f84ebdc58bf1ec8b27f941545a61a86fcd78e2b6b94f3c6b3`.
The [selected V1 source archive](results/selected-v1-source.tar) has SHA256
`79a46a34de070d1e23cc724ea017d8d301563602497a06a339aa741a3769513e`;
the current branch's `fixer/` remains experimental R4 source.

This branch develops an autonomous Docker fixer with AI-assisted implementation
under human supervision. Graded runs remain hands-off. The active branch is
`solution/prototype-v2`, based on finalized V1 `96e06b2`. **Do not merge or push
V2 without a new user request.**

The repository [assessment brief](../README.md) and [rules](../RULES.md) are
authoritative. [V2_PLAN.md](V2_PLAN.md) defines the iteration gates;
[STATUS.md](STATUS.md) and [V2_REVIEW.md](V2_REVIEW.md) record evidence and review.
The supplied [V3 proposal](v3_architecture.md) is mapped in
[V3_IMPLEMENTATION_PLAN.md](V3_IMPLEMENTATION_PLAN.md): bounded minor R4 work
is now frozen/tested; major architecture changes remain planning only.

## Current checkpoints

| Checkpoint | Official practice evidence | Meaning |
| --- | --- | --- |
| Preserved V1 final | **9/12**, all six cases; **$5.850678**, **991.65 s** fixer time | **Selected deliverable**; complete evidence |
| V2-r1 | **1/5** on B2/B3; **$6.061312**, **876.019 s** | Setback: V1 fixed **2/5** on those same cases |
| V2-r2 | **2/5** on B2/B3; **$4.624972**, **817.972 s** | Nonpromotable: B3 rollback failed, exit 1, new regressions |
| V2-r3 | **2/6** on A1/B2/B3; **$11.533084**, **1,928.95 s** | Partial result only; A2/A3/B1 were not evaluated on R3 |
| V2-r4 | **4/6** on A1/B2/B3; **$10.619585**, **1,980.916 s** | Partial/interrupted batch; no six-case comparison; not selected |

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

The [R2 pilot](benchmarks/v2-r2-pilot.json) scored B2 2/3 and B3 0/2. B3 exited
1 during rejected-candidate rollback on a real Docker host bind mount; an
unaccepted change remained installed and introduced three baseline regressions.
R2 is not promotable. Its B2 result also showed that green public seeds can miss
a contract bug, motivating targeted derived probes and independent review.

The [R3 partial scorecard](benchmarks/v2-r3-partial.json), source `2096b49`,
records A1 1/1, B2 0/3 and B3 1/2. Those three cases passed public and
baseline-relative regression gates with clean exits and no timeout/infra errors.
The credited bugs passed 20/20 seeds. R3's **2/6** is not a six-case result;
do not fill its missing cases with R4 results.

The preserved experimental candidate is `c3-fixer-prototype:v2-r4`, source `ac409bf`.
[Image/test evidence](benchmarks/v2-r4-image.json) records `linux/amd64`,
47,646,285 bytes, all ten build-context files matching the image, and
**287 offline Docker tests passed in 31.00 seconds**, including real host
bind-mount recovery. Its recorded image identity is
`sha256:0c590ba5b53715f361871365a8213ec2a6689eb31a7a57e35c5905f61dda1ba4`.
Offline tests verify controller behavior; they do not establish a repair score.
The [R4 partial scorecard](benchmarks/v2-r4-partial.json) records three completed,
uninterrupted cases: A1 **1/1** ($2.695635, 538.803 s), B2 **2/3** ($3.397598,
695.563 s), B3 **1/2** ($4.526352, 746.550 s). Total: **4/6**, **$10.619585**,
**1,980.916 s** summed fixer time; all credited bugs passed 20/20 seeds, with
clean exits, passing public/regression gates and no timeout/infra errors.
V1 scored **3/6** on those same cases, but R4 has no complete six-case comparison.
A2 was SIGTERM-stopped; its existing grader then credited **2/2** on the retained
snapshot (20/20 each, passing gates; $1.168160, 146.047 s). This is
[separate interrupted-run evidence](benchmarks/v2-r4-interrupted-A2.json), not part
of the uninterrupted score or proof of controller completion. A3/B1 never launched.
V1 remains selected.

## How the experimental R4 harness works

This section describes the V2 branch, not the selected frozen V1 implementation.

1. **Reproduce and retrieve.** Read the ticket, invariants, source layout, logs,
   case metadata, and corpus index. Run syntax/public tests and every declared
   public seed. Retrieve bounded source and contract excerpts instead of loading
   the approximately 26M-token corpus.
2. **Investigate in parallel.** Three read-only Sonnet 4.6 specialists cover
   `state-recovery`, `leases-membership`, and `delivery-commit`. Each has at most
   five tool-enabled calls, then tool-free synthesis, with at most seven total
   attempts including truncation recovery. Incomplete synthesis is marked, not
   treated as a completed finding. They cannot modify source.
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
   Rejected candidates retain bounded check/artifact citations and rejection
   reasons through compaction; their counterexamples are not current passing guards.
   `claimed-resolved` is a model claim, never hidden-bug certification.
5. **Repair iteratively.** One integrating editor makes small, serialized
   candidates. Context compaction preserves cited observations and recorded
   issue hypotheses. A separate fresh diagnosis drops prior hypotheses while
   keeping factual evidence and the latest validated source. Repeated empty
   reads do not count as useful progress. Stagnation, budget, deadline, and
   completion checks control continuation. The initial editor gets **up to 55
   rounds** with additional review/follow-up time reserved; all editor phases
   share an **80-round total emergency ceiling**, replacing V1's 14-round cap.
   After 12 consecutive read-only rounds without a candidate, the initial phase
   hands off for independent review. Audited completion is checked before an
   otherwise unnecessary fresh restart.
6. **Validate and checkpoint.** Candidate checks cover public tests, every
   declared public seed, and registered `(seed, scenario, faults)` probes.
   Preserve previously passing checks, reject newly introduced invariant
   categories, and require complete execution plus a repeated-trace determinism
   check before retaining a candidate. Roll back rejected or interrupted edits;
   R3 adds portable exchange fallback for Docker host bind mounts and explicit
   fatal rollback status if restoration persistently fails.
   Related prerequisite repairs can form one coherent candidate; original
   unrelated failures may remain after a partial repair.
7. **Probe and independently review contracts.** The editor can create bounded,
   write-once scenarios derived from supplied scenarios. Generated probes are
   hashed, verified before replay, and registered as scenario-aware checks;
   supplied scenarios remain unchanged. `source_diff` exposes a bounded diff
   from the trusted original source checkpoint, with no model-selected paths.
   If allowance remains, a fresh read-only contract reviewer audits the full
   patch and every ticket item, without original specialist hypotheses. It can
   make up to six attempts, at most four tool-enabled, with tool-free synthesis
   and bounded truncation recovery. A completion flag distinguishes a concluded
   review from partial notes. Supported concerns go
   back to the editor for follow-up within the shared 80-round limit.
8. **Finish with evidence.** Run automatic final validation over the required
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

Derived probes permit only node classes from their supplied base and supplied
fault-file paths. Bounds include 32 expanded nodes, 500 actions, a simulation
end time of at most 600, and 64 KiB serialized data. Creation alone proves
nothing; the controller must replay and check the immutable probe. Review
findings and model-authored expectations remain claims, not hidden-test proof.

The model client uses standard-library HTTP and the supplied proxy. Runtime
uses only permitted Sonnet 4.6; Jev is deferred. Local tools provide retrieval
and validation. No practice-specific patches, grader data, credentials, or
cross-case state are embedded in the fixer image. Only case `src/` edits count.

## Time, spend, and shutdown

- Read `C3_WORKSPACE`, `C3_CORPUS`, `C3_DEADLINE`, `C3_BUDGET_USD`, and proxy
  settings. Actual supplied limits take precedence over defaults.
- Assessment maximum: 900 seconds, $3 **per bug**, 2 CPUs, and 4 GB per fixer.
  The latest schedule amendment permits **at most three active case sessions**, each
  containing one case and one evaluation worker. Keep the Docker VM unchanged
  at its recorded **1,973 MiB and 4 CPUs**; model investigators remain parallel.
- Share conservative request reservations across all agents. Investigation is
  capped at 45% of case budget and 35% of initial usable time.
  Tool-enabled investigator/editor output limits are 1,800/3,800 tokens per call;
  investigator synthesis and contract review allow up to 3,200.
- Reserve 75 seconds under the normal allowance; shorter runs use 10% of initial
  remaining time, bounded between 5 and 75 seconds. Bound HTTP/tools and stop
  new edits while enough allowance remains for validation. The initial editor
  temporarily reserves additional contract-review/follow-up allowance, up to
  135 seconds above the final reserve; later phases retain the final reserve.
- Reject truncated or malformed model replies before executing partial tools.
  Truncation requests a shorter conclusion/tool batch within the existing phase
  cap; charged responses still count against the shared budget.
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

## Preserved Docker deliverable

Run from the repository root. Inspect the existing selected image; do not rebuild
the V1 tag from this branch's R4 source. Keep all frozen tags/artifacts intact.
No new build, test or paid evaluation is required for this wrap-up.

```sh
docker image inspect c3-fixer-prototype:best-verified \
  --format '{{.Os}}/{{.Architecture}} {{.Size}} {{.Id}}'
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

The interrupted R4 batch began **2026-10-13 21:47:53 UTC**. Results remain under
`solution/results/v2-r4-cases/<case>-session/`; no remaining cases will launch
without a new request. The historical cap was three independent case sessions,
each `--concurrency 1 --eval-workers 1`, on the unchanged 1,973 MiB/4-CPU VM.
Never combine scores from different images. For a retained run,
inspect `result.json` (credited bugs, actual spend/time, gates), `eval.json`
(per-bug seed outcomes), `patch.diff`, and `fixer.log`. Count official fixes,
not diagnoses. A credited bug must pass all 20 hidden practice seeds. A patch
that breaks baseline-passing public/private tests can zero its case.

## Artifact paths and comparison policy

New repository artifacts stay under `solution/`:

- `results/<run>/`: retained result/eval summaries, logs and patches; bulky replays were moved out.
- Scratch workspaces, runner proxy state and caches were recoverably removed during upload cleanup.
- `evidence/runtime-reports/`: nineteen controller reports preserved before removing scratch.
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

R4 did not reach this full-comparison gate. Preserve V1 as selected; an
interrupted case or missing case is not a successful evaluation.

## Handoff and next evidence

`fixer/` contains runtime code/build context; `tests/` holds offline harness
checks; `dev/` and `grade-docker.sh` provide the Docker grader environment.
`WRITEUP.md` is the short design/results account. `export_build_chats.py`
exports public user/assistant messages and linked tool evidence with credential
redaction and hashes; analysis, system/developer context, and inherited parent
history are excluded. No credential file is read by that exporter.

The current work is ended. Preserve checkpoints and terminal partial results;
do not resume the queue or implement the V3 plan without a new request.
The target is 12/12 supplied bugs; neither that target nor unseen-case
correctness is presently demonstrated. Prioritize observed repair failures
over additional orchestration complexity.

The redundant interim R3 chat checkpoint was moved to the recoverable cleanup
location; [cleanup manifest](cleanup-manifest.json) records its original path.

The [R4 wrap-up build-chat export](evidence/build-chats-r4-final/manifest.json)
captures four actual sessions through **2026-10-13 22:02:36 UTC** at user-directed
wrap-up. Its manifest records verified source/export hashes, counts and exclusions.
It may predate final result bookkeeping and is not
evidence that all six R4 cases completed. The selected V1 chat export remains intact.
