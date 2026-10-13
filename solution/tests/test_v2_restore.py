"""Restore/shutdown interleavings, including a filesystem without atomic exchange."""

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

import pytest

import validation as validation_module
from validation import Validation
from test_v2_guards import guarded_harness


@pytest.fixture
def restore_validator(tmp_path):
    workspace = tmp_path / "workspace"
    (workspace / "src").mkdir(parents=True)
    (workspace / "src/service.py").write_text("VALIDATED = True\n")
    return Validation(workspace, tmp_path / "scratch", time.time() + 90, threading.Event())


def test_native_directory_exchange_swaps_complete_trees_without_replace_gap(restore_validator, monkeypatch):
    validator = restore_validator
    source = validator.workspace / "src"
    first, second = validator.workspace / "exchange-first", validator.workspace / "exchange-second"
    first.mkdir()
    second.mkdir()
    (first / "value").write_text("first")
    (second / "value").write_text("second")
    if not validator._exchange_directories(first, second):
        pytest.skip("native atomic directory exchange is unavailable on this filesystem")
    assert (first / "value").read_text() == "second"
    assert (second / "value").read_text() == "first"
    checkpoint = validator.snapshot("supported")
    (source / "service.py").write_text("VALIDATED = False\n")
    (source / "new.py").write_text("UNCHECKED = True\n")
    original_exchange = Validation._exchange_directories
    observed = []

    def exchange(a, b):
        assert a.is_dir() and b.is_dir()
        outcome = original_exchange(a, b)
        assert outcome and a.is_dir() and b.is_dir()
        observed.append((a, b))
        return outcome

    def unexpected_replace(*_args, **_kwargs):
        pytest.fail("native exchange must not move src away through a two-rename fallback")

    monkeypatch.setattr(Validation, "_exchange_directories", staticmethod(exchange))
    monkeypatch.setattr(validation_module.os, "replace", unexpected_replace)
    validator.restore(checkpoint)
    assert len(observed) == 1
    assert (source / "service.py").read_text() == "VALIDATED = True\n"
    assert not (source / "new.py").exists()
    assert validator.ensure_source_present()


def test_fallback_gap_can_be_recovered_before_restore_owner_resumes(restore_validator, monkeypatch):
    validator = restore_validator
    source = validator.workspace / "src"
    checkpoint = validator.snapshot("supported")
    (source / "service.py").write_text("VALIDATED = False\n")
    replace = validation_module.os.replace
    recovered = []
    monkeypatch.setattr(Validation, "_exchange_directories", staticmethod(lambda *_: False))

    def recover_during_gap(first, second):
        outcome = replace(first, second)
        if Path(first) == source:
            assert not source.exists()
            assert validator.ensure_source_present()
            assert (source / "service.py").read_text() == "VALIDATED = True\n"
            recovered.append(True)
        return outcome

    monkeypatch.setattr(validation_module.os, "replace", recover_during_gap)
    validator.restore(checkpoint)
    assert recovered == [True]
    assert (source / "service.py").read_text() == "VALIDATED = True\n"
    assert validator._pending_restore is None
    assert not list(validator.workspace.glob(".fixer-restore-*"))


def test_fallback_install_failure_preserves_complete_previous_source(restore_validator, monkeypatch):
    validator = restore_validator
    source = validator.workspace / "src"
    checkpoint = validator.snapshot("supported")
    (source / "service.py").write_text("VALIDATED = False\n")
    before = (source / "service.py").read_bytes()
    replace = validation_module.os.replace
    monkeypatch.setattr(Validation, "_exchange_directories", staticmethod(lambda *_: False))

    def fail_install(first, second):
        if Path(first).name == "src" and Path(first).parent.name.startswith(".fixer-restore-") and Path(second) == source:
            raise OSError("fixture staged-source installation failed")
        return replace(first, second)

    monkeypatch.setattr(validation_module.os, "replace", fail_install)
    with pytest.raises(OSError, match="installation failed"):
        validator.restore(checkpoint)
    assert source.is_dir()
    assert (source / "service.py").read_bytes() == before
    assert validator.ensure_source_present()


def test_failed_recovery_keeps_staged_checkpoint_for_later_emergency_attempt(restore_validator, monkeypatch):
    validator = restore_validator
    source = validator.workspace / "src"
    checkpoint = validator.snapshot("supported")
    (source / "service.py").write_text("VALIDATED = False\n")
    replace = validation_module.os.replace
    monkeypatch.setattr(Validation, "_exchange_directories", staticmethod(lambda *_: False))

    def fail_recovery(first, second):
        if Path(second) == source:
            raise PermissionError("fixture filesystem temporarily rejects installation")
        return replace(first, second)

    with monkeypatch.context() as context:
        context.setattr(validation_module.os, "replace", fail_recovery)
        with pytest.raises(OSError):
            validator.restore(checkpoint)
        assert not source.exists()
        assert validator._pending_restore is not None
        assert not validator.ensure_source_present()
        _, staged, previous = validator._pending_restore
        assert staged.is_dir() and previous.is_dir()
    assert validator.ensure_source_present()
    assert (source / "service.py").read_text() == "VALIDATED = True\n"


def test_sigterm_during_final_rollback_restores_source_before_process_exit(guarded_harness):
    harness, _, _ = guarded_harness
    workspace = harness.workspace
    marker = workspace / "restore-gap.marker"
    module_path = str(Path(validation_module.__file__).parent)
    script = f'''
import os,signal,threading,time
from pathlib import Path
from fix import Harness,check_key
import validation
h=Harness()
source=h.workspace/'src'
(source/'service.py').write_text('STATE = 1\\nSECOND = 0\\n')
h.patch_count=1
supported=h.validation.snapshot('supported-first')
for seed in h.seeds:
    h.observe_check({{'seed':seed,'spec':{{'seed':seed,'scenario':'public'}},'ok':True,
        'replay_exit':0,'check_exit':0,'violations':[],'deterministic':True}})
prior=h.checkpoint_state(supported)
(source/'service.py').write_text('STATE = 2\\nSECOND = 0\\n')
h.patch_count=2
h.best_snapshot=h.validation.snapshot('latent-bad-candidate')
h.checkpoints=[prior]
report={{'syntax':{{'ok':True}},'tests':{{'ok':True}},'replays':[
    {{'seed':seed,'spec':{{'seed':seed,'scenario':'public'}},'ok':False,
      'replay_exit':0,'check_exit':1,'violations':[{{'invariant':'I_new'}}],
      'deterministic':True}} for seed in h.seeds]}}
h.checks=lambda *_args,**_kwargs:report
h.extra_checks=lambda *_args,**_kwargs:None
h.validation._exchange_directories=lambda *_args:False
replace=validation.os.replace
def block_owner_in_gap(first,second):
    outcome=replace(first,second)
    if Path(first)==source:
        Path({str(marker)!r}).write_text('restore owner paused after first rename')
        threading.Event().wait(60)
    return outcome
validation.os.replace=block_owner_in_gap
shutdown=threading.Event()
signal.signal(signal.SIGTERM,lambda *_:shutdown.set())
def watchdog():
    shutdown.wait()
    h.terminate('SIGTERM')
threading.Thread(target=watchdog,daemon=True).start()
h.final_validation()
raise SystemExit('fixture expected SIGTERM while rollback was paused')
'''
    env = dict(os.environ, PYTHONPATH=module_path, PYTHONDONTWRITEBYTECODE="1")
    process = subprocess.Popen([sys.executable, "-c", script], cwd=workspace, env=env,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        end_at = time.monotonic() + 5
        while not marker.exists() and time.monotonic() < end_at:
            if process.poll() is not None:
                pytest.fail(f"controller exited before the restore gap: {process.communicate()[0]}")
            time.sleep(0.02)
        assert marker.exists(), "final rollback did not reach the forced filesystem gap"
        process.send_signal(signal.SIGTERM)
        output, _ = process.communicate(timeout=5)
        assert process.returncode == 0, output
        assert '"status": "SIGTERM"' in output
        assert (workspace / "src").is_dir()
        assert (workspace / "src/service.py").read_text() == "STATE = 1\nSECOND = 0\n"
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=2)
