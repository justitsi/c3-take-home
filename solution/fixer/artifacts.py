"""Bounded, cancellable JSONL evidence inspection without simulator knowledge."""

from __future__ import annotations

import json
import math
from pathlib import Path
import threading


MAX_TRACE_BYTES = 64 * 1024 * 1024
MAX_LINE_BYTES = 256 * 1024
MAX_TRACE_OUTPUT = 18_000
MAX_TRACE_TERMS = 8
MAX_TERM_CHARS = 256


def _reject_constant(value):
    raise ValueError(f"invalid JSON constant: {value}")


def _clip(value, depth=0):
    if isinstance(value, str):
        return value if len(value) <= 700 else value[:700] + "…"
    if isinstance(value, dict):
        if depth >= 5:
            return "[nested object omitted]"
        result = {str(key)[:120]: _clip(item, depth + 1) for key, item in list(value.items())[:24]}
        if len(value) > 24:
            result["_omitted_keys"] = len(value) - 24
        return result
    if isinstance(value, list):
        if depth >= 5:
            return "[nested array omitted]"
        result = [_clip(item, depth + 1) for item in value[:12]]
        if len(value) > 12:
            result.append(f"[{len(value) - 12} items omitted]")
        return result
    return value


def inspect_jsonl(path: Path, label: str, query: str | None = None,
                  center_t: float | None = None, window_s: float = 2.0,
                  limit: int = 30, stop: threading.Event | None = None,
                  all_terms: list[str] | None = None, start_line: int = 1) -> dict:
    """Return matching trace rows with original line numbers, never a full trace."""
    result = {"ok": True, "path": label, "events": [], "scanned_lines": 0,
              "scanned_bytes": 0, "matched_events": 0, "malformed_lines": 0,
              "malformed_line_numbers": [], "oversized_lines": 0,
              "truncated": False, "cancelled": False, "start_line": 1,
              "next_line": None, "returned_events": 0,
              "returned_time_range": None, "scan_limit_reached": False,
              "query_mode": "all_events"}
    try:
        if query is not None and (not isinstance(query, str) or not query.strip()):
            raise ValueError("query must be nonempty literal text when provided")
        needle = query.casefold() if query is not None else None
        if all_terms is not None and (
            not isinstance(all_terms, list) or not 1 <= len(all_terms) <= MAX_TRACE_TERMS
            or any(not isinstance(term, str) or not term.strip() or len(term) > MAX_TERM_CHARS for term in all_terms)
        ):
            raise ValueError("all_terms must contain 1–8 nonempty literal strings, each at most 256 characters")
        needles = ([needle] if needle is not None else []) + [term.casefold() for term in all_terms or []]
        result["query_mode"] = "literal+all_terms" if needle is not None and all_terms else (
            "literal" if needle is not None else "all_terms" if all_terms else "all_events")
        if isinstance(start_line, bool) or not isinstance(start_line, int) or start_line < 1:
            raise ValueError("start_line must be a positive line number")
        first = int(start_line)
        result["start_line"] = first
        center = float(center_t) if center_t is not None else None
        window = float(window_s)
        if (center is not None and not math.isfinite(center)) or not math.isfinite(window) or window < 0:
            raise ValueError("time filters must be finite and window_s must be nonnegative")
        limit = max(1, min(int(limit), 100))
        if not path.is_file():
            raise ValueError("trace path must name a regular file")
        output_chars = 0
        file_size = path.stat().st_size
        with path.open("rb") as handle:
            while result["scanned_bytes"] < MAX_TRACE_BYTES:
                if stop is not None and stop.is_set():
                    result.update(ok=False, cancelled=True, truncated=True, error="trace inspection cancelled")
                    result["next_line"] = max(first, result["scanned_lines"] + 1)
                    break
                allowance = min(MAX_LINE_BYTES + 1, MAX_TRACE_BYTES - result["scanned_bytes"])
                raw = handle.readline(allowance)
                if not raw:
                    break
                result["scanned_bytes"] += len(raw)
                result["scanned_lines"] += 1
                number = result["scanned_lines"]
                oversized = len(raw) > MAX_LINE_BYTES
                # Discard an oversized line in bounded chunks, preserving the
                # provenance of all following records without buffering it.
                while raw and not raw.endswith(b"\n") and result["scanned_bytes"] < file_size:
                    oversized = True
                    if stop is not None and stop.is_set():
                        result.update(ok=False, cancelled=True, truncated=True, error="trace inspection cancelled")
                        result["next_line"] = max(first, number)
                        break
                    remaining = MAX_TRACE_BYTES - result["scanned_bytes"]
                    if remaining <= 0:
                        break
                    raw = handle.readline(min(MAX_LINE_BYTES, remaining))
                    result["scanned_bytes"] += len(raw)
                if result["cancelled"]:
                    break
                if oversized:
                    if number >= first:
                        result["oversized_lines"] += 1
                        result["truncated"] = True
                        result["malformed_lines"] += 1
                        if len(result["malformed_line_numbers"]) < 8:
                            result["malformed_line_numbers"].append(number)
                    if result["scanned_bytes"] >= MAX_TRACE_BYTES:
                        result["next_line"] = max(first, number if not raw.endswith(b"\n") else number + 1)
                        break
                    continue
                if number < first:
                    continue
                if not raw.strip():
                    continue
                try:
                    text = raw.decode("utf-8")
                    event = json.loads(text, parse_constant=_reject_constant)
                    if not isinstance(event, dict):
                        raise ValueError("trace row is not an object")
                except (UnicodeError, ValueError, RecursionError):
                    result["malformed_lines"] += 1
                    if len(result["malformed_line_numbers"]) < 8:
                        result["malformed_line_numbers"].append(number)
                    continue
                timestamp = event.get("t", event.get("time"))
                try:
                    valid_time = isinstance(timestamp, (int, float)) and not isinstance(timestamp, bool) and math.isfinite(float(timestamp))
                except OverflowError:
                    valid_time = False
                if not valid_time:
                    timestamp = None
                if center is not None and (timestamp is None or abs(timestamp - center) > window):
                    continue
                matched_text = text
                folded_text = text.casefold()
                if any(term not in folded_text for term in needles):
                    # JSON may escape a Unicode entity identifier. Match its
                    # decoded representation as well as the on-disk spelling.
                    matched_text = json.dumps(event, ensure_ascii=False)
                    folded_text = matched_text.casefold()
                    if any(term not in folded_text for term in needles):
                        continue
                result["matched_events"] += 1
                clipped = _clip(event)
                rendered = json.dumps(clipped, ensure_ascii=False)
                row = {"line": number, "t": timestamp, "event": clipped}
                if len(rendered) > 2800:
                    offset = matched_text.casefold().find(needles[0]) if needles else 0
                    start = max(0, offset - 500)
                    row["event"] = {}
                    for key in ("t", "time", "seq", "kind", "event", "node"):
                        if key in event:
                            value = _clip(event[key])
                            preview = json.dumps(value, ensure_ascii=False)
                            row["event"][key] = value if len(preview) <= 500 else preview[:500] + "…"
                    row["excerpt"] = matched_text[start:start + 2200]
                    row["event_truncated"] = True
                elif clipped != event:
                    row["event_truncated"] = True
                    if needle is not None and needle not in rendered.casefold():
                        offset = matched_text.casefold().find(needle)
                        row["excerpt"] = matched_text[max(0, offset - 350):offset + 850]
                if all_terms:
                    visible = json.dumps(row, ensure_ascii=False).casefold()
                    missing = [term for term in all_terms if term.casefold() not in visible]
                    if missing:
                        row["term_excerpts"] = []
                        for term in missing:
                            offset = matched_text.casefold().find(term.casefold())
                            row["term_excerpts"].append({
                                "term": term,
                                "text": matched_text[max(0, offset - 160):offset + max(340, len(term))],
                            })
                cost = len(json.dumps(row, ensure_ascii=False)) + 2
                if output_chars + cost > MAX_TRACE_OUTPUT - 1200:
                    result["truncated"] = True
                    result["next_line"] = number
                    break
                result["events"].append(row)
                output_chars += cost
                if len(result["events"]) >= limit:
                    result["truncated"] = result["truncated"] or result["scanned_bytes"] < file_size
                    if result["scanned_bytes"] < file_size:
                        result["next_line"] = number + 1
                    break
        if result["scanned_bytes"] < file_size:
            result["truncated"] = True
            if result["next_line"] is None:
                result["next_line"] = max(first, result["scanned_lines"] + 1)
        result["scan_limit_reached"] = result["scanned_bytes"] >= MAX_TRACE_BYTES and result["scanned_bytes"] < file_size

        def summarize():
            result["returned_events"] = len(result["events"])
            times = [row["t"] for row in result["events"] if row["t"] is not None]
            result["returned_time_range"] = [min(times), max(times)] if times else None
            if result["cancelled"]:
                result["hint"] = "Inspection cancelled; returned events are partial evidence."
            elif result["scan_limit_reached"]:
                result["hint"] = "64MiB scan limit reached, including skipped lines; evidence is incomplete beyond this scan region."
            elif not result["events"]:
                result["hint"] = "Matching rows exceeded the output bound; narrow filters or inspect next_line with read_file." if result["matched_events"] else (
                    "No matching records. query is one literal substring, not words in separate fields; "
                    "use all_terms=[\"entity\",\"event\"] for same-record AND. "
                    "Broaden terms/time filters or check the requested start_line."
                )
            elif result["next_line"] is not None:
                result["hint"] = "More evidence follows. Repeat the same filters with start_line=next_line, or narrow center_t/window_s."
            elif result["oversized_lines"]:
                result["hint"] = "Oversized rows were omitted; line numbers and returned events do not certify complete evidence."

        summarize()
        while result["events"] and len(json.dumps(result, ensure_ascii=False)) > MAX_TRACE_OUTPUT:
            removed = result["events"].pop()
            result["next_line"] = min(result["next_line"] or removed["line"], removed["line"])
            result["truncated"] = True
            summarize()
        return result
    except (OSError, OverflowError, TypeError, ValueError) as exc:
        result.update(ok=False, error=str(exc))
        return result
