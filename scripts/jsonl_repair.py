"""
JSONL ledger repair and malformed-line classification utilities.

Extracted from scripts/session_close.py (Phase 4 maintainability restructuring).
Provides dependency-free heuristics for diagnosing and repairing corrupted JSONL ledgers.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def read_jsonl_count(path: Path) -> Tuple[int, int]:
    """
    Returns (line_count, parseable_count). JSONL may contain blank lines or partial last line.
    We'll count lines, and also count parseable JSON objects.
    """
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    line_count = 0
    parseable = 0
    for ln in lines:
        if not ln.strip():
            continue
        line_count += 1
        try:
            json.loads(ln)
            parseable += 1
        except json.JSONDecodeError:
            # Ignore malformed line; a partial last line can happen after crashes.
            pass
    return line_count, parseable


def scan_jsonl_lines(path: Path) -> Tuple[List[str], int, int, Optional[int]]:
    """
    Returns:
      lines: original lines (including blank lines)
      nonblank_count: number of non-blank lines
      parseable_count: number of non-blank lines that parse as JSON
      last_bad_idx: index into `lines` of the last non-blank line that failed JSON parse, else None
    """
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    nonblank = 0
    ok = 0
    last_bad_idx: Optional[int] = None

    for i, ln in enumerate(lines):
        if not ln.strip():
            continue
        nonblank += 1
        try:
            json.loads(ln)
            ok += 1
        except json.JSONDecodeError:
            last_bad_idx = i

    return lines, nonblank, ok, last_bad_idx


def get_jsonl_context(
    lines: list[str], bad_idx: int, n_prev: int
) -> list[dict[str, Any]]:
    """
    Returns up to n_prev preceding NON-BLANK lines before bad_idx, with their original indexes.
    Ordered from oldest->newest.
    """
    out: list[dict[str, Any]] = []
    if n_prev <= 0:
        return out

    i = bad_idx - 1
    while i >= 0 and len(out) < n_prev:
        if lines[i].strip():
            out.append({"idx": i, "line": lines[i]})
        i -= 1

    out.reverse()
    return out


def classify_malformed_jsonl_line(line: str) -> str:
    """
    Rough, dependency-free classification for a malformed JSONL line.
    Tags are heuristic — meant to quickly diagnose common corruption modes.
    """
    s = line

    # Encoding/BOM oddities
    if s.startswith("\ufeff"):
        return "BOM/ENCODING"

    # Strip leading/trailing whitespace for classification
    t = s.strip()
    if not t:
        return "BLANK/WHITESPACE"

    # High proportion of non-printable control chars often indicates binary / encoding damage
    nonprint = sum(1 for ch in t if (ord(ch) < 32 and ch not in "\t\r\n"))
    if len(t) > 0 and (nonprint / len(t)) > 0.10:
        return "BINARY/ENCODING_NOISE"

    # Obvious "should be JSON but cut off" patterns
    if t.startswith("{") or t.startswith("["):
        # If it starts like JSON but doesn't end like JSON, likely truncated
        if not (t.endswith("}") or t.endswith("]")):
            return "TRUNCATED_JSON"
        # Ends properly but still doesn't parse: could be quoting/escape damage
        return "JSON_SYNTAX_ERROR"

    # JSONL should usually start with '{' (object per line); if not, probably garbage
    # But detect common cases:
    if t[0] in "\"'":
        return "STRING_LINE_NOT_OBJECT"
    if t[0].isdigit() or t.startswith("-"):
        return "NUMBER_LINE_NOT_OBJECT"
    if t.lower().startswith(("true", "false", "null")):
        return "LITERAL_LINE_NOT_OBJECT"

    # If it contains lots of braces but doesn't start with one, could be prefixed junk
    if "{" in t or "[" in t:
        return "PREFIXED_OR_GARBLED_JSON"

    return "NON_JSON_GARBAGE"


def suggest_action_for_tag(tag: str) -> str:
    """
    Returns a one-line suggested action for a given malformed line classification tag.
    """
    tag = (tag or "").strip().upper()

    suggestions = {
        "TRUNCATED_JSON": "Likely partial write/crash at EOF → try --repair-ledger (safe only if malformed line is last non-blank).",
        "JSON_SYNTAX_ERROR": "JSON-looking but invalid → inspect the line; compare with prior context (--show-bad-line-context) and consider regenerating that entry.",
        "BOM/ENCODING": "UTF-8 BOM/encoding anomaly → rewrite file as UTF-8 without BOM; avoid mixed editors; re-run scan.",
        "BINARY/ENCODING_NOISE": "Looks like binary/control chars → file corruption or wrong encoding; restore from backup (.bak) if available.",
        "PREFIXED_OR_GARBLED_JSON": "Line may have junk prefix/suffix → inspect surrounding context; search for log prefixes; consider stripping known prefixes at write-time.",
        "NON_JSON_GARBAGE": "Not JSON-like → inspect context lines; determine source (log spam, accidental append); fix generator before repair.",
        "STRING_LINE_NOT_OBJECT": "Ledger line is a string literal → verify writer; JSONL entries should be objects; inspect generator and context.",
        "NUMBER_LINE_NOT_OBJECT": "Ledger line is numeric → verify writer; JSONL entries should be objects; inspect generator and context.",
        "LITERAL_LINE_NOT_OBJECT": "Ledger line is true/false/null → verify writer; JSONL entries should be objects; inspect generator and context.",
        "BLANK/WHITESPACE": "Blank line is usually harmless → ignore unless your tooling forbids it; keep parseability threshold based on non-blank lines.",
    }

    return suggestions.get(
        tag,
        "Inspect the malformed line and nearby context; decide whether repair is safe or restore from backup.",
    )


def scan_all_malformed_jsonl_indexes(
    path: Path, sample_k: int = 0, keep_full: bool = False
) -> Dict[str, Any]:
    """
    Returns summary + list of malformed line indexes (0-based file line index).
    If sample_k > 0, includes a sample prefix for each malformed line.
    If keep_full is True, includes the full line text for classification.
    """
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    nonblank = 0
    ok = 0
    bad_indexes: list[int] = []
    bad_samples: list[dict[str, Any]] = []

    k = max(0, int(sample_k))
    need_full = bool(keep_full)

    for i, ln in enumerate(lines):
        if not ln.strip():
            continue
        nonblank += 1
        try:
            json.loads(ln)
            ok += 1
        except json.JSONDecodeError:
            bad_indexes.append(i)
            if k > 0 or need_full:
                s_prefix = (ln[:k] + ("…" if len(ln) > k else "")) if k > 0 else None
                rec: dict[str, Any] = {"idx": i}
                if s_prefix is not None:
                    rec["sample"] = s_prefix
                if need_full:
                    rec["full_line"] = ln
                bad_samples.append(rec)

    return {
        "ledger_path": path.as_posix(),
        "total_lines_in_file": len(lines),
        "nonblank_lines": nonblank,
        "parseable_lines": ok,
        "malformed_count": len(bad_indexes),
        "malformed_indexes": bad_indexes,
        "malformed_samples": bad_samples if (k > 0 or need_full) else None,
        "sample_k": k if k > 0 else None,
    }


def repair_ledger_truncate_last_bad_line(
    path: Path, backup_suffix: str = ".bak"
) -> Dict[str, Any]:
    """
    Repairs by truncating the last malformed non-blank line if (and only if) it is the LAST non-blank line.
    Creates a backup first. Returns a dict describing what happened.
    """
    lines, nonblank, ok, last_bad_idx = scan_jsonl_lines(path)

    if nonblank == 0:
        return {"repaired": False, "reason": "ledger_empty"}

    if last_bad_idx is None:
        return {"repaired": False, "reason": "no_malformed_lines"}

    # Find last non-blank line index
    last_nonblank_idx = None
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip():
            last_nonblank_idx = i
            break

    if last_nonblank_idx is None:
        return {"repaired": False, "reason": "ledger_all_blank"}

    # Only safe to truncate if the malformed line is the last non-blank line (classic partial write).
    if last_bad_idx != last_nonblank_idx:
        return {
            "repaired": False,
            "reason": "malformed_not_last_line",
            "last_bad_idx": last_bad_idx,
            "last_nonblank_idx": last_nonblank_idx,
        }

    # Backup
    backup_path = (
        path.with_suffix(path.suffix + backup_suffix)
        if path.suffix
        else path.with_name(path.name + backup_suffix)
    )
    backup_path.write_bytes(path.read_bytes())

    # Truncate: remove that last malformed line, preserve earlier lines exactly.
    repaired_lines = lines[:last_bad_idx]  # drop the bad line
    # Preserve trailing newline in the output for cleanliness
    repaired_text = (
        "\n".join(repaired_lines).rstrip("\n") + "\n" if repaired_lines else ""
    )
    path.write_text(repaired_text, encoding="utf-8")

    # Re-scan post repair
    _, nonblank2, ok2, last_bad2 = scan_jsonl_lines(path)

    return {
        "repaired": True,
        "reason": "truncated_last_malformed_line",
        "backup_path": backup_path.as_posix(),
        "dropped_line_index": last_bad_idx,
        "before": {"nonblank_lines": nonblank, "parseable_lines": ok},
        "after": {
            "nonblank_lines": nonblank2,
            "parseable_lines": ok2,
            "last_bad_idx": last_bad2,
        },
    }


def ledger_has_blank_lines(path: Path) -> bool:
    """Returns True if the ledger contains any blank or whitespace-only lines."""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return any((ln == "" or ln.strip() == "") for ln in lines)


def _gather_malformed_lines(
    lines: list[str], nonblank_indexes: list[int]
) -> list[dict]:
    """Gather malformed lines with their indexes and tags."""
    malformed: list[dict[str, Any]] = []
    for i in nonblank_indexes:
        ln = lines[i]
        try:
            json.loads(ln)
        except json.JSONDecodeError:
            tag = classify_malformed_jsonl_line(ln)
            malformed.append({"idx": i, "tag": tag, "line": ln})
    return malformed


def _identify_trailing_malformed(
    nonblank_indexes: list[int],
    malformed: list[dict],
) -> list[int]:
    """Identify trailing malformed line indexes."""
    trailing_malformed_idxs: list[int] = []
    for idx in reversed(nonblank_indexes):
        if any(m["idx"] == idx for m in malformed):
            trailing_malformed_idxs.append(idx)
        else:
            break
    return list(reversed(trailing_malformed_idxs))


def _check_repair_preconditions(
    malformed: list[dict],
    trailing_malformed_idxs: list[int],
    req: str,
    max_drop: int,
) -> Optional[Dict[str, Any]]:
    """Check if repair is allowed. Returns error dict or None if OK."""
    bad_tags = sorted({m["tag"] for m in malformed if m["tag"] != req})
    if bad_tags:
        return {
            "repaired": False,
            "reason": "tags_not_all_match",
            "required_tag": req,
            "other_tags": bad_tags,
            "malformed_count": len(malformed),
        }

    if not trailing_malformed_idxs:
        return {"repaired": False, "reason": "no_trailing_malformed_lines"}

    trailing_set = set(trailing_malformed_idxs)
    outside = [m["idx"] for m in malformed if m["idx"] not in trailing_set]
    if outside:
        return {
            "repaired": False,
            "reason": "malformed_not_confined_to_eof",
            "outside_malformed_indexes": sorted(outside),
            "trailing_malformed_indexes": trailing_malformed_idxs,
        }

    if len(trailing_malformed_idxs) > max_drop:
        return {
            "repaired": False,
            "reason": "too_many_trailing_malformed_lines",
            "trailing_malformed_count": len(trailing_malformed_idxs),
            "max_drop": max_drop,
            "trailing_malformed_indexes": trailing_malformed_idxs,
        }

    return None


def _perform_ledger_repair(
    ledger_path: Path,
    lines: list[str],
    trailing_malformed_idxs: list[int],
    backup_suffix: str,
    req: str,
) -> Dict[str, Any]:
    """Perform the actual repair by truncating trailing malformed lines."""
    backup_path = (
        ledger_path.with_suffix(ledger_path.suffix + backup_suffix)
        if ledger_path.suffix
        else ledger_path.with_name(ledger_path.name + backup_suffix)
    )
    backup_path.write_bytes(ledger_path.read_bytes())

    drop_set = set(trailing_malformed_idxs)
    kept_lines = [ln for i, ln in enumerate(lines) if i not in drop_set]

    repaired_text = "\n".join(kept_lines).rstrip("\n") + "\n"
    ledger_path.write_text(repaired_text, encoding="utf-8")

    post = scan_all_malformed_jsonl_indexes(ledger_path, sample_k=0, keep_full=False)

    return {
        "repaired": True,
        "reason": "auto_repair_truncated_trailing_malformed",
        "required_tag": req,
        "backup_path": backup_path.as_posix(),
        "dropped_line_indexes": trailing_malformed_idxs,
        "after": {
            "malformed_count": post["malformed_count"],
            "nonblank_lines": post["nonblank_lines"],
            "parseable_lines": post["parseable_lines"],
        },
    }


def auto_repair_ledger_if_tag(
    ledger_path: Path,
    *,
    required_tag: str,
    backup_suffix: str,
    max_drop: int = 1,
    require_no_blank_lines: bool = False,
) -> Dict[str, Any]:
    """
    Auto-repair strategy:
      - Scan all malformed lines and classify them.
      - Only proceed if conditions allow repair.
      - Repair action: truncate trailing malformed non-blank lines.
      - Always writes backup first.
    Returns a dict describing what happened.
    """
    req = (required_tag or "").strip().upper()
    if not req:
        return {"repaired": False, "reason": "no_required_tag"}

    if require_no_blank_lines and ledger_has_blank_lines(ledger_path):
        return {
            "repaired": False,
            "reason": "blank_lines_present_refusing_auto_repair",
            "required_tag": req,
        }

    lines = ledger_path.read_text(encoding="utf-8", errors="replace").splitlines()
    nonblank_indexes: list[int] = [i for i, ln in enumerate(lines) if ln.strip()]

    if not nonblank_indexes:
        return {"repaired": False, "reason": "ledger_empty_or_all_blank"}

    malformed = _gather_malformed_lines(lines, nonblank_indexes)
    if not malformed:
        return {"repaired": False, "reason": "no_malformed_lines"}

    trailing_malformed_idxs = _identify_trailing_malformed(nonblank_indexes, malformed)
    max_drop = max(1, int(max_drop))

    err = _check_repair_preconditions(malformed, trailing_malformed_idxs, req, max_drop)
    if err:
        return err

    return _perform_ledger_repair(
        ledger_path,
        lines,
        trailing_malformed_idxs,
        backup_suffix,
        req,
    )


def get_last_malformed_line_preview(path: Path, context_n: int = 0) -> Dict[str, Any]:
    """
    Returns a preview dict:
      - can_truncate: bool (only if malformed line is the last non-blank line)
      - last_bad_idx, last_nonblank_idx
      - bad_line (string) if present
      - context_prev: list of preceding non-blank lines (if context_n > 0)
      - reason if not safe
    """
    lines, nonblank, ok, last_bad_idx = scan_jsonl_lines(path)

    if nonblank == 0:
        return {"can_truncate": False, "reason": "ledger_empty"}

    if last_bad_idx is None:
        return {"can_truncate": False, "reason": "no_malformed_lines"}

    last_nonblank_idx = None
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip():
            last_nonblank_idx = i
            break

    if last_nonblank_idx is None:
        return {"can_truncate": False, "reason": "ledger_all_blank"}

    if last_bad_idx != last_nonblank_idx:
        ctx = get_jsonl_context(lines, last_bad_idx, context_n)
        return {
            "can_truncate": False,
            "reason": "malformed_not_last_line",
            "last_bad_idx": last_bad_idx,
            "last_nonblank_idx": last_nonblank_idx,
            "bad_line": lines[last_bad_idx],
            "context_prev": ctx,
        }

    ctx = get_jsonl_context(lines, last_bad_idx, context_n)
    return {
        "can_truncate": True,
        "reason": "truncatable_last_malformed_line",
        "last_bad_idx": last_bad_idx,
        "last_nonblank_idx": last_nonblank_idx,
        "bad_line": lines[last_bad_idx],
        "context_prev": ctx,
    }


def handle_scan_all_malformed(args: argparse.Namespace, ledger_path: Path) -> int:
    """Scan-all-malformed inspection mode (no modifications, no close file written)."""
    # --suggest-action implies --classify behavior
    want_suggest = bool(args.scan_all_malformed_suggest_action)
    want_classify = bool(args.scan_all_malformed_classify) or want_suggest

    summary = scan_all_malformed_jsonl_indexes(
        ledger_path,
        sample_k=int(args.scan_all_malformed_with_sample or 0),
        keep_full=want_classify,
    )

    malformed = summary["malformed_indexes"]
    max_n = max(0, int(args.scan_all_malformed_max))
    samples = summary.get("malformed_samples") or []
    k = summary.get("sample_k") or 0

    print("Ledger malformed scan (JSONL)")
    print(f"Ledger: {ledger_path}")
    print(
        f"Non-blank lines: {summary['nonblank_lines']} | "
        f"Parseable: {summary['parseable_lines']} | "
        f"Malformed: {summary['malformed_count']}"
    )

    if not malformed:
        print("No malformed JSONL lines detected.")
        return 0

    if k > 0 or want_classify:
        if k > 0:
            print(
                f"Malformed lines (0-based), showing up to {max_n} with first {k} chars:"
            )
        else:
            print(f"Malformed lines (0-based), showing up to {max_n}:")
        shown = samples[:max_n]
        for item in shown:
            tag = ""
            suggest = ""
            if want_classify:
                full = item.get("full_line") or ""
                tag_val = classify_malformed_jsonl_line(full)
                tag = f"[{tag_val}] "
                if want_suggest:
                    suggest = suggest_action_for_tag(tag_val)
            sample_txt = item.get("sample")
            if sample_txt is None:
                full = item.get("full_line") or ""
                sample_txt = full[:120] + ("…" if len(full) > 120 else "")
            print(f"  - {item['idx']}: {tag}{sample_txt}")
            if suggest:
                print(f"      ↳ {suggest}")
        if len(malformed) > max_n:
            print(f"  ... (+{len(malformed) - max_n} more)")
    else:
        print(f"Malformed line indexes (0-based), showing up to {max_n}:")
        for idx in malformed[:max_n]:
            print(f"  - {idx}")
        if len(malformed) > max_n:
            print(f"  ... (+{len(malformed) - max_n} more)")
    return 2  # Exit code 2 indicates corruption exists
