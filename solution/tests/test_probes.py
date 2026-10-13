"""Generic scenario authoring and trusted source-audit contracts."""

import hashlib
import json
from pathlib import Path
import threading

import pytest

from fixer.tools import PROBE_TOOL_SCHEMA, READ_TOOL_SCHEMAS, Tools


BASE = """name: provided
seed: 7
end_at: 50
quiesce_at: 30
liveness_window: 20
gpu: {capacity: 4}
nodes:
  - {name: leader, class: 'example.leader:Leader'}
  - {name: 'worker-{i}', count: 2, class: 'example.worker:Worker'}
client: {target: leader}
faults: faults/calm.yaml
workload:
  - {action: work, at: 1, repeat: 2, every: 1, key: 'item-{i}'}
expect: {no_unhandled_exceptions: true, all_actions_resolved_by: 49}
"""


@pytest.fixture
def probe_tools(tmp_path):
    workspace = tmp_path / "workspace"
    (workspace / "src").mkdir(parents=True)
    (workspace / "scenarios/faults").mkdir(parents=True)
    (workspace / "scenarios/public.yaml").write_text(BASE)
    (workspace / "scenarios/faults/calm.yaml").write_text("network: {drop: 0}\n")
    (workspace / "scenarios/faults/other.yaml").write_text("network: {drop: 0.02}\n")
    return Tools(workspace, tmp_path / "corpus", tmp_path / "scratch")


def test_clone_merge_hash_and_write_once_registry(probe_tools):
    supplied = probe_tools.workspace / "scenarios/public.yaml"
    before = supplied.read_bytes()
    result = probe_tools.create_probe(overrides={"gpu": {"capacity": 2}, "workload": [
        {"action": "work", "at": 2, "key": "one"}, {"action": "stop", "at": 3, "key": "one"},
    ]}, name="ordering", seed=9)
    assert result["ok"], result
    path = Path(result["scenario_path"])
    data = json.loads(path.read_text())
    assert result["seed"] == data["seed"] == 9
    assert data["expect"]["no_unhandled_exceptions"] is True
    assert data["gpu"] == {"capacity": 2}
    assert data["faults"] == str(probe_tools.workspace / "scenarios/faults/calm.yaml")
    assert result["expanded_nodes"] == 3 and result["expanded_actions"] == 2
    assert hashlib.sha256(path.read_bytes()).hexdigest() == result["sha256"]
    assert probe_tools.authored_probes[result["scenario_artifact"]] == {
        "path": str(path), "sha256": result["sha256"],
    }
    assert path.stat().st_mode & 0o222 == 0
    assert probe_tools.read_file(result["scenario_artifact"])["ok"]
    assert supplied.read_bytes() == before
    another = probe_tools.create_probe(overrides={}, name="ordering")
    assert another["ok"] and another["seed"] == 7
    assert another["scenario_path"] != result["scenario_path"]
    assert path.read_bytes() == json.dumps(data, ensure_ascii=False, indent=2).encode() + b"\n"


def test_fault_override_is_only_a_supplied_file(probe_tools):
    result = probe_tools.create_probe(overrides={}, faults="scenarios/faults/other.yaml")
    assert result["ok"], result
    assert json.loads(Path(result["scenario_path"]).read_text())["faults"].endswith("/scenarios/faults/other.yaml")
    assert not probe_tools.create_probe(overrides={"faults": {"network": {"drop": 1}}})["ok"]
    assert not probe_tools.create_probe(overrides={}, faults="../outside.yaml")["ok"]


@pytest.mark.parametrize("overrides", [
    {"nodes": [{"name": "unsafe", "class": "os:system"}]},
    {"nodes": [{"name": "worker-{i}", "class": "example.worker:Worker", "count": 33}]},
    {"nodes": [{"name": "same", "class": "example.worker:Worker", "count": 2}]},
    {"nodes": [{"name": "gpu", "class": "example.worker:Worker"}]},
    {"nodes": [{"name": "worker-{i}", "class": "example.worker:Worker", "count": True}]},
    {"workload": [{"at": 1, "action": "work", "repeat": 501}]},
    {"workload": [{"at": 1, "action": "work", "repeat": 250}, {"at": 1, "action": "work", "repeat": 251}]},
    {"workload": [{"at": 49, "action": "work", "repeat": 2, "every": 2}]},
    {"workload": [{"at": 1, "action": "work", "repeat": 1.5}]},
    {"workload": [{"at": float("nan"), "action": "work"}]},
    {"end_at": 601}, {"end_at": True}, {"end_at": float("inf")}, {"quiesce_at": 100},
    {"unknown": True}, {"seed": -1}, {"meta": {"bad": {1, 2}}},
    {"meta": {"large": "x" * 8193}},
    {"meta": {str(i): "x" * 2000 for i in range(40)}},
])
def test_resource_and_safe_data_rejections_leave_no_probe(probe_tools, overrides):
    result = probe_tools.create_probe(overrides=overrides)
    assert not result["ok"], result
    assert probe_tools.authored_probes == {}
    assert not (probe_tools.artifacts_root / "probes").exists()


@pytest.mark.parametrize("yaml", [
    "name: one\nname: two\n",
    "!!python/object/apply:os.system ['echo unsafe']\n",
    "loop: &loop {child: *loop}\n",
    "date: 2026-01-01\n",
    "name: " + "x" * 65536,
])
def test_unsafe_or_ambiguous_supplied_yaml_is_rejected(probe_tools, yaml):
    (probe_tools.workspace / "scenarios/public.yaml").write_text(yaml)
    assert not probe_tools.create_probe(overrides={})["ok"]
    assert probe_tools.authored_probes == {}


def test_inline_supplied_faults_preserved_without_authoring_new_faults(probe_tools):
    path = probe_tools.workspace / "scenarios/public.yaml"
    path.write_text(BASE.replace("faults: faults/calm.yaml", "faults: {network: {drop: 0.01}}"))
    result = probe_tools.create_probe(overrides={})
    assert result["ok"], result
    assert json.loads(Path(result["scenario_path"]).read_text())["faults"] == {"network": {"drop": 0.01}}


def test_scenario_fault_and_artifact_symlink_escapes_rejected(probe_tools, tmp_path):
    outside = tmp_path / "outside.yaml"
    outside.write_text(BASE)
    (probe_tools.workspace / "scenarios/escape.yaml").symlink_to(outside)
    (probe_tools.workspace / "scenarios/faults/escape.yaml").symlink_to(outside)
    assert not probe_tools.create_probe(base_scenario="escape", overrides={})["ok"]
    assert not probe_tools.create_probe(base_scenario=str(outside), overrides={})["ok"]
    assert not probe_tools.create_probe(overrides={}, faults="scenarios/faults/escape.yaml")["ok"]
    probe_tools.artifacts_root.mkdir(parents=True)
    (probe_tools.artifacts_root / "probes").symlink_to(tmp_path)
    assert not probe_tools.create_probe(overrides={})["ok"]
    assert not (tmp_path / "scenario.yaml").exists()


def test_probe_cancellation_and_invalid_name(probe_tools):
    assert not probe_tools.create_probe(overrides={}, name="../escape")["ok"]
    assert not probe_tools.create_probe(overrides={}, seed=True)["ok"]
    probe_tools.stop = threading.Event()
    probe_tools.stop.set()
    result = probe_tools.create_probe(overrides={})
    assert not result["ok"] and "cancelled" in result["error"]
    assert not probe_tools.artifacts_root.exists()


def test_source_diff_requires_trusted_checkpoint_and_covers_added_removed_empty(probe_tools, tmp_path):
    assert not probe_tools.source_diff()["ok"]
    original = tmp_path / "original"
    original.mkdir()
    (original / "same.py").write_text("x = 1\n")
    (original / "changed.py").write_text("before = 1\n")
    (original / "removed.py").write_text("remove = 1\n")
    (probe_tools.workspace / "src/same.py").write_text("x = 1\n")
    (probe_tools.workspace / "src/changed.py").write_text("after = 2\n")
    (probe_tools.workspace / "src/empty.py").write_text("")
    probe_tools.original_source = original
    result = probe_tools.source_diff()
    assert result["ok"] and not result["truncated"], result
    assert result["changed_files"] == ["src/changed.py", "src/empty.py", "src/removed.py"]
    assert "-before = 1" in result["diff"] and "+after = 2" in result["diff"]
    assert "empty file added" in result["diff"] and "/dev/null" in result["diff"]
    assert "same.py" not in result["diff"]


def test_source_diff_output_is_bounded_and_cancellable(probe_tools, tmp_path):
    original = tmp_path / "original"
    original.mkdir()
    (original / "large.py").write_text("x = 1\n" * 7000)
    (probe_tools.workspace / "src/large.py").write_text("y = 2\n" * 7000)
    probe_tools.original_source = original
    result = probe_tools.source_diff()
    assert result["ok"] and result["truncated"]
    assert len(json.dumps(result, ensure_ascii=False)) <= 18000
    probe_tools.stop = threading.Event()
    probe_tools.stop.set()
    assert not probe_tools.source_diff()["ok"]


def test_source_diff_never_follows_symlinks(probe_tools, tmp_path):
    original = tmp_path / "original"
    original.mkdir()
    outside = tmp_path / "secret"
    outside.write_text("must not be exposed")
    (probe_tools.workspace / "src/escape.py").symlink_to(outside)
    probe_tools.original_source = original
    result = probe_tools.source_diff()
    assert not result["ok"] and "symlink" in result["error"]
    assert "must not be exposed" not in str(result)


def test_source_diff_handles_binary_changes_without_false_empty_file_claim(probe_tools, tmp_path):
    original = tmp_path / "original"
    original.mkdir()
    (original / "asset.bin").write_bytes(b"\xff")
    (probe_tools.workspace / "src/asset.bin").write_bytes(b"\xfe")
    probe_tools.original_source = original
    result = probe_tools.source_diff()
    assert result["ok"] and "binary source changed" in result["diff"]
    assert "empty file" not in result["diff"]


def test_probe_authoring_is_editor_only_and_diff_is_read_only():
    read_names = {schema["function"]["name"] for schema in READ_TOOL_SCHEMAS}
    assert "source_diff" in read_names and "create_probe" not in read_names
    assert PROBE_TOOL_SCHEMA["function"]["name"] == "create_probe"
