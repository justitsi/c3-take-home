"""Write-once, bounded scenario probes derived from supplied scenario files."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile


MAX_BYTES = 64 * 1024
SCENARIO_KEYS = frozenset({
    "name", "seed", "end_at", "quiesce_at", "liveness_window", "gpu", "nodes",
    "service", "client", "client_retry", "faults", "workload", "expect", "description", "meta",
})


def _cancel(stop):
    if stop is not None and stop.is_set():
        raise ValueError("probe authoring cancelled")


def _json_safe(value, depth=0, ancestors=None, counter=None):
    """Reject aliases/cycles, non-JSON YAML types, nonfinite numbers and deep data."""
    ancestors = set() if ancestors is None else ancestors
    counter = [0] if counter is None else counter
    counter[0] += 1
    if counter[0] > 10000 or depth > 24:
        raise ValueError("probe data exceeds structural bounds")
    if value is None or isinstance(value, (bool, int)):
        if isinstance(value, int) and abs(value) > 10**12:
            raise ValueError("probe integer exceeds bounds")
        return
    if isinstance(value, float):
        if not math.isfinite(value) or abs(value) > 10**12:
            raise ValueError("probe numbers must be finite and bounded")
        return
    if isinstance(value, str):
        if len(value) > 8192 or "\x00" in value:
            raise ValueError("probe string exceeds bounds or contains NUL")
        return
    if not isinstance(value, (list, dict)):
        raise ValueError("probe values must be JSON-safe data")
    if id(value) in ancestors:
        raise ValueError("recursive YAML aliases are forbidden")
    ancestors.add(id(value))
    try:
        for key, item in value.items() if isinstance(value, dict) else enumerate(value):
            if isinstance(value, dict) and (not isinstance(key, str) or len(key) > 256):
                raise ValueError("probe mapping keys must be bounded strings")
            _json_safe(item, depth + 1, ancestors, counter)
    finally:
        ancestors.remove(id(value))


def _read_yaml(path):
    import yaml

    class UniqueLoader(yaml.SafeLoader):
        pass

    def mapping(loader, node, deep=False):
        loader.flatten_mapping(node)
        result = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node, deep=deep)
            if not isinstance(key, str) or key in result:
                raise ValueError("scenario YAML needs unique string mapping keys")
            result[key] = loader.construct_object(value_node, deep=deep)
        return result

    UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)
    with path.open("rb") as handle:
        raw = handle.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("supplied scenario exceeds 64KiB")
    try:
        value = yaml.load(raw.decode("utf-8"), Loader=UniqueLoader)
    except yaml.YAMLError as error:
        raise ValueError("invalid safe scenario YAML") from error
    _json_safe(value)
    if not isinstance(value, dict):
        raise ValueError("supplied scenario must be a mapping")
    return value


def _provided_file(workspace, value, relative_to=None, scenario=False):
    if not isinstance(value, str) or not value or "\x00" in value:
        raise ValueError("supplied scenario/fault path must be a nonempty string")
    path = Path(value)
    if ".." in path.parts:
        raise ValueError("parent traversal is forbidden")
    root = workspace / "scenarios"
    if root.is_symlink() or not root.is_dir():
        raise ValueError("supplied scenarios must be a real directory")
    if path.is_absolute():
        candidates = [path]
    elif path.parts[0] == "scenarios":
        candidates = [workspace / path]
    elif scenario:
        candidates = [root / (value + suffix) for suffix in (".yaml", ".yml", ".json", "")]
    else:
        candidates = [(relative_to or root) / path]
    for candidate in candidates:
        resolved = candidate.resolve()
        if not resolved.is_relative_to(root):
            raise ValueError("scenario/fault path escapes protected scenarios/")
        if resolved.is_file():
            return resolved
    raise ValueError("supplied scenario/fault file not found")


def _merge(base, overrides):
    result = copy.deepcopy(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _number(value, name, minimum=0, maximum=600):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


def _integer(value, name, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be an integer between {minimum} and {maximum}")
    return value


def _validate(scenario, base):
    unknown = set(scenario) - SCENARIO_KEYS
    if unknown:
        raise ValueError("unknown scenario keys: " + ", ".join(sorted(unknown)))
    end_at = _number(scenario.get("end_at"), "end_at", minimum=0.001)
    for key in ("quiesce_at", "liveness_window"):
        if scenario.get(key) is not None:
            _number(scenario[key], key, maximum=end_at)
    _integer(scenario.get("seed", 1), "seed", 0, 2**31 - 1)
    base_nodes = base.get("nodes") or []
    allowed_classes = {item.get("class") for item in base_nodes if isinstance(item, dict)}
    nodes = scenario.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        raise ValueError("probe nodes must be a nonempty list")
    expanded_nodes = 0
    names = set()
    for item in nodes:
        if not isinstance(item, dict) or set(item) - {"name", "class", "count", "config"}:
            raise ValueError("each probe node needs only name/class/count/config fields")
        if item.get("class") not in allowed_classes or not isinstance(item.get("class"), str):
            raise ValueError("probe node class must come from the supplied base scenario")
        if not isinstance(item.get("name"), str) or not item["name"] or len(item["name"]) > 128:
            raise ValueError("probe node name must be a bounded nonempty string")
        count = _integer(item.get("count", 1), "node count", 1, 32)
        expanded_nodes += count
        for index in range(1, count + 1):
            name = item["name"].replace("{i}", str(index)) if "count" in item else item["name"]
            if name in names or name in {"gpu", "client"}:
                raise ValueError("expanded probe node names must be unique and not reserved")
            names.add(name)
        if "config" in item and not isinstance(item["config"], dict):
            raise ValueError("node config must be a mapping")
    if expanded_nodes > 32:
        raise ValueError("probe expands to more than 32 nodes")
    workload = scenario.get("workload", [])
    if not isinstance(workload, list):
        raise ValueError("probe workload must be a list")
    expanded_actions = 0
    for item in workload:
        if not isinstance(item, dict) or not isinstance(item.get("action"), str) or not item["action"]:
            raise ValueError("each probe workload entry needs an action string")
        count = _integer(item.get("repeat", 1), "workload repeat", 1, 500)
        expanded_actions += count
        at = _number(item.get("at"), "workload at", maximum=end_at)
        every = _number(item.get("every", 0), "workload every", maximum=end_at)
        jitter = _number(item.get("jitter", 0), "workload jitter", maximum=end_at)
        if at + (count - 1) * every + jitter > end_at:
            raise ValueError("expanded workload must be scheduled within end_at")
    if expanded_actions > 500:
        raise ValueError("probe expands to more than 500 actions")
    for key in ("gpu", "service", "client", "client_retry", "expect", "meta"):
        if key in scenario and not isinstance(scenario[key], dict):
            raise ValueError(f"scenario {key} must be a mapping")
    return expanded_nodes, expanded_actions


def author_probe(workspace, artifacts_root, registry, *, base_scenario="public", overrides=None,
                 faults=None, name=None, seed=None, stop=None):
    """Author data only. The controller replays and registers its counterexample."""
    directory = None
    try:
        _cancel(stop)
        if not isinstance(overrides, dict):
            raise ValueError("overrides must be a mapping (use {} to clone the base)")
        _json_safe(overrides)
        if "faults" in overrides:
            raise ValueError("use faults= with a supplied file; inline fault overrides are forbidden")
        if name is not None and (not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", name)):
            raise ValueError("probe name must be 1-64 safe filename characters")
        workspace, artifacts_root = Path(workspace).resolve(), Path(artifacts_root)
        base_path = _provided_file(workspace, base_scenario, scenario=True)
        base = _read_yaml(base_path)
        scenario = _merge(base, overrides)
        if seed is not None:
            scenario["seed"] = seed
        if name is not None:
            scenario["name"] = name
        if faults is not None:
            scenario["faults"] = str(_provided_file(workspace, faults, base_path.parent))
        elif isinstance(scenario.get("faults"), str):
            scenario["faults"] = str(_provided_file(workspace, scenario["faults"], base_path.parent))
        _json_safe(scenario)
        expanded_nodes, expanded_actions = _validate(scenario, base)
        # JSON is a strict, safe YAML subset; never emit executable YAML tags.
        encoded = (json.dumps(scenario, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
        if len(encoded) > MAX_BYTES:
            raise ValueError("serialized probe exceeds 64KiB")
        if artifacts_root.is_symlink() or artifacts_root.resolve() != artifacts_root.absolute():
            raise ValueError("artifacts root must be a real contained directory")
        probes = artifacts_root / "probes"
        if probes.is_symlink():
            raise ValueError("probe directory must not be a symlink")
        _cancel(stop)
        probes.mkdir(parents=True, exist_ok=True)
        directory = Path(tempfile.mkdtemp(prefix=(name or "probe") + "-", dir=probes))
        path = directory / "scenario.yaml"
        with path.open("xb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        _cancel(stop)
        digest = hashlib.sha256(encoded).hexdigest()
        alias = "artifacts/" + path.relative_to(artifacts_root).as_posix()
        path.chmod(0o444)
        directory.chmod(0o555)
        registry[alias] = {"path": str(path.resolve()), "sha256": digest}
        return {"ok": True, "scenario_artifact": alias, "scenario_path": str(path.resolve()),
                "sha256": digest, "base_scenario": base_scenario, "seed": scenario.get("seed", 1),
                "expanded_nodes": expanded_nodes, "expanded_actions": expanded_actions}
    except (OSError, TypeError, ValueError, RecursionError, UnicodeError) as error:
        if directory is not None:
            directory.chmod(0o755)
            (directory / "scenario.yaml").unlink(missing_ok=True)
            directory.rmdir()
        return {"ok": False, "error": str(error)}
