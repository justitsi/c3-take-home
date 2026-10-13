import copy

from benchmark import CASES, compare


def result(fixed):
    return {"complete": True, "bugs_fixed": fixed, "image_id": "sha256:fixture", "source_ref": "fixture",
            "cases": {case: {"bugs": [{"id": "bug-1", "seeds_total": 20}], "bugs_fixed": 0,
                             "tests_ok": True, "regression_ok": True} for case in CASES}}


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
