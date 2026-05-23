from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import List, Optional

# Handle import whether run as script or module
try:
    from ci.boundary_spec import BoundarySpec, format_banner, format_violations
except ModuleNotFoundError:
    from boundary_spec import BoundarySpec, format_banner, format_violations


README_LINK_DEFAULT = "docs/BOUNDARY_RULES.md#boundary-rules"


def _repo_root() -> Path:
    # tap_tone_pi/ci/check_boundary_imports.py -> tap_tone_pi/ci -> tap_tone_pi
    return Path(__file__).resolve().parents[1]


def _analyzer_spec() -> BoundarySpec:
    """
    Analyzer repo boundary: the Analyzer must not import ToolBox namespaces.

    Analyzer importable roots:
      tap_tone, modes, schemas
    ToolBox roots to forbid:
      app (and optionally services, packages, etc.)
    """
    return BoundarySpec(
        name="analyzer",
        allowed_roots=["tap_tone", "modes", "schemas", "tests"],
        forbidden_import_prefixes=[
            # ToolBox / backend namespaces (prevent accidental coupling)
            "app",
            "services",
            "packages",
        ],
    )


def _toolbox_spec() -> BoundarySpec:
    """
    Included for convenience if you ever run this guard in ToolBox using this file,
    but in practice ToolBox has its own guard.
    """
    return BoundarySpec(
        name="toolbox",
        allowed_roots=["app", "tests"],
        forbidden_import_prefixes=["tap_tone", "modes", "schemas"],
    )


def _analyzer_isolation_spec() -> BoundarySpec:
    """
    Analyzer desktop app isolation spec.

    The analyzer/ package MUST NOT import from:
      - tap_tone_pi.capture   (live audio capture, Pi hardware)
      - tap_tone_pi.calibration  (calibration session context)
      - tap_tone_pi.phase2    (35-point grid capture workflow)
      - tap_tone_pi.cli       (command-line interface)
      - tap_tone_pi.server    (FastAPI server)

    The correct interface is viewer_pack_v1.json / bundle files on disk.
    The analyzer reads those. It does not invoke capture.

    tap_tone_pi.core, tap_tone_pi.wolf, and tap_tone_pi.agentic
    are deliberately NOT forbidden — the analyzer may use DSP
    utilities from core and advisory modules from wolf.
    """
    return BoundarySpec(
        name="analyzer_isolation",
        allowed_roots=["analyzer", "tests"],
        forbidden_import_prefixes=[
            "tap_tone_pi.capture",
            "tap_tone_pi.calibration",
            "tap_tone_pi.phase2",
            "tap_tone_pi.cli",
            "tap_tone_pi.server",
            # Also block legacy namespace
            "tap_tone.capture",
            "tap_tone.calibration",
        ],
    )


def _select_spec(preset: str) -> BoundarySpec:
    preset = (preset or "").strip().lower()
    if preset == "analyzer":
        return _analyzer_spec()
    if preset == "toolbox":
        return _toolbox_spec()
    if preset == "analyzer_isolation":
        return _analyzer_isolation_spec()
    raise ValueError(f"Unknown preset: {preset!r} (expected: analyzer|toolbox|analyzer_isolation)")


def _parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="check_boundary_imports",
        description="Fail CI if forbidden cross-repo imports are detected.",
    )
    p.add_argument(
        "--preset",
        default=os.getenv("BOUNDARY_PRESET", "analyzer"),
        help="Boundary preset to apply. Default: analyzer (env: BOUNDARY_PRESET).",
    )
    p.add_argument(
        "--root",
        default=os.getenv("BOUNDARY_SCAN_ROOT", str(_repo_root())),
        help="Path to scan. Default: repo root (env: BOUNDARY_SCAN_ROOT).",
    )
    p.add_argument(
        "--readme-link",
        default=os.getenv("BOUNDARY_README_LINK", README_LINK_DEFAULT),
        help="Path/anchor to boundary rules for CI hint (env: BOUNDARY_README_LINK).",
    )
    p.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Directory name exclusions (repeatable). Example: --exclude .venv --exclude node_modules",
    )
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = _parse_args(argv or sys.argv[1:])

    try:
        spec = _select_spec(args.preset)
    except Exception as e:
        print(f"[boundary] ERROR: {e}", file=sys.stderr)
        return 2

    scan_root = Path(args.root).resolve()
    excludes = set(args.exclude or [])

    violations = spec.scan_path(scan_root, excludes=excludes)
    if violations:
        print(format_banner(spec, scan_root))
        print(format_violations(violations))
        print(
            f"\n[boundary] Fix: remove forbidden imports or refactor boundaries. Rules: {args.readme_link}",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
