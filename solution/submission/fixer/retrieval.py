"""Small lexical context builder; never ingest the background corpus wholesale."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
import re


_STOP = set("about after again also are before both can case code does each every file files for from has have into its log logs may more must not only other public read same service should some than that the their then there these they this time under until use using was were when where which while with workspace".split())


def _words(text: str) -> Counter:
    return Counter(word.rstrip("s") for word in re.findall(r"[a-z][a-z0-9_]{2,}", text.casefold()) if word not in _STOP)


def _read(path: Path, limit=20000) -> str:
    try:
        with path.open(encoding="utf-8", errors="replace") as handle:
            return handle.read(limit)
    except OSError:
        return ""


def _current(text: str) -> bool:
    # CURRENT documents often mention the superseded version, so inspect status.
    return not re.search(r"(?im)^\s*(?:status|version status)\s*:\s*(?:\*\*)?superseded", text[:1200])


def _excerpt(text: str, limit: int, query: Counter) -> str:
    if len(text) <= limit:
        return text
    lines = text.splitlines()
    # Retain document identity and highest-signal paragraphs, preserving order.
    selected = set(range(min(9, len(lines))))
    remaining = max(0, limit - sum(len(lines[index]) + 1 for index in selected) - 120)
    ranking = []
    for index, line in enumerate(lines):
        words = _words(line)
        score = sum(min(query[word], 3) for word in words if word in query)
        if line.startswith("#"):
            score += 1
        if score:
            ranking.append((score, index))
    for _, index in sorted(ranking, key=lambda item: (-item[0], item[1])):
        block = set(range(max(0, index - 2), min(len(lines), index + 5))) - selected
        cost = sum(len(lines[pos]) + 1 for pos in block)
        if cost <= remaining:
            selected.update(block)
            remaining -= cost
    output = []
    previous = -1
    for index in sorted(selected):
        if index > previous + 1:
            output.append("[…] (use read_file for omitted lines)")
        output.append(lines[index])
        previous = index
    return "\n".join(output)[:limit]


def _safe_files(directory: Path, allowed: Path):
    if not directory.is_dir():
        return []
    return [path for path in sorted(directory.rglob("*.md")) if path.is_file() and path.resolve().is_relative_to(allowed)]


def build_context(workspace: Path, corpus: Path, max_chars=45000) -> str:
    """Infer service docs from README/source names, then prioritize current contracts."""
    workspace, corpus = Path(workspace).resolve(), Path(corpus).resolve()
    max_chars = max(0, int(max_chars))
    if max_chars == 0:
        return ""
    ticket = _read(workspace / "SYMPTOM.md", 12000)
    readme = _read(workspace / "README.md", 14000)
    invariants = _read(workspace / "INVARIANTS.md", 20000)
    query = _words(ticket + "\n" + invariants)
    sections = []

    def add(label: str, text: str, cap: int):
        if text:
            sections.append(f"\n--- {label} ---\n{_excerpt(text, cap, query)}\n")

    add("SYMPTOM.md", ticket, 6500)
    add("README.md", readme, 5000)
    add("INVARIANTS.md", invariants, 8500)
    source = workspace / "src"
    source_files = [path for path in sorted(source.rglob("*")) if path.is_file() and path.resolve().is_relative_to(source) and "__pycache__" not in path.parts] if source.is_dir() else []
    add("Source tree (read files with tools)", "\n".join(str(path.relative_to(workspace)) for path in source_files[:150]), 3500)

    log_sections = []
    logs = workspace / "logs"
    if logs.is_dir():
        for path in sorted(logs.iterdir())[:12]:
            if not path.is_file() or not path.resolve().is_relative_to(workspace):
                continue
            # Bounded head for keywords plus a bounded tail for the final state.
            head = _read(path, 16000)
            try:
                with path.open("rb") as handle:
                    handle.seek(0, 2)
                    handle.seek(max(0, handle.tell() - 6500))
                    tail = handle.read(6500).decode("utf-8", errors="replace")
            except OSError:
                tail = ""
            signals = [line[:700] for line in head.splitlines() if re.search(r"(?i)error|violation|unknown|expired|missing|fail|cancel|requeue|reject", line)]
            log_sections.append(f"{path.relative_to(workspace)}:\n" + "\n".join(signals[:5] + tail.splitlines()[-4:]))
    add("Log signals and final state (bounded samples)", "\n\n".join(log_sections), 6500)
    add("corpus/INDEX.md", _read(corpus / "INDEX.md", 7000), 3500)

    # Explicit corpus paths are strongest evidence. Otherwise match package names
    # in document titles; this works even when README references absent local docs.
    explicit_services = set(re.findall(r"(?:corpus/)?(service/[A-Za-z0-9_-]+)(?:/|\b)", readme))
    package_names = {path.name.casefold() for path in source.iterdir() if path.is_dir() and not path.name.startswith("_")} if source.is_dir() else set()
    service_docs = []
    service_root = corpus / "service"
    for directory in sorted(service_root.iterdir()) if service_root.is_dir() else []:
        if not directory.is_dir() or not directory.resolve().is_relative_to(corpus):
            continue
        documents = _safe_files(directory, corpus)
        heading_text = "\n".join(_read(path, 900) for path in documents)
        explicit = str(directory.relative_to(corpus)) in explicit_services
        matched = any(re.search(r"\b" + re.escape(name) + r"\b", heading_text.casefold()) for name in package_names)
        if explicit or (not explicit_services and matched):
            service_docs.extend(documents)
    local_docs = _safe_files(workspace / "service-docs", workspace)
    all_service_docs = [(path, workspace) for path in local_docs] + [(path, corpus) for path in service_docs]
    preferred = {"operational-notes.md": 8, "design-overview.md": 7, "api-reference.md": 3, "changelog.md": 1}
    ranked_service = []
    for path, root in all_service_docs:
        text = _read(path, 24000)
        if not _current(text):
            continue
        score = preferred.get(path.name, 0) + sum(min(query[word], 2) for word in _words(text) if word in query) / 20
        ranked_service.append((score, path, root, text))
    for _, path, root, text in sorted(ranked_service, key=lambda item: (-item[0], str(item[1])))[:5]:
        label = ("corpus/" if root == corpus else "") + str(path.relative_to(root))
        add(label, text, 6500 if path.name == "operational-notes.md" else 5500)

    # Index status and explicit references choose current platform contracts;
    # filename/version or practice case ids are never used to select a patch.
    platform_docs = []
    references = ticket + readme + "\n".join(item[3] for item in ranked_service)
    for path in _safe_files(corpus / "platform", corpus):
        text = _read(path, 20000)
        if not _current(text) or path.name == "changelog.md":
            continue
        score = sum(min(query[word], 3) for word in _words(text) if word in query)
        if str(path.relative_to(corpus)) in references:
            score += 15
        platform_docs.append((score, path, text))
    for _, path, text in sorted(platform_docs, key=lambda item: (-item[0], str(item[1])))[:4]:
        add("corpus/" + str(path.relative_to(corpus)), text, 6000)

    # Share the budget across sections instead of dropping late platform docs.
    total = sum(len(section) for section in sections)
    if total > max_chars:
        scale = max_chars / total
        compacted = []
        for section in sections:
            header, _, body = section.partition("---\n")
            cap = max(0, int(len(section) * scale) - len(header) - 5)
            compacted.append(header + "---\n" + _excerpt(body, cap, query))
        sections = compacted
    return "\n".join(sections)[:max_chars]
