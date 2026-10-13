#!/usr/bin/env python3
"""Collect official grader results and require a strictly better, comparable score."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

CASES = {"A1", "A2", "A3", "B1", "B2", "B3"}
FIELDS = ("case", "fixer_exit", "timed_out", "wall_s", "spend_usd", "input_tokens",
          "cached_input_tokens", "output_tokens", "patch_sha256", "patch_files",
          "tests_ok", "regression_ok", "bugs_fixed", "bugs", "infra_error")


def collect(directories: list[Path], image: str, source_ref: str, image_id: str) -> dict:
    cases = {}
    for directory in directories:
        for path in sorted(directory.glob("*/result.json")):
            raw = json.loads(path.read_text())
            case = raw["case"]
            # A successful serial retry replaces an infrastructure failure.
            # Failed retries never silently replace existing valid evidence.
            if raw.get("infra_error") and case in cases and not cases[case].get("infra_error"):
                continue
            cases[case] = {key: raw.get(key) for key in FIELDS}
            cases[case]["result_path"] = str(path)
    missing = sorted(CASES - cases.keys())
    errors = [case for case, result in cases.items() if result.get("infra_error")]
    valid = [result for result in cases.values() if not result.get("infra_error")]
    return {"image": image, "image_id": image_id, "source_ref": source_ref,
            "cases": cases, "missing_cases": missing, "infrastructure_errors": errors,
            "complete": not missing and not errors and set(cases) == CASES,
            "bugs_fixed": sum(int(r["bugs_fixed"] or 0) for r in valid),
            "bugs_total": sum(len(r["bugs"] or []) for r in valid),
            "spend_usd": round(sum(float(r["spend_usd"] or 0) for r in cases.values()), 6),
            "fixer_wall_s": round(sum(float(r["wall_s"] or 0) for r in valid), 3)}


def compare(baseline: dict, candidate: dict) -> dict:
    reasons = []
    if not baseline.get("complete") or not candidate.get("complete"):
        reasons.append("all six cases must have non-infrastructure results for both versions")
    if set(baseline.get("cases", {})) != set(candidate.get("cases", {})):
        reasons.append("case sets differ")
    for case in set(baseline.get("cases", {})) & set(candidate.get("cases", {})):
        old = baseline["cases"][case]
        new = candidate["cases"][case]
        old_bugs = {(b["id"], b["seeds_total"]) for b in old.get("bugs") or []}
        new_bugs = {(b["id"], b["seeds_total"]) for b in new.get("bugs") or []}
        if old_bugs != new_bugs:
            reasons.append(f"{case}: bug/seed coverage differs")
        if new.get("bugs_fixed") and not (new.get("tests_ok") and new.get("regression_ok")):
            reasons.append(f"{case}: positive score contradicts regression gates")
    improvement = int(candidate.get("bugs_fixed", 0)) - int(baseline.get("bugs_fixed", 0))
    if improvement <= 0:
        reasons.append("candidate does not fix strictly more bugs")
    return {"promote": not reasons, "baseline_fixed": baseline.get("bugs_fixed", 0),
            "candidate_fixed": candidate.get("bugs_fixed", 0), "improvement": improvement,
            "reasons": reasons, "candidate_image_id": candidate.get("image_id"),
            "candidate_source_ref": candidate.get("source_ref")}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    gather = sub.add_parser("collect")
    gather.add_argument("--results", type=Path, nargs="+", required=True)
    gather.add_argument("--image", required=True)
    gather.add_argument("--image-id", required=True)
    gather.add_argument("--source-ref", required=True)
    gather.add_argument("--out", type=Path, required=True)
    check = sub.add_parser("compare")
    check.add_argument("baseline", type=Path)
    check.add_argument("candidate", type=Path)
    args = parser.parse_args()
    if args.action == "collect":
        report = collect(args.results, args.image, args.source_ref, args.image_id)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        print(json.dumps({key: value for key, value in report.items() if key != "cases"}, indent=2))
        return 0 if report["complete"] else 1
    result = compare(json.loads(args.baseline.read_text()), json.loads(args.candidate.read_text()))
    print(json.dumps(result, indent=2))
    return 0 if result["promote"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
