"""Validation contracts, using real child processes and a tiny simulator."""

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "fixer"))
import validation as validation_module
from validation import MAX_OUTPUT, Validation


@pytest.fixture
def validator(tmp_path):
    workspace = tmp_path / "case"
    workspace.mkdir()
    (workspace / "src").mkdir()
    (workspace / "src" / "service.py").write_text("VALUE = 1\n")
    return Validation(workspace, tmp_path / "scratch", time.time() + 90,
                      threading.Event())


@pytest.fixture
def simulator(validator):
    sim = validator.workspace / "sim"
    sim.mkdir()
    (sim / "__init__.py").write_text("")
    (sim / "__main__.py").write_text('''
import json, os, sys
from pathlib import Path
assert os.environ['PYTHONHASHSEED'] == '0'
args = sys.argv[1:]
if args[0] == 'replay':
    out = Path(args[args.index('--out') + 1])
    seed = int(args[args.index('--seed') + 1])
    (out / 'trace.jsonl').write_text('{}\\n')
    (out / 'summary.json').write_text(json.dumps({'seed': seed, 'outcomes': {'ok': 1}, 'actions': ['large-action-record'] * 1000}))
    print(json.dumps({'seed': seed, 'replay_complete': True}))
    sys.exit(3 if seed == 4 else 0)
assert args[0] == 'check'
summary_path = Path(args[args.index('--trace') + 1]).parent / 'summary.json'
summary = json.loads(summary_path.read_text())
violations = [{'invariant': 'I2', 'detail': 'lost accepted operation'}] if summary['seed'] == 1 else []
if summary['seed'] != 3:
    summary['invariants'] = violations
summary_path.write_text(json.dumps(summary))
print(json.dumps({'invariants': violations, 'violations': len(violations)}))
sys.exit(1 if violations else 0)
''')
    return validator


def _running(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    stat = Path(f"/proc/{pid}/stat")
    if stat.exists() and stat.read_text().split()[2] == "Z":
        return False
    return True


def _wait_for_file(path, timeout=3):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if path.exists():
            return
        time.sleep(0.02)
    pytest.fail(f"child never created {path}")


def test_replay_success_still_checks_invariants(simulator):
    result = simulator.replay_check(1)
    assert result["replay_exit"] == 0
    assert result["check_exit"] == 1
    assert not result["ok"]
    assert result["violation_count"] == 1
    assert result["violations"][0]["invariant"] == "I2"
    assert Path(result["trace_path"]).is_file()
    assert "actions" not in result["summary"]
    assert len(json.loads(Path(result["summary_path"]).read_text())["actions"]) == 1000
    assert result["replay"]["elapsed_s"] > 0
    assert result["check"]["elapsed_s"] > 0


def test_replays_use_unique_artifacts_and_require_checked_summary(simulator):
    first = simulator.replay_check(2)
    second = simulator.replay_check(2, faults={"network": {"drop": 0.1}})
    assert first["ok"] and second["ok"]
    assert first["trace_path"] != second["trace_path"]
    assert (Path(second["trace_path"]).parent / "faults.json").is_file()
    missing_result = simulator.replay_check(3)
    assert missing_result["check_exit"] == 0
    assert not missing_result["ok"]


def test_failed_replay_never_counts_as_checked(simulator):
    result = simulator.replay_check(4)
    assert result["replay_exit"] == 3
    assert result["check_exit"] is None
    assert not result["ok"]


def test_source_syntax_compiled_without_bytecode(validator):
    assert validator.compile_source()["ok"]
    assert not list((validator.workspace / "src").rglob("__pycache__"))
    (validator.workspace / "src" / "service.py").write_text("def broken(:\n")
    report = validator.compile_source()
    assert not report["ok"]
    assert "SyntaxError" in report["output"]


def test_actual_pytest_pass_and_failure(validator):
    tests = validator.workspace / "tests"
    tests.mkdir()
    test = tests / "test_public.py"
    test.write_text("import os\ndef test_environment():\n    assert os.environ['PYTHONHASHSEED'] == '0'\n")
    assert validator.run_tests()["ok"]
    test.write_text("def test_regression():\n    assert False, 'public regression'\n")
    result = validator.run_tests()
    assert not result["ok"]
    assert "public regression" in result["output"]


def test_snapshot_restore_removes_new_source_and_preserves_unrelated_files(validator):
    root = validator.workspace
    source = root / "src"
    (source / "__pycache__").mkdir()
    (source / "__pycache__" / "service.pyc").write_bytes(b"cache")
    (source / "nested").mkdir()
    (source / "nested" / "removed.py").write_text("ORIGINAL = True\n")
    (source / "service-link.py").symlink_to("service.py")
    unrelated = root / "README.md"
    unrelated.write_text("must survive restore\n")
    snapshot = validator.snapshot("before/patch")
    assert not (snapshot / "__pycache__").exists()
    assert (snapshot / "service-link.py").is_symlink()
    (source / "service.py").write_text("VALUE = 999\n")
    (source / "new.py").write_text("NEW = True\n")
    (source / "nested" / "removed.py").unlink()
    validator.restore(snapshot)
    assert (source / "service.py").read_text() == "VALUE = 1\n"
    assert (source / "nested" / "removed.py").read_text() == "ORIGINAL = True\n"
    assert not (source / "new.py").exists()
    assert not (source / "__pycache__").exists()
    assert (source / "service-link.py").is_symlink()
    assert unrelated.read_text() == "must survive restore\n"
    assert not list(root.glob(".fixer-restore-*"))


def test_restore_rejects_unknown_checkpoint(validator):
    with pytest.raises(ValueError, match="checkpoint made by"):
        validator.restore(validator.workspace)
    assert (validator.workspace / "src" / "service.py").is_file()


def test_deadline_and_stop_prevent_process_launch(validator, monkeypatch):
    def unexpected(*args, **kwargs):
        pytest.fail("expired/stopped validation must not launch a subprocess")
    monkeypatch.setattr(validation_module.subprocess, "Popen", unexpected)
    validator.deadline = time.time() + 1
    result = validator.compile_source()
    assert not result["ok"] and result["timed_out"]
    validator.deadline = time.time() + 90
    validator.stop.set()
    result = validator.run_tests()
    assert not result["ok"] and result["cancelled"]


def test_timeout_kills_process_group_including_term_ignoring_child(validator):
    script = '''
import signal, subprocess, sys, time
signal.signal(signal.SIGTERM, signal.SIG_IGN)
child = subprocess.Popen([sys.executable, '-c', 'import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(60)'])
print(child.pid, flush=True)
time.sleep(60)
'''
    result = validator._run([sys.executable, "-c", script], timeout_s=0.5)
    assert result["timed_out"] and not result["ok"]
    assert result["elapsed_s"] < 2
    child_pid = int(result["output"].strip())
    assert not _running(child_pid)
    assert not validator._children


def test_sigterm_handler_cancels_validation_and_reaps_child(validator):
    marker = validator.workspace / "child.pid"
    child_script = (
        "import os,signal,time; from pathlib import Path; "
        "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
        f"Path({str(marker)!r}).write_text(str(os.getpid())); time.sleep(60)"
    )
    wrapper = f'''
import json, signal, sys, threading, time
from pathlib import Path
sys.path.insert(0, {str(Path(validation_module.__file__).parent)!r})
from validation import Validation
stop = threading.Event()
signal.signal(signal.SIGTERM, lambda *_: stop.set())
validator = Validation(Path({str(validator.workspace)!r}), Path({str(validator.scratch)!r}), time.time()+90, stop)
result = validator._run([sys.executable, '-c', {child_script!r}], 60)
print(json.dumps(result), flush=True)
'''
    process = subprocess.Popen([sys.executable, "-c", wrapper], stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, start_new_session=True)
    try:
        _wait_for_file(marker)
        process.send_signal(signal.SIGTERM)
        stdout, stderr = process.communicate(timeout=3)
        assert process.returncode == 0, stderr.decode()
        result = json.loads(stdout)
        assert result["cancelled"] and not result["ok"]
        assert not _running(int(marker.read_text()))
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=2)


def test_exited_parent_does_not_hang_on_inherited_stdout(validator):
    script = '''
import subprocess,sys
child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
print(child.pid, flush=True)
'''
    result = validator._run([sys.executable, "-c", script], timeout_s=3)
    assert result["ok"]
    assert result["elapsed_s"] < 1.5
    assert not _running(int(result["output"].strip()))


def test_cleanup_waits_for_descendant_after_leader_exited(monkeypatch):
    class ExitedProcess:
        pid = 12345

        def wait(self, timeout):
            return 0

    signals = []
    running_states = iter([True, True, False])
    observed = []

    def group_running(pgid):
        observed.append(pgid)
        return next(running_states)

    monkeypatch.setattr(Validation, "_signal_group", lambda process, sig: signals.append(sig))
    monkeypatch.setattr(Validation, "_group_running", group_running)
    assert Validation._terminate(ExitedProcess())
    assert signals == [signal.SIGTERM, signal.SIGKILL]
    assert observed == [12345, 12345, 12345]


def test_unconfirmed_cleanup_is_reported_as_validation_failure(validator, monkeypatch):
    monkeypatch.setattr(Validation, "_terminate", staticmethod(lambda process: False))
    result = validator._run([sys.executable, "-c", "print('command completed')"], 3)
    assert result["exit_code"] == 0
    assert not result["ok"]
    assert "cleanup failed" in result["output"]
    assert validator._children  # Retain the handle for another shutdown attempt.


def test_command_output_is_bounded(validator):
    result = validator._run([sys.executable, "-c", "print('x' * 1000000)"], 3)
    assert result["ok"]
    assert result["truncated"]
    assert len(result["output"]) <= MAX_OUTPUT


def test_simulator_artifact_growth_stops_command(validator, monkeypatch):
    monkeypatch.setattr(validation_module, "MAX_ARTIFACT_BYTES", 100)
    output = validator.scratch / "too-large"
    output.mkdir()
    script = (
        "import time; from pathlib import Path; "
        f"Path({str(output / 'trace.jsonl')!r}).write_bytes(b'x'*10000); time.sleep(60)"
    )
    result = validator._run([sys.executable, "-c", script], 3, artifact_dir=output)
    assert not result["ok"] and result["artifact_limit"]
    assert result["elapsed_s"] < 2
