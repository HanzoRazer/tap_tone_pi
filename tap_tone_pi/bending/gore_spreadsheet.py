#!/usr/bin/env python3
"""
gore_spreadsheet.py — Unified Gore-style build spreadsheet generator.

Integrates:
- Static 3-point bending MOE (merge_and_moe.py with Timoshenko correction)
- Acoustic tap tone dynamic MOE (frequency-derived)
- Gore stiffness index calculations
- Cross-validation between static and dynamic E

Output:
- JSON primary (full data, provenance, cross-validation)
- CSV export (flat table for import into spreadsheets)

Physics — Static vs Dynamic E Cross-Validation:
-----------------------------------------------
Static MOE (from 3-point bending):
    E_static = (k × L³) / (4 × b × h³)
    where k = force/deflection slope

Dynamic MOE (from tap tone frequency):
    E_dynamic = (48 × π² × f² × ρ × L⁴) / (h² × λ_n⁴)
    where:
        f = fundamental frequency (Hz)
        ρ = density (kg/m³)
        L = free length (m)
        h = thickness (m)
        λ_n = modal constant (4.730 for fundamental mode, clamped-free)

Expected Relationship:
    E_static ≈ E_dynamic (within 5-10% for quality tonewoods)

    Significant divergence indicates:
    - Measurement error
    - Internal defects (knots, checks, decay)
    - Anisotropy effects
    - Environmental conditions

Usage:
    python -m tap_tone_pi.bending.gore_spreadsheet \\
        --bending-json out/RUN/bending/bending_moe.json \\
        --acoustic-json out/RUN/acoustic/peaks.json \\
        --specimen-id "Sitka_001_L" \\
        --direction L \\
        --h_mm 3.5 --density_kg_m3 420 \\
        --instrument dreadnought \\
        --out build_spreadsheet.json \\
        --csv build_spreadsheet.csv
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from .gore_stiffness import (
    stiffness_index,
    thickness_for_target_SI,
    orthotropic_ratio,
    get_preset,
)


# =============================================================================
# Constants
# =============================================================================

# Modal constant λ_n for free-free beam (fundamental mode n=1)
LAMBDA_FREE_FREE_N1 = 4.730041  # First mode
LAMBDA_FREE_FREE_N2 = 7.853205  # Second mode
LAMBDA_FREE_FREE_N3 = 10.99561  # Third mode

# Modal constant for clamped-free (cantilever) beam
LAMBDA_CANTILEVER_N1 = 1.8751

# Typical acceptable divergence between static and dynamic E (%)
DEFAULT_CROSSVAL_THRESHOLD_PCT = 10.0


# =============================================================================
# Dynamic MOE from Tap Tone
# =============================================================================


def dynamic_modulus_from_frequency(
    freq_hz: float,
    density_kg_m3: float,
    length_mm: float,
    thickness_mm: float,
    boundary: str = "free-free",
    mode_number: int = 1,
) -> float:
    """
    Compute dynamic elastic modulus from resonant frequency.

    Uses Euler-Bernoulli beam vibration equation:
        f_n = (λ_n² / (2π)) × √(E × I / (ρ × A × L⁴))

    Solving for E:
        E = (4 × π² × f_n² × ρ × A × L⁴) / (λ_n⁴ × I)
        E = (48 × π² × f_n² × ρ × L⁴) / (h² × λ_n⁴)  [for rect section]

    Args:
        freq_hz: Measured resonant frequency (Hz)
        density_kg_m3: Wood density (kg/m³)
        length_mm: Specimen free length (mm)
        thickness_mm: Specimen thickness (mm)
        boundary: Boundary condition ("free-free" or "cantilever")
        mode_number: Mode number (1, 2, or 3)

    Returns:
        E_dynamic in GPa

    Physics Notes:
    - Free-free beam: λ₁ = 4.730, λ₂ = 7.853, λ₃ = 10.996
    - Cantilever: λ₁ = 1.875, λ₂ = 4.694
    - For thin beams (L/h > 20), rotary inertia and shear are negligible
    - Dynamic E typically 5-15% higher than static E for wood
    """
    # Select modal constant
    if boundary == "cantilever":
        if mode_number == 1:
            lambda_n = LAMBDA_CANTILEVER_N1
        else:
            raise ValueError(f"Cantilever mode {mode_number} not implemented")
    else:  # free-free
        if mode_number == 1:
            lambda_n = LAMBDA_FREE_FREE_N1
        elif mode_number == 2:
            lambda_n = LAMBDA_FREE_FREE_N2
        elif mode_number == 3:
            lambda_n = LAMBDA_FREE_FREE_N3
        else:
            raise ValueError(f"Mode number {mode_number} must be 1, 2, or 3")

    # Convert to SI
    L = length_mm / 1000.0  # m
    h = thickness_mm / 1000.0  # m
    rho = density_kg_m3  # kg/m³

    # Euler-Bernoulli frequency equation solved for E:
    # E = (48 × π² × f² × ρ × L⁴) / (h² × λ⁴)
    pi_sq = math.pi**2
    E_Pa = (48.0 * pi_sq * (freq_hz**2) * rho * (L**4)) / ((h**2) * (lambda_n**4))

    return E_Pa / 1e9  # Convert to GPa


def frequency_from_modulus(
    E_GPa: float,
    density_kg_m3: float,
    length_mm: float,
    thickness_mm: float,
    boundary: str = "free-free",
    mode_number: int = 1,
) -> float:
    """
    Predict resonant frequency from elastic modulus.

    Inverse of dynamic_modulus_from_frequency.

    Args:
        E_GPa: Elastic modulus (GPa)
        density_kg_m3: Wood density (kg/m³)
        length_mm: Specimen free length (mm)
        thickness_mm: Specimen thickness (mm)
        boundary: Boundary condition
        mode_number: Mode number

    Returns:
        Predicted frequency in Hz
    """
    # Select modal constant
    if boundary == "cantilever":
        lambda_n = LAMBDA_CANTILEVER_N1
    else:
        lambda_map = {
            1: LAMBDA_FREE_FREE_N1,
            2: LAMBDA_FREE_FREE_N2,
            3: LAMBDA_FREE_FREE_N3,
        }
        lambda_n = lambda_map.get(mode_number, LAMBDA_FREE_FREE_N1)

    # Convert to SI
    E_Pa = E_GPa * 1e9
    L = length_mm / 1000.0
    h = thickness_mm / 1000.0
    rho = density_kg_m3

    # f = (λ² / (2π)) × √(E × h² / (12 × ρ × L⁴))
    # Simplified for rectangular section
    f = (lambda_n**2 / (2 * math.pi)) * math.sqrt(E_Pa * (h**2) / (12.0 * rho * (L**4)))

    return f


# =============================================================================
# Cross-Validation
# =============================================================================


@dataclass
class CrossValidationResult:
    """Result of static vs dynamic E cross-validation."""

    E_static_GPa: float
    E_dynamic_GPa: Optional[float]  # None if no acoustic data
    delta_GPa: Optional[float]
    delta_percent: Optional[float]
    agreement: str  # "good", "marginal", "poor", "no_acoustic"
    threshold_percent: float

    # Additional diagnostics
    predicted_freq_hz: Optional[float] = None  # Based on E_static
    measured_freq_hz: Optional[float] = None  # From acoustic
    freq_delta_percent: Optional[float] = None

    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None and v != []}


def cross_validate_modulus(
    E_static_GPa: float,
    E_dynamic_GPa: Optional[float] = None,
    measured_freq_hz: Optional[float] = None,
    density_kg_m3: Optional[float] = None,
    length_mm: Optional[float] = None,
    thickness_mm: Optional[float] = None,
    threshold_percent: float = DEFAULT_CROSSVAL_THRESHOLD_PCT,
) -> CrossValidationResult:
    """
    Cross-validate static E against dynamic E (or compute from frequency).

    Args:
        E_static_GPa: Static modulus from bending test
        E_dynamic_GPa: Dynamic modulus (if already computed)
        measured_freq_hz: Measured tap tone frequency
        density_kg_m3: Density for computing dynamic E from freq
        length_mm: Specimen length
        thickness_mm: Specimen thickness
        threshold_percent: Acceptable divergence threshold

    Returns:
        CrossValidationResult with agreement assessment
    """
    warnings = []
    predicted_freq = None
    freq_delta_pct = None

    # Compute E_dynamic from frequency if not provided
    if E_dynamic_GPa is None and measured_freq_hz is not None:
        if (
            density_kg_m3 is not None
            and length_mm is not None
            and thickness_mm is not None
        ):
            E_dynamic_GPa = dynamic_modulus_from_frequency(
                measured_freq_hz, density_kg_m3, length_mm, thickness_mm
            )
        else:
            warnings.append(
                "Cannot compute E_dynamic: missing density, length, or thickness"
            )

    # Predict frequency from static E for comparison
    if density_kg_m3 is not None and length_mm is not None and thickness_mm is not None:
        predicted_freq = frequency_from_modulus(
            E_static_GPa, density_kg_m3, length_mm, thickness_mm
        )

        if measured_freq_hz is not None:
            freq_delta_pct = (
                100.0 * abs(measured_freq_hz - predicted_freq) / predicted_freq
            )

    # No acoustic data
    if E_dynamic_GPa is None:
        return CrossValidationResult(
            E_static_GPa=round(E_static_GPa, 3),
            E_dynamic_GPa=None,
            delta_GPa=None,
            delta_percent=None,
            agreement="no_acoustic",
            threshold_percent=threshold_percent,
            predicted_freq_hz=round(predicted_freq, 1) if predicted_freq else None,
            measured_freq_hz=measured_freq_hz,
            freq_delta_percent=round(freq_delta_pct, 1) if freq_delta_pct else None,
            warnings=warnings,
        )

    # Compute divergence
    delta = abs(E_static_GPa - E_dynamic_GPa)
    delta_pct = 100.0 * delta / E_static_GPa

    # Assess agreement
    if delta_pct <= threshold_percent * 0.5:
        agreement = "good"
    elif delta_pct <= threshold_percent:
        agreement = "marginal"
    else:
        agreement = "poor"
        warnings.append(
            f"Static/dynamic E divergence ({delta_pct:.1f}%) exceeds threshold "
            f"({threshold_percent:.1f}%). Check for defects or measurement error."
        )

    # Expected relationship
    if E_dynamic_GPa > E_static_GPa * 1.2:
        warnings.append(
            "E_dynamic >> E_static: unusual. Check density measurement or specimen constraints."
        )
    elif E_static_GPa > E_dynamic_GPa * 1.2:
        warnings.append(
            "E_static >> E_dynamic: may indicate internal defects affecting dynamic response."
        )

    return CrossValidationResult(
        E_static_GPa=round(E_static_GPa, 3),
        E_dynamic_GPa=round(E_dynamic_GPa, 3),
        delta_GPa=round(delta, 3),
        delta_percent=round(delta_pct, 1),
        agreement=agreement,
        threshold_percent=threshold_percent,
        predicted_freq_hz=round(predicted_freq, 1) if predicted_freq else None,
        measured_freq_hz=measured_freq_hz,
        freq_delta_percent=round(freq_delta_pct, 1) if freq_delta_pct else None,
        warnings=warnings,
    )


# =============================================================================
# Build Spreadsheet Data Structure
# =============================================================================


@dataclass
class BuildSpreadsheetEntry:
    """Single entry in the build spreadsheet."""

    # Identification
    specimen_id: str
    direction: str  # "L" or "C"
    timestamp_utc: str

    # Geometry
    thickness_mm: float
    length_mm: Optional[float] = None
    width_mm: Optional[float] = None

    # Material
    density_kg_m3: Optional[float] = None
    species: Optional[str] = None

    # Static bending
    E_static_GPa: Optional[float] = None
    E_uncorrected_GPa: Optional[float] = None  # Pre-Timoshenko
    shear_correction_applied: bool = False
    shear_correction_percent: Optional[float] = None
    fit_r_squared: Optional[float] = None

    # Acoustic tap tone
    E_dynamic_GPa: Optional[float] = None
    fundamental_freq_hz: Optional[float] = None

    # Stiffness index
    SI: Optional[float] = None  # GPa·mm³
    SI_target: Optional[float] = None
    h_target_mm: Optional[float] = None

    # Cross-validation
    crossval_agreement: Optional[str] = None
    crossval_delta_percent: Optional[float] = None

    # Derived properties
    specific_stiffness: Optional[float] = None  # E/ρ
    wave_speed_m_s: Optional[float] = None  # √(E/ρ)
    radiation_ratio: Optional[float] = None  # c/ρ

    # Instrument matching
    instrument_type: Optional[str] = None
    preset_SI_typical: Optional[float] = None
    preset_h_recommended_mm: Optional[float] = None
    preset_match_status: Optional[str] = None  # "low", "good", "high"

    # Warnings and provenance
    warnings: List[str] = field(default_factory=list)
    provenance: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, removing None values."""
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None and v != [] and v != {}}


@dataclass
class BuildSpreadsheet:
    """Complete build spreadsheet with multiple entries."""

    schema_id: str = "gore_build_spreadsheet"
    schema_version: str = "1.0"
    created_utc: str = ""
    entries: List[BuildSpreadsheetEntry] = field(default_factory=list)

    # Orthotropic summary (if both L and C present)
    orthotropic_summary: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
            "created_utc": self.created_utc,
            "entries": [e.to_dict() for e in self.entries],
        }
        if self.orthotropic_summary:
            d["orthotropic_summary"] = self.orthotropic_summary
        return d


# =============================================================================
# Integration Functions
# =============================================================================


def load_bending_moe(json_path: str) -> Dict[str, Any]:
    """Load bending MOE JSON from merge_and_moe.py output."""
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_acoustic_peaks(json_path: str) -> Dict[str, Any]:
    """Load acoustic peaks JSON (from tap tone analysis)."""
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_fundamental_frequency(peaks: Dict[str, Any]) -> Optional[float]:
    """Extract fundamental frequency from peaks data."""
    # Support multiple formats
    if "peaks_hz" in peaks and peaks["peaks_hz"]:
        # Simple list format
        return float(min(peaks["peaks_hz"]))
    elif "peaks" in peaks and peaks["peaks"]:
        # Structured format with dicts
        peak_list = peaks["peaks"]
        if isinstance(peak_list[0], dict):
            freqs = [p.get("frequency_hz", p.get("freq_hz", 0)) for p in peak_list]
            return float(min(f for f in freqs if f > 0))
        else:
            return float(min(peak_list))
    elif "fundamental_hz" in peaks:
        return float(peaks["fundamental_hz"])
    return None


def _sha256(path: Path) -> str:
    """Compute SHA-256 hash of file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_bending_data(
    entry: BuildSpreadsheetEntry,
    bending_json_path: str,
    warnings: List[str],
    provenance: Dict[str, str],
) -> Optional[float]:
    """Load static bending data and populate entry fields. Returns E_static."""
    bending = load_bending_moe(bending_json_path)
    E_static = bending.get("E_GPa")
    entry.E_static_GPa = round(E_static, 3) if E_static else None
    entry.E_uncorrected_GPa = round(bending.get("E_euler_bernoulli_GPa", E_static), 3)

    shear_info = bending.get("shear_correction", {})
    entry.shear_correction_applied = shear_info.get("applied", False)
    entry.shear_correction_percent = round(shear_info.get("reduction_percent", 0), 2)

    fit_info = bending.get("fit", {})
    entry.fit_r_squared = round(fit_info.get("r2", 0), 4)

    if fit_info.get("warning"):
        warnings.append(f"Bending fit: {fit_info['warning']}")

    provenance["bending_json_path"] = bending_json_path
    provenance["bending_json_sha256"] = _sha256(Path(bending_json_path))
    return E_static


def _load_acoustic_data(
    entry: BuildSpreadsheetEntry,
    acoustic_json_path: str,
    density_kg_m3: Optional[float],
    length_mm: Optional[float],
    thickness_mm: float,
    provenance: Dict[str, str],
) -> tuple[Optional[float], Optional[float]]:
    """Load acoustic tap tone data. Returns (E_dynamic, measured_freq)."""
    peaks = load_acoustic_peaks(acoustic_json_path)
    measured_freq = extract_fundamental_frequency(peaks)
    entry.fundamental_freq_hz = round(measured_freq, 1) if measured_freq else None

    E_dynamic = None
    if measured_freq and density_kg_m3 and length_mm:
        E_dynamic = dynamic_modulus_from_frequency(
            measured_freq, density_kg_m3, length_mm, thickness_mm
        )
        entry.E_dynamic_GPa = round(E_dynamic, 3)

    provenance["acoustic_json_path"] = acoustic_json_path
    provenance["acoustic_json_sha256"] = _sha256(Path(acoustic_json_path))
    return E_dynamic, measured_freq


def _apply_stiffness_and_preset(
    entry: BuildSpreadsheetEntry,
    E_best: float,
    thickness_mm: float,
    direction: str,
    SI_target: Optional[float],
    instrument: Optional[str],
) -> None:
    """Compute stiffness index and compare against instrument preset."""
    entry.SI = round(stiffness_index(E_best, thickness_mm), 2)

    target = SI_target
    preset = get_preset(instrument) if instrument else None

    if target is None and preset is not None:
        if direction.upper() == "L":
            target = preset.SI_L_typical
        elif direction.upper() == "C" and preset.SI_C_typical:
            target = preset.SI_C_typical

    if target is not None:
        entry.SI_target = target
        entry.h_target_mm = round(thickness_for_target_SI(target, E_best), 3)

    if preset is not None:
        entry.instrument_type = preset.instrument.value
        if direction.upper() == "L":
            entry.preset_SI_typical = preset.SI_L_typical
            entry.preset_h_recommended_mm = round(
                thickness_for_target_SI(preset.SI_L_typical, E_best), 3
            )
            if entry.SI < preset.SI_L_min:
                entry.preset_match_status = "low"
            elif entry.SI > preset.SI_L_max:
                entry.preset_match_status = "high"
            else:
                entry.preset_match_status = "good"


def _compute_derived_properties(
    entry: BuildSpreadsheetEntry,
    E_best: float,
    density_kg_m3: float,
) -> None:
    """Compute specific stiffness, wave speed, and radiation ratio."""
    E_Pa = E_best * 1e9
    spec = E_Pa / density_kg_m3  # m²/s²
    c = math.sqrt(spec)  # m/s

    entry.specific_stiffness = round(spec, 0)
    entry.wave_speed_m_s = round(c, 0)
    entry.radiation_ratio = round(c / density_kg_m3, 4)


def build_spreadsheet_entry(
    specimen_id: str,
    direction: str,
    thickness_mm: float,
    bending_json_path: Optional[str] = None,
    acoustic_json_path: Optional[str] = None,
    density_kg_m3: Optional[float] = None,
    length_mm: Optional[float] = None,
    width_mm: Optional[float] = None,
    species: Optional[str] = None,
    instrument: Optional[str] = None,
    SI_target: Optional[float] = None,
    crossval_threshold_pct: float = DEFAULT_CROSSVAL_THRESHOLD_PCT,
) -> BuildSpreadsheetEntry:
    """
    Build a single spreadsheet entry from input data.

    Args:
        specimen_id: Unique specimen identifier
        direction: Grain direction ("L" or "C")
        thickness_mm: Specimen thickness
        bending_json_path: Path to bending_moe.json
        acoustic_json_path: Path to peaks.json
        density_kg_m3: Wood density
        length_mm: Specimen length (for dynamic E)
        width_mm: Specimen width
        species: Wood species name
        instrument: Target instrument for preset matching
        SI_target: Explicit target SI (overrides preset)
        crossval_threshold_pct: Threshold for static/dynamic agreement

    Returns:
        Populated BuildSpreadsheetEntry
    """
    warnings = []
    provenance = {}

    entry = BuildSpreadsheetEntry(
        specimen_id=specimen_id,
        direction=direction.upper(),
        timestamp_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        thickness_mm=thickness_mm,
        length_mm=length_mm,
        width_mm=width_mm,
        density_kg_m3=density_kg_m3,
        species=species,
    )

    # -------------------------------------------------------------------------
    # Load data sources
    # -------------------------------------------------------------------------
    E_static = None
    if bending_json_path:
        E_static = _load_bending_data(entry, bending_json_path, warnings, provenance)

    E_dynamic = None
    measured_freq = None
    if acoustic_json_path:
        E_dynamic, measured_freq = _load_acoustic_data(
            entry,
            acoustic_json_path,
            density_kg_m3,
            length_mm,
            thickness_mm,
            provenance,
        )

    # -------------------------------------------------------------------------
    # Cross-validation
    # -------------------------------------------------------------------------
    if E_static is not None:
        crossval = cross_validate_modulus(
            E_static_GPa=E_static,
            E_dynamic_GPa=E_dynamic,
            measured_freq_hz=measured_freq,
            density_kg_m3=density_kg_m3,
            length_mm=length_mm,
            thickness_mm=thickness_mm,
            threshold_percent=crossval_threshold_pct,
        )
        entry.crossval_agreement = crossval.agreement
        entry.crossval_delta_percent = crossval.delta_percent
        warnings.extend(crossval.warnings)

    # -------------------------------------------------------------------------
    # Stiffness Index + Instrument Preset
    # -------------------------------------------------------------------------
    E_best = E_static or E_dynamic  # Prefer static if available
    if E_best is not None:
        _apply_stiffness_and_preset(
            entry,
            E_best,
            thickness_mm,
            direction,
            SI_target,
            instrument,
        )

    # -------------------------------------------------------------------------
    # Derived properties
    # -------------------------------------------------------------------------
    if E_best is not None and density_kg_m3 is not None:
        _compute_derived_properties(entry, E_best, density_kg_m3)

    entry.warnings = warnings
    entry.provenance = provenance

    return entry


def generate_spreadsheet(
    entries: List[BuildSpreadsheetEntry],
) -> BuildSpreadsheet:
    """
    Generate complete build spreadsheet from entries.

    Adds orthotropic summary if both L and C directions present.
    """
    sheet = BuildSpreadsheet(
        created_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        entries=entries,
    )

    # Check for orthotropic data (both L and C for same specimen)
    l_entries = [e for e in entries if e.direction == "L"]
    c_entries = [e for e in entries if e.direction == "C"]

    if l_entries and c_entries:
        # Find matching specimens
        l_ids = {e.specimen_id.rsplit("_", 1)[0] for e in l_entries}
        c_ids = {e.specimen_id.rsplit("_", 1)[0] for e in c_entries}
        common = l_ids & c_ids

        if common:
            # Use first matching pair for summary
            base_id = next(iter(common))
            l_entry = next(
                (e for e in l_entries if e.specimen_id.startswith(base_id)),
                l_entries[0],
            )
            c_entry = next(
                (e for e in c_entries if e.specimen_id.startswith(base_id)),
                c_entries[0],
            )

            E_L = l_entry.E_static_GPa or l_entry.E_dynamic_GPa
            E_C = c_entry.E_static_GPa or c_entry.E_dynamic_GPa

            if E_L and E_C:
                sheet.orthotropic_summary = {
                    "E_L_GPa": E_L,
                    "E_C_GPa": E_C,
                    "E_ratio_L_C": round(orthotropic_ratio(E_L, E_C), 2),
                    "SI_L": l_entry.SI,
                    "SI_C": c_entry.SI,
                    "SI_ratio_L_C": round(l_entry.SI / c_entry.SI, 2)
                    if c_entry.SI
                    else None,
                }

    return sheet


# =============================================================================
# CSV Export
# =============================================================================


CSV_COLUMNS = [
    "specimen_id",
    "direction",
    "species",
    "thickness_mm",
    "length_mm",
    "width_mm",
    "density_kg_m3",
    "E_static_GPa",
    "E_dynamic_GPa",
    "crossval_agreement",
    "crossval_delta_percent",
    "SI",
    "SI_target",
    "h_target_mm",
    "specific_stiffness",
    "wave_speed_m_s",
    "radiation_ratio",
    "instrument_type",
    "preset_match_status",
    "preset_h_recommended_mm",
    "fundamental_freq_hz",
    "shear_correction_applied",
    "shear_correction_percent",
    "fit_r_squared",
    "warnings",
]


def export_csv(sheet: BuildSpreadsheet, csv_path: str) -> None:
    """Export spreadsheet to CSV format."""
    path = Path(csv_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()

        for entry in sheet.entries:
            row = entry.to_dict()
            # Convert warnings list to semicolon-separated string
            if "warnings" in row:
                row["warnings"] = "; ".join(row["warnings"])
            writer.writerow(row)


# =============================================================================
# CLI Interface
# =============================================================================


def main() -> None:
    """CLI entry point."""
    ap = argparse.ArgumentParser(
        description="Generate Gore-style build spreadsheet with cross-validation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Required inputs
    ap.add_argument("--specimen-id", required=True, help="Specimen identifier")
    ap.add_argument("--h_mm", type=float, required=True, help="Thickness in mm")
    ap.add_argument(
        "--direction",
        choices=["L", "C"],
        default="L",
        help="Grain direction (L=long, C=cross)",
    )

    # Data sources
    ap.add_argument("--bending-json", help="Path to bending_moe.json (static MOE)")
    ap.add_argument("--acoustic-json", help="Path to peaks.json (tap tone)")

    # Specimen properties
    ap.add_argument("--density", type=float, help="Density in kg/m³")
    ap.add_argument("--length", type=float, help="Free length in mm (for dynamic E)")
    ap.add_argument("--width", type=float, help="Width in mm")
    ap.add_argument("--species", help="Wood species name")

    # Target and instrument
    ap.add_argument(
        "--instrument", help="Target instrument (e.g., dreadnought, classical)"
    )
    ap.add_argument(
        "--SI-target", type=float, help="Explicit target SI (overrides preset)"
    )

    # Cross-validation
    ap.add_argument(
        "--crossval-threshold",
        type=float,
        default=DEFAULT_CROSSVAL_THRESHOLD_PCT,
        help=f"Static/dynamic divergence threshold %% (default: {DEFAULT_CROSSVAL_THRESHOLD_PCT})",
    )

    # Output
    ap.add_argument("--out", required=True, help="Output JSON path")
    ap.add_argument("--csv", help="Also export CSV to this path")
    ap.add_argument("--quiet", action="store_true", help="Suppress console output")

    args = ap.parse_args()

    # Build entry
    entry = build_spreadsheet_entry(
        specimen_id=args.specimen_id,
        direction=args.direction,
        thickness_mm=args.h_mm,
        bending_json_path=args.bending_json,
        acoustic_json_path=args.acoustic_json,
        density_kg_m3=args.density,
        length_mm=args.length,
        width_mm=args.width,
        species=args.species,
        instrument=args.instrument,
        SI_target=args.SI_target,
        crossval_threshold_pct=args.crossval_threshold,
    )

    # Generate spreadsheet
    sheet = generate_spreadsheet([entry])

    # Write JSON
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(sheet.to_dict(), f, indent=2)

    if not args.quiet:
        print(f"Wrote: {out_path}")

        # Print summary
        e = entry
        print(f"\nSpecimen: {e.specimen_id} ({e.direction}-grain)")
        print(f"  h = {e.thickness_mm:.3f} mm")

        if e.E_static_GPa:
            print(f"  E_static  = {e.E_static_GPa:.3f} GPa", end="")
            if e.shear_correction_applied:
                print(f" (Timoshenko -{e.shear_correction_percent:.1f}%)")
            else:
                print()

        if e.E_dynamic_GPa:
            print(
                f"  E_dynamic = {e.E_dynamic_GPa:.3f} GPa (from {e.fundamental_freq_hz:.1f} Hz)"
            )

        if e.crossval_agreement and e.crossval_agreement != "no_acoustic":
            print(
                f"  Cross-validation: {e.crossval_agreement.upper()} (Δ{e.crossval_delta_percent:.1f}%)"
            )

        if e.SI:
            print(f"  SI = {e.SI:.2f} GPa·mm³")
            if e.h_target_mm:
                delta = e.thickness_mm - e.h_target_mm
                action = "remove" if delta > 0 else "add"
                print(
                    f"  Target h = {e.h_target_mm:.3f} mm ({action} {abs(delta):.3f} mm)"
                )

        if e.preset_match_status:
            print(
                f"  Instrument match ({e.instrument_type}): {e.preset_match_status.upper()}"
            )

        if e.warnings:
            print("\n  Warnings:")
            for w in e.warnings:
                print(f"    - {w}")

    # Export CSV if requested
    if args.csv:
        export_csv(sheet, args.csv)
        if not args.quiet:
            print(f"Wrote: {args.csv}")


if __name__ == "__main__":
    main()
