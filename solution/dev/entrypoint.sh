#!/bin/bash
set -euo pipefail

: "${C3_ASSESSMENT_ROOT:?runner must set C3_ASSESSMENT_ROOT}"
: "${C3_PROXY_STATE:?runner must set C3_PROXY_STATE}"
: "${C3_RUNNER_LOG_DIR:?runner must set C3_RUNNER_LOG_DIR}"

cd "$C3_ASSESSMENT_ROOT"
source /opt/c3-dev/runner_paths.sh
SOLUTION_DIR="$C3_ASSESSMENT_ROOT/solution"
RESULTS_ROOT=$(c3_solution_path "${C3_RESULTS_ROOT:-$SOLUTION_DIR/results}" \
    "$C3_ASSESSMENT_ROOT" "$SOLUTION_DIR")
RUNNER_LOG_DIR=$(c3_solution_path "$C3_RUNNER_LOG_DIR" "$C3_ASSESSMENT_ROOT" "$SOLUTION_DIR")
SCRATCH_ROOT=$(c3_solution_path "$RESULTS_ROOT/.scratch" "$C3_ASSESSMENT_ROOT" "$SOLUTION_DIR")
c3_validate_grader_paths "$C3_ASSESSMENT_ROOT" "$SOLUTION_DIR" "$@"
if [[ ! -f .env ]]; then
    echo "Docker grader: missing .env containing the supplied OPENROUTER_API_KEY." >&2
    exit 2
fi

mkdir -p "$C3_PROXY_STATE" "$RUNNER_LOG_DIR" "$SCRATCH_ROOT"
export TMPDIR="$SCRATCH_ROOT"
export C3_PROXY_LEDGER="$RUNNER_LOG_DIR/spend.jsonl"
export C3_PROXY_URL=http://127.0.0.1:8787
export C3_GRADER_PYTHON=/usr/local/bin/python3

PROXY_RUN_PID=""
cleanup() {
    if [[ -n "$PROXY_RUN_PID" ]]; then
        kill "$PROXY_RUN_PID" 2>/dev/null || true
        wait "$PROXY_RUN_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

python3 proxy/server.py --env "$C3_ASSESSMENT_ROOT/.env" \
    --state "$C3_PROXY_STATE" >"$RUNNER_LOG_DIR/proxy.log" 2>&1 &
PROXY_RUN_PID=$!

# Fail closed if the real proxy cannot start or does not load an upstream key.
# The health response contains a boolean, never the credential itself.
if ! python3 - <<'PY'
import json
import time
import urllib.error
import urllib.request

for _ in range(100):
    try:
        with urllib.request.urlopen("http://127.0.0.1:8787/healthz", timeout=1) as response:
            health = json.load(response)
        if health.get("ok") and health.get("key_loaded"):
            break
        raise SystemExit("Docker grader: proxy did not load OPENROUTER_API_KEY from .env.")
    except (OSError, urllib.error.URLError):
        time.sleep(0.1)
else:
    raise SystemExit("Docker grader: model proxy did not become healthy.")
PY
then
    echo "Docker grader: see $RUNNER_LOG_DIR/proxy.log for startup details." >&2
    exit 2
fi

# Keep temporary case workspaces under the identically mounted host repository.
# Host Docker must be able to bind these paths into each assessed fixer image.
./grade.sh --proxy http --mode docker \
    --concurrency 1 --eval-workers 1 \
    --tmp "$SCRATCH_ROOT" \
    --out "$RESULTS_ROOT/grade-${RUNNER_LOG_DIR##*/}" "${C3_VALIDATED_ARGS[@]}"
