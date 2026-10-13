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


def _integer(value) -> bool:
    return type(value) is int and value >= 0


def _evidence(report: dict, label: str, reasons: list[str]) -> tuple[dict, int]:
    """Validate score provenance before using any headline as promotion evidence."""
    cases = report.get("cases")
    if not isinstance(cases, dict):
        reasons.append(f"{label}: missing case evidence")
        return {}, 0
    if report.get("complete") is not True or set(cases) != CASES:
        reasons.append(f"{label}: all six practice cases must have complete evidence")
    if report.get("infrastructure_errors") or report.get("missing_cases"):
        reasons.append(f"{label}: report contains missing cases or infrastructure errors")
    coverage = {}
    credited_total = 0
    bug_total = 0
    for case, result in sorted(cases.items()):
        prefix = f"{label} {case}"
        if not isinstance(result, dict):
            reasons.append(f"{prefix}: missing result evidence")
            continue
        if result.get("infra_error") is not None:
            reasons.append(f"{prefix}: infrastructure failure")
        if label == "candidate":
            if "infra_error" not in result:
                reasons.append(f"{prefix}: infrastructure status is missing")
            if result.get("tests_ok") is not True or result.get("regression_ok") is not True:
                reasons.append(f"{prefix}: public and regression gates must both pass")
            if type(result.get("fixer_exit")) is not int or result["fixer_exit"] != 0:
                reasons.append(f"{prefix}: fixer must exit zero")
            if result.get("timed_out") is not False:
                reasons.append(f"{prefix}: fixer timeout status must be false")
        bugs = result.get("bugs")
        if not isinstance(bugs, list) or not bugs:
            reasons.append(f"{prefix}: missing per-bug evidence")
            continue
        bug_total += len(bugs)
        ids = set()
        case_coverage = set()
        credited = 0
        for bug in bugs:
            if not isinstance(bug, dict):
                reasons.append(f"{prefix}: malformed bug evidence")
                continue
            bug_id = bug.get("id")
            total, passed, fixed = bug.get("seeds_total"), bug.get("seeds_passed"), bug.get("fixed")
            if not isinstance(bug_id, str) or not bug_id or bug_id in ids:
                reasons.append(f"{prefix}: bug IDs must be non-empty and unique")
            else:
                ids.add(bug_id)
                if _integer(total):
                    case_coverage.add((bug_id, total))
            if type(fixed) is not bool:
                reasons.append(f"{prefix}: fixed flags must be explicit booleans")
            if not _integer(total) or total != 20 or not _integer(passed) or passed > 20:
                reasons.append(f"{prefix}: each bug needs coherent counts across 20 seeds")
            if fixed is True:
                credited += 1
                if type(passed) is not int or passed != 20 or type(total) is not int or total != 20:
                    reasons.append(f"{prefix}: credited bug must pass all 20 seeds")
            # A later chained bug can pass its own seeds yet remain uncredited
            # until a prerequisite is repaired, so false does not imply <20.
        coverage[case] = case_coverage
        if not _integer(result.get("bugs_fixed")) or result["bugs_fixed"] != credited:
            reasons.append(f"{prefix}: case score disagrees with credited bug flags")
        credited_total += credited
    if not _integer(report.get("bugs_fixed")) or report["bugs_fixed"] != credited_total:
        reasons.append(f"{label}: headline score disagrees with credited bug flags")
    if "bugs_total" in report and (not _integer(report["bugs_total"]) or report["bugs_total"] != bug_total):
        reasons.append(f"{label}: headline bug total disagrees with per-bug evidence")
    return coverage, credited_total


def compare(baseline: dict, candidate: dict) -> dict:
    reasons = []
    old_coverage, old_score = _evidence(baseline, "baseline", reasons)
    new_coverage, new_score = _evidence(candidate, "candidate", reasons)
    if set(old_coverage) != set(new_coverage):
        reasons.append("case sets differ")
    for case in sorted(set(old_coverage) & set(new_coverage)):
        if old_coverage[case] != new_coverage[case]:
            reasons.append(f"{case}: bug/seed coverage differs")
    improvement = new_score - old_score
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
