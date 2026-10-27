#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd -P)
IMAGE=${C3_V3_IMAGE:-c3-fixer-prototype:v3.2}
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
OUT=${C3_V3_OUT:-"$ROOT/results/v3-$STAMP"}

if [[ $# -gt 0 && "$1" == "--help" ]]; then
    cat <<'EOF'
Usage: solution/run-v3.sh [grader options]

Builds the V3 fixer image, runs the official Docker grader on practice cases,
and reports the number of bugs fixed per case and overall.

Environment:
  C3_V3_IMAGE  Docker image tag (default: c3-fixer-prototype:v3.2)
  C3_V3_OUT    Results directory (default: results/v3-<UTC timestamp>)

Requires Docker and solution/.env with the supplied grading proxy key.
Additional arguments are passed to the grader wrapper.
EOF
    exit 0
fi

if [[ ! -f "$SCRIPT_DIR/.env" ]]; then
    echo "V3 runner: add the supplied OPENROUTER_API_KEY to $SCRIPT_DIR/.env first." >&2
    exit 2
fi

docker build --platform linux/amd64 -t "$IMAGE" "$SCRIPT_DIR/fixer"

mkdir -p "$(dirname "$OUT")"
"$SCRIPT_DIR/grade-docker.sh" \
    --fixer "$IMAGE" \
    --cases practice \
    --concurrency 1 \
    --eval-workers 1 \
    --keep \
    --out "$OUT" \
    "$@"

SUMMARY="$OUT/summary.json"
if [[ ! -f "$SUMMARY" ]]; then
    echo "V3 runner: grading finished but summary is missing: $SUMMARY" >&2
    exit 1
fi

python3 - "$SUMMARY" "$OUT" <<'PY'
import json
import sys
from pathlib import Path

summary_path, output_dir = Path(sys.argv[1]), Path(sys.argv[2])
summary = json.loads(summary_path.read_text(encoding="utf-8"))
results = summary.get("results", [])
total_fixed = 0
total_bugs = 0

print(f"\nV3 results: {output_dir}")
for result in results:
    case = result.get("case", "unknown")
    case_result_path = output_dir / case / "result.json"
    fixed = int(result.get("bugs_fixed", 0))
    bugs = []
    if case_result_path.is_file():
        case_result = json.loads(case_result_path.read_text(encoding="utf-8"))
        bugs = case_result.get("bugs", [])
        if bugs:
            fixed = sum(bool(bug.get("fixed")) for bug in bugs)
    total_fixed += fixed
    total_bugs += len(bugs)
    denominator = f"/{len(bugs)}" if bugs else ""
    print(f"  {case}: {fixed}{denominator} bugs fixed")

reported_fixed = int(summary.get("bugs_fixed", total_fixed))
reported_total = int(summary.get("bugs_total", total_bugs))
print(f"Total: {reported_fixed}/{reported_total} bugs fixed across {summary.get('cases', len(results))} cases")
if summary.get("infra_errors"):
    print(f"Infrastructure errors: {len(summary['infra_errors'])}")
    for error in summary["infra_errors"]:
        print(f"  - {error}")
PY
