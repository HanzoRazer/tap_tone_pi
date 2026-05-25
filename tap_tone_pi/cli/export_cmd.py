# INSTRUMENT CLASS: MEASUREMENT
"""
CLI export-pack command — extracted from cli/main.py (Phase 4 maintainability restructuring).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def cmd_export_pack(args: argparse.Namespace, project_root: Path) -> int:
    """Export a session as viewer_pack_v1 ZIP."""
    import subprocess

    from tap_tone_pi.cli.validators import confirm_overwrite

    # Consistent with other CLI commands - resolve against PROJECT_ROOT
    session_path = Path(args.session)
    if not session_path.is_absolute():
        session_path = (project_root / session_path).resolve()

    # Output path: allow relative-to-CWD for convenience
    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = Path.cwd() / out_path

    if not session_path.exists():
        print(f"Session not found: {session_path}", file=sys.stderr)
        return 1

    # Confirm overwrite if output exists
    confirm_overwrite(out_path, force=getattr(args, "force", False))

    # Guardrail: exporter expects Phase 2 session structure
    grid_json = session_path / "grid.json"
    if not grid_json.exists():
        print(
            "export-pack expects a Phase 2 session directory.\n"
            f"Missing grid.json in: {session_path}",
            file=sys.stderr,
        )
        return 1

    export_script = project_root / "scripts" / "export" / "viewer_pack_v1_export.py"
    if not export_script.exists():
        print(f"Exporter script not found: {export_script}", file=sys.stderr)
        return 1

    argv = [
        sys.executable,
        str(export_script),
        "--session",
        str(session_path),
        "--out",
        str(out_path),
    ]

    # Run export
    rc = subprocess.call(argv, cwd=str(project_root))
    if rc != 0:
        return rc

    # Optional ZIP validation
    if args.validate:
        validate_script = project_root / "scripts" / "viewer_pack_validate.py"
        if not validate_script.exists():
            print(f"ZIP validator script not found: {validate_script}", file=sys.stderr)
            return 1

        v_argv = [
            sys.executable,
            str(validate_script),
            str(out_path),
        ]

        # Passthrough flags
        if args.strict:
            v_argv.append("--strict")
        if args.json:
            v_argv.append("--json")

        v_rc = subprocess.call(v_argv, cwd=str(project_root))
        if v_rc != 0:
            return v_rc

    print(f"Wrote: {out_path}")
    return 0
