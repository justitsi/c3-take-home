# C3 autonomous repair fixer — V1

A Docker-packaged Python program that repairs unfamiliar distributed services.
Input: a service workspace, incident report, logs, tests, simulator and read-only
contracts. Output: changes under the service's `src/`. Each run is autonomous
and starts fresh.

**Verified practice result: 9/12 bugs**, all six cases; **$5.850678** model spend,
**991.65 seconds** summed fixer runtime. Every credited bug passed 20 hidden
practice seeds. Public/baseline-relative regression gates passed, with no
timeouts or infrastructure errors. All 240 repeated trace pairs were audited.
Offline suite: **62 tests passed**. Unseen-service performance is unknown.

Case scores: A1 1/1; A2 2/2; A3 3/3; B1 1/1; B2 1/3; B3 1/2.
See the [scorecard](benchmarks/v1-final-evaluation.json) and
[image/hash record](benchmarks/v1-final.json).
The [Docker image tar](upload/prototype-v1-final.tar) and
[SHA-256 checksum](upload/prototype-v1-final.tar.sha256) are tracked in this repo.

## How it works

1. Establish public-test and simulator baselines; retrieve bounded source,
   logs and current contracts.
2. Run three read-only Sonnet 4.6 investigators in parallel: recovery,
   leases/membership and delivery/commit.
3. Give their evidence to one editor, which makes small, serialized source edits.
4. Check syntax, public tests, simulator invariants and repeated-trace hashes.
   Keep supported changes as source checkpoints; restore rejected candidates.

All model calls use the supplied proxy and shared spending reservations.
Subprocess timeouts, a shutdown reserve and SIGTERM handling bound execution.
Tests, scenarios, simulator and corpus remain unchanged; the image contains no
practice-specific repairs or cross-case state.

## Run

From the repository root, load the preserved graded image and run offline tests:

```sh
docker load -i solution/upload/prototype-v1-final.tar

docker run --rm --platform linux/amd64 --network none \
  --mount "type=bind,source=$PWD/solution,target=/solution,readonly" \
  --entrypoint python c3-fixer-prototype:v1-final \
  -m pytest -q -p no:cacheprovider /solution/tests
```

To rebuild, use a new tag; do not overwrite the graded image:

```sh
docker build --platform linux/amd64 -t c3-fixer-prototype:v1-rebuild solution/fixer
```

Paid practice grading requires the supplied key in ignored `.env`. Never commit
or print it. Use a fresh output directory and keep cases serial on the ~2 GB VM:

```sh
./solution/grade-docker.sh --fixer c3-fixer-prototype:v1-final \
  --cases practice --concurrency 1 --eval-workers 1 --keep \
  --out results/v1-recheck
```

The wrapper runs the official grader/proxy in Docker; Docker is the only host
dependency. Tests use fake model responses; grading makes paid calls.
Assessment limits: 900 seconds, $3 per bug, 2 CPUs/4 GB per fixer. Actual
environment settings control. See the [brief](../README.md) and [rules](../RULES.md).

## Code and evidence

- [fixer/](fixer/): `fix.py` orchestration; `model.py` proxy/budget;
  `retrieval.py` context; `tools.py` reads/edits; `validation.py` checks/rollback.
- [tests/](tests/): offline harness tests.
- [WRITEUP.md](WRITEUP.md): short explanation; [STATUS.md](STATUS.md): measured history.
- [benchmarks/](benchmarks/): scorecards and identities. Raw results retain
  `result.json`, `eval.json`, `patch.diff` and `fixer.log`.
- [Build-chat manifest](../evidence/build-chats/manifest.json): redacted public
  development messages/tools, with hashes; private reasoning excluded.

## Limits and next work

V1 allows fourteen editor rounds and automatically checks at most two public
seeds per candidate. Extra seeds/faults are editor-selected, not persistent
regression guards. Inspection tools cannot read generated scratch traces.

Three bugs remain: heartbeat/cancellation reconciliation, ambiguous-submit
liveness and registration amplification. Priorities: trace access,
evidence-driven continuation, retained extra guards and broader final checks.
Public-green is not proof of a full repair.

Retain the best fully evaluated image. Any replacement needs its own comparable
six-case evaluation; do not combine results across builds. No 100% or unseen-case
success claim is supported.
