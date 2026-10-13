#!/usr/bin/env python3
"""Build and verify the selected handoff; never read credentials or run models."""
from __future__ import annotations

import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOLUTION = ROOT / "solution"
OUTPUT = SOLUTION / "upload"
PREFIX = "c3-submission-v1"
IMAGE = "results/prototype-v1-final.tar"
SOURCE_ARCHIVE = "solution/results/selected-v1-source.tar"
SUPPLIED_DOCS = {"v2_architecture.md", "v3_architecture.md"}
EXCLUDED_PARTS = {".git", "__pycache__", ".pytest_cache", "eval-work",
                  ".scratch", ".runner", ".grader-cache", ".bind-restore-test",
                  "build-chats-r3-checkpoint", "upload"}
CREDENTIAL = re.compile(
    rb"(?:sk-or-v1-[A-Za-z0-9]{32,}|sk-ant-[A-Za-z0-9_-]{32,}|"
    rb"c3[paf]-[A-Za-z0-9_-]{24,}|"
    rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----\s+[A-Za-z0-9+/=]{40,})"
)
# Exact synthetic values in the preserved redaction fixtures, never a file-wide bypass.
SYNTHETIC_CREDENTIALS = {
    b"sk-or-v1-abcdef0123456789abcdef0123456789",
    b"c3p-AbCdEf0123456789AbCdEf0123456789",
    b"c3a-AbCdEf0123456789AbCdEf0123456789",
}


def digest(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def collect() -> list[Path]:
    files = []
    for base in (SOLUTION, ROOT / "results", ROOT / "evidence"):
        for path in sorted(base.rglob("*")):
            relative = path.relative_to(ROOT)
            if any(part in EXCLUDED_PARTS for part in relative.parts):
                continue
            if path.is_symlink():
                raise ValueError(f"symlink not allowed: {relative}")
            if not path.is_file():
                continue
            if path.name == ".DS_Store" or path.suffix in {".pyc", ".tmp", ".bak"}:
                continue
            if path.name == ".env" or path.name.startswith(".env."):
                raise ValueError(f"credential file not allowed: {relative}")
            if path.suffix == ".tar" and str(relative) not in {IMAGE, SOURCE_ARCHIVE}:
                continue
            files.append(path)
    return sorted(set(files))


def validate(files: list[Path]) -> dict:
    selection = json.loads((SOLUTION / "benchmarks/selected-version.json").read_text())
    if selection["selected_version"] != "v1-final" or not selection["all_six_cases_evaluated"]:
        raise ValueError("selected version lacks complete evaluation")
    if digest(ROOT / IMAGE) != selection["image_export_sha256"]:
        raise ValueError("selected image tar hash mismatch")
    source_manifest = json.loads((SOLUTION / "submission/source-manifest.json").read_text())
    for relative, expected in source_manifest["files"].items():
        if digest(SOLUTION / "submission" / relative) != expected:
            raise ValueError(f"selected source mismatch: {relative}")
    word_counts = {}
    for path in files:
        relative = path.relative_to(ROOT)
        if path.suffix == ".md" and path.name not in SUPPLIED_DOCS:
            count = len(path.read_text().split())
            limit = 450 if relative == Path("solution/WRITEUP.md") else 3000
            if count > limit:
                raise ValueError(f"word limit exceeded: {relative}: {count}/{limit}")
            word_counts[str(relative)] = count
        if path.suffix != ".tar":
            matches = CREDENTIAL.finditer(path.read_bytes())
            if any(match[0] not in SYNTHETIC_CREDENTIALS for match in matches):
                raise ValueError(f"possible credential in: {relative}; inspect locally")
    for directory in (ROOT / "evidence/build-chats", SOLUTION / "evidence/build-chats-r4-final"):
        manifest = json.loads((directory / "manifest.json").read_text())
        for entry in manifest["sessions"]:
            if digest(directory / entry["export_file"]) != entry["export_sha256"]:
                raise ValueError("chat export hash mismatch")
    return {"selected_version": "v1-final", "image_identity": selection["image_identity"],
            "score": "9/12; complete six-case evaluation",
            "source": "solution/submission/fixer", "word_counts": word_counts,
            "supplied_proposals_unchanged": sorted(SUPPLIED_DOCS),
            "credential_scan_exception": "Three exact synthetic redaction-test tokens; no file-wide bypass.",
            "exclusions": "credentials, Git, corpus/cases/grader, scratch, replay traces, caches, runner state, redundant checkpoints, experimental image tars",
            "files": {str(path.relative_to(ROOT)): {"sha256": digest(path), "bytes": path.stat().st_size}
                      for path in files}}


def main() -> None:
    files = collect()
    manifest = validate(files)
    OUTPUT.mkdir(exist_ok=True)
    target = OUTPUT / "c3-submission-v1.tar.gz"
    with tempfile.TemporaryDirectory(dir=OUTPUT, prefix=".package-") as staging:
        temporary_path = Path(staging) / "bundle.tar.gz"
        with temporary_path.open("wb") as temporary, gzip.GzipFile(fileobj=temporary, mode="wb", filename="", mtime=0, compresslevel=1) as compressed:
            with tarfile.open(fileobj=compressed, mode="w|") as archive:
                for path in files:
                    name = f"{PREFIX}/{path.relative_to(ROOT)}"
                    info = archive.gettarinfo(str(path), arcname=name)
                    info.uid = info.gid = info.mtime = 0
                    info.uname = info.gname = ""
                    info.mode = 0o755 if path.name.endswith(".sh") else 0o644
                    with path.open("rb") as source:
                        archive.addfile(info, source)
                encoded = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
                info = tarfile.TarInfo(f"{PREFIX}/UPLOAD_MANIFEST.json")
                info.size, info.mode = len(encoded), 0o644
                archive.addfile(info, io.BytesIO(encoded))
        # Verify archive members and contents without extracting anything.
        with tarfile.open(temporary_path, "r:gz") as archive:
            seen = set()
            manifest_seen = False
            for member in archive:
                if not member.isfile() or not member.name.startswith(PREFIX + "/"):
                    raise ValueError("unexpected archive member")
                name = member.name[len(PREFIX) + 1:]
                if name == "UPLOAD_MANIFEST.json":
                    if manifest_seen or archive.extractfile(member).read() != encoded:
                        raise ValueError("archive manifest mismatch")
                    manifest_seen = True
                    continue
                if name in seen or name not in manifest["files"]:
                    raise ValueError("duplicate or unexpected archive path")
                seen.add(name)
                source = archive.extractfile(member)
                if source is None or hashlib.file_digest(source, "sha256").hexdigest() != manifest["files"][name]["sha256"]:
                    raise ValueError(f"archive hash mismatch: {name}")
            if not manifest_seen or seen != set(manifest["files"]):
                raise ValueError("archive files missing")
        temporary_path.replace(target)
    checksum = digest(target)
    (OUTPUT / "c3-submission-v1.tar.gz.sha256").write_text(f"{checksum}  {target.name}\n")
    print(json.dumps({"archive": str(target.relative_to(ROOT)), "bytes": target.stat().st_size,
                      "sha256": checksum, "files_verified": len(files),
                      "writeup_words": manifest["word_counts"]["solution/WRITEUP.md"]}, indent=2))


if __name__ == "__main__":
    main()
