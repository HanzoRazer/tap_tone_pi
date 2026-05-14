#!/usr/bin/env python3
"""
Close a measurement session: hash the JSONL ledger, write session_close.json, optionally zip.

Usage:
    python scripts/session_close.py --session-dir ./out/session_S_20251228_A --operator "Ross"
    python scripts/session_close.py --session-dir ./out/session_S_20251228_A --operator "Ross" --zip
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from zipfile import ZipFile, ZIP_DEFLATED

from jsonl_repair import (
    auto_repair_ledger_if_tag,
    get_last_malformed_line_preview,
    handle_scan_all_malformed,
    repair_ledger_truncate_last_bad_line,
    scan_jsonl_lines,
)


def utc_now_iso() -> str:
    import datetime as _dt

    return (
        _dt.datetime.now(_dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")


def strip_nulls(x: Any) -> Any:
    if isinstance(x, dict):
        out = {}
        for k, v in x.items():
            vv = strip_nulls(v)
            if vv is None:
                continue
            out[k] = vv
        return out
    if isinstance(x, list):
        return [strip_nulls(v) for v in x]
    return x


def parse_percent(s: str) -> float:
    """Parse a percent string like '100%' or '99.5%' into a float 0-100."""
    s = s.strip()
    if s.endswith("%"):
        s = s[:-1].strip()
    try:
        v = float(s)
    except json.JSONDecodeError:
        raise ValueError(f"Invalid percent value: {s!r} (expected like 100% or 99.5%)")
    if v < 0.0 or v > 100.0:
        raise ValueError(f"Percent out of range: {v} (expected 0..100)")
    return v


def zip_dir(
    src_dir: Path,
    dst_zip: Path,
    *,
    include_patterns: Optional[List[str]] = None,
    exclude_patterns: Optional[List[str]] = None,
) -> None:
    """
    Zips the session directory with relative paths.
    Patterns use simple suffix matching and substring checks (kept minimal + dependency-free).
    """
    dst_zip.parent.mkdir(parents=True, exist_ok=True)

    def included(rel: str) -> bool:
        if exclude_patterns:
            for p in exclude_patterns:
                if p in rel:
                    return False
        if not include_patterns:
            return True
        for p in include_patterns:
            if rel.endswith(p) or p in rel:
                return True
        return False

    with ZipFile(dst_zip, "w", compression=ZIP_DEFLATED) as zf:
        for p in sorted(src_dir.rglob("*")):
            if p.is_dir():
                continue
            rel = p.relative_to(src_dir).as_posix()
            if included(rel):
                zf.write(p, arcname=rel)


def _handle_repair_dry_run(args: argparse.Namespace, ledger_path: Path) -> int:
    """Dry-run preview (no modifications, early exit)."""
    preview = get_last_malformed_line_preview(
        ledger_path, context_n=max(0, args.show_bad_line_context)
    )

    print("Ledger repair dry-run preview")
    print(f"Ledger: {ledger_path}")
    print(f"Result: {preview.get('reason')}")
    if "last_bad_idx" in preview:
        print(
            f"last_bad_idx: {preview.get('last_bad_idx')}  last_nonblank_idx: {preview.get('last_nonblank_idx')}"
        )

    ctx = preview.get("context_prev") or []
    if ctx:
        print(f"---- context: {len(ctx)} preceding non-blank line(s) ----")
        for item in ctx:
            print(f"[{item['idx']}] {item['line']}")
        print("---- end context ----")

    if preview.get("bad_line") is not None:
        print("---- last malformed line (verbatim) ----")
        print(preview["bad_line"])
        print("---- end ----")

    if preview.get("reason") == "malformed_not_last_line":
        return 2
    return 0


def _do_ledger_repair(
    args: argparse.Namespace, ledger_path: Path
) -> Optional[Dict[str, Any]]:
    """Attempt ledger repair if requested."""
    if args.auto_repair_if:
        return auto_repair_ledger_if_tag(
            ledger_path,
            required_tag=args.auto_repair_if,
            backup_suffix=args.repair_backup_suffix,
            max_drop=args.auto_repair_max_drop,
            require_no_blank_lines=bool(args.auto_repair_if_only),
        )
    elif args.repair_ledger:
        return repair_ledger_truncate_last_bad_line(
            ledger_path, backup_suffix=args.repair_backup_suffix
        )
    return None


def _build_close_obj(
    session_id: str,
    session_dir: Path,
    operator: str,
    signer: str,
    ledger_path: Path,
    ledger_sha: str,
    ledger_lines: int,
    ledger_parseable: int,
    calibration_path: Path,
    calibration_sha: Optional[str],
    repair_info: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build the session_close object."""
    return {
        "schema": {
            "name": "session_close",
            "version": "1.0",
            "created_at_utc": utc_now_iso(),
        },
        "session": {
            "session_id": session_id,
            "session_dir_name": session_dir.name,
        },
        "signing": {
            "operator": operator,
            "signer": signer,
        },
        "artifacts": {
            "ledger": {
                "relpath": ledger_path.relative_to(session_dir).as_posix(),
                "sha256": ledger_sha,
                "lines": ledger_lines,
                "parseable_lines": ledger_parseable,
            },
            "calibration": {
                "present": calibration_path.exists(),
                "relpath": calibration_path.relative_to(session_dir).as_posix()
                if calibration_path.exists()
                else None,
                "sha256": calibration_sha,
            },
        },
        "ledger_repair": repair_info,
        "zip": None,
    }


def _handle_zip_archive(
    args: argparse.Namespace,
    session_dir: Path,
    session_id: str,
    close_path: Path,
    close_obj: Dict[str, Any],
) -> None:
    """Create zip archive and update close_obj."""
    if args.zip_out:
        zip_path = Path(args.zip_out).expanduser().resolve()
    else:
        zip_path = session_dir.parent / f"session_{session_id}.zip"

    excludes = list(args.zip_exclude or [])
    for p in [".venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".DS_Store"]:
        if p not in excludes:
            excludes.append(p)

    zip_dir(session_dir, zip_path, exclude_patterns=excludes)

    zip_sha = sha256_file(zip_path)
    close_obj["zip"] = {
        "created": True,
        "relpath": zip_path.resolve().as_posix(),
        "sha256": zip_sha,
        "bytes": zip_path.stat().st_size,
        "excluded_patterns": excludes,
    }
    tmp2 = close_path.with_suffix(".tmp")
    write_json(tmp2, strip_nulls(close_obj))
    tmp2.replace(close_path)

    print(f"Wrote: {close_path}")
    print(f"Zip:   {zip_path} ({zip_path.stat().st_size} bytes)")


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="session_close",
        description="Close a measurement session: hash the JSONL ledger, write session_close.json, optionally zip.",
    )
    ap.add_argument(
        "--session-dir", required=True, help="Path to session_<id>/ directory."
    )
    ap.add_argument(
        "--session-id",
        default=None,
        help="Session id (if omitted, derived from folder name).",
    )
    ap.add_argument(
        "--operator",
        default=os.getenv("USER") or os.getenv("USERNAME") or None,
        help="Signer/operator name.",
    )
    ap.add_argument(
        "--signer",
        default=None,
        help="Optional distinct signer name (defaults to operator).",
    )

    ap.add_argument(
        "--ledger",
        default="session_manifest.jsonl",
        help="Ledger filename within session dir.",
    )
    ap.add_argument(
        "--calibration",
        default="session_calibration.json",
        help="Calibration filename within session dir.",
    )
    ap.add_argument(
        "--close-out",
        default="session_close.json",
        help="Close file name to write within session dir.",
    )

    ap.add_argument(
        "--zip", action="store_true", help="If set, produce a session_<id>.zip archive."
    )
    ap.add_argument(
        "--zip-out",
        default=None,
        help="Optional output path for zip. Default: <session_dir>/../session_<id>.zip",
    )

    # Safety knobs
    ap.add_argument(
        "--zip-exclude",
        action="append",
        default=[],
        help="Exclude pattern substring (repeatable). Example: --zip-exclude .venv --zip-exclude __pycache__",
    )
    ap.add_argument(
        "--require-ledger-parseable",
        default=None,
        help="Fail unless at least this percent of non-blank JSONL lines parse as JSON. Examples: 100%%, 95%%, 99.5%%",
    )
    ap.add_argument(
        "--repair-ledger",
        action="store_true",
        help="Attempt to repair ledger JSONL by truncating the last malformed non-blank line. Creates a .bak backup. Explicit only.",
    )
    ap.add_argument(
        "--repair-backup-suffix",
        default=".bak",
        help="Backup suffix to use when repairing (default: .bak).",
    )
    ap.add_argument(
        "--auto-repair-if",
        type=str,
        default=None,
        help="Auto-attempt repair only if ALL malformed lines classify as this TAG and are safely truncatable at EOF (e.g., TRUNCATED_JSON).",
    )
    ap.add_argument(
        "--auto-repair-max-drop",
        type=int,
        default=1,
        help="Maximum number of trailing malformed non-blank lines allowed to drop during auto-repair (default 1).",
    )
    ap.add_argument(
        "--auto-repair-if-only",
        action="store_true",
        help="Stricter auto-repair: refuse to auto-repair if the ledger contains ANY blank/whitespace-only lines.",
    )
    ap.add_argument(
        "--repair-dry-run",
        action="store_true",
        help="Dry-run ledger repair: report what would be truncated (and show the last malformed line) without modifying files.",
    )
    ap.add_argument(
        "--show-bad-line-context",
        type=int,
        default=0,
        help="When reporting a malformed JSONL line, also print N preceding non-blank lines for context (default 0).",
    )
    ap.add_argument(
        "--scan-all-malformed",
        action="store_true",
        help="Scan the ledger and list every malformed non-blank JSONL line index (no file modifications).",
    )
    ap.add_argument(
        "--scan-all-malformed-max",
        type=int,
        default=50,
        help="Maximum malformed line indexes to print (default 50).",
    )
    ap.add_argument(
        "--scan-all-malformed-with-sample",
        type=int,
        default=0,
        help="When scanning malformed lines, also print the first K characters of each malformed line (default 0 = off).",
    )
    ap.add_argument(
        "--scan-all-malformed-classify",
        action="store_true",
        help="When scanning malformed lines with samples, print a rough classification tag per line (no deps).",
    )
    ap.add_argument(
        "--scan-all-malformed-suggest-action",
        action="store_true",
        help="When scanning malformed lines with classify, also print a one-line suggested action per tag.",
    )
    return ap


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    session_dir = Path(args.session_dir).expanduser().resolve()
    if not session_dir.exists() or not session_dir.is_dir():
        raise SystemExit(f"ERROR: session-dir not found or not a dir: {session_dir}")

    session_id = args.session_id or session_dir.name.replace("session_", "")
    operator = args.operator or "unknown"
    signer = args.signer or operator

    ledger_path = session_dir / args.ledger
    if not ledger_path.exists():
        raise SystemExit(f"ERROR: ledger not found: {ledger_path}")

    # Scan-all-malformed inspection mode
    if args.scan_all_malformed:
        return handle_scan_all_malformed(args, ledger_path)

    # Dry-run preview
    if args.repair_dry_run:
        return _handle_repair_dry_run(args, ledger_path)

    calibration_path = session_dir / args.calibration
    close_path = session_dir / args.close_out

    # Scan ledger (and optionally repair)
    repair_info = (
        _do_ledger_repair(args, ledger_path) if not args.repair_dry_run else None
    )
    _, ledger_lines, ledger_parseable, _ = scan_jsonl_lines(ledger_path)

    # Hash after potential repair
    ledger_sha = sha256_file(ledger_path)

    # Enforce ledger integrity threshold if requested
    if args.require_ledger_parseable is not None:
        required_pct = parse_percent(args.require_ledger_parseable)

        # If there are zero non-blank lines, treat as 0% parseable (explicit)
        actual_pct = (
            (ledger_parseable / ledger_lines * 100.0) if ledger_lines > 0 else 0.0
        )

        if actual_pct + 1e-9 < required_pct:
            raise SystemExit(
                f"ERROR: ledger parseability check failed: "
                f"{ledger_parseable}/{ledger_lines} parseable lines = {actual_pct:.3f}% "
                f"(required >= {required_pct:.3f}%). "
                f"Ledger: {ledger_path}"
            )

    calibration_sha = (
        sha256_file(calibration_path) if calibration_path.exists() else None
    )

    close_obj = _build_close_obj(
        session_id,
        session_dir,
        operator,
        signer,
        ledger_path,
        ledger_sha,
        ledger_lines,
        ledger_parseable,
        calibration_path,
        calibration_sha,
        repair_info,
    )

    # Write session_close.json (atomic-ish)
    tmp = close_path.with_suffix(".tmp")
    write_json(tmp, strip_nulls(close_obj))
    tmp.replace(close_path)

    # Optional zip archive
    if args.zip:
        _handle_zip_archive(args, session_dir, session_id, close_path, close_obj)
        return 0

    print(f"Wrote: {close_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
