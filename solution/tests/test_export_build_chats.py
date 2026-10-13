import hashlib
import json

import pytest

from export_build_chats import export_sessions, main, read_snapshot, redact


ROOT_ID = "01a131f6-1a58-7710-8f27-1d55a902fd4d"
CHILD_ID = "01a13214-e5db-7e31-84a4-f06b99dcc896"


def transcript(tmp_path, records, tail=b""):
    source = tmp_path / "session.jsonl"
    source.write_bytes(b"".join(json.dumps(record).encode() + b"\n" for record in records) + tail)
    return source


def metadata(session=ROOT_ID, agent=None):
    source = {"subagent": {"thread_spawn": {"agent_path": agent, "parent_thread_id": ROOT_ID}}} if agent else "vscode"
    return {"type": "session_meta", "payload": {"id": session, "source": source,
            "base_instructions": "PRIVATE SYSTEM INSTRUCTIONS"}}


def message(kind, text, *, session=ROOT_ID, turn="own", phase=None):
    item = {"type": kind, "content": [{"type": "Text", "text": text}]}
    if phase is not None:
        item["phase"] = phase
    return {"type": "event_msg", "timestamp": "2026-10-13T00:00:00Z", "payload": {
        "type": "item_completed", "thread_id": session, "turn_id": turn, "item": item}}


def tool(kind, call_id="call-1", *, turn="own", **fields):
    return {"type": "response_item", "payload": {"type": kind, "call_id": call_id,
            "internal_chat_message_metadata_passthrough": {"turn_id": turn}, **fields}}


def test_exports_public_channels_and_linked_tools_only(tmp_path):
    source = transcript(tmp_path, [
        metadata(),
        {"type": "turn_context", "payload": {"secret": "PRIVATE TURN CONTEXT"}},
        {"type": "response_item", "payload": {"type": "reasoning", "summary": "PRIVATE REASONING"}},
        {"type": "response_item", "payload": {"type": "message", "role": "developer", "content": "PRIVATE DEVELOPER"}},
        message("UserMessage", "Implement the prototype"),
        message("AgentMessage", "Checking the image", phase="commentary"),
        message("AgentMessage", "PRIVATE ANALYSIS", phase="analysis"),
        message("Reasoning", "PRIVATE REASONING EVENT"),
        tool("function_call", name="exec_command", arguments=json.dumps({"cmd": "pytest -q"})),
        tool("function_call_output", output="12 passed"),
        tool("function_call_output", call_id="unrelated", output="PRIVATE UNRELATED RESULT"),
        message("AgentMessage", "Prototype ready", phase="final_answer"),
    ])
    out = tmp_path / "export"
    manifest = export_sessions([source], out)
    summary = manifest["sessions"][0]
    raw = (out / summary["export_file"]).read_text()
    assert "PRIVATE" not in raw
    entries = [json.loads(line) for line in raw.splitlines()]
    assert [entry["kind"] for entry in entries] == ["message", "message", "tool_call", "tool_result", "message"]
    assert entries[2]["arguments"] == {"cmd": "pytest -q"}
    assert summary["source_snapshot_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert summary["export_sha256"] == hashlib.sha256(raw.encode()).hexdigest()


def test_child_identity_uses_first_metadata_and_excludes_inherited_history(tmp_path):
    source = transcript(tmp_path, [
        metadata(CHILD_ID, "/root/packaging"), metadata(),
        message("AgentMessage", "PRIVATE PARENT HISTORY", phase="final_answer", turn="parent"),
        tool("custom_tool_call", turn="parent", name="exec", input="PRIVATE PARENT TOOL"),
        tool("custom_tool_call_output", turn="parent", output="PRIVATE PARENT OUTPUT"),
        tool("custom_tool_call", call_id="child-call", name="exec", input="text(42)"),
        tool("custom_tool_call_output", call_id="child-call", output="42"),
        message("AgentMessage", "Packaging ready", session=CHILD_ID, phase="final_answer"),
    ])
    out = tmp_path / "export"
    summary = export_sessions([source], out)["sessions"][0]
    assert summary["session_id"] == CHILD_ID
    assert summary["agent_path"] == "/root/packaging"
    assert summary["role"] == "packaging-evaluation"
    raw = (out / summary["export_file"]).read_text()
    assert "PRIVATE" not in raw
    assert "text(42)" in raw and "Packaging ready" in raw


@pytest.mark.parametrize("secret", [
    "sk-or-v1-abcdef0123456789abcdef0123456789",
    "c3p-AbCdEf0123456789AbCdEf0123456789",
    "c3a-AbCdEf0123456789AbCdEf0123456789",
    "stub-abcdef0123456789abcdef01",
    "Bearer AbCdEf0123456789",
    "OPENROUTER_API_KEY=short-credential",
    'admin_token="short-credential"',
    "AbCdEf0123456789AbCdEf0123456789AbCdEf0123456789",
    "eyJhbGciOiJub25lIn0.eyJzdWIiOiJidWlsZCJ9.0123456789abcdef",
    "token=short-credential",
    "-----BEGIN PRIVATE KEY-----\nprivate material\n-----END PRIVATE KEY-----",
])
def test_masks_token_like_text(secret):
    masked = redact(secret)
    assert "[REDACTED]" in masked
    assert "short-credential" not in masked
    assert "private material" not in masked
    assert "abcdef0123456789" not in masked


def test_masks_structured_credentials_and_preserves_session_uuid():
    assert redact({"OPENAI_API_KEY": "short", "nested": [{"Authorization": "Bearer short"}],
                   "token": "short", "session": ROOT_ID}) == {
        "OPENAI_API_KEY": "[REDACTED]", "nested": [{"Authorization": "[REDACTED]"}],
        "token": "[REDACTED]", "session": ROOT_ID}


def test_partial_active_tail_is_skipped_and_hashed(tmp_path):
    source = transcript(tmp_path, [metadata(), message("UserMessage", "Build it")], tail=b'{"type":')
    out = tmp_path / "export"
    summary = export_sessions([source], out)["sessions"][0]
    assert summary["incomplete_final_lines_skipped"] == 1
    assert summary["source_snapshot_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()


def test_refuses_non_transcript_files_and_does_not_print_content(tmp_path, capsys):
    credential = tmp_path / ".env"
    credential.write_text("PRIVATE CREDENTIAL FILE")
    with pytest.raises(ValueError, match="only JSONL"):
        read_snapshot(credential)
    malformed = tmp_path / "bad.jsonl"
    malformed.write_text("PRIVATE MALFORMED CONTENT\n")
    assert main(["--session", str(malformed), "--out", str(tmp_path / "export")]) == 2
    output = capsys.readouterr().out
    assert "PRIVATE" not in output
    assert json.loads(output)["ok"] is False


def test_cli_prints_only_summary_not_transcript(tmp_path, capsys):
    source = transcript(tmp_path, [metadata(), message("UserMessage", "ACTUAL USER CONTENT")])
    assert main(["--session", str(source), "--out", str(tmp_path / "export")]) == 0
    output = capsys.readouterr().out
    assert "ACTUAL USER CONTENT" not in output
    assert json.loads(output)["sessions"] == 1
