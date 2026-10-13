from pathlib import Path
import json
import threading

import pytest

from fixer.retrieval import build_context
from fixer.tools import Tools


@pytest.fixture
def tools(tmp_path):
    workspace = tmp_path / "workspace"
    corpus = tmp_path / "corpus"
    (workspace / "src").mkdir(parents=True)
    (corpus / "platform").mkdir(parents=True)
    return Tools(workspace, corpus, tmp_path / "scratch")


def test_source_containment_and_symlink_escape(tools, tmp_path):
    outside = tmp_path / "outside.py"
    outside.write_text("x = 1\n")
    (tools.workspace / "src" / "escape.py").symlink_to(outside)
    for path in ("../outside.py", str(outside), "src/escape.py", "corpus/platform/new.py", "tests/new.py"):
        assert not tools.apply_edits([{"path": path, "old": "", "new": "x = 2\n"}])["ok"]
    assert not tools.read_file("src/escape.py")["ok"]
    assert outside.read_text() == "x = 1\n"


def test_new_file_and_multi_edit_journal(tools):
    result = tools.apply_edits([{"path": "src/nested/new.py", "old": "", "new": "value = 1\n"}])
    assert result["ok"]
    assert (tools.workspace / "src/nested/new.py").read_text() == "value = 1\n"
    assert (Path(result["journal"]) / "manifest.json").is_file()
    result = tools.apply_edits([
        {"path": "src/nested/new.py", "old": "value = 1", "new": "value = 2"},
        {"path": "src/nested/new.py", "old": "value = 2", "new": "value = 3"},
    ])
    assert result["ok"]
    assert (Path(result["journal"]) / "0.before").read_text() == "value = 1\n"


@pytest.mark.parametrize("replacements", [
    [("value = 1", "value = 1")],
    [("value = 1", "value = 2"), ("value = 2", "value = 1")],
])
def test_entirely_unchanged_transaction_is_rejected(tools, replacements):
    path = tools.workspace / "src/code.py"
    path.write_text("value = 1\n")
    before = path.stat().st_mtime_ns
    result = tools.apply_edits([{"path": "src/code.py", "old": old, "new": new} for old, new in replacements])
    assert not result["ok"]
    assert "no source changes" in result["error"]
    assert path.read_text() == "value = 1\n"
    assert path.stat().st_mtime_ns == before
    assert not tools.scratch.exists()


def test_unchanged_files_are_omitted_from_mixed_transaction(tools):
    first = tools.workspace / "src/first.py"
    second = tools.workspace / "src/second.py"
    first.write_text("x = 1\n")
    second.write_text("y = 2\n")
    before = first.stat().st_mtime_ns
    result = tools.apply_edits([
        {"path": "src/first.py", "old": "x = 1", "new": "x = 1"},
        {"path": "src/second.py", "old": "y = 2", "new": "y = 3"},
    ])
    assert result["ok"] and result["changed"] == ["src/second.py"]
    assert first.stat().st_mtime_ns == before
    assert first.read_text() == "x = 1\n"
    assert second.read_text() == "y = 3\n"
    manifest = json.loads((Path(result["journal"]) / "manifest.json").read_text())
    assert len(manifest) == 1 and manifest[0]["path"] == str(second)


def test_creating_absent_empty_file_is_a_source_change(tools):
    result = tools.apply_edits([{"path": "src/empty.py", "old": "", "new": ""}])
    assert result["ok"] and result["changed"] == ["src/empty.py"]
    assert (tools.workspace / "src/empty.py").read_bytes() == b""


@pytest.mark.parametrize("old", ["x = 1", "missing", ""])
def test_exact_old_match_rejects_ambiguous_missing_or_create_existing(tools, old):
    path = tools.workspace / "src/code.py"
    original = "x = 1\nx = 1\n"
    path.write_text(original)
    result = tools.apply_edits([{"path": "src/code.py", "old": old, "new": "x = 2"}])
    assert not result["ok"]
    assert path.read_text() == original


def test_invalid_python_rejects_whole_candidate_batch(tools):
    first = tools.workspace / "src/first.py"
    second = tools.workspace / "src/second.py"
    first.write_text("x = 1\n")
    second.write_text("y = 2\n")
    result = tools.apply_edits([
        {"path": "src/first.py", "old": "x = 1", "new": "x = 4"},
        {"path": "src/second.py", "old": "y = 2", "new": "if :"},
    ])
    assert not result["ok"]
    assert first.read_text() == "x = 1\n"
    assert second.read_text() == "y = 2\n"


def test_replace_failure_rolls_back_installed_candidates(tools, monkeypatch):
    import fixer.tools as module

    first = tools.workspace / "src/first.py"
    second = tools.workspace / "src/second.py"
    first.write_text("x = 1\n")
    second.write_text("y = 2\n")
    replace = module.os.replace
    calls = 0

    def interrupted(source, destination):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated replacement failure")
        return replace(source, destination)

    monkeypatch.setattr(module.os, "replace", interrupted)
    result = tools.apply_edits([
        {"path": "src/first.py", "old": "x = 1", "new": "x = 4"},
        {"path": "src/second.py", "old": "y = 2", "new": "y = 5"},
    ])
    assert not result["ok"]
    assert result["rollback_errors"] == []
    assert first.read_text() == "x = 1\n"
    assert second.read_text() == "y = 2\n"


def test_cancellation_before_staging_has_no_source_changes(tools):
    tools.stop = threading.Event()
    tools.stop.set()
    result = tools.apply_edits([{"path": "src/new.py", "old": "", "new": "x = 1\n"}])
    assert not result["ok"]
    assert "cancelled" in result["error"]
    assert not (tools.workspace / "src/new.py").exists()
    assert not tools.scratch.exists()


@pytest.mark.parametrize("stop_after_install", [1, 2, 3])
def test_cancellation_during_install_restores_files_and_removes_additions(tools, monkeypatch, stop_after_install):
    import fixer.tools as module

    first = tools.workspace / "src/first.py"
    second = tools.workspace / "src/second.py"
    new = tools.workspace / "src/nested/new.py"
    original_first = b"x = 1\n"
    original_second = b"y = 2\n"
    first.write_bytes(original_first)
    second.write_bytes(original_second)
    tools.stop = threading.Event()
    replace = module.os.replace
    installs = 0

    def cancel_after_install(source, destination):
        nonlocal installs
        result = replace(source, destination)
        # Only candidate installation triggers cancellation; rollback must run.
        if Path(source).name.startswith(".fixer-") and not Path(source).name.startswith(".fixer-rollback-"):
            installs += 1
            if installs == stop_after_install:
                tools.stop.set()
        return result

    monkeypatch.setattr(module.os, "replace", cancel_after_install)
    result = tools.apply_edits([
        {"path": "src/first.py", "old": "x = 1", "new": "x = 4"},
        {"path": "src/nested/new.py", "old": "", "new": "new = True\n"},
        {"path": "src/second.py", "old": "y = 2", "new": "y = 5"},
    ])
    assert not result["ok"]
    assert "cancelled" in result["error"]
    assert result["rollback_errors"] == []
    assert first.read_bytes() == original_first
    assert second.read_bytes() == original_second
    assert not new.exists()
    assert not new.parent.exists()


def test_bounded_reads_and_case_insensitive_search(tools):
    (tools.workspace / "src/code.py").write_text("before\nLEASE EXPIRED\nafter\n" * 300)
    read = tools.read_file("src/code.py", 2, 900)
    assert read["ok"] and read["truncated"]
    assert read["end_line"] <= 401
    assert len(read["content"]) <= 18000
    result = tools.search("lease expired", limit=2)
    assert result["ok"] and len(result["matches"]) == 2
    assert result["matches"][0]["line"] == 2
    assert result["matches"][0]["before"] == "before"
    assert result["matches"][0]["after"] == "after"


def test_corpus_broad_search_excludes_background(tools):
    (tools.corpus / "platform/current.md").write_text("token needle\n")
    (tools.corpus / "background").mkdir()
    (tools.corpus / "background/paper.md").write_text("needle theory\n")
    result = tools.search("needle", root="corpus")
    assert [match["path"] for match in result["matches"]] == ["corpus/platform/current.md"]
    assert tools.search("needle", root="corpus/background")["matches"][0]["path"] == "corpus/background/paper.md"


def test_retrieval_infers_service_and_avoids_superseded_background(tools):
    workspace, corpus = tools.workspace, tools.corpus
    (workspace / "src/processor").mkdir()
    (workspace / "src/processor/worker.py").write_text("x = 1\n")
    (workspace / "README.md").write_text("processor: shard processing. Read service-docs/design-overview.md and platform/gpu-v3.md.")
    (workspace / "SYMPTOM.md").write_text("Leases expire and shard jobs hang after timeout.")
    (workspace / "INVARIANTS.md").write_text("Every shard finishes, and leases remain fenced.")
    (corpus / "INDEX.md").write_text("Current service and platform contracts.")
    (corpus / "service/X").mkdir(parents=True)
    (corpus / "service/X/design-overview.md").write_text("# processor design\nStatus: CURRENT\nWorkers process shard leases.")
    (corpus / "service/X/operational-notes.md").write_text("# processor constants\nStatus: CURRENT\nLease duration is 12 seconds.")
    (corpus / "service/X/design-v1.md").write_text("# processor old design\nStatus: SUPERSEDED\nBAD_OLD_CONSTANT")
    (corpus / "platform/gpu-v3.md").write_text("# GPU\nStatus: CURRENT\nRetry with the same operation id.")
    (corpus / "platform/gpu-v1.md").write_text("# GPU\nStatus: SUPERSEDED\nBAD_OLD_GPU")
    (corpus / "background").mkdir()
    (corpus / "background/paper.md").write_text("BACKGROUND_PAPER_MUST_NOT_LOAD")
    context = build_context(workspace, corpus)
    assert "12 seconds" in context
    assert "Retry with the same operation id" in context
    assert "src/processor/worker.py" in context
    assert "BAD_OLD" not in context
    assert "BACKGROUND_PAPER" not in context
    assert len(build_context(workspace, corpus, max_chars=1200)) <= 1200
