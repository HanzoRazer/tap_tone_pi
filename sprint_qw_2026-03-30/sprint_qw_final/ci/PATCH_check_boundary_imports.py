"""
PATCH: check_boundary_imports.py — add analyzer_isolation preset.

Apply this as a git diff against ci/check_boundary_imports.py.
The patch adds a new preset that prevents the analyzer/ desktop app
from importing capture-side modules (tap_tone_pi.capture,
tap_tone_pi.calibration, tap_tone_pi.phase2).

The analyzer reads viewer_pack bundles from disk.
It must never import live-capture or calibration modules.

WHY: If analyzer/ imports tap_tone_pi.capture, deployment of the
desktop app would require sounddevice, PyAudio, and Pi-specific
hardware drivers installed on the PC. The correct interface
between capture and analysis is viewer_pack_v1.json on disk.

---

ADD the following function to ci/check_boundary_imports.py
AFTER the existing _analyzer_spec() function:
"""

# ============================================================
# NEW FUNCTION — insert after _analyzer_spec() in
# ci/check_boundary_imports.py
# ============================================================


def _analyzer_isolation_spec():
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
    from ci.boundary_spec import BoundarySpec  # noqa: F401
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


# ============================================================
# ADD "analyzer_isolation" to _select_spec() match block:
#
#     if preset == "analyzer_isolation":
#         return _analyzer_isolation_spec()
#
# AFTER the existing "toolbox" case.
# ============================================================


# ============================================================
# ADD to boundary_guard.yml:
#
#   - name: Enforce analyzer desktop isolation (ADR-0009)
#     run: |
#       python ci/check_boundary_imports.py \
#         --preset analyzer_isolation \
#         --root analyzer
#
# ============================================================


# ============================================================
# STANDALONE VERIFICATION — run this script directly to test
# ============================================================

if __name__ == "__main__":
    import sys
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[1]
    analyzer_dir = repo_root / "analyzer"

    if not analyzer_dir.exists():
        print(f"[analyzer_isolation] analyzer/ directory not found at {analyzer_dir}")
        sys.exit(0)

    print(f"[analyzer_isolation] Scanning {analyzer_dir} ...")

    forbidden = [
        "tap_tone_pi.capture",
        "tap_tone_pi.calibration",
        "tap_tone_pi.phase2",
        "tap_tone_pi.cli",
        "tap_tone_pi.server",
    ]

    import ast
    violations = []
    for py_file in sorted(analyzer_dir.rglob("*.py")):
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                else:
                    names = [node.module] if node.module else []
                for name in names:
                    for forb in forbidden:
                        if name == forb or name.startswith(forb + "."):
                            violations.append(
                                f"  {py_file.relative_to(repo_root)}: "
                                f"imports '{name}'"
                            )

    if violations:
        print("[analyzer_isolation] VIOLATIONS FOUND:")
        for v in violations:
            print(v)
        print(
            "\nAnalyzer must not import capture-side modules. "
            "Use viewer_pack_v1.json as the interface. "
            "See docs/ADR-0009-advisory-boundary.md"
        )
        sys.exit(1)
    else:
        print("[analyzer_isolation] PASS — no capture-side imports in analyzer/")
        sys.exit(0)
