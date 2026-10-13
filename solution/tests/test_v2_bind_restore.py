"""Portable rollback and fail-closed checkpoint contracts, without case patches.

The opt-in bind-root fixture must point at a Docker host bind mount, not the
container's native /tmp. The lead runs this separately with C3_TEST_BIND_ROOT.
"""

from copy import deepcopy
import errno
import os
from pathlib import Path
import shutil
import tempfile
import threading
import time

import pytest

import fix as harness_module
import validation as validation_module
from validation import Validation
from test_v2_guards import guarded_harness, _baseline, _edit


class _FailedExchange:
    def __init__(self):
        self.calls = []

    def __call__(self, *args):
        self.calls.append(args)
        return -1


@pytest.mark.parametrize("exchange_errno", [errno.ENOTEMPTY, errno.EEXIST])
def test_nonempty_or_exists_exchange_error_uses_complete_portable_restore(tmp_path, monkeypatch, exchange_errno):
    workspace = tmp_path / "workspace"
    source = workspace / "src"
    (source / "nested").mkdir(parents=True)
    (source / "service.py").write_text("VALIDATED = True\n")
    (source / "nested/config.json").write_text('{"preserved": true}\n')
    untouched = workspace / "user-notes.txt"
    untouched.write_text("Outside src must not change.\n")
    validator = Validation(workspace, tmp_path / "scratch", time.time() + 60, threading.Event())
    snapshot = validator.snapshot("supported")
    (source / "service.py").write_text("UNCHECKED = True\n")
    (source / "nested/config.json").unlink()
    (source / "extra.py").write_text("NEW_UNCHECKED_FILE = True\n")
    exchange = _FailedExchange()

    class Library:
        renameat2 = exchange

    monkeypatch.setattr(validation_module.sys, "platform", "linux")
    monkeypatch.setattr(validation_module.ctypes, "CDLL", lambda *_args, **_kwargs: Library())
    monkeypatch.setattr(validation_module.ctypes, "get_errno", lambda: exchange_errno)
    validator.restore(snapshot)
    assert len(exchange.calls) == 1
    assert exchange.calls[0][-1] == 2, "the attempted operation must be RENAME_EXCHANGE"
    assert (source / "service.py").read_text() == "VALIDATED = True\n"
    assert (source / "nested/config.json").read_text() == '{"preserved": true}\n'
    assert not (source / "extra.py").exists()
    assert untouched.read_text() == "Outside src must not change.\n"
    assert validator.ensure_source_present()
    assert validator._pending_restore is None
    assert not list(workspace.glob(".fixer-restore-*"))


@pytest.fixture
def bind_workspace():
    configured = os.environ.get("C3_TEST_BIND_ROOT")
    if not configured:
        pytest.skip("set C3_TEST_BIND_ROOT to an existing Docker host bind mount")
    root = Path(configured).resolve(strict=True)
    assert root.is_dir() and root != Path(root.anchor)
    directory = Path(tempfile.mkdtemp(prefix="c3-bind-restore-", dir=root))
    try:
        yield directory
    finally:
        # Delete only the exact fixture directory allocated above.
        shutil.rmtree(directory)


def test_real_bind_mount_restore_recovers_exact_source_scope(bind_workspace, tmp_path):
    workspace = bind_workspace
    source = workspace / "src"
    (source / "nested").mkdir(parents=True)
    (source / "service.py").write_text("VALIDATED = 17\n")
    (source / "nested/state.json").write_text('{"version": 17}\n')
    (workspace / "tests").mkdir()
    (workspace / "tests/user-test.txt").write_text("Preserve unrelated tests.\n")
    (workspace / "user-notes.txt").write_text("Preserve user content.\n")
    validator = Validation(workspace, tmp_path / "native-scratch", time.time() + 60, threading.Event())
    checkpoint = validator.snapshot("bind-supported")
    expected = {path.relative_to(source): path.read_bytes() for path in source.rglob("*") if path.is_file()}
    for revision in range(3):
        (source / "service.py").write_text(f"UNCHECKED = {revision}\n")
        (source / "nested/state.json").unlink()
        (source / f"added-{revision}.py").write_text("UNCHECKED = True\n")
        validator.restore(checkpoint)  # Real filesystem operation: no forced fallback or fake libc.
        actual = {path.relative_to(source): path.read_bytes() for path in source.rglob("*") if path.is_file()}
        assert actual == expected
        assert validator.ensure_source_present()
        assert validator._pending_restore is None
        assert not list(workspace.glob(".fixer-restore-*"))
        assert (workspace / "tests/user-test.txt").read_text() == "Preserve unrelated tests.\n"
        assert (workspace / "user-notes.txt").read_text() == "Preserve user content.\n"


def _reject_changed_source(harness, behavior):
    behavior["evaluate"] = lambda values, _spec: ["I_original"] if values["STATE"] == 0 else ["I_new"]
    _baseline(harness)


def test_persistent_rollback_failure_retains_checkpoint_and_stops_mutation(guarded_harness, monkeypatch):
    harness, behavior, _ = guarded_harness
    _reject_changed_source(harness, behavior)
    source = harness.workspace / "src/service.py"
    original = source.read_bytes()
    supported = harness.best_snapshot
    registries = deepcopy((harness.check_specs, harness.check_results, harness.check_revisions,
                           harness.passing_checks, harness.seed_results, harness.passing_seeds))
    restores = []

    def fail_restore(checkpoint):
        restores.append(checkpoint)
        raise OSError(errno.EIO, "fixture persistent filesystem rollback failure")

    monkeypatch.setattr(harness.validation, "restore", fail_restore)
    result = _edit(harness, "STATE = 0", "STATE = 1")
    assert result["ok"] is False and result.get("fatal") is True
    assert "rollback failed" in result["error"].lower()
    assert len(restores) >= 2, "a failure-handler retry must not silently discard the checkpoint"
    assert harness.status == harness.stop_reason == "rollback-failed"
    assert harness.stop.is_set()
    assert harness.active_snapshot is not None
    assert (harness.active_snapshot / "service.py").read_bytes() == original
    assert harness.best_snapshot == supported
    assert harness.patch_count == 0
    assert not any(record.get("accepted") for record in harness.records)
    assert (harness.check_specs, harness.check_results, harness.check_revisions,
            harness.passing_checks, harness.seed_results, harness.passing_seeds) == registries
    unchecked = source.read_bytes()
    assert unchecked != original, "fixture must exercise a real unchecked mutation"
    assert not _edit(harness, "STATE = 1", "STATE = 2")["ok"]
    assert source.read_bytes() == unchecked
    assert harness.active_snapshot is not None


def test_run_reports_persistent_restore_failure_not_running_or_verified(guarded_harness, monkeypatch):
    harness, behavior, _ = guarded_harness
    behavior["evaluate"] = lambda values, _spec: ["I_original"] if values["STATE"] == 0 else ["I_new"]
    original = (harness.workspace / "src/service.py").read_bytes()
    reports, results, restores = [], [], []

    def fail_restore(checkpoint):
        restores.append(checkpoint)
        raise OSError(errno.EIO, "fixture persistent filesystem rollback failure")

    def edit(_context):
        results.append(_edit(harness, "STATE = 0", "STATE = 1"))

    monkeypatch.setattr(harness.validation, "restore", fail_restore)
    monkeypatch.setattr(harness_module, "build_context", lambda *_args, **_kwargs: "Generic fixture contracts.")
    monkeypatch.setattr(harness_module.signal, "signal", lambda *_args: None)
    monkeypatch.setattr(harness, "investigate", lambda profile, _context: {"agent": profile[0], "finding": "No supported fixture claim."})
    monkeypatch.setattr(harness, "edit", edit)
    monkeypatch.setattr(harness, "report", lambda status: reports.append(status))
    with pytest.raises(harness_module.RollbackFailed, match="(?i)rollback"):
        harness.run()
    assert results and results[0].get("fatal") is True
    assert len(restores) >= 3, "run finalization must retry the retained validated checkpoint"
    assert reports and reports[-1] == "rollback-failed"
    assert "running" not in reports and "public-verified" not in reports
    assert harness.status == harness.stop_reason == "rollback-failed"
    assert harness.patch_count == 0
    assert harness.active_snapshot is not None
    assert (harness.active_snapshot / "service.py").read_bytes() == original
    assert harness.final_result.get("all_passed") is not True
    assert harness.finished.is_set(), "watchdog finalization must complete even when restoration fails"


def test_final_validation_restore_failure_retains_checkpoint_and_explicit_failure(guarded_harness, monkeypatch):
    harness, behavior, _ = guarded_harness
    _baseline(harness)
    assert _edit(harness, "STATE = 0", "STATE = 1")["ok"]
    assert harness.patch_count == 1 and harness.checkpoints
    prior = harness.checkpoints[-1]["snapshot"]
    before_source = (harness.workspace / "src/service.py").read_bytes()
    before_results = deepcopy(harness.check_results)
    behavior["evaluate"] = lambda values, _spec: ["I_latent"] if values["STATE"] == 1 else ["I_original"]
    restores = []

    def fail_restore(checkpoint):
        restores.append(checkpoint)
        raise OSError(errno.EIO, "fixture persistent final rollback failure")

    monkeypatch.setattr(harness.validation, "restore", fail_restore)
    with pytest.raises(harness_module.RollbackFailed, match="(?i)rollback"):
        harness.final_validation()
    assert restores == [prior]
    assert harness.status == harness.stop_reason == "rollback-failed"
    assert harness.stop.is_set()
    assert harness.active_snapshot == prior
    assert (prior / "service.py").read_text() == "STATE = 0\nSECOND = 0\n"
    assert harness.patch_count == 1, "never claim the prior revision before source restoration succeeds"
    assert harness.check_results == before_results
    assert (harness.workspace / "src/service.py").read_bytes() == before_source
    assert harness.final_result.get("all_passed") is not True
