#!/usr/bin/env python3
"""viewer_pack_v1.py — Pre-export validator for viewer_pack_v1 contract.

Validates a staged pack directory before ZIP creation.
Enforces all rules defined in docs/PRE_EXPORT_VALIDATION.md.

Usage:
    python -m tap_tone.validate.viewer_pack_v1 path/to/staged_pack
    python -m tap_tone.validate.viewer_pack_v1 path/to/staged_pack --report report.json
    python -m tap_tone.validate.viewer_pack_v1 path/to/staged_pack --audio-required

Exit codes:
    0 = Validation passed (no errors)
    2 = Validation failed (errors found)
    3 = Validator internal failure
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


@dataclass
class ValidationIssue:
    """Single validation issue."""

    rule: str
    message: str
    path: Optional[str] = None
    severity: str = "ERROR"  # ERROR or WARN


@dataclass
class ValidationReport:
    """Complete validation report."""

    schema_id: str = "validation_report_v1"
    validated_at_utc: str = ""
    pack_path: str = ""
    passed: bool = True
    errors: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[Dict[str, Any]] = field(default_factory=list)
    stats: Dict[str, int] = field(default_factory=dict)

    def add_error(self, rule: str, message: str, path: Optional[str] = None) -> None:
        self.errors.append(
            {
                "rule": rule,
                "message": message,
                "path": path,
            }
        )
        self.passed = False

    def add_warning(self, rule: str, message: str, path: Optional[str] = None) -> None:
        self.warnings.append(
            {
                "rule": rule,
                "message": message,
                "path": path,
            }
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "validated_at_utc": self.validated_at_utc,
            "pack_path": self.pack_path,
            "passed": self.passed,
            "errors": self.errors,
            "warnings": self.warnings,
            "stats": self.stats,
        }


def _repo_root() -> Path:
    """Best-effort repo root locator for schema files.

    This module lives at: <root>/tap_tone/validate/viewer_pack_v1.py
    """
    try:
        return Path(__file__).resolve().parents[2]
    except (IndexError, OSError):
        return Path.cwd()


def _load_contract_schema(schema_relpath: str) -> Optional[Dict[str, Any]]:
    """Load a JSON schema shipped in-repo under contracts/schemas/.

    Fail-closed: return None if missing/unreadable.
    """
    try:
        p = _repo_root() / schema_relpath
        if not p.is_file():
            return None
        obj = json.loads(p.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else None
    except (OSError, json.JSONDecodeError, ValueError):
        return None


def _validate_json_against_schema(
    doc: Dict[str, Any],
    schema: Dict[str, Any],
) -> Optional[str]:
    """Return None if valid; else return a short error string."""
    try:
        from jsonschema import Draft202012Validator

        v = Draft202012Validator(schema)
        errs = sorted(v.iter_errors(doc), key=lambda e: list(e.path))
        if not errs:
            return None
        e = errs[0]
        loc = "/".join(str(x) for x in e.path) if e.path else "<root>"
        return f"{loc}: {e.message}"
    except ImportError:
        return None  # jsonschema not installed → skip
    except Exception as ex:
        return f"<validator>: {ex}"


def _read_csv_columns(path: Path) -> tuple[List[str], List[Dict[str, str]]]:
    """Read CSV and return (headers, rows as dicts)."""
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        rows = list(reader)
    return headers, rows


def _parse_float(value: str) -> Optional[float]:
    """Parse float, return None if invalid."""
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _is_ci() -> bool:
    """Check if running in CI environment."""
    return os.getenv("CI", "").strip().lower() in ("1", "true", "yes", "on")


def _validate_timeline(
    pack: Path,
    timeline_path: Path,
    report: ValidationReport,
    stats: Dict[str, int],
) -> None:
    """Validate optional session timeline (T-000, T-001)."""
    if not timeline_path.exists():
        return

    stats["timeline_present"] = 1
    try:
        doc = json.loads(timeline_path.read_text(encoding="utf-8"))
        if not isinstance(doc, dict):
            report.add_error(
                "T-001",
                "session_timeline_v1.json is not a JSON object",
                str(timeline_path.relative_to(pack)),
            )
            return

        schema = _load_contract_schema(
            "contracts/schemas/session_timeline_v1.schema.json",
        )
        if schema is None:
            if _is_ci():
                report.add_error(
                    "T-000",
                    "Session timeline schema not found in CI; failing validation",
                    str(timeline_path.relative_to(pack)),
                )
            else:
                report.add_warning(
                    "T-000",
                    "Session timeline schema not found; skipping schema validation",
                    str(timeline_path.relative_to(pack)),
                )
            return

        err = _validate_json_against_schema(doc, schema)
        if err is None:
            stats["timeline_valid"] = 1
        else:
            report.add_error(
                "T-001",
                f"session_timeline_v1.json does not conform to schema: {err}",
                str(timeline_path.relative_to(pack)),
            )
    except json.JSONDecodeError as e:
        report.add_error(
            "T-001",
            f"session_timeline_v1.json is not valid JSON: {e}",
            str(timeline_path.relative_to(pack)),
        )
    except Exception as e:
        report.add_error(
            "T-001",
            f"session_timeline_v1.json validation failed: {e}",
            str(timeline_path.relative_to(pack)),
        )


def _collect_shared_freq_grid(
    pack: Path,
    points: List[str],
) -> tuple[Optional[List[float]], Optional[str]]:
    """Collect shared frequency grid from first valid spectrum."""
    for pid in points:
        spectrum_path = pack / "spectra" / "points" / pid / "spectrum.csv"
        if spectrum_path.exists():
            try:
                headers, rows = _read_csv_columns(spectrum_path)
                if "freq_hz" in headers:
                    freqs = []
                    for row in rows:
                        f = _parse_float(row.get("freq_hz", ""))
                        if f is not None:
                            freqs.append(f)
                    if freqs:
                        return freqs, pid
            except (IndexError, OSError, KeyError, TypeError):
                pass
    return None, None


def _validate_wsi(
    pack: Path,
    report: ValidationReport,
    stats: Dict[str, int],
    shared_freq_grid: Optional[List[float]],
) -> None:
    """Validate WSI curve (W-001 to W-003)."""
    wsi_path = pack / "wolf" / "wsi_curve.csv"
    if not wsi_path.exists():
        return

    try:
        headers, rows = _read_csv_columns(wsi_path)
        rel_path = str(wsi_path.relative_to(pack))

        # W-001: Required Columns
        required_cols = [
            "freq_hz",
            "wsi",
            "loc",
            "grad",
            "phase_disorder",
            "coh_mean",
            "admissible",
        ]
        for col in required_cols:
            if col not in headers:
                report.add_error(
                    "W-001", f"WSI curve missing required column: {col}", rel_path
                )

        if not all(col in headers for col in required_cols):
            return

        # W-002: Admissible Values
        for i, row in enumerate(rows):
            adm = row.get("admissible", "").lower().strip()
            if adm not in ("true", "false"):
                report.add_error(
                    "W-002",
                    f"WSI curve: invalid admissible value '{row.get('admissible', '')}' at row {i + 2}",
                    rel_path,
                )
                break

        # W-003: Frequency Alignment
        wsi_freqs = []
        for row in rows:
            f = _parse_float(row.get("freq_hz", ""))
            if f is not None:
                wsi_freqs.append(f)

        if shared_freq_grid:
            if len(wsi_freqs) != len(shared_freq_grid):
                report.add_error(
                    "W-003",
                    f"WSI frequency grid mismatch: {len(wsi_freqs)} bins vs {len(shared_freq_grid)} spectrum bins",
                    rel_path,
                )
            else:
                for i, (f1, f2) in enumerate(zip(shared_freq_grid, wsi_freqs)):
                    if abs(f1 - f2) > 1e-6:
                        report.add_error(
                            "W-003",
                            f"WSI frequency mismatch at bin {i}: spectrum={f1}, wsi={f2}",
                            rel_path,
                        )
                        break

        stats["wsi_valid"] = 1

    except Exception as e:
        report.add_error(
            "W-001", f"Cannot read WSI curve: {e}", str(wsi_path.relative_to(pack))
        )


def _validate_optional_files(
    pack: Path,
    report: ValidationReport,
) -> None:
    """Validate optional JSON files (O-001)."""
    optional_json_files = [
        pack / "coherence" / "coherence_summary.json",
        pack / "meta" / "session_meta.json",
        pack / "provenance.json",
    ]

    for opt_path in optional_json_files:
        if opt_path.exists():
            try:
                with open(opt_path, "r", encoding="utf-8") as f:
                    json.load(f)
            except json.JSONDecodeError as e:
                report.add_warning(
                    "O-001",
                    f"Optional file is not valid JSON: {e}",
                    str(opt_path.relative_to(pack)),
                )


def _validate_point_spectrum(
    pack: Path,
    pid: str,
    report: ValidationReport,
    shared_freq_grid: Optional[List[float]],
    first_spectrum_pid: Optional[str],
) -> Optional[List[float]]:
    """Validate spectrum for a single point (S-001 to S-006).

    Returns freq_hz_values if valid, None otherwise.
    """
    spectrum_path = pack / "spectra" / "points" / pid / "spectrum.csv"
    if not spectrum_path.exists():
        report.add_error(
            "S-001",
            f"Spectrum missing for point {pid}",
            str(spectrum_path.relative_to(pack)),
        )
        return None

    try:
        headers, rows = _read_csv_columns(spectrum_path)
    except Exception as e:
        report.add_error(
            "S-001",
            f"Cannot read spectrum for point {pid}: {e}",
            str(spectrum_path.relative_to(pack)),
        )
        return None

    rel_path = str(spectrum_path.relative_to(pack))

    # S-002: Required Columns
    if "freq_hz" not in headers:
        report.add_error(
            "S-002", f"Spectrum {pid} missing required column: freq_hz", rel_path
        )
    if "H_mag" not in headers:
        report.add_error(
            "S-002", f"Spectrum {pid} missing required column: H_mag", rel_path
        )

    if "freq_hz" not in headers or "H_mag" not in headers:
        return None

    # Parse freq_hz and H_mag
    freq_hz_values: List[float] = []
    parse_errors = False

    for i, row in enumerate(rows):
        f = _parse_float(row.get("freq_hz", ""))
        m = _parse_float(row.get("H_mag", ""))

        if f is None:
            report.add_error(
                "S-002", f"Spectrum {pid}: invalid freq_hz at row {i + 2}", rel_path
            )
            parse_errors = True
            continue

        freq_hz_values.append(f)

        if m is None:
            report.add_error(
                "S-005", f"Spectrum {pid}: invalid H_mag at row {i + 2}", rel_path
            )
            parse_errors = True
        else:
            # S-005: Finite Magnitudes
            if not math.isfinite(m):
                report.add_error(
                    "S-005",
                    f"Spectrum {pid}: non-finite H_mag at row {i + 2}",
                    rel_path,
                )
                parse_errors = True

    if parse_errors:
        return None

    # S-003: Frequency Monotonicity
    for i in range(1, len(freq_hz_values)):
        if freq_hz_values[i] <= freq_hz_values[i - 1]:
            report.add_error(
                "S-003",
                f"Spectrum {pid}: freq_hz not strictly increasing at row {i + 2} ({freq_hz_values[i - 1]} >= {freq_hz_values[i]})",
                rel_path,
            )
            break

    # S-004: No Duplicate Frequencies
    if len(set(freq_hz_values)) != len(freq_hz_values):
        seen: Set[float] = set()
        for f in freq_hz_values:
            if f in seen:
                report.add_error(
                    "S-004", f"Spectrum {pid}: duplicate freq_hz value {f}", rel_path
                )
                break
            seen.add(f)

    # S-006: Shared Frequency Grid
    if shared_freq_grid is not None and first_spectrum_pid != pid:
        if len(freq_hz_values) != len(shared_freq_grid):
            report.add_error(
                "S-006",
                f"Frequency grid mismatch: {first_spectrum_pid} has {len(shared_freq_grid)} bins, {pid} has {len(freq_hz_values)} bins",
                rel_path,
            )
        else:
            for i, (f1, f2) in enumerate(zip(shared_freq_grid, freq_hz_values)):
                if abs(f1 - f2) > 1e-6:
                    report.add_error(
                        "S-006",
                        f"Frequency mismatch at bin {i}: {first_spectrum_pid}={f1}, {pid}={f2}",
                        rel_path,
                    )
                    break

    return freq_hz_values


def _validate_point_analysis(
    pack: Path,
    pid: str,
    report: ValidationReport,
    stats: Dict[str, int],
    shared_freq_grid: Optional[List[float]],
    peak_tolerance_hz: float,
) -> None:
    """Validate analysis for a single point (P-001 to P-003)."""
    analysis_path = pack / "spectra" / "points" / pid / "analysis.json"
    if not analysis_path.exists():
        report.add_error(
            "P-001",
            f"Analysis missing for point {pid}",
            str(analysis_path.relative_to(pack)),
        )
        return

    try:
        with open(analysis_path, "r", encoding="utf-8") as f:
            analysis = json.load(f)

        peaks = analysis.get("peaks", [])
        if not isinstance(peaks, list):
            report.add_error(
                "P-002",
                f"Analysis {pid}: peaks is not an array",
                str(analysis_path.relative_to(pack)),
            )
            return

        # P-003: Peaks Grid Alignment
        peaks_aligned = True
        for peak in peaks:
            if not isinstance(peak, dict) or "freq_hz" not in peak:
                report.add_error(
                    "P-002",
                    f"Analysis {pid}: peak missing freq_hz",
                    str(analysis_path.relative_to(pack)),
                )
                peaks_aligned = False
                continue

            peak_freq = peak["freq_hz"]
            if shared_freq_grid:
                # Find nearest bin
                min_dist = min(abs(peak_freq - f) for f in shared_freq_grid)
                if min_dist > peak_tolerance_hz:
                    nearest = min(shared_freq_grid, key=lambda x: abs(x - peak_freq))
                    report.add_error(
                        "P-003",
                        f"Peak {pid}@{peak_freq}Hz not in frequency grid (nearest: {nearest}Hz, delta: {min_dist:.2f}Hz)",
                        str(analysis_path.relative_to(pack)),
                    )
                    peaks_aligned = False

        if peaks_aligned:
            stats["peaks_aligned"] += 1

    except json.JSONDecodeError as e:
        report.add_error(
            "P-002",
            f"Analysis {pid}: invalid JSON: {e}",
            str(analysis_path.relative_to(pack)),
        )


def validate_pack(
    pack_path: Path,
    peak_tolerance_hz: float = 0.0,
    audio_required: bool = False,
) -> ValidationReport:
    """Validate a staged viewer pack directory.

    Args:
        pack_path: Path to the staged pack directory (un-zipped)
        peak_tolerance_hz: Tolerance for peak-to-bin alignment (0 = exact match)
        audio_required: If True, missing audio is ERROR; if False, WARN

    Returns:
        ValidationReport with errors, warnings, and stats
    """
    pack = Path(pack_path).resolve()

    report = ValidationReport(
        validated_at_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        pack_path=str(pack),
    )

    stats = {
        "point_count_manifest": 0,
        "points_checked": 0,
        "spectrum_files_expected": 0,
        "spectrum_files_found": 0,
        "spectra_valid": 0,
        "analysis_files_expected": 0,
        "analysis_files_found": 0,
        "peaks_aligned": 0,
        "audio_files_expected": 0,
        "audio_files_found": 0,
        "audio_present": 0,
        "wsi_present": 0,
        "wsi_valid": 0,
        "timeline_present": 0,
        "timeline_valid": 0,
        "error_count": 0,
        "warning_count": 0,
    }

    def _finalize() -> ValidationReport:
        stats["error_count"] = len(report.errors)
        stats["warning_count"] = len(report.warnings)
        report.stats = stats
        return report

    # ========================================
    # M-001: Manifest Existence
    # ========================================
    manifest_path = pack / "viewer_pack.json"
    if not manifest_path.exists():
        report.add_error(
            "M-001",
            "Manifest viewer_pack.json not found at pack root",
            "viewer_pack.json",
        )
        return _finalize()

    # Load manifest
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except json.JSONDecodeError as e:
        report.add_error(
            "M-001", f"Manifest is not valid JSON: {e}", "viewer_pack.json"
        )
        return _finalize()

    # ========================================
    # M-002: Schema Identity
    # ========================================
    schema_id = manifest.get("schema_id", "")
    schema_version = manifest.get("schema_version", "")
    if schema_id != "viewer_pack_v1" or schema_version != "v1":
        report.add_error(
            "M-002",
            f"Schema identity mismatch: expected viewer_pack_v1/v1, got {schema_id}/{schema_version}",
            "viewer_pack.json",
        )

    # ========================================
    # M-003: Points List
    # ========================================
    points = manifest.get("points", [])
    if not points or not isinstance(points, list):
        report.add_error("M-003", "Points list empty or missing", "viewer_pack.json")
        return _finalize()

    stats["point_count_manifest"] = len(points)
    stats["points_checked"] = len(points)

    # ========================================
    # T-001: Optional Session Timeline (schema-validated)
    # ========================================
    timeline_path = pack / "meta" / "session_timeline_v1.json"
    _validate_timeline(pack, timeline_path, report, stats)

    # ========================================
    # Collect shared frequency grid from first valid spectrum
    # ========================================
    shared_freq_grid, first_spectrum_pid = _collect_shared_freq_grid(pack, points)

    # ========================================
    # Validate each point
    # ========================================
    for pid in points:
        # S-xxx: Spectrum Validation
        freq_hz_values = _validate_point_spectrum(
            pack, pid, report, shared_freq_grid, first_spectrum_pid
        )
        if freq_hz_values is not None:
            stats["spectra_valid"] += 1

            # P-xxx: Analysis/Peaks Validation
            _validate_point_analysis(
                pack, pid, report, stats, shared_freq_grid, peak_tolerance_hz
            )

        # A-001: Audio Existence
        audio_path = pack / "audio" / "points" / f"{pid}.wav"
        if audio_path.exists():
            stats["audio_present"] += 1
        else:
            if audio_required:
                report.add_error(
                    "A-001",
                    f"Audio missing for point {pid}",
                    str(audio_path.relative_to(pack)),
                )
            else:
                report.add_warning(
                    "A-001",
                    f"Audio missing for point {pid}",
                    str(audio_path.relative_to(pack)),
                )

    # ========================================
    # W-xxx: WSI Curve Validation
    # ========================================
    _validate_wsi(pack, report, stats, shared_freq_grid)

    # ========================================
    # O-001: Optional Files
    # ========================================
    _validate_optional_files(pack, report)

    # ========================================
    # T-002 CI gate: timeline_present requires timeline_valid
    # Intentionally redundant with T-000/T-001 — this is a catch-all
    # so CI never greenlights a pack whose timeline failed to validate,
    # even if future refactors alter T-000/T-001 paths.  Do not remove.
    # ========================================
    if (
        _is_ci()
        and stats.get("timeline_present") == 1
        and stats.get("timeline_valid") != 1
    ):
        report.add_error(
            "T-002",
            "CI requires timeline_valid==1 when session_timeline_v1.json is present",
        )

    return _finalize()


def write_validation_report(pack_path: Path, report: ValidationReport) -> Path:
    """Persist validation_report.json into the pack root directory.

    Args:
        pack_path: Path to the staged pack directory
        report: ValidationReport to persist

    Returns:
        Path to the written validation_report.json file
    """
    out = Path(pack_path) / "validation_report.json"
    out.write_text(
        json.dumps(report.to_dict(), indent=2, sort_keys=False), encoding="utf-8"
    )
    return out


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Validate a staged viewer pack directory before ZIP creation.",
        epilog="""
Exit codes:
  0 = Validation passed (no errors)
  2 = Validation failed (errors found)
  3 = Validator internal failure
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("pack_path", type=Path, help="Path to staged pack directory")
    parser.add_argument(
        "--report", type=Path, help="Write validation report JSON to this path"
    )
    parser.add_argument(
        "--audio-required",
        action="store_true",
        help="Treat missing audio as ERROR (default: WARN)",
    )
    parser.add_argument(
        "--peak-tolerance",
        type=float,
        default=0.0,
        help="Peak-to-bin tolerance in Hz (default: 0 = exact)",
    )
    parser.add_argument(
        "--json", action="store_true", help="Output report as JSON to stdout"
    )

    args = parser.parse_args()

    if not args.pack_path.exists():
        print(f"ERROR: Pack path not found: {args.pack_path}", file=sys.stderr)
        return 2

    if not args.pack_path.is_dir():
        print(f"ERROR: Pack path is not a directory: {args.pack_path}", file=sys.stderr)
        return 2

    try:
        report = validate_pack(
            args.pack_path,
            peak_tolerance_hz=args.peak_tolerance,
            audio_required=args.audio_required,
        )
    except Exception as e:
        print(f"INTERNAL ERROR: {e}", file=sys.stderr)
        return 3

    # Write report if requested
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2)
        print(f"Validation report written to: {args.report}")

    # Output
    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        if report.passed:
            print(f"✅ Validation PASSED: {args.pack_path}")
            print(f"   Points: {report.stats.get('points_checked', 0)}")
            print(f"   Spectra valid: {report.stats.get('spectra_valid', 0)}")
            print(f"   Peaks aligned: {report.stats.get('peaks_aligned', 0)}")
            print(f"   Audio present: {report.stats.get('audio_present', 0)}")
        else:
            print(f"❌ Validation FAILED: {args.pack_path}")
            print(f"\nErrors ({len(report.errors)}):")
            for err in report.errors:
                print(f"  [{err['rule']}] {err['message']}")
                if err.get("path"):
                    print(f"           → {err['path']}")

        if report.warnings:
            print(f"\nWarnings ({len(report.warnings)}):")
            for warn in report.warnings:
                print(f"  [{warn['rule']}] {warn['message']}")

    return 0 if report.passed else 2


if __name__ == "__main__":
    sys.exit(main())
