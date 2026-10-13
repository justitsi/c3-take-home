from pathlib import Path
import os
import shutil
import subprocess

import pytest


SOLUTION = Path(__file__).resolve().parents[1]
PATH_HELPER = SOLUTION / "dev" / "runner_paths.sh"


def resolve(repo, requested):
    return subprocess.run(
        ["bash", "-c", 'source "$1"; c3_solution_path "$2" "$3" "$4"',
         "path-test", str(PATH_HELPER), str(requested), str(repo), str(repo / "solution")],
        capture_output=True, text=True,
    )


def test_paths_normalize_with_spaces_and_nonexistent_children(tmp_path):
    repo = tmp_path / "repo with spaces"
    (repo / "solution").mkdir(parents=True)
    result = resolve(repo, "./solution/results/new run")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(repo / "solution/results/new run")


@pytest.mark.parametrize("requested", ["results/out", "../outside", "/tmp/out", "solution/../out", ""])
def test_paths_outside_solution_are_rejected_before_creation(tmp_path, requested):
    (tmp_path / "solution").mkdir()
    before = set(tmp_path.rglob("*"))
    assert resolve(tmp_path, requested).returncode == 2
    assert set(tmp_path.rglob("*")) == before


def test_symlink_ancestor_escape_is_rejected(tmp_path):
    repo = tmp_path / "repo"
    (repo / "solution").mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    (repo / "solution/results").symlink_to(outside, target_is_directory=True)
    assert resolve(repo, "solution/results/new-output").returncode == 2
    assert not (outside / "new-output").exists()


def test_output_and_scratch_options_validate_both_cli_spellings(tmp_path):
    (tmp_path / "solution").mkdir()
    result = subprocess.run(
        ["bash", "-c", 'source "$1"; c3_validate_grader_paths "$2" "$3" "${@:4}"; '
         'printf "%s\\n" "${C3_VALIDATED_ARGS[@]}"', "args-test", str(PATH_HELPER),
         str(tmp_path), str(tmp_path / "solution"), "--fixer", "candidate:v2",
         "--out=solution/results/pilot", "--tmp", "solution/results/.scratch"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert f"--out={tmp_path}/solution/results/pilot" in result.stdout
    assert str(tmp_path / "solution/results/.scratch") in result.stdout


def test_wrapper_routes_new_artifacts_and_preserves_original_cache(tmp_path):
    repo = tmp_path / "repo"
    solution = repo / "solution"
    solution.mkdir(parents=True)
    shutil.copy2(SOLUTION / "grade-docker.sh", solution / "grade-docker.sh")
    shutil.copytree(SOLUTION / "dev", solution / "dev")
    (repo / ".env").write_text("THIS FILE MUST NOT BE READ OR PRINTED")
    original_cache = repo / "grader/.cache"
    original_cache.mkdir(parents=True)
    (original_cache / "v1.json").write_text("preserve-v1")
    stub_dir = solution / "test-bin"
    stub_dir.mkdir()
    docker = stub_dir / "docker"
    docker.write_text(
        '#!/bin/sh\n'
        'if [ "$1" = volume ] && [ "$2" = inspect ]; then\n'
        '  printf "%s\\n" /var/lib/docker/volumes/test-proxy/_data\n'
        'elif [ "$1" = run ]; then\n'
        '  printf "%s\\n" "$@"\n'
        'fi\n'
    )
    docker.chmod(0o755)
    env = {**os.environ, "PATH": f"{stub_dir}:{os.environ['PATH']}"}
    env.pop("C3_RESULTS_ROOT", None)
    result = subprocess.run(
        ["bash", str(solution / "grade-docker.sh"), "--fixer", "candidate:v2",
         "--out", "solution/results/pilot"], cwd=repo, env=env,
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert f"C3_RESULTS_ROOT={solution}/results" in result.stdout
    assert f"C3_RUNNER_LOG_DIR={solution}/results/.runner/" in result.stdout
    assert f"source={solution}/results/.grader-cache,target={original_cache}" in result.stdout
    assert str(solution / "results/pilot") in result.stdout
    assert "THIS FILE MUST NOT BE READ OR PRINTED" not in result.stdout + result.stderr
    assert (original_cache / "v1.json").read_text() == "preserve-v1"
    assert not (repo / "results").exists()
