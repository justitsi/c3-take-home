"""Bounded inspection and transactional, source-only edits for the fixer."""

from __future__ import annotations

import ast
import difflib
import fnmatch
import json
import os
from pathlib import Path
import stat
import tempfile
import threading

if __package__:
    from .artifacts import inspect_jsonl
    from .probe_authoring import author_probe
else:
    from artifacts import inspect_jsonl
    from probe_authoring import author_probe


READ_TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "source_diff",
            "description": "Review a bounded unified diff of the trusted original service src/ checkpoint versus current source. Takes no paths; no test, scenario, or simulator edits are included. Use it to audit unintended side effects across all retained repairs.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List bounded file paths. Workspace paths are relative; corpus/ is documentation; artifacts/ is read-only generated simulator evidence. Corpus root excludes background papers unless explicitly requested.",
            "parameters": {
                "type": "object",
                "properties": {
                    "root": {"type": "string", "default": "src"},
                    "pattern": {"type": "string", "default": "*"},
                    "limit": {"type": "integer", "default": 120},
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read numbered lines, at most 400 lines or 18,000 characters. Use corpus/ for documentation and artifacts/ for generated trace/summary/log evidence. Prefer inspect_trace for trace JSONL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "start_line": {"type": "integer", "default": 1},
                    "end_line": {"type": "integer", "default": 160},
                },
                "required": ["path"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search",
            "description": "Case-insensitive literal text search with filename, line number and adjacent context. artifacts/ searches generated evidence. Search corpus/service or corpus/platform before explicitly narrowing into background papers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "root": {"type": "string", "default": "src"},
                    "limit": {"type": "integer", "default": 20},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "inspect_trace",
            "description": "Inspect bounded JSONL trace events with original line numbers. query is ONE literal substring; use all_terms for AND across separate JSON fields. Optional center_t ± window_s combines with text filters. When next_line is returned, repeat with start_line=next_line to reach later evidence. Returns at most 100 events/18,000 characters; scans at most 64MiB including skipped lines. Malformed lines are counted, not executed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "query": {"type": "string"},
                    "all_terms": {"type": "array", "minItems": 1, "maxItems": 8,
                                  "items": {"type": "string", "minLength": 1, "maxLength": 256}},
                    "center_t": {"type": "number"},
                    "window_s": {"type": "number", "default": 2.0},
                    "limit": {"type": "integer", "default": 30},
                    "start_line": {"type": "integer", "minimum": 1, "default": 1},
                },
                "required": ["path"],
                "additionalProperties": False,
            },
        },
    },
]

PROBE_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "create_probe",
        "description": "Author a bounded, write-once scenario derived from a supplied base. Mappings merge recursively; lists/scalars replace. Do not modify provided scenarios. Use a small workload targeting a cited contract concern, with optional supplied fault file. Only base node classes are allowed. Limits: 32 nodes, 500 expanded actions, end_at<=600, 64KiB. The controller replays this probe; creation alone is not evidence of correctness.",
        "parameters": {
            "type": "object",
            "properties": {
                "base_scenario": {"type": "string", "default": "public"},
                "overrides": {"type": "object"},
                "faults": {"type": "string"},
                "name": {"type": "string", "maxLength": 64},
                "seed": {"type": "integer", "minimum": 0, "maximum": 2147483647},
            },
            "required": ["overrides"], "additionalProperties": False,
        },
    },
}

EDIT_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "apply_edits",
        "description": "Apply exact, unambiguous text replacements under src/ only. All Python candidates must parse before any changes. old='' creates an absent file. Multiple edits may target one file. Returns a rollback journal path.",
        "parameters": {
            "type": "object",
            "properties": {
                "edits": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "old": {"type": "string"},
                            "new": {"type": "string"},
                        },
                        "required": ["path", "old", "new"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["edits"],
            "additionalProperties": False,
        },
    },
}


class Tools:
    """The coordinator owns writes; investigators receive only read schemas."""

    def __init__(self, workspace: Path, corpus: Path, scratch: Path):
        self.workspace = Path(workspace).resolve()
        self.corpus = Path(corpus).resolve()
        self.scratch = Path(scratch).resolve()
        self.artifacts_root = self.scratch / "artifacts"
        self._write_lock = threading.Lock()
        self.stop: threading.Event | None = None
        self.authored_probes: dict[str, dict] = {}
        self.original_source: Path | None = None

    def _check_cancelled(self) -> None:
        if self.stop is not None and self.stop.is_set():
            raise ValueError("source edit cancelled; transaction rolled back")

    @staticmethod
    def _within(path: Path, root: Path) -> bool:
        return path == root or root in path.parents

    def _resolve(self, value: str) -> tuple[Path, Path]:
        if not isinstance(value, str):
            raise ValueError("path must be a relative string")
        path = Path(value)
        if ".." in path.parts:
            raise ValueError("parent traversal is forbidden")
        is_artifact = bool(path.parts) and path.parts[0] == "artifacts"
        is_corpus = bool(path.parts) and path.parts[0] == "corpus"
        if path.is_absolute():
            if not self._within(path, self.artifacts_root):
                raise ValueError("absolute paths are only allowed inside generated artifacts/")
            is_artifact = True
        root = self.artifacts_root if is_artifact else (self.corpus if is_corpus else self.workspace)
        if is_artifact and (root.is_symlink() or not self._within(root.resolve(), self.scratch)):
            raise ValueError("artifacts root must remain a real directory under scratch")
        relative = Path(*path.parts[1:]) if is_artifact or is_corpus else path
        target = path.resolve() if path.is_absolute() else (root / relative).resolve()
        if not self._within(target, root):
            raise ValueError("path or symlink escapes its allowed root")
        return target, root

    def _label(self, path: Path, root: Path) -> str:
        prefix = "artifacts/" if root == self.artifacts_root else ("corpus/" if root == self.corpus else "")
        return prefix + path.relative_to(root).as_posix()

    def _files(self, value: str):
        target, root = self._resolve(value)
        if not target.exists():
            raise ValueError(f"path does not exist: {value}")
        # Avoid even opening the 26M-token background corpus for a broad search.
        if target == self.corpus:
            candidates = [self.corpus / "INDEX.md"]
            for directory in ("service", "platform"):
                if (self.corpus / directory).is_dir():
                    candidates.extend(sorted((self.corpus / directory).rglob("*")))
        elif target.is_file():
            candidates = [target]
        else:
            candidates = sorted(target.rglob("*"))
        for candidate in candidates:
            relative_parts = candidate.relative_to(root).parts
            if any(part.startswith(".") or part == "__pycache__" for part in relative_parts):
                continue
            resolved = candidate.resolve()
            if not self._within(resolved, root) or not resolved.is_file():
                continue
            yield candidate, root

    def list_files(self, root="src", pattern="*", limit=120) -> dict:
        try:
            limit = max(1, min(int(limit), 300))
            files = []
            truncated = False
            for path, allowed_root in self._files(root):
                label = self._label(path, allowed_root)
                if fnmatch.fnmatch(path.name, pattern) or fnmatch.fnmatch(label, pattern):
                    if len(files) >= limit:
                        truncated = True
                        break
                    files.append(label)
            return {"ok": True, "files": files, "truncated": truncated}
        except (OSError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def read_file(self, path: str, start_line=1, end_line=160) -> dict:
        try:
            target, root = self._resolve(path)
            first = max(1, int(start_line))
            last = max(first, min(int(end_line), first + 399))
            content = []
            chars = 0
            truncated = False
            actual_last = first - 1
            with target.open(encoding="utf-8", errors="replace") as handle:
                for number, line in enumerate(handle, 1):
                    if number < first:
                        continue
                    if number > last:
                        truncated = True
                        break
                    text = line.rstrip("\r\n")
                    if len(text) > 1600:
                        text = text[:1600] + " … [line truncated]"
                        truncated = True
                    rendered = f"{number}: {text}"
                    if chars + len(rendered) + 1 > 18000:
                        truncated = True
                        break
                    content.append(rendered)
                    chars += len(rendered) + 1
                    actual_last = number
            return {
                "ok": True, "path": self._label(target, root),
                "start_line": first, "end_line": actual_last,
                "content": "\n".join(content), "truncated": truncated,
            }
        except (OSError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def search(self, query: str, root="src", limit=20) -> dict:
        try:
            if not isinstance(query, str) or not query.strip():
                raise ValueError("query must be nonempty literal text")
            needle = query.casefold()
            limit = max(1, min(int(limit), 40))
            matches = []
            total_bytes = 0
            output_chars = 0
            truncated = False
            for path, allowed_root in self._files(root):
                label = self._label(path, allowed_root)
                if needle in label.casefold():
                    matches.append({"path": label, "line": 0, "text": "[filename match]"})
                    output_chars += len(label) + 80
                if len(matches) >= limit:
                    truncated = True
                    break
                # Stream a bounded prefix even if a background proceeding is huge.
                lines = []
                file_bytes = 0
                with path.open(encoding="utf-8", errors="replace") as handle:
                    for line in handle:
                        file_bytes += len(line.encode("utf-8"))
                        total_bytes += len(line.encode("utf-8"))
                        if file_bytes > 2_000_000 or total_bytes > 8_000_000:
                            truncated = True
                            break
                        lines.append(line.rstrip("\r\n"))
                for index, line in enumerate(lines):
                    if needle not in line.casefold():
                        continue
                    match = {
                        "path": label, "line": index + 1,
                        "text": line[:650],
                        "before": lines[index - 1][:300] if index else "",
                        "after": lines[index + 1][:300] if index + 1 < len(lines) else "",
                    }
                    cost = sum(len(value) for value in match.values() if isinstance(value, str)) + 100
                    if output_chars + cost > 18000:
                        truncated = True
                        break
                    matches.append(match)
                    output_chars += cost
                    if len(matches) >= limit:
                        truncated = True
                        break
                if len(matches) >= limit or total_bytes > 8_000_000 or output_chars > 16500:
                    truncated = True
                    break
            return {"ok": True, "matches": matches, "truncated": truncated}
        except (OSError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def apply_edits(self, edits: list[dict]) -> dict:
        with self._write_lock:
            return self._apply_edits(edits)

    def create_probe(self, base_scenario="public", overrides=None, faults=None, name=None, seed=None) -> dict:
        with self._write_lock:
            return author_probe(self.workspace, self.artifacts_root, self.authored_probes,
                                base_scenario=base_scenario, overrides=overrides, faults=faults,
                                name=name, seed=seed, stop=self.stop)

    def source_diff(self) -> dict:
        """No model-selected checkpoint path; root assigns original_source once."""
        try:
            if self.original_source is None:
                raise ValueError("trusted original source checkpoint is unavailable")
            original, current = Path(self.original_source), self.workspace / "src"
            if any(root.is_symlink() or not root.is_dir() for root in (original, current)):
                raise ValueError("source diff requires real source directories")
            trees = []
            for root in (original, current):
                files = {}
                for path in sorted(root.rglob("*")):
                    self._check_cancelled()
                    relative = path.relative_to(root)
                    if any(part.startswith(".") or part == "__pycache__" for part in relative.parts):
                        continue
                    if path.is_symlink():
                        raise ValueError("source diff refuses symlink files/directories")
                    if path.is_file() and path.suffix not in {".pyc", ".pyo"}:
                        files[relative.as_posix()] = path
                    if len(files) > 500:
                        raise ValueError("source diff exceeds 500-file bound")
                trees.append(files)
            result = {"ok": True, "diff": "", "changed_files": [], "compared_files": 0, "truncated": False}
            total_bytes = 0
            for name in sorted(trees[0].keys() | trees[1].keys()):
                self._check_cancelled()
                contents = []
                for tree in trees:
                    if name not in tree:
                        contents.append(b"")
                        continue
                    with tree[name].open("rb") as handle:
                        content = handle.read(262145)
                    total_bytes += len(content)
                    if len(content) > 262144 or total_bytes > 4_000_000:
                        raise ValueError("source diff exceeds bounded source bytes; inspect a file directly")
                    contents.append(content)
                result["compared_files"] += 1
                if contents[0] == contents[1] and (name in trees[0]) == (name in trees[1]):
                    continue
                proposed_files = result["changed_files"] + ["src/" + name]
                if len(json.dumps({**result, "changed_files": proposed_files}, ensure_ascii=False)) > 17000:
                    result["truncated"] = True
                    break
                result["changed_files"] = proposed_files
                try:
                    before, after = (content.decode("utf-8").splitlines(keepends=True) for content in contents)
                except UnicodeDecodeError:
                    line = f"[binary source changed: src/{name}]\n"
                    if len(json.dumps(result, ensure_ascii=False)) + len(json.dumps(line)) > 17800:
                        result["truncated"] = True
                        break
                    result["diff"] += line
                    continue
                if max(len(before), len(after)) > 8000:
                    raise ValueError("source diff exceeds bounded source lines")
                diff = difflib.unified_diff(before, after,
                    fromfile="original/src/" + name if name in trees[0] else "/dev/null",
                    tofile="current/src/" + name if name in trees[1] else "/dev/null")
                any_lines = False
                for line in diff:
                    any_lines = True
                    if len(json.dumps(result, ensure_ascii=False)) + len(json.dumps(line, ensure_ascii=False)) > 17800:
                        result["truncated"] = True
                        break
                    result["diff"] += line
                if not any_lines:
                    line = f"[empty file {'added' if name not in trees[0] else 'removed'}: src/{name}]\n"
                    if len(json.dumps(result, ensure_ascii=False)) + len(json.dumps(line)) > 17800:
                        result["truncated"] = True
                        break
                    result["diff"] += line
                if result["truncated"]:
                    break
            return result
        except (OSError, TypeError, ValueError) as error:
            return {"ok": False, "error": str(error)}

    def inspect_trace(self, path: str, query=None, center_t=None, window_s=2.0, limit=30,
                      all_terms=None, start_line=1) -> dict:
        try:
            target, root = self._resolve(path)
            return inspect_jsonl(target, self._label(target, root), query=query,
                                 center_t=center_t, window_s=window_s, limit=limit,
                                 stop=self.stop, all_terms=all_terms, start_line=start_line)
        except (OSError, TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def _apply_edits(self, edits: list[dict]) -> dict:
        staged: dict[Path, Path] = {}
        originals: dict[Path, bytes | None] = {}
        created_dirs: list[Path] = []
        applied: list[Path] = []
        journal = None
        try:
            if not isinstance(edits, list) or not edits or len(edits) > 30:
                raise ValueError("edits must contain between 1 and 30 replacements")
            source = self.workspace / "src"
            if source.is_symlink() or not source.is_dir():
                raise ValueError("src must be a real workspace directory")
            candidates: dict[Path, str] = {}
            for edit in edits:
                if not isinstance(edit, dict) or not all(isinstance(edit.get(key), str) for key in ("path", "old", "new")):
                    raise ValueError("each edit needs string path, old and new fields")
                if not Path(edit["path"]).parts or Path(edit["path"]).parts[0] != "src":
                    raise ValueError("only workspace src/ files may be edited")
                target, root = self._resolve(edit["path"])
                if root != self.workspace or not self._within(target, source) or target == source:
                    raise ValueError("edit target escapes workspace src/")
                if target not in candidates:
                    originals[target] = target.read_bytes() if target.exists() else None
                    candidates[target] = originals[target].decode("utf-8") if originals[target] is not None else ""
                old, new = edit["old"], edit["new"]
                if old == "":
                    if originals[target] is not None or candidates[target] != "":
                        raise ValueError(f"empty old is only allowed for an absent new file: {edit['path']}")
                    candidates[target] = new
                else:
                    count = candidates[target].count(old)
                    if count != 1:
                        raise ValueError(f"old text must match exactly once, found {count}: {edit['path']}")
                    candidates[target] = candidates[target].replace(old, new, 1)
            candidates = {
                target: candidate for target, candidate in candidates.items()
                if originals[target] is None or candidate.encode("utf-8") != originals[target]
            }
            if not candidates:
                raise ValueError("no source changes: transaction leaves existing files unchanged")
            for target, candidate in candidates.items():
                if target.suffix == ".py":
                    ast.parse(candidate, filename=str(target))
            self._check_cancelled()
            self.scratch.mkdir(parents=True, exist_ok=True)
            journal = Path(tempfile.mkdtemp(prefix="edits-", dir=self.scratch))
            manifest = []
            # Preserve every original before installing any candidate.
            for index, (target, candidate) in enumerate(candidates.items()):
                self._check_cancelled()
                backup = journal / f"{index}.before"
                original = originals[target]
                if original is not None:
                    backup.write_bytes(original)
                manifest.append({"path": str(target), "before": str(backup) if original is not None else None})
                missing = []
                parent = target.parent
                while not parent.exists():
                    missing.append(parent)
                    parent = parent.parent
                for parent in reversed(missing):
                    parent.mkdir()
                    created_dirs.append(parent)
                descriptor, temporary = tempfile.mkstemp(prefix=".fixer-", dir=target.parent)
                staged[target] = Path(temporary)
                with os.fdopen(descriptor, "wb") as handle:
                    handle.write(candidate.encode("utf-8"))
                    handle.flush()
                    os.fsync(handle.fileno())
                mode = stat.S_IMODE(target.stat().st_mode) if target.exists() else 0o644
                os.chmod(temporary, mode)
            (journal / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            for target, temporary in staged.items():
                self._check_cancelled()
                os.replace(temporary, target)
                applied.append(target)
            self._check_cancelled()
            return {"ok": True, "changed": [str(path.relative_to(self.workspace)) for path in candidates], "journal": str(journal)}
        except (OSError, SyntaxError, TypeError, ValueError) as exc:
            rollback_errors = []
            for target in reversed(applied):
                try:
                    original = originals[target]
                    if original is None:
                        target.unlink(missing_ok=True)
                    else:
                        descriptor, rollback_path = tempfile.mkstemp(prefix=".fixer-rollback-", dir=target.parent)
                        with os.fdopen(descriptor, "wb") as handle:
                            handle.write(original)
                        os.chmod(rollback_path, stat.S_IMODE(target.stat().st_mode))
                        os.replace(rollback_path, target)
                except OSError as rollback_error:
                    rollback_errors.append(f"{target}: {rollback_error}")
            return {"ok": False, "error": str(exc), "rollback_errors": rollback_errors, "journal": str(journal) if journal else None}
        finally:
            for temporary in staged.values():
                temporary.unlink(missing_ok=True)
            for directory in reversed(created_dirs):
                try:
                    directory.rmdir()
                except OSError:
                    pass
