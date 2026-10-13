import copy

import pytest

from benchmark import CASES, compare


def result(fixed):
    cases = {}
    for index, case in enumerate(sorted(CASES)):
        credited = index < fixed
        cases[case] = {
            "bugs": [{"id": "bug-1", "fixed": credited,
                      "seeds_passed": 20 if credited else 0, "seeds_total": 20}],
            "bugs_fixed": int(credited), "tests_ok": True, "regression_ok": True,
            "fixer_exit": 0, "timed_out": False, "infra_error": None,
        }
    return {"complete": True, "bugs_fixed": fixed, "bugs_total": len(CASES),
            "image_id": "sha256:fixture", "source_ref": "fixture", "cases": cases}


def test_only_strict_complete_improvement_promotes():
    baseline = result(0)
    candidate = result(1)
    assert compare(baseline, candidate)["promote"]
    assert not compare(candidate, copy.deepcopy(candidate))["promote"]
    candidate["complete"] = False
    assert not compare(baseline, candidate)["promote"]


def test_different_seed_coverage_cannot_promote():
    baseline, candidate = result(0), result(1)
    candidate["cases"]["B2"]["bugs"][0]["seeds_total"] = 1
    assert not compare(baseline, candidate)["promote"]


@pytest.mark.parametrize("gate,value", [
    ("tests_ok", False), ("regression_ok", False), ("tests_ok", None),
    ("regression_ok", "true"), ("tests_ok", 1),
])
def test_zero_score_case_regression_blocks_other_case_improvement(gate, value):
    baseline, candidate = result(0), result(1)
    assert candidate["cases"]["B2"]["bugs_fixed"] == 0
    candidate["cases"]["B2"][gate] = value
    compared = compare(baseline, candidate)
    assert not compared["promote"]
    assert any("candidate B2" in reason and "gates" in reason for reason in compared["reasons"])


@pytest.mark.parametrize("field,value", [
    ("fixer_exit", 1), ("fixer_exit", -9), ("fixer_exit", None), ("fixer_exit", False),
    ("timed_out", True), ("timed_out", None), ("timed_out", "false"),
    ("infra_error", "proxy unavailable"),
])
def test_zero_score_case_process_failure_blocks_promotion(field, value):
    baseline, candidate = result(0), result(1)
    candidate["cases"]["B2"][field] = value
    assert not compare(baseline, candidate)["promote"]


@pytest.mark.parametrize("field", ["tests_ok", "regression_ok", "fixer_exit", "timed_out", "infra_error"])
def test_missing_zero_score_case_gate_evidence_blocks_promotion(field):
    baseline, candidate = result(0), result(1)
    candidate["cases"]["B2"].pop(field)
    assert not compare(baseline, candidate)["promote"]


@pytest.mark.parametrize("field,value", [
    ("seeds_passed", 19), ("seeds_passed", 21), ("seeds_passed", -1),
    ("seeds_passed", "20"), ("seeds_passed", True), ("seeds_total", 19),
    ("seeds_total", None), ("fixed", "true"), ("fixed", 1),
])
def test_credited_bug_requires_explicit_flag_and_all_twenty_seeds(field, value):
    baseline, candidate = result(0), result(1)
    candidate["cases"]["A1"]["bugs"][0][field] = value
    assert not compare(baseline, candidate)["promote"]


def test_same_undercovered_seed_counts_on_both_sides_do_not_legitimize_score():
    baseline, candidate = result(0), result(1)
    for report in (baseline, candidate):
        report["cases"]["A1"]["bugs"][0]["seeds_total"] = 1
    candidate["cases"]["A1"]["bugs"][0]["seeds_passed"] = 1
    assert not compare(baseline, candidate)["promote"]


@pytest.mark.parametrize("scope,value", [("case", 0), ("case", True), ("headline", 2), ("headline", "1")])
def test_headline_and_case_scores_must_match_credited_flags(scope, value):
    baseline, candidate = result(0), result(1)
    if scope == "case":
        candidate["cases"]["A1"]["bugs_fixed"] = value
    else:
        candidate["bugs_fixed"] = value
    assert not compare(baseline, candidate)["promote"]


def test_malformed_baseline_headline_cannot_support_promotion():
    baseline, candidate = result(0), result(1)
    baseline["bugs_fixed"] = -1
    assert not compare(baseline, candidate)["promote"]


def test_duplicate_bug_ids_do_not_hide_invalid_coverage():
    baseline, candidate = result(0), result(1)
    for report in (baseline, candidate):
        report["cases"]["B2"]["bugs"].append(copy.deepcopy(report["cases"]["B2"]["bugs"][0]))
        report["bugs_total"] += 1
    assert not compare(baseline, candidate)["promote"]


@pytest.mark.parametrize("alteration", ["missing", "extra"])
def test_forged_complete_flags_cannot_hide_missing_or_extra_cases(alteration):
    baseline, candidate = result(0), result(1)
    for report in (baseline, candidate):
        if alteration == "missing":
            report["cases"].pop("B2")
            report["bugs_total"] -= 1
        else:
            report["cases"]["extra-case"] = copy.deepcopy(report["cases"]["B2"])
            report["bugs_total"] += 1
    assert not compare(baseline, candidate)["promote"]


def test_chained_uncredited_bug_can_pass_own_seeds_without_being_counted():
    baseline, candidate = result(0), result(1)
    candidate["cases"]["B2"]["bugs"][0]["seeds_passed"] = 20
    assert compare(baseline, candidate)["promote"]


def test_missing_or_malformed_bug_evidence_fails_closed():
    baseline, candidate = result(0), result(1)
    candidate["cases"]["B2"]["bugs"] = [None]
    assert not compare(baseline, candidate)["promote"]


def test_mismatched_bug_id_and_reported_bug_total_block_promotion():
    baseline, candidate = result(0), result(1)
    candidate["cases"]["B2"]["bugs"][0]["id"] = "different-bug"
    assert not compare(baseline, candidate)["promote"]
    candidate = result(1)
    candidate["bugs_total"] += 1
    assert not compare(baseline, candidate)["promote"]
