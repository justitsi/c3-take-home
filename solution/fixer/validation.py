"""Bounded validation commands and source-only checkpoints.

Replay merely produces a trace: only a separate ``sim check`` proves that the
public invariants passed. No command is run through a shell.
"""

from __future__ import annotations

import json
import ctypes
import errno
import os
from pathlib import Path
import re
import selectors
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time


MAX_OUTPUT = 24_000
MAX_JSON_BYTES = 1_000_000
MAX_ARTIFACT_BYTES = 64 * 1024 * 1024
DEADLINE_RESERVE_S = 2.0
SUMMARY_KEYS = (
    "scenario", "seed", "outcomes", "all_resolved", "messages_sent", "event_counts",
    "error", "trace_sha256", "final_t", "end_at", "quiesce_at", "liveness_window",
    "validation_error",
)


class Validation:
    def __init__(self, workspace: Path, scratch: Path, deadline: float,
                 stop: threading.Event):
        self.workspace = Path(workspace).resolve()
        self.scratch = Path(scratch).resolve()
        self.scratch.mkdir(parents=True, exist_ok=True)
        self.artifacts = self.scratch / "artifacts"
        self.artifacts.mkdir(exist_ok=True)
        self.deadline = float(deadline)
        self.stop = stop
        self._children: set[subprocess.Popen] = set()
        self._lock = threading.Lock()
        self._snapshots: set[Path] = set()
        self._pending_restore: tuple[Path, Path, Path] | None = None

    @staticmethod
    def _signal_group(process: subprocess.Popen, signum: int) -> None:
        try:
            os.killpg(process.pid, signum)
        except ProcessLookupError:
            pass

    @staticmethod
    def _group_running(pgid: int) -> bool:
        try:
            os.killpg(pgid, 0)
        except ProcessLookupError:
            return False
        # Linux keeps orphan zombies in a group until its init process reaps
        # them. They cannot execute or hold a pipe open, so do not mistake them
        # for a live descendant. /proc also lets us observe SIGKILL delivery.
        proc = Path("/proc")
        if not proc.is_dir():
            return True
        for entry in proc.iterdir():
            if not entry.name.isdecimal():
                continue
            try:
                fields = (entry / "stat").read_text().rpartition(")")[2].split()
                if int(fields[2]) == pgid and fields[0] not in {"Z", "X"}:
                    return True
            except (OSError, ValueError, IndexError):
                # Processes can disappear between the directory and stat read.
                continue
        return False

    @classmethod
    def _terminate(cls, process: subprocess.Popen) -> bool:
        # Kill the group even when its leader has exited: a descendant may still
        # hold stdout open, or otherwise outlive the validation command.
        cls._signal_group(process, signal.SIGTERM)
        try:
            process.wait(timeout=0.15)
        except subprocess.TimeoutExpired:
            pass
        cls._signal_group(process, signal.SIGKILL)
        try:
            process.wait(timeout=0.15)
        except subprocess.TimeoutExpired:
            pass
        # wait() reaps only the leader. When that leader already exited, a
        # descendant can still be runnable for a moment after killpg returns.
        end_at = time.monotonic() + 0.25
        while cls._group_running(process.pid):
            if time.monotonic() >= end_at:
                return False
            time.sleep(0.01)
        return True

    def terminate_children(self) -> None:
        with self._lock:
            children = tuple(self._children)
        for process in children:
            if self._terminate(process):
                with self._lock:
                    self._children.discard(process)

    @staticmethod
    def _artifact_size(directory: Path | None) -> int:
        if directory is None:
            return 0
        return sum(p.stat().st_size for p in directory.rglob("*")
                   if p.is_file() and not p.is_symlink())

    def _run(self, arguments: list[str], timeout_s: float,
             artifact_dir: Path | None = None) -> dict:
        started = time.monotonic()
        allowance = min(float(timeout_s),
                        self.deadline - time.time() - DEADLINE_RESERVE_S)
        if self.stop.is_set() or allowance <= 0:
            return {"ok": False, "exit_code": None, "output": "validation cancelled",
                    "elapsed_s": 0.0, "timed_out": allowance <= 0,
                    "cancelled": self.stop.is_set(), "truncated": False}

        process = None
        output = bytearray()
        discarded = 0
        timed_out = False
        cancelled = False
        artifact_limit = False
        error = None
        end_at = started + allowance
        env = dict(os.environ, PYTHONHASHSEED="0", PYTHONDONTWRITEBYTECODE="1",
                   PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")
        selector = selectors.DefaultSelector()
        try:
            process = subprocess.Popen(
                arguments, cwd=self.workspace, env=env, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            with self._lock:
                self._children.add(process)
            os.set_blocking(process.stdout.fileno(), False)
            selector.register(process.stdout, selectors.EVENT_READ)
            next_size_check = started
            while True:
                now = time.monotonic()
                cancelled = self.stop.is_set()
                timed_out = now >= end_at
                if artifact_dir is not None and now >= next_size_check:
                    artifact_limit = self._artifact_size(artifact_dir) > MAX_ARTIFACT_BYTES
                    next_size_check = now + 0.1
                if cancelled or timed_out or artifact_limit:
                    break
                for key, _ in selector.select(timeout=min(0.05, max(0, end_at - now))):
                    # Bound work per poll; a noisy child must not starve the
                    # cancellation/deadline checks above.
                    chunk = os.read(key.fd, 65_536)
                    if chunk:
                        output.extend(chunk)
                        if len(output) > MAX_OUTPUT:
                            excess = len(output) - MAX_OUTPUT
                            del output[:excess]
                            discarded += excess
                    else:
                        selector.unregister(key.fileobj)
                if process.poll() is not None:
                    # Only drain currently available bytes. Never wait for EOF
                    # from an inherited pipe belonging to a stray grandchild.
                    for _ in range(8):
                        try:
                            chunk = os.read(process.stdout.fileno(), 65_536)
                        except BlockingIOError:
                            break
                        if not chunk:
                            break
                        output.extend(chunk)
                        if len(output) > MAX_OUTPUT:
                            excess = len(output) - MAX_OUTPUT
                            del output[:excess]
                            discarded += excess
                    break
        except (OSError, ValueError) as exc:
            error = f"validation launch/read error: {exc}"
        finally:
            if process is not None:
                cleaned_up = self._terminate(process)
                if not cleaned_up:
                    error = "validation cleanup failed: process group is still running"
                if process.stdout is not None:
                    process.stdout.close()
                if cleaned_up:
                    with self._lock:
                        self._children.discard(process)
            selector.close()

        messages = []
        if discarded:
            messages.append(f"[output truncated; {discarded} bytes omitted]")
        if error:
            messages.append(error)
        if artifact_limit:
            messages.append("validation stopped: simulator artifact size limit exceeded")
        messages.append(output.decode("utf-8", errors="replace"))
        exit_code = process.returncode if process is not None else None
        return {"ok": exit_code == 0 and not (timed_out or cancelled or error or artifact_limit),
                "exit_code": exit_code, "output": "\n".join(messages)[-MAX_OUTPUT:],
                "elapsed_s": round(time.monotonic() - started, 4),
                "timed_out": timed_out, "cancelled": cancelled,
                "truncated": bool(discarded), "artifact_limit": artifact_limit}

    def run_tests(self, timeout_s: float = 45) -> dict:
        return self._run([sys.executable, "-m", "pytest", "-q", "tests"], timeout_s)

    def compile_source(self) -> dict:
        script = (
            "from pathlib import Path\n"
            "root=Path('src')\n"
            "assert root.is_dir(), 'src directory missing'\n"
            "paths=sorted(root.rglob('*.py'))\n"
            "for path in paths:\n"
            "    compile(path.read_bytes(), str(path), 'exec')\n"
            "print(f'syntax checked {len(paths)} Python files')\n"
        )
        return self._run([sys.executable, "-c", script], 15)

    @staticmethod
    def _read_json(path: Path) -> dict:
        try:
            if path.stat().st_size > MAX_JSON_BYTES:
                return {"validation_error": "summary exceeds size limit"}
            value = json.loads(path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {"validation_error": "summary is not an object"}
        except (OSError, ValueError) as exc:
            return {"validation_error": f"summary unavailable: {exc}"}

    def replay_check(self, seed: int, scenario: str = "public", faults=None,
                     timeout_s: float = 45) -> dict:
        started = time.monotonic()
        directory = Path(tempfile.mkdtemp(prefix=f"replay-{int(seed)}-", dir=self.artifacts))
        trace = directory / "trace.jsonl"
        args = [sys.executable, "-m", "sim", "replay", "--scenario", str(scenario),
                "--seed", str(int(seed)), "--out", str(directory)]
        if faults is not None:
            if isinstance(faults, (dict, list)):
                fault_path = directory / "faults.json"
                fault_path.write_text(json.dumps(faults), encoding="utf-8")
                args.extend(["--faults", str(fault_path)])
            else:
                args.extend(["--faults", str(faults)])
        replay = self._run(args, timeout_s, artifact_dir=directory)
        check = {"ok": False, "exit_code": None, "output": "check skipped: replay failed",
                 "elapsed_s": 0.0, "timed_out": False, "cancelled": self.stop.is_set()}
        if replay["ok"] and trace.is_file():
            remaining = max(0.0, float(timeout_s) - (time.monotonic() - started))
            check = self._run([sys.executable, "-m", "sim", "check", "--trace", str(trace)],
                              remaining, artifact_dir=directory)
        summary = self._read_json(directory / "summary.json")
        violations = summary.get("invariants", [])
        if not isinstance(violations, list):
            violations = [{"invariant": "validation", "detail": "invalid invariants in summary"}]
        # A missing invariant result is not evidence of a successful check.
        checked_summary = "invariants" in summary and "validation_error" not in summary
        # Full summaries contain all client actions and can dwarf useful
        # diagnostics. Keep those on disk, not in every model tool response.
        compact_summary = {key: summary[key] for key in SUMMARY_KEYS if key in summary}
        bounded_violations = []
        for violation in violations[:40]:
            if isinstance(violation, dict):
                bounded_violations.append({
                    "invariant": str(violation.get("invariant", "unknown"))[:120],
                    "t": violation.get("t"),
                    "detail": str(violation.get("detail", ""))[:1200],
                })
            else:
                bounded_violations.append({"invariant": "unknown", "detail": str(violation)[:1200]})
        return {"ok": replay["ok"] and check["ok"] and checked_summary and not violations,
                "replay_exit": replay["exit_code"], "check_exit": check["exit_code"],
                "checked_summary": checked_summary,
                "violations": bounded_violations, "violation_count": len(violations),
                "invariant_categories": sorted({str(v.get("invariant", "unknown"))
                    if isinstance(v, dict) else "unknown" for v in violations}),
                "summary": compact_summary, "trace_path": str(trace),
                "summary_path": str(directory / "summary.json"),
                "trace_artifact": "artifacts/" + trace.relative_to(self.artifacts).as_posix(),
                "summary_artifact": "artifacts/" + (directory / "summary.json").relative_to(self.artifacts).as_posix(),
                "output": (replay["output"] + "\n" + check["output"])[-MAX_OUTPUT:],
                "elapsed_s": round(time.monotonic() - started, 4),
                "timed_out": replay["timed_out"] or check["timed_out"],
                "cancelled": replay["cancelled"] or check["cancelled"],
                "replay": replay, "check": check}

    def snapshot(self, name: str) -> Path:
        source = self.workspace / "src"
        if source.is_symlink() or not source.is_dir():
            raise ValueError("checkpoint requires a real workspace/src directory")
        safe_name = re.sub(r"[^a-zA-Z0-9_.-]", "_", str(name))[:60] or "checkpoint"
        directory = Path(tempfile.mkdtemp(prefix=f"snapshot-{safe_name}-", dir=self.scratch))
        target = directory / "src"
        shutil.copytree(source, target, symlinks=True,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"))
        with self._lock:
            self._snapshots.add(target)
        return target

    @staticmethod
    def _exchange_directories(first: Path, second: Path) -> bool:
        """Linux can atomically exchange nonempty directories, with no src gap."""
        if sys.platform != "linux":
            return False
        library = ctypes.CDLL(None, use_errno=True)
        exchange = getattr(library, "renameat2", None)
        if exchange is None:
            return False
        exchange.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        exchange.restype = ctypes.c_int
        if exchange(-100, os.fsencode(first), -100, os.fsencode(second), 2) == 0:
            return True
        error = ctypes.get_errno()
        # Docker Desktop bind mounts can reject RENAME_EXCHANGE with the
        # ordinary nonempty-directory errors even when native /tmp supports it.
        # A failed syscall has not exchanged either tree; use the tested
        # staged two-rename protocol on these filesystems.
        if error in {errno.ENOSYS, errno.EINVAL, errno.EOPNOTSUPP, errno.EXDEV,
                     errno.ENOTEMPTY, errno.EEXIST}:
            return False
        raise OSError(error, os.strerror(error))

    def ensure_source_present(self) -> bool:
        """Emergency recovery for filesystems without atomic directory exchange.

        No locks: the watchdog may call this while the restore owner is blocked.
        Each recovery uses one atomic rename from a known staged/checkpoint tree.
        """
        pending = self._pending_restore
        if pending is not None:
            source, staged, previous = pending
            if not source.exists():
                for candidate in (staged, previous):
                    try:
                        os.replace(candidate, source)
                        break
                    except FileNotFoundError:
                        continue
                    except OSError:
                        if source.is_dir():
                            break
        source = self.workspace / "src"
        return source.is_dir() and not source.is_symlink()

    def restore(self, snapshot: Path) -> None:
        snapshot = Path(snapshot).absolute()
        with self._lock:
            known = snapshot in self._snapshots
        if not known or snapshot.is_symlink() or not snapshot.is_dir():
            raise ValueError("restore requires a checkpoint made by this Validation instance")
        source = self.workspace / "src"
        if source.is_symlink():
            raise ValueError("refusing to restore through a workspace/src symlink")
        # Stage on the same filesystem, then exchange whole source trees. This
        # restores deleted files and removes additions without touching tests,
        # simulator, or unrelated workspace content.
        staging = Path(tempfile.mkdtemp(prefix=".fixer-restore-", dir=self.workspace))
        staged_source, previous = staging / "src", staging / "previous-src"
        try:
            shutil.copytree(snapshot, staged_source, symlinks=True)
            if not source.exists():
                os.replace(staged_source, source)
            elif not self._exchange_directories(source, staged_source):
                self._pending_restore = (source, staged_source, previous)
                os.replace(source, previous)
                try:
                    os.replace(staged_source, source)
                except BaseException:
                    # A watchdog may already have installed the staged tree.
                    if not source.exists() and previous.exists():
                        os.replace(previous, source)
                    if staged_source.exists():
                        raise
        finally:
            present = self.ensure_source_present()
            if present:
                self._pending_restore = None
            # Never remove the only recoverable source if filesystem recovery
            # itself failed; retain staging for emergency inspection/recovery.
            if present:
                shutil.rmtree(staging)
