#!/usr/bin/env python3
"""
apply_instrument_class_banners.py

Adds '# INSTRUMENT CLASS:' declarations to the four modules
flagged in ADR-0009 and renames CoherenceAnalysis.quality_grade
→ coherence_band.

Usage:
    python scripts/apply_instrument_class_banners.py [--dry-run] [--repo-root PATH]

Changes applied:
  1. tap_tone_pi/wolf/wolf_advisor.py     → DECISION SUPPORT banner
  2. tap_tone_pi/wolf/wolf_beat.py        → MEASUREMENT banner
  3. analyzer/analysis/wood_properties.py → DECISION SUPPORT banner
  4. tap_tone_pi/transfer_function/estimators.py
       → MEASUREMENT banner
       → quality_grade field/var renamed to coherence_band
       → string values "excellent"/"good"/"acceptable"/"poor"
         replaced with "high"/"medium-high"/"medium"/"low"
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Banner text
# ---------------------------------------------------------------------------

MEASUREMENT_BANNER = (
    "# INSTRUMENT CLASS: MEASUREMENT\n"
    "# Outputs from this module are calibrated measurement results.\n"
    "# They may appear in viewer_pack_v1 and are subject to provenance tracking.\n"
    "# See docs/ADR-0009-advisory-boundary.md\n"
)

DECISION_SUPPORT_BANNER = (
    "# INSTRUMENT CLASS: DECISION SUPPORT\n"
    "# Outputs from this module are physics-grounded recommendations,\n"
    "# NOT calibrated measurement results.\n"
    "# They MUST NOT appear in viewer_pack_v1 or the provenance chain.\n"
    "# Operator expertise is required to interpret recommendations.\n"
    "# See docs/ADR-0009-advisory-boundary.md\n"
)


# ---------------------------------------------------------------------------
# Patch definitions
# ---------------------------------------------------------------------------


def _insert_banner_after_docstring(content: str, banner: str) -> str:
    """
    Insert banner after the module-level docstring (or at top if no docstring).

    Strategy: find the end of the first triple-quoted string at the start of
    the file, insert the banner immediately after.
    """
    # Match triple-quoted docstring at start of file (with optional leading whitespace)
    pattern = re.compile(
        r'^(\s*""".*?"""|\s*\'\'\'.*?\'\'\')',
        re.DOTALL | re.MULTILINE,
    )
    m = pattern.match(content)
    if m:
        end = m.end()
        # Insert banner after the closing triple-quote
        return content[:end] + "\n\n" + banner + content[end:]
    else:
        # No docstring — insert at very top
        return banner + "\n" + content


def _patch_wolf_advisor(content: str) -> str:
    """Add DECISION SUPPORT banner to wolf_advisor.py."""
    if "# INSTRUMENT CLASS:" in content:
        return content  # Already declared
    return _insert_banner_after_docstring(content, DECISION_SUPPORT_BANNER)


def _patch_wolf_beat(content: str) -> str:
    """Add MEASUREMENT banner to wolf_beat.py."""
    if "# INSTRUMENT CLASS:" in content:
        return content
    return _insert_banner_after_docstring(content, MEASUREMENT_BANNER)


def _patch_wood_properties(content: str) -> str:
    """
    Add DECISION SUPPORT banner to analyzer/analysis/wood_properties.py
    and annotate quality_grade field as a heuristic.
    """
    if "# INSTRUMENT CLASS:" in content:
        return content

    content = _insert_banner_after_docstring(content, DECISION_SUPPORT_BANNER)

    # Add note to quality_grade field
    content = content.replace(
        "quality_grade: str  # A, B, C, D based on radiation coefficient",
        (
            "quality_grade: str  "
            "# A/B/C/D — HEURISTIC ONLY, not a calibrated measurement. "
            "Do not include in viewer_pack_v1."
        ),
    )
    # Also handle variant without trailing comment
    content = content.replace(
        "    quality_grade: str\n",
        (
            "    quality_grade: str  "
            "# HEURISTIC ONLY — not a calibrated measurement. "
            "See ADR-0009.\n"
        ),
    )
    return content


def _patch_estimators(content: str) -> str:
    """
    Add MEASUREMENT banner to transfer_function/estimators.py and rename
    quality_grade → coherence_band, replacing value strings with objective terms.
    """
    if "# INSTRUMENT CLASS:" in content:
        content_out = content
    else:
        content_out = _insert_banner_after_docstring(content, MEASUREMENT_BANNER)

    # Rename field declarations and assignments
    renames = [
        # dataclass field
        (r"\bquality_grade\s*:\s*str\b", "coherence_band: str"),
        # default values
        (r"quality_grade\s*=\s*\"unknown\"", 'coherence_band = "unknown"'),
        (r"quality_grade\s*=\s*grade", "coherence_band = grade"),
        # docstring description
        (r"quality_grade\s*:\s*str", "coherence_band: str"),
        # any remaining references
        (r"\bquality_grade\b", "coherence_band"),
    ]
    for pattern, replacement in renames:
        content_out = re.sub(pattern, replacement, content_out)

    # Replace subjective value strings with objective terms
    value_map = {
        '"excellent"': '"high"',
        '"good"': '"medium-high"',
        '"acceptable"': '"medium"',
        '"poor"': '"low"',
        "'excellent'": "'high'",
        "'good'": "'medium-high'",
        "'acceptable'": "'medium'",
        "'poor'": "'low'",
        # Title case variants
        '"Excellent"': '"High"',
        '"Good"': '"Medium-High"',
        '"Acceptable"': '"Medium"',
        '"Poor"': '"Low"',
    }
    for old, new in value_map.items():
        content_out = content_out.replace(old, new)

    return content_out


# ---------------------------------------------------------------------------
# File patch table
# ---------------------------------------------------------------------------

PATCHES = [
    (
        "tap_tone_pi/wolf/wolf_advisor.py",
        _patch_wolf_advisor,
        "Add DECISION SUPPORT banner",
    ),
    (
        "tap_tone_pi/wolf/wolf_beat.py",
        _patch_wolf_beat,
        "Add MEASUREMENT banner",
    ),
    (
        "analyzer/analysis/wood_properties.py",
        _patch_wood_properties,
        "Add DECISION SUPPORT banner + quality_grade annotation",
    ),
    (
        "tap_tone_pi/transfer_function/estimators.py",
        _patch_estimators,
        "Add MEASUREMENT banner + rename quality_grade → coherence_band",
    ),
]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Apply INSTRUMENT CLASS banners per ADR-0009"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print diffs without writing files",
    )
    parser.add_argument(
        "--repo-root",
        default=str(Path(__file__).resolve().parents[1]),
        help="Path to repo root (default: parent of scripts/)",
    )
    args = parser.parse_args(argv or sys.argv[1:])

    repo_root = Path(args.repo_root).resolve()
    changed = 0
    skipped = 0
    errors = 0

    for rel_path, patch_fn, description in PATCHES:
        target = repo_root / rel_path
        if not target.exists():
            print(f"[SKIP] {rel_path} — file not found")
            skipped += 1
            continue

        original = target.read_text(encoding="utf-8")
        patched = patch_fn(original)

        if patched == original:
            print(f"[UNCHANGED] {rel_path} — already up to date")
            skipped += 1
            continue

        if args.dry_run:
            print(f"[DRY-RUN] {rel_path} — {description}")
            # Show first meaningful diff line
            orig_lines = original.splitlines()
            patch_lines = patched.splitlines()
            for i, (ol, pl) in enumerate(zip(orig_lines, patch_lines)):
                if ol != pl:
                    print(f"  Line {i + 1}: - {ol[:80]!r}")
                    print(f"  Line {i + 1}: + {pl[:80]!r}")
                    break
        else:
            try:
                target.write_text(patched, encoding="utf-8")
                print(f"[PATCHED] {rel_path} — {description}")
                changed += 1
            except OSError as e:
                print(f"[ERROR] {rel_path} — {e}", file=sys.stderr)
                errors += 1

    print(f"\nDone: {changed} patched, {skipped} unchanged/skipped, {errors} errors")
    if args.dry_run and changed == 0 and skipped > 0:
        print("(All files already up to date or not found)")

    return 0 if errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
