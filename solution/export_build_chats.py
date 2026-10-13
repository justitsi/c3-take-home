#!/usr/bin/env python3
"""Export public build conversation and tool evidence, never private reasoning.

The default four sessions belong to this assessment's development team. Files
are read once as byte snapshots: the manifest hashes that exact snapshot even
when an active session subsequently grows. No credential file is opened.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import tempfile


DEFAULT_SESSIONS_DIR = Path("/Users/h/.codex/sessions/2026/10/12")
KNOWN_SESSIONS = {
    "01a131f6-1a58-7710-8f27-1d55a902fd4d": "/root",
    "01a13214-8286-7b40-aaf6-074a6b180e42": "/root/tools_retrieval",
    "01a13214-acac-7451-baf7-d4d3cf9616e6": "/root/validation",
    "01a13214-e5db-7e31-84a4-f06b99dcc896": "/root/packaging",
}
ROLES = {
    "/root": "lead-integration",
    "/root/tools_retrieval": "tools-retrieval",
    "/root/validation": "validation-reliability",
    "/root/packaging": "packaging-evaluation",
}
UUID = re.compile(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", re.I)
SENSITIVE_KEY = re.compile(
    r"(?:api[_-]?key|authorization|password|secret|(?:access|admin|auth|proxy|refresh)[_-]?token|"
    r"^(?:token|key|credential|credentials|cookie|set-cookie)$)",
    re.I,
)
PREFIXED_TOKEN = re.compile(r"\b(?:sk-|c3p-|c3a-|stub-)[A-Za-z0-9_-]{8,}\b")
BEARER = re.compile(r"(\bBearer\s+)[A-Za-z0-9._~+/=-]{8,}", re.I)
ASSIGNMENT = re.compile(
    r"(?i)(\b(?:[A-Z][A-Z0-9_]*_API_KEY|api[_-]?key|password|secret|token|key|credential|"
    r"(?:access|admin|auth|proxy|refresh)[_-]?token)\b[\"']?\s*[:=]\s*)"
    r"([\"']?)([^\s\"'`,;}\]]+)",
)
OPAQUE = re.compile(
    r"(?<![A-Za-z0-9_./-])(?=[A-Za-z0-9_+=-]*[A-Za-z])"
    r"(?=[A-Za-z0-9_+=-]*[0-9])[A-Za-z0-9_+=-]{32,}(?![A-Za-z0-9_./-])"
)
PRIVATE_KEY = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S,
)
JWT = re.compile(r"\b[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")
REDACTED = "[REDACTED]"


def redact(value):
    """Mask credentials recursively; retain structural IDs and safe field names."""
    if isinstance(value, dict):
        return {key: REDACTED if SENSITIVE_KEY.search(str(key)) else redact(item)
                for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if not isinstance(value, str):
        return value
    value = PRIVATE_KEY.sub(REDACTED, value)
    value = ASSIGNMENT.sub(lambda match: match[1] + match[2] + REDACTED, value)
    value = PREFIXED_TOKEN.sub(REDACTED, value)
    value = JWT.sub(REDACTED, value)
    value = BEARER.sub(lambda match: match[1] + REDACTED, value)
    return OPAQUE.sub(lambda match: match[0] if UUID.fullmatch(match[0]) else REDACTED, value)


def _text(content) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    return "\n".join(item["text"] for item in content
                     if isinstance(item, dict) and item.get("type", "").lower() in
                     {"text", "input_text", "output_text"} and isinstance(item.get("text"), str))


def read_snapshot(path: Path) -> tuple[bytes, list[tuple[int, dict]], int]:
    path = path.resolve(strict=True)
    if path.suffix != ".jsonl":
        raise ValueError("only JSONL session transcripts may be read")
    with path.open("rb") as source:
        size = path.stat().st_size
        raw = source.read(size)
    lines = raw.splitlines()
    records = []
    incomplete = 0
    for number, line in enumerate(lines, 1):
        try:
            record = json.loads(line)
        except (json.JSONDecodeError, UnicodeDecodeError):
            if number == len(lines) and not raw.endswith(b"\n"):
                incomplete = 1
                break
            raise ValueError(f"invalid session JSON at line {number}") from None
        if not isinstance(record, dict):
            raise ValueError(f"non-object session record at line {number}")
        records.append((number, record))
    return raw, records, incomplete


def extract(records: list[tuple[int, dict]]) -> tuple[dict, list[dict]]:
    # A fork includes inherited parent metadata/history. Only the FIRST metadata
    # record identifies the session being exported.
    meta = next((record["payload"] for _, record in records
                 if record.get("type") == "session_meta"), None)
    if not isinstance(meta, dict) or not UUID.fullmatch(str(meta.get("id", ""))):
        raise ValueError("session is missing a valid initial metadata ID")
    session_id = meta["id"]
    source = meta.get("source")
    spawn = source.get("subagent", {}).get("thread_spawn", {}) if isinstance(source, dict) else {}
    agent_path = spawn.get("agent_path", "/root")
    if agent_path not in ROLES:
        raise ValueError("unrecognized development agent role")
    identity = {"session_id": session_id, "agent_path": agent_path,
                "role": ROLES[agent_path], "parent_session_id": spawn.get("parent_thread_id")}
    owned_turns = {
        record["payload"].get("turn_id") for _, record in records
        if record.get("type") == "event_msg" and isinstance(record.get("payload"), dict)
        and record["payload"].get("type") == "item_completed"
        and record["payload"].get("thread_id") == session_id
    } - {None}
    calls = set()
    selected = []
    for number, record in records:
        payload = record.get("payload")
        if not isinstance(payload, dict):
            continue
        entry = {"source_line": number, "timestamp": record.get("timestamp")}
        if record.get("type") == "event_msg" and payload.get("type") == "item_completed":
            if payload.get("thread_id") != session_id:
                continue
            item = payload.get("item") or {}
            kind = item.get("type")
            if kind == "UserMessage":
                role, phase = "user", "input"
            elif kind == "AgentMessage" and item.get("phase") in {"commentary", "final_answer", "final"}:
                role, phase = "assistant", item["phase"]
            else:
                continue
            text = _text(item.get("content"))
            if not text:
                continue
            entry.update(kind="message", role=role, phase=phase, text=redact(text))
        elif record.get("type") == "response_item":
            kind = payload.get("type")
            turn = (payload.get("internal_chat_message_metadata_passthrough") or {}).get("turn_id")
            if kind in {"function_call", "custom_tool_call"} and turn in owned_turns:
                call_id = payload.get("call_id")
                if not call_id:
                    continue
                calls.add(call_id)
                arguments = payload.get("arguments", payload.get("input"))
                if isinstance(arguments, str):
                    try:
                        arguments = json.loads(arguments)
                    except json.JSONDecodeError:
                        pass
                entry.update(kind="tool_call", call_id=call_id, name=payload.get("name"),
                             arguments=redact(arguments))
            elif kind in {"function_call_output", "custom_tool_call_output"} and payload.get("call_id") in calls:
                entry.update(kind="tool_result", call_id=payload["call_id"], output=redact(payload.get("output")))
            else:
                continue
        else:
            continue
        selected.append(entry)
    return identity, selected


def _atomic_write(path: Path, data: bytes) -> None:
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".chat-export-", delete=False) as output:
        output.write(data)
        temporary = Path(output.name)
    temporary.replace(path)


def export_sessions(paths: list[Path], output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    summaries = []
    for path in paths:
        raw, records, incomplete = read_snapshot(path)
        identity, entries = extract(records)
        filename = f"{identity['role']}-{identity['session_id']}.jsonl"
        encoded = "".join(json.dumps(entry, ensure_ascii=False) + "\n" for entry in entries).encode()
        _atomic_write(output_dir / filename, encoded)
        summaries.append({**identity, "source_file": path.name,
                          "source_snapshot_bytes": len(raw),
                          "source_snapshot_sha256": hashlib.sha256(raw).hexdigest(),
                          "incomplete_final_lines_skipped": incomplete,
                          "export_file": filename, "export_bytes": len(encoded),
                          "export_sha256": hashlib.sha256(encoded).hexdigest(),
                          "entries": dict(Counter(entry["kind"] for entry in entries))})
    manifest = {
        "format": "c3-public-build-chat-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "own-thread user input, assistant commentary/final, and linked tool calls/results",
        "excluded": ["analysis", "reasoning", "system", "developer", "turn_context",
                     "compaction", "inherited parent history", "unrelated tool results"],
        "redaction": "credential fields, API/proxy tokens, bearer credentials, private keys, opaque token-like strings",
        "sessions": summaries,
    }
    _atomic_write(output_dir / "manifest.json", (json.dumps(manifest, indent=2) + "\n").encode())
    return manifest


def default_sessions(directory: Path) -> list[Path]:
    paths = []
    for session_id, expected_agent in KNOWN_SESSIONS.items():
        matches = sorted(directory.glob(f"*{session_id}.jsonl"))
        if len(matches) != 1:
            raise ValueError("expected exactly one transcript per known development session")
        _, records, _ = read_snapshot(matches[0])
        identity, _ = extract(records)
        if identity["session_id"] != session_id or identity["agent_path"] != expected_agent:
            raise ValueError("development session identity did not match its expected agent")
        paths.append(matches[0])
    return paths


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sessions-dir", type=Path, default=DEFAULT_SESSIONS_DIR)
    parser.add_argument("--session", type=Path, action="append", help="explicit JSONL session; repeat for each agent")
    parser.add_argument("--out", type=Path, default=Path("evidence/build-chats"))
    args = parser.parse_args(argv)
    try:
        paths = args.session or default_sessions(args.sessions_dir)
        manifest = export_sessions(paths, args.out)
    except (OSError, ValueError) as error:
        # Do not print exception bodies: a malformed source line may contain a
        # secret. The failure class is sufficient for a safe CLI diagnostic.
        print(json.dumps({"ok": False, "error": type(error).__name__}))
        return 2
    print(json.dumps({"ok": True, "sessions": len(manifest["sessions"]),
                      "manifest": str(args.out / "manifest.json")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
