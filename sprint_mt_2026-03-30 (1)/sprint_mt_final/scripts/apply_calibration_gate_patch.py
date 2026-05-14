"""
PATCH: tap_tone_pi/cli/phase2_cmd.py
Adds calibration gate enforcement to _run_new().

Apply with:
    python scripts/apply_calibration_gate_patch.py

Or manually:

1. Add import at top of phase2_cmd.py (after existing calibration imports):

    from tap_tone_pi.calibration.gate import (
        enforce_calibration_gate,
        print_gate_result,
    )

2. In _run_new(), BEFORE the session directory creation, insert:

    # === CALIBRATION GATE ===
    device_index = getattr(args, "device", None) or 0
    force_uncal = getattr(args, "force_uncalibrated", False)
    force_stale = getattr(args, "force", False) or force_uncal

    gate = enforce_calibration_gate(
        device_index,
        allow_stale=force_stale,
        allow_uncalibrated=force_uncal,
    )
    print_gate_result(gate)
    if not gate.allowed:
        return 1
    # === END CALIBRATION GATE ===

3. In _build_parser() / add_phase2_subparser(), add flags to the 'run' subcommand:

    p_run.add_argument(
        "--force",
        action="store_true",
        help="Proceed with stale calibration (warns but allows)",
    )
    p_run.add_argument(
        "--force-uncalibrated",
        action="store_true",
        dest="force_uncalibrated",
        help="Proceed without calibration (development/synthetic only)",
    )
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def patch_phase2_cmd() -> bool:
    target = REPO_ROOT / "tap_tone_pi" / "cli" / "phase2_cmd.py"
    if not target.exists():
        print(f"[SKIP] {target} not found")
        return False

    content = target.read_text(encoding="utf-8")

    # --- 1. Add import ---
    import_marker = "from tap_tone_pi.calibration.session_context import ("
    gate_import = (
        "from tap_tone_pi.calibration.gate import (\n"
        "    enforce_calibration_gate,\n"
        "    print_gate_result,\n"
        ")\n"
    )
    if "enforce_calibration_gate" in content:
        print("[OK] calibration gate import already present")
    elif import_marker in content:
        content = content.replace(import_marker, gate_import + import_marker)
        print("[PATCH] added calibration gate import")
    else:
        print("[WARN] could not find import anchor — add manually")

    # --- 2. Add gate check before session directory creation ---
    gate_block = '''\
    # === CALIBRATION GATE ===
    device_index = getattr(args, "device", None) or 0
    force_uncal = getattr(args, "force_uncalibrated", False)
    force_stale = getattr(args, "force", False) or force_uncal

    gate = enforce_calibration_gate(
        device_index,
        allow_stale=force_stale,
        allow_uncalibrated=force_uncal,
    )
    print_gate_result(gate)
    if not gate.allowed:
        return 1
    # === END CALIBRATION GATE ===

'''
    # Inject before session directory creation
    session_create_anchor = "    # Create session directory"
    if "CALIBRATION GATE" in content:
        print("[OK] calibration gate block already present")
    elif session_create_anchor in content:
        content = content.replace(
            session_create_anchor,
            gate_block + session_create_anchor,
        )
        print("[PATCH] added calibration gate block")
    else:
        print("[WARN] could not find session-create anchor — add manually")

    # --- 3. Add CLI flags ---
    # Find where --no-progress is added to get the anchor
    noprogress_anchor = '"--no-progress",'
    force_flags = '''\
    p_run.add_argument(
        "--force",
        action="store_true",
        help="Proceed with stale calibration (warns but allows)",
    )
    p_run.add_argument(
        "--force-uncalibrated",
        action="store_true",
        dest="force_uncalibrated",
        help="Proceed without calibration (development/synthetic only)",
    )
'''
    if "--force-uncalibrated" in content:
        print("[OK] force flags already present")
    else:
        # Find a good anchor — look for set_defaults on p_run
        run_defaults_anchor = "p_run.set_defaults"
        if run_defaults_anchor in content:
            content = content.replace(
                run_defaults_anchor,
                force_flags + "    " + run_defaults_anchor,
                1,  # only first occurrence
            )
            print("[PATCH] added --force/--force-uncalibrated flags")
        else:
            print("[WARN] could not find p_run.set_defaults anchor — add flags manually")

    target.write_text(content, encoding="utf-8")
    print(f"[DONE] patched {target}")
    return True


if __name__ == "__main__":
    ok = patch_phase2_cmd()
    sys.exit(0 if ok else 1)
