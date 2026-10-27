# C3 autonomous repair fixer (V3.2)

A Dockerised Python program that repairs distributed-service bugs without human input. It receives a workspace (source, incident report, logs, tests, simulator, contracts), edits only `src/`, and uses Claude Sonnet 4.6 through the supplied proxy.

**Submitted build:** branch `solution/prototype-v3.2`, image `c3-fixer-prototype:v3.2` ([tar](upload/c3-fixer-prototype-v3.2.tar), [SHA-256](upload/c3-fixer-prototype-v3.2.tar.sha256)). It is `linux/amd64` and 48 MB. Source and `Dockerfile` are in [fixer/](fixer/). 88 offline tests pass.

## Results

V1 is the only build with a complete, audited six-case result: 9/12 practice bugs. V3.2 has no full six-case run, because the model API began returning HTTP 403 before the regression reruns. Local-mode single runs:

| Case | V1 (audited) | V3.x local runs |
|---|---|---|
| A1 | 1/1 | 1/1 (V3.1) |
| A2 | 2/2 | 2/2 (V3.1) |
| A3 | 3/3 | 3/3 (V3.1); not rerun on V3.2 |
| B1 | 1/1 | 1/1 on one V3.2 run; the next run is invalid (API 403) |
| B2 | 1/3 | 1/3 to 3/3 across seven V3.2 runs |
| B3 | 1/2 | 0/2; later run invalid (API 403) |

No claim is made about unseen cases.

## How it works

1. Run public tests and seeds to set baselines.
2. Replay every `scenarios/faults` profile. Profiles that violate invariants, or show a log token the ticket names, become pinned probes.
3. Run read-only investigators in parallel, including one per numbered ticket report. Each registers hypotheses, runs replay experiments and ends with a structured conclusion.
4. One editor repairs in rounds: a focus round per ticket report, then residual rounds that must submit a candidate while violations remain.
5. Check each candidate for syntax, tests, invariants and determinism, and replay it on the probes. Reject it if a probe gains violations. Keep it, or roll it back.

Model calls share one budget. Timeouts and a shutdown reserve bound each run. The image holds no case-specific repairs.

## Run

```sh
python -m pytest -q solution/tests                      # offline tests
docker load -i solution/upload/c3-fixer-prototype-v3.2.tar
./grade.sh --fixer c3-fixer-prototype:v3.2 --cases practice/B2   # paid; key in ignored .env
```

[run-v3.sh](run-v3.sh) grades all practice cases. Never commit the key.

## Contents

- [fixer/](fixer/): controller (`fix.py`), model client, retrieval, tools, validation.
- [tests/](tests/): offline tests.
- [WRITEUP.md](WRITEUP.md): short write-up.
- [benchmarks/](benchmarks/): V1 scorecards.
- [build-chats/](build-chats/): V1 and V3.x chat logs, keys redacted.
- [future-work-plan/](future-work-plan/README.md), [progress/](progress/README.md): next steps and status.

## Limits

- Run-to-run variance is high (B2: 1/3 to 3/3).
- B1 and B3 root causes are known from source reading but not implemented.
- A3 now runs five rounds and is unverified on V3.2.

The V1 baseline (branch `solution/prototype-v1`) uses three investigators and one editor, and scored 9/12 at $5.85.
