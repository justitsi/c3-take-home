"""Bounded validation commands and source-only checkpoints.

Replay merely produces a trace: only a separate ``sim check`` proves that the
public invariants passed. No command is run through a shell.
"""

from __future__ import annotations

import hashlib
import json
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


SIGNATURE_FIELDS = ("outcome", "reason", "code", "state", "verdict", "cause")


def log_signatures(trace: Path, limit: int = 60) -> dict:
    """Count log events by name and discriminating fields, e.g. task_finished|outcome=lost."""
    counts: dict[str, int] = {}
    try:
        if not trace.is_file() or trace.stat().st_size > MAX_ARTIFACT_BYTES:
            return {}
        with trace.open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if '"kind":"log"' not in line:
                    continue
                try:
                    record = json.loads(line)
                except ValueError:
                    continue
                parts = [str(record.get("event", "?"))]
                parts += [f"{key}={record[key]}" for key in SIGNATURE_FIELDS
                          if isinstance(record.get(key), (str, int, bool))]
                key = "|".join(parts)[:160]
                counts[key] = counts.get(key, 0) + 1
    except OSError:
        return {}
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit])


def unresolved_entities(summary: dict, cap: int = 5) -> list[str]:
    """Trace `job` ids of client actions that never resolved, so a stuck entity can be traced."""
    out = []
    for action in summary.get("actions") or []:
        if not isinstance(action, dict) or action.get("outcome") != "unresolved":
            continue
        args = action.get("args") or {}
        job = args.get("job_id")
        if job is None:
            continue
        tenant = args.get("tenant")
        out.append(f"{tenant}:{job}" if tenant is not None else str(job))
    return out[:cap]


class Validation:
    def __init__(self, workspace: Path, scratch: Path, deadline: float,
                 stop: threading.Event):
        self.workspace = Path(workspace).resolve()
        self.scratch = Path(scratch).resolve()
        self.scratch.mkdir(parents=True, exist_ok=True)
        self.deadline = float(deadline)
        self.stop = stop
        self._children: set[subprocess.Popen] = set()
        self._lock = threading.Lock()
        self._snapshots: set[Path] = set()

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
        directory = Path(tempfile.mkdtemp(prefix=f"replay-{int(seed)}-", dir=self.scratch))
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
                "violations": bounded_violations, "violation_count": len(violations),
                "unresolved_entities": unresolved_entities(summary),
                "summary": compact_summary, "log_signatures": log_signatures(trace),
                "trace_path": str(trace),
                "summary_path": str(directory / "summary.json"),
                "output": (replay["output"] + "\n" + check["output"])[-MAX_OUTPUT:],
                "elapsed_s": round(time.monotonic() - started, 4),
                "timed_out": replay["timed_out"] or check["timed_out"],
                "cancelled": replay["cancelled"] or check["cancelled"],
                "replay": replay, "check": check}

    def entity_timeline(self, trace_path: str, job: str, limit: int = 40) -> dict:
        """Application-level events of one job and the tasks/batches that carry it, oldest first."""
        try:
            path = Path(trace_path).resolve(strict=True)
            if (not path.is_relative_to(self.scratch) or path.is_symlink() or not path.is_file()
                    or path.stat().st_size > 16 * 1024 * 1024):
                raise ValueError("trace must be a regular file under fixer scratch and at most 16 MiB")
            records = []
            with path.open(encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    try:
                        record = json.loads(line)
                    except ValueError:
                        continue
                    if isinstance(record, dict) and "event" in record:
                        records.append(record)
            tasks = {str(r["task"]) for r in records if str(r.get("job")) == job and r.get("task") is not None}
            batches = {str(r["batch"]) for r in records if str(r.get("job")) == job and r.get("batch") is not None}
            batches |= {str(r["batch"]) for r in records if str(r.get("task")) in tasks and r.get("batch") is not None}
            events = [{k: v for k, v in r.items() if k not in ("local_t", "node_boot", "seq", "kind")}
                      for r in records
                      if str(r.get("job")) == job or str(r.get("task")) in tasks
                      or str(r.get("batch")) in batches]
            truncated = len(events) > limit
            return {"ok": True, "job": job, "events": events[:limit] if not truncated else events[-limit:],
                    "truncated": truncated}
        except (OSError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def compare_traces(self, first: str, second: str) -> dict:
        """Compare two bounded traces created in this run's private scratch area."""
        try:
            paths = [Path(first).resolve(strict=True), Path(second).resolve(strict=True)]
            for path in paths:
                if (not path.is_relative_to(self.scratch) or path.is_symlink() or
                        not path.is_file() or path.stat().st_size > 4 * 1024 * 1024):
                    raise ValueError("trace must be a regular file under fixer scratch and at most 4 MiB")
            contents = [path.read_bytes() for path in paths]
            lines = [content.splitlines() for content in contents]
            differences = []
            for index in range(max(len(lines[0]), len(lines[1]))):
                left = lines[0][index] if index < len(lines[0]) else None
                right = lines[1][index] if index < len(lines[1]) else None
                if left != right:
                    differences.append({
                        "line": index + 1,
                        "first": left.decode("utf-8", errors="replace")[:600] if left is not None else None,
                        "second": right.decode("utf-8", errors="replace")[:600] if right is not None else None,
                    })
                    if len(differences) == 8:
                        break
            return {
                "ok": True,
                "identical": contents[0] == contents[1],
                "first_sha256": hashlib.sha256(contents[0]).hexdigest(),
                "second_sha256": hashlib.sha256(contents[1]).hexdigest(),
                "first_lines": len(lines[0]),
                "second_lines": len(lines[1]),
                "differences": differences,
                "truncated": len(differences) == 8,
            }
        except (OSError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def trace_query(self, trace_path: str, match: dict, before_s: float = 3.0, after_s: float = 0.5,
                    limit: int = 60, anchor_last: bool = False) -> dict:
        """Events around the first trace record matching `match`, limited to records sharing its entities."""
        try:
            path = Path(trace_path).resolve(strict=True)
            if (not path.is_relative_to(self.scratch) or path.is_symlink() or not path.is_file()
                    or path.stat().st_size > 16 * 1024 * 1024):
                raise ValueError("trace must be a regular file under fixer scratch and at most 16 MiB")
            if not isinstance(match, dict) or not match:
                raise ValueError("match must be a non-empty object of exact field values")
            records, anchor, total = [], None, 0
            with path.open(encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    try:
                        record = json.loads(line)
                    except ValueError:
                        continue
                    records.append(record)
                    if all(str(record.get(key)) == str(value) for key, value in match.items()):
                        total += 1
                        anchor = record if anchor_last else (anchor or record)
            if anchor is None:
                return {"ok": True, "matches": 0, "events": []}
            keys = ("task", "job", "worker", "node", "src", "dst", "batch")
            entities = {str(anchor[key]) for key in ("task", "job", "worker", "batch")
                        if anchor.get(key) is not None}
            low, high = anchor.get("t", 0) - float(before_s), anchor.get("t", 0) + float(after_s)
            events = []
            for record in records:
                moment = record.get("t")
                if not isinstance(moment, (int, float)) or not low <= moment <= high:
                    continue
                if record is anchor or any(str(record.get(key)) in entities for key in keys):
                    events.append({k: v for k, v in record.items()
                                   if k not in ("local_t", "node_boot", "seq", "kind") or k == "kind" and v != "log"})
            truncated = len(events) > min(int(limit), 120)
            return {"ok": True, "matches": total, "anchor_t": anchor.get("t"), "anchor": anchor.get("event"),
                    "events": events[:min(int(limit), 120)], "truncated": truncated}
        except (OSError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

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
            if source.exists():
                os.replace(source, previous)
            try:
                os.replace(staged_source, source)
            except BaseException:
                if previous.exists():
                    os.replace(previous, source)
                raise
        finally:
            shutil.rmtree(staging)
