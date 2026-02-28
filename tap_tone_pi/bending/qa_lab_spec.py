#!/usr/bin/env python3
"""
qa_lab_spec.py — Complete QA/QC Lab Specification Sheet for Tonewood Analysis.

Extends the Gore-style spreadsheet with full laboratory traceability:

SECTION 1: SAMPLE IDENTIFICATION & TRACEABILITY
- Unique specimen ID, batch/lot, material source
- Run ID, session ID, timestamp
- Device/fixture/mic identification

SECTION 2: TEST PARAMETERS & SETUP
- Operator, calibration reference
- Environment (temperature, humidity)
- Protocol version, sample rate

SECTION 3: PRIMARY MEASUREMENTS
- Dimensions (L, W, H), mass, density
- Frequencies, amplitudes

SECTION 4: DERIVED PROPERTIES (from gore_spreadsheet)
- E_static, E_dynamic, SI
- Wave speed, specific stiffness

SECTION 5: MODAL ANALYSIS
- Mode identification (frequency, damping, Q, confidence)
- Mode shapes, MAC values

SECTION 6: ERROR ANALYSIS (GUM-compliant)
- Full uncertainty budget
- Combined uncertainty, expanded uncertainty
- Dominant error source, sensitivity coefficients
- Correlation information

SECTION 7: QUALITY ASSESSMENT
- Quality verdict (PASS/WARN/FAIL)
- Triggered rules
- Cross-validation result

SECTION 8: SPECIAL ANALYSIS
- Wolf tone detection
- Chladni pattern matching

SECTION 9: AUDIT TRAIL
- Software version, schema version
- Integrity hash, raw data links
- Provenance chain

Usage:
    from tap_tone_pi.bending.qa_lab_spec import (
        QALabSpecEntry,
        build_qa_lab_spec_entry,
        export_qa_lab_csv,
    )
"""

from __future__ import annotations

import csv
import hashlib
import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Import from sister modules
from .gore_spreadsheet import (
    cross_validate_modulus,
    dynamic_modulus_from_frequency,
    DEFAULT_CROSSVAL_THRESHOLD_PCT,
    _sha256,
)
from .gore_stiffness import (
    stiffness_index,
    thickness_for_target_SI,
    get_preset,
)


# =============================================================================
# Schema Version
# =============================================================================

SCHEMA_VERSION = "1.0.0"
SOFTWARE_VERSION = "tap_tone_pi 2026.02"


# =============================================================================
# Section 1: Sample Identification & Traceability
# =============================================================================


@dataclass
class SampleIdentification:
    """Unique sample markers and traceability."""

    # Core identification
    specimen_id: str = ""
    batch_id: Optional[str] = None
    lot_number: Optional[str] = None
    material_source: Optional[str] = None

    # Run identification
    run_id: Optional[str] = None
    session_id: Optional[str] = None

    # Material properties
    species: Optional[str] = None
    grain_direction: str = "L"  # L or C
    cut_date: Optional[str] = None
    conditioning_history: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None}


# =============================================================================
# Section 2: Test Parameters & Setup
# =============================================================================


@dataclass
class SetupParameters:
    """Test parameters and equipment setup."""

    # Timestamps
    test_timestamp_utc: str = ""

    # Personnel
    operator_id: Optional[str] = None

    # Equipment
    device_id: Optional[str] = None
    fixture_id: Optional[str] = None
    mic_id: Optional[str] = None
    mic_gain_db: Optional[float] = None
    preamp_model: Optional[str] = None

    # Calibration
    calibration_date: Optional[str] = None
    calibration_reference: Optional[str] = None
    is_calibrated: bool = False

    # Environment
    temperature_c: Optional[float] = None
    humidity_rh: Optional[float] = None
    ambient_notes: Optional[str] = None

    # Protocol
    protocol_version: Optional[str] = None
    sample_rate_hz: Optional[int] = None
    tap_count: Optional[int] = None
    tap_protocol: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None}


# =============================================================================
# Section 3: Primary Measurements
# =============================================================================


@dataclass
class PrimaryMeasurements:
    """Direct physical measurements."""

    # Dimensions
    length_mm: Optional[float] = None
    width_mm: Optional[float] = None
    thickness_mm: Optional[float] = None

    # Mass and density
    mass_g: Optional[float] = None
    density_kg_m3: Optional[float] = None

    # Acoustic measurements
    fundamental_freq_hz: Optional[float] = None
    peak_frequencies_hz: List[float] = field(default_factory=list)
    peak_amplitudes: List[float] = field(default_factory=list)

    # Bending measurements
    deflection_mm: Optional[float] = None
    force_N: Optional[float] = None
    span_mm: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None and v != []}


# =============================================================================
# Section 5: Modal Analysis
# =============================================================================


@dataclass
class ModeResult:
    """Single mode identification result."""

    mode_number: int
    frequency_hz: float
    damping_ratio: float
    quality_factor: float
    amplitude: float
    confidence: str  # "high", "medium", "low", "computational"
    stability_count: int = 0
    phase_deg: Optional[float] = None
    bandwidth_hz: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ModalAnalysis:
    """Complete modal analysis results."""

    modes: List[ModeResult] = field(default_factory=list)
    n_modes_identified: int = 0
    dominant_mode_freq_hz: Optional[float] = None
    dominant_mode_damping: Optional[float] = None
    dominant_mode_Q: Optional[float] = None
    mac_matrix: Optional[List[List[float]]] = None  # Modal Assurance Criterion
    modal_overlap_warning: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "n_modes_identified": self.n_modes_identified,
            "dominant_mode_freq_hz": self.dominant_mode_freq_hz,
            "dominant_mode_damping": self.dominant_mode_damping,
            "dominant_mode_Q": self.dominant_mode_Q,
            "modal_overlap_warning": self.modal_overlap_warning,
        }
        if self.modes:
            d["modes"] = [m.to_dict() for m in self.modes]
        if self.mac_matrix:
            d["mac_matrix"] = self.mac_matrix
        return {k: v for k, v in d.items() if v is not None}


# =============================================================================
# Section 6: Error Analysis (GUM-compliant)
# =============================================================================


@dataclass
class UncertaintyComponent:
    """Single uncertainty source."""

    name: str
    value: float  # Standard uncertainty
    unit: str
    type: str  # "type_a" or "type_b"
    sensitivity_coefficient: float = 1.0
    contribution_percent: float = 0.0
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ErrorAnalysis:
    """GUM-compliant uncertainty budget."""

    # Combined uncertainty
    combined_standard_uncertainty: Optional[float] = None
    expanded_uncertainty: Optional[float] = None
    coverage_factor: float = 2.0
    confidence_level_percent: float = 95.0

    # Effective degrees of freedom
    effective_dof: Optional[float] = None

    # Breakdown
    components: List[UncertaintyComponent] = field(default_factory=list)
    dominant_error_source: Optional[str] = None

    # Relative uncertainties
    E_uncertainty_GPa: Optional[float] = None
    E_uncertainty_percent: Optional[float] = None
    SI_uncertainty: Optional[float] = None
    SI_uncertainty_percent: Optional[float] = None
    frequency_uncertainty_hz: Optional[float] = None

    # Correlation
    static_dynamic_correlation: Optional[float] = None
    measurement_repeatability: Optional[float] = None  # From repeated measurements

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # Remove empty lists and None values
        d["components"] = [c.to_dict() if hasattr(c, "to_dict") else c for c in self.components]
        return {k: v for k, v in d.items() if v is not None and v != []}


# =============================================================================
# Section 7: Quality Assessment
# =============================================================================


@dataclass
class TriggeredRuleInfo:
    """Triggered quality rule info."""

    rule_id: str
    severity: str  # "hard" or "soft"
    message: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class QualityAssessment:
    """Quality verdict and checks."""

    # Overall verdict
    verdict: str = "pass"  # "pass", "warn", "fail"
    policy_version: str = ""

    # Triggered rules
    triggered_rules: List[TriggeredRuleInfo] = field(default_factory=list)
    error_count: int = 0
    warning_count: int = 0

    # Cross-validation
    crossval_agreement: Optional[str] = None  # "good", "marginal", "poor"
    crossval_delta_percent: Optional[float] = None

    # Individual checks
    signal_quality_ok: bool = True
    snr_db: Optional[float] = None
    clipping_detected: bool = False
    confidence_score: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["triggered_rules"] = [r.to_dict() if hasattr(r, "to_dict") else r for r in self.triggered_rules]
        return {k: v for k, v in d.items() if v is not None and v != []}


# =============================================================================
# Section 8: Special Analysis
# =============================================================================


@dataclass
class WolfToneAnalysis:
    """Wolf tone detection results."""

    wolf_detected: bool = False
    worst_wolf_freq_hz: Optional[float] = None
    worst_wolf_beat_hz: Optional[float] = None
    worst_wolf_severity: str = "none"  # "none", "mild", "moderate", "severe"
    n_wolf_pairs: int = 0

    # Recommendations
    recommendation: Optional[str] = None
    mass_addition_suggested_g: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class ChladniAnalysis:
    """Chladni pattern matching results."""

    pattern_matched: bool = False
    matched_pattern_id: Optional[str] = None
    match_confidence: Optional[float] = None
    expected_patterns: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None and v != []}


@dataclass
class SpecialAnalysis:
    """Wolf tone and Chladni pattern results."""

    wolf: WolfToneAnalysis = field(default_factory=WolfToneAnalysis)
    chladni: ChladniAnalysis = field(default_factory=ChladniAnalysis)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "wolf": self.wolf.to_dict(),
            "chladni": self.chladni.to_dict(),
        }


# =============================================================================
# Section 9: Audit Trail
# =============================================================================


@dataclass
class AuditTrail:
    """Provenance and audit information."""

    # Versions
    software_version: str = SOFTWARE_VERSION
    schema_version: str = SCHEMA_VERSION

    # Integrity
    entry_hash_sha256: Optional[str] = None

    # Data links
    raw_audio_path: Optional[str] = None
    raw_audio_sha256: Optional[str] = None
    bending_data_path: Optional[str] = None
    bending_data_sha256: Optional[str] = None
    peaks_data_path: Optional[str] = None
    peaks_data_sha256: Optional[str] = None

    # Reviewer
    reviewed_by: Optional[str] = None
    review_date: Optional[str] = None
    review_notes: Optional[str] = None

    # Export
    export_timestamp_utc: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


# =============================================================================
# Complete QA Lab Spec Entry
# =============================================================================


@dataclass
class QALabSpecEntry:
    """
    Complete QA/QC Laboratory Specification Sheet Entry.

    Combines all sections into a single, comprehensive record for
    tonewood acoustic analysis with full traceability.

    This is the authoritative data structure for QA/QC reporting.
    """

    # === SECTION 1: Sample Identification ===
    sample: SampleIdentification = field(default_factory=SampleIdentification)

    # === SECTION 2: Test Setup ===
    setup: SetupParameters = field(default_factory=SetupParameters)

    # === SECTION 3: Primary Measurements ===
    measurements: PrimaryMeasurements = field(default_factory=PrimaryMeasurements)

    # === SECTION 4: Derived Properties (from Gore spreadsheet) ===
    E_static_GPa: Optional[float] = None
    E_dynamic_GPa: Optional[float] = None
    E_uncorrected_GPa: Optional[float] = None
    shear_correction_applied: bool = False
    shear_correction_percent: Optional[float] = None
    fit_r_squared: Optional[float] = None

    SI: Optional[float] = None  # Stiffness Index (GPa·mm³)
    SI_target: Optional[float] = None
    h_target_mm: Optional[float] = None

    specific_stiffness: Optional[float] = None  # E/ρ
    wave_speed_m_s: Optional[float] = None  # √(E/ρ)
    radiation_ratio: Optional[float] = None  # c/ρ

    # Instrument matching
    instrument_type: Optional[str] = None
    preset_SI_typical: Optional[float] = None
    preset_h_recommended_mm: Optional[float] = None
    preset_match_status: Optional[str] = None

    # === SECTION 5: Modal Analysis ===
    modal: ModalAnalysis = field(default_factory=ModalAnalysis)

    # === SECTION 6: Error Analysis ===
    errors: ErrorAnalysis = field(default_factory=ErrorAnalysis)

    # === SECTION 7: Quality Assessment ===
    quality: QualityAssessment = field(default_factory=QualityAssessment)

    # === SECTION 8: Special Analysis ===
    special: SpecialAnalysis = field(default_factory=SpecialAnalysis)

    # === SECTION 9: Audit Trail ===
    audit: AuditTrail = field(default_factory=AuditTrail)

    # === Warnings ===
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        d = {
            "schema_id": "qa_lab_spec_v1",
            "schema_version": SCHEMA_VERSION,
            # Section 1
            "sample_identification": self.sample.to_dict(),
            # Section 2
            "test_setup": self.setup.to_dict(),
            # Section 3
            "primary_measurements": self.measurements.to_dict(),
            # Section 4: Derived
            "derived_properties": {
                "E_static_GPa": self.E_static_GPa,
                "E_dynamic_GPa": self.E_dynamic_GPa,
                "E_uncorrected_GPa": self.E_uncorrected_GPa,
                "shear_correction": {
                    "applied": self.shear_correction_applied,
                    "percent": self.shear_correction_percent,
                },
                "fit_r_squared": self.fit_r_squared,
                "stiffness_index": {
                    "SI": self.SI,
                    "SI_target": self.SI_target,
                    "h_target_mm": self.h_target_mm,
                },
                "specific_stiffness": self.specific_stiffness,
                "wave_speed_m_s": self.wave_speed_m_s,
                "radiation_ratio": self.radiation_ratio,
                "instrument_match": {
                    "type": self.instrument_type,
                    "preset_SI_typical": self.preset_SI_typical,
                    "preset_h_recommended_mm": self.preset_h_recommended_mm,
                    "status": self.preset_match_status,
                } if self.instrument_type else None,
            },
            # Section 5
            "modal_analysis": self.modal.to_dict(),
            # Section 6
            "error_analysis": self.errors.to_dict(),
            # Section 7
            "quality_assessment": self.quality.to_dict(),
            # Section 8
            "special_analysis": self.special.to_dict(),
            # Section 9
            "audit_trail": self.audit.to_dict(),
            # Warnings
            "warnings": self.warnings if self.warnings else None,
        }
        # Clean up None values at top level
        return {k: v for k, v in d.items() if v is not None}

    def compute_entry_hash(self) -> str:
        """Compute SHA-256 hash of entry for integrity verification."""
        # Use deterministic JSON serialization
        d = self.to_dict()
        # Remove the hash field itself if present
        if "audit_trail" in d:
            d["audit_trail"].pop("entry_hash_sha256", None)
        content = json.dumps(d, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(content.encode("utf-8")).hexdigest()


# =============================================================================
# Builder Helpers — extracted from build_qa_lab_spec_entry (CC reduction)
# Each helper addresses one section of the QA lab spec.
# Pure data logic; I/O (JSON loads) is kept minimal and explicit.
# =============================================================================


def _load_bending_data(
    entry: "QALabSpecEntry",
    bending_json_path: str,
    warnings: List[str],
) -> Optional[float]:
    """Load bending JSON and populate entry fields.

    Returns:
        E_static (GPa) or None if loading failed.
    """
    try:
        with open(bending_json_path, "r", encoding="utf-8") as f:
            bending = json.load(f)
        E_static = bending.get("E_GPa")
        entry.E_static_GPa = round(E_static, 3) if E_static else None
        entry.E_uncorrected_GPa = round(
            bending.get("E_euler_bernoulli_GPa", E_static or 0), 3
        )

        shear_info = bending.get("shear_correction", {})
        entry.shear_correction_applied = shear_info.get("applied", False)
        entry.shear_correction_percent = round(
            shear_info.get("reduction_percent", 0), 2
        )

        fit_info = bending.get("fit", {})
        entry.fit_r_squared = round(fit_info.get("r2", 0), 4)

        entry.audit.bending_data_path = bending_json_path
        entry.audit.bending_data_sha256 = _sha256(Path(bending_json_path))
        return E_static
    except Exception as e:
        warnings.append(f"Failed to load bending data: {e}")
        return None


def _load_acoustic_data(
    entry: "QALabSpecEntry",
    acoustic_json_path: str,
    density_kg_m3: Optional[float],
    length_mm: Optional[float],
    thickness_mm: float,
    warnings: List[str],
) -> Tuple[Optional[float], Optional[float]]:
    """Load acoustic JSON, extract peaks, compute dynamic E.

    Returns:
        (measured_freq, E_dynamic) — either may be None.
    """
    measured_freq: Optional[float] = None
    E_dynamic: Optional[float] = None
    try:
        with open(acoustic_json_path, "r", encoding="utf-8") as f:
            peaks = json.load(f)

        # Extract frequencies from multiple possible formats
        if "peaks_hz" in peaks and peaks["peaks_hz"]:
            freqs = peaks["peaks_hz"]
            measured_freq = min(freqs)
            entry.measurements.peak_frequencies_hz = freqs
        elif "peaks" in peaks and peaks["peaks"]:
            peak_list = peaks["peaks"]
            if isinstance(peak_list[0], dict):
                freqs = [
                    p.get("frequency_hz", p.get("freq_hz", 0)) for p in peak_list
                ]
                amps = [p.get("amplitude", 0) for p in peak_list]
                measured_freq = min(f for f in freqs if f > 0)
                entry.measurements.peak_frequencies_hz = freqs
                entry.measurements.peak_amplitudes = amps
        elif "fundamental_hz" in peaks:
            measured_freq = peaks["fundamental_hz"]

        entry.measurements.fundamental_freq_hz = (
            round(measured_freq, 1) if measured_freq else None
        )

        # Compute dynamic E if we have the required inputs
        if measured_freq and density_kg_m3 and length_mm:
            E_dynamic = dynamic_modulus_from_frequency(
                measured_freq, density_kg_m3, length_mm, thickness_mm
            )
            entry.E_dynamic_GPa = round(E_dynamic, 3)

        entry.audit.peaks_data_path = acoustic_json_path
        entry.audit.peaks_data_sha256 = _sha256(Path(acoustic_json_path))
    except Exception as e:
        warnings.append(f"Failed to load acoustic data: {e}")
    return measured_freq, E_dynamic


def _apply_crossvalidation(
    entry: "QALabSpecEntry",
    E_static: float,
    E_dynamic: Optional[float],
    measured_freq: Optional[float],
    density_kg_m3: Optional[float],
    length_mm: Optional[float],
    thickness_mm: float,
    crossval_threshold_pct: float,
    warnings: List[str],
) -> None:
    """Run cross-validation between static and dynamic modulus."""
    crossval = cross_validate_modulus(
        E_static_GPa=E_static,
        E_dynamic_GPa=E_dynamic,
        measured_freq_hz=measured_freq,
        density_kg_m3=density_kg_m3,
        length_mm=length_mm,
        thickness_mm=thickness_mm,
        threshold_percent=crossval_threshold_pct,
    )
    entry.quality.crossval_agreement = crossval.agreement
    entry.quality.crossval_delta_percent = crossval.delta_percent
    warnings.extend(crossval.warnings)


def _compute_stiffness_index(
    entry: "QALabSpecEntry",
    E_best: float,
    thickness_mm: float,
    direction: str,
    instrument: Optional[str],
    SI_target: Optional[float],
) -> None:
    """Compute SI, preset matching, and target thickness."""
    entry.SI = round(stiffness_index(E_best, thickness_mm), 2)

    preset = get_preset(instrument) if instrument else None
    target = SI_target

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


def _compute_derived_physics(
    entry: "QALabSpecEntry",
    E_best: float,
    density_kg_m3: float,
) -> None:
    """Compute wave speed, specific stiffness, radiation ratio."""
    import math

    E_Pa = E_best * 1e9
    spec = E_Pa / density_kg_m3
    c = math.sqrt(spec)
    entry.specific_stiffness = round(spec, 0)
    entry.wave_speed_m_s = round(c, 0)
    entry.radiation_ratio = round(c / density_kg_m3, 4)


def _load_modal_data(
    entry: "QALabSpecEntry",
    modes_json_path: str,
    warnings: List[str],
) -> None:
    """Load modal analysis JSON and populate entry.modal."""
    try:
        with open(modes_json_path, "r", encoding="utf-8") as f:
            modes_data = json.load(f)

        modes_list = modes_data.get("modes", [])
        entry.modal.n_modes_identified = len(modes_list)

        for i, m in enumerate(modes_list):
            mode_result = ModeResult(
                mode_number=i + 1,
                frequency_hz=m.get("frequency_hz", 0),
                damping_ratio=m.get("damping_ratio", 0),
                quality_factor=m.get("quality_factor", m.get("Q", 0)),
                amplitude=m.get("amplitude", 0),
                confidence=m.get("confidence", "medium"),
                stability_count=m.get("stability_count", 0),
                phase_deg=m.get("phase_deg"),
                bandwidth_hz=m.get("bandwidth_hz"),
            )
            entry.modal.modes.append(mode_result)

        # Find dominant mode
        if modes_list:
            dominant = max(modes_list, key=lambda x: x.get("amplitude", 0))
            entry.modal.dominant_mode_freq_hz = dominant.get("frequency_hz")
            entry.modal.dominant_mode_damping = dominant.get("damping_ratio")
            entry.modal.dominant_mode_Q = dominant.get(
                "quality_factor", dominant.get("Q")
            )

    except Exception as e:
        warnings.append(f"Failed to load modal data: {e}")


def _load_uncertainty_data(
    entry: "QALabSpecEntry",
    uncertainty_json_path: str,
    E_best: Optional[float],
    warnings: List[str],
) -> None:
    """Load uncertainty budget JSON and populate entry.errors."""
    try:
        with open(uncertainty_json_path, "r", encoding="utf-8") as f:
            unc_data = json.load(f)

        entry.errors.combined_standard_uncertainty = unc_data.get(
            "combined_standard_uncertainty"
        )
        entry.errors.expanded_uncertainty = unc_data.get("expanded_uncertainty")
        entry.errors.coverage_factor = unc_data.get("coverage_factor", 2.0)
        entry.errors.effective_dof = unc_data.get("degrees_of_freedom")
        entry.errors.E_uncertainty_percent = unc_data.get(
            "relative_uncertainty_percent"
        )

        if entry.errors.combined_standard_uncertainty and E_best:
            entry.errors.E_uncertainty_GPa = entry.errors.combined_standard_uncertainty

        # Components
        for comp in unc_data.get("components", []):
            entry.errors.components.append(
                UncertaintyComponent(
                    name=comp.get("name", ""),
                    value=comp.get("value", 0),
                    unit=comp.get("unit", ""),
                    type=comp.get("type", "type_b"),
                    sensitivity_coefficient=comp.get("sensitivity_coefficient", 1.0),
                    description=comp.get("description", ""),
                )
            )

        # Find dominant source
        if entry.errors.components:
            dominant = max(entry.errors.components, key=lambda x: x.value)
            entry.errors.dominant_error_source = dominant.name

    except Exception as e:
        warnings.append(f"Failed to load uncertainty data: {e}")


def _load_quality_data(
    entry: "QALabSpecEntry",
    quality_json_path: str,
    warnings: List[str],
) -> None:
    """Load quality assessment JSON and populate entry.quality."""
    try:
        with open(quality_json_path, "r", encoding="utf-8") as f:
            qual_data = json.load(f)

        entry.quality.verdict = qual_data.get("verdict", "pass")
        entry.quality.policy_version = qual_data.get("policy_version", "")
        entry.quality.error_count = qual_data.get("error_count", 0)
        entry.quality.warning_count = qual_data.get("warning_count", 0)

        for rule in qual_data.get("triggered_rules", []):
            entry.quality.triggered_rules.append(
                TriggeredRuleInfo(
                    rule_id=rule.get("rule_id", ""),
                    severity=rule.get("severity", "soft"),
                    message=rule.get("message", ""),
                )
            )

    except Exception as e:
        warnings.append(f"Failed to load quality data: {e}")


def _load_wolf_data(
    entry: "QALabSpecEntry",
    wolf_json_path: str,
    warnings: List[str],
) -> None:
    """Load wolf-tone analysis JSON and populate entry.special."""
    try:
        with open(wolf_json_path, "r", encoding="utf-8") as f:
            wolf_data = json.load(f)

        worst = wolf_data.get("worst_wolf", {})
        entry.special.wolf = WolfToneAnalysis(
            wolf_detected=wolf_data.get("n_pairs", 0) > 0,
            worst_wolf_freq_hz=worst.get("center_freq_hz"),
            worst_wolf_beat_hz=worst.get("beat_freq_hz"),
            worst_wolf_severity=worst.get("severity", "none"),
            n_wolf_pairs=wolf_data.get("n_pairs", 0),
        )

    except Exception as e:
        warnings.append(f"Failed to load wolf data: {e}")


# =============================================================================
# Builder — Orchestrator
# =============================================================================


def build_qa_lab_spec_entry(
    # Core identification
    specimen_id: str,
    direction: str = "L",
    thickness_mm: float = 3.0,
    # Session metadata
    run_id: Optional[str] = None,
    session_id: Optional[str] = None,
    operator_id: Optional[str] = None,
    device_id: Optional[str] = None,
    fixture_id: Optional[str] = None,
    mic_id: Optional[str] = None,
    calibration_date: Optional[str] = None,
    is_calibrated: bool = False,
    # Environment
    temperature_c: Optional[float] = None,
    humidity_rh: Optional[float] = None,
    # Material
    species: Optional[str] = None,
    batch_id: Optional[str] = None,
    density_kg_m3: Optional[float] = None,
    length_mm: Optional[float] = None,
    width_mm: Optional[float] = None,
    mass_g: Optional[float] = None,
    # Data sources
    bending_json_path: Optional[str] = None,
    acoustic_json_path: Optional[str] = None,
    modes_json_path: Optional[str] = None,
    wolf_json_path: Optional[str] = None,
    uncertainty_json_path: Optional[str] = None,
    quality_json_path: Optional[str] = None,
    # Instrument
    instrument: Optional[str] = None,
    SI_target: Optional[float] = None,
    # Settings
    crossval_threshold_pct: float = DEFAULT_CROSSVAL_THRESHOLD_PCT,
) -> QALabSpecEntry:
    """
    Build a complete QA Lab Spec entry from various data sources.

    This is the main entry point for creating a comprehensive QA/QC record.
    It integrates data from multiple analysis modules into a single entry.

    Args:
        specimen_id: Unique specimen identifier
        direction: Grain direction ("L" or "C")
        thickness_mm: Specimen thickness
        ... (see function signature for all parameters)

    Returns:
        Complete QALabSpecEntry with all available data populated
    """
    entry = QALabSpecEntry()
    warnings: List[str] = []

    # === Section 1: Sample Identification ===
    entry.sample = SampleIdentification(
        specimen_id=specimen_id,
        grain_direction=direction.upper(),
        species=species,
        batch_id=batch_id,
        run_id=run_id,
        session_id=session_id,
    )

    # === Section 2: Test Setup ===
    entry.setup = SetupParameters(
        test_timestamp_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        operator_id=operator_id,
        device_id=device_id,
        fixture_id=fixture_id,
        mic_id=mic_id,
        calibration_date=calibration_date,
        is_calibrated=is_calibrated,
        temperature_c=temperature_c,
        humidity_rh=humidity_rh,
    )

    # === Section 3: Primary Measurements ===
    entry.measurements = PrimaryMeasurements(
        thickness_mm=thickness_mm,
        length_mm=length_mm,
        width_mm=width_mm,
        mass_g=mass_g,
        density_kg_m3=density_kg_m3,
    )

    # === Section 4: Derived Properties ===
    E_static: Optional[float] = None
    E_dynamic: Optional[float] = None
    measured_freq: Optional[float] = None

    if bending_json_path:
        E_static = _load_bending_data(entry, bending_json_path, warnings)

    if acoustic_json_path:
        measured_freq, E_dynamic = _load_acoustic_data(
            entry, acoustic_json_path, density_kg_m3, length_mm, thickness_mm, warnings
        )

    if E_static is not None:
        _apply_crossvalidation(
            entry, E_static, E_dynamic, measured_freq,
            density_kg_m3, length_mm, thickness_mm,
            crossval_threshold_pct, warnings,
        )

    E_best = E_static or E_dynamic
    if E_best is not None:
        _compute_stiffness_index(
            entry, E_best, thickness_mm, direction, instrument, SI_target
        )

    if E_best is not None and density_kg_m3 is not None:
        _compute_derived_physics(entry, E_best, density_kg_m3)

    # === Section 5: Modal Analysis ===
    if modes_json_path:
        _load_modal_data(entry, modes_json_path, warnings)

    # === Section 6: Error Analysis ===
    if uncertainty_json_path:
        _load_uncertainty_data(entry, uncertainty_json_path, E_best, warnings)

    # === Section 7: Quality Assessment ===
    if quality_json_path:
        _load_quality_data(entry, quality_json_path, warnings)

    # === Section 8: Special Analysis ===
    if wolf_json_path:
        _load_wolf_data(entry, wolf_json_path, warnings)

    # === Section 9: Audit Trail ===
    entry.audit.export_timestamp_utc = time.strftime(
        "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
    )

    # Store warnings
    entry.warnings = warnings

    # Compute entry hash
    entry.audit.entry_hash_sha256 = entry.compute_entry_hash()

    return entry


# =============================================================================
# CSV Export
# =============================================================================


QA_LAB_CSV_COLUMNS = [
    # Section 1: Sample ID
    "specimen_id",
    "batch_id",
    "run_id",
    "species",
    "grain_direction",
    # Section 2: Setup
    "test_timestamp_utc",
    "operator_id",
    "device_id",
    "is_calibrated",
    "temperature_c",
    "humidity_rh",
    # Section 3: Measurements
    "thickness_mm",
    "length_mm",
    "width_mm",
    "density_kg_m3",
    "fundamental_freq_hz",
    # Section 4: Derived
    "E_static_GPa",
    "E_dynamic_GPa",
    "SI",
    "SI_target",
    "h_target_mm",
    "crossval_agreement",
    "crossval_delta_percent",
    "wave_speed_m_s",
    # Section 5: Modal
    "n_modes_identified",
    "dominant_mode_freq_hz",
    "dominant_mode_damping",
    "dominant_mode_Q",
    # Section 6: Errors
    "expanded_uncertainty",
    "E_uncertainty_percent",
    "dominant_error_source",
    # Section 7: Quality
    "verdict",
    "error_count",
    "warning_count",
    "confidence_score",
    "snr_db",
    # Section 8: Special
    "wolf_detected",
    "worst_wolf_severity",
    "worst_wolf_freq_hz",
    # Section 9: Audit
    "entry_hash_sha256",
    # Misc
    "instrument_type",
    "preset_match_status",
    "warnings",
]


def export_qa_lab_csv(
    entries: List[QALabSpecEntry],
    csv_path: str,
) -> None:
    """Export QA Lab Spec entries to CSV format."""
    path = Path(csv_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=QA_LAB_CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()

        for entry in entries:
            row = {
                # Section 1
                "specimen_id": entry.sample.specimen_id,
                "batch_id": entry.sample.batch_id,
                "run_id": entry.sample.run_id,
                "species": entry.sample.species,
                "grain_direction": entry.sample.grain_direction,
                # Section 2
                "test_timestamp_utc": entry.setup.test_timestamp_utc,
                "operator_id": entry.setup.operator_id,
                "device_id": entry.setup.device_id,
                "is_calibrated": entry.setup.is_calibrated,
                "temperature_c": entry.setup.temperature_c,
                "humidity_rh": entry.setup.humidity_rh,
                # Section 3
                "thickness_mm": entry.measurements.thickness_mm,
                "length_mm": entry.measurements.length_mm,
                "width_mm": entry.measurements.width_mm,
                "density_kg_m3": entry.measurements.density_kg_m3,
                "fundamental_freq_hz": entry.measurements.fundamental_freq_hz,
                # Section 4
                "E_static_GPa": entry.E_static_GPa,
                "E_dynamic_GPa": entry.E_dynamic_GPa,
                "SI": entry.SI,
                "SI_target": entry.SI_target,
                "h_target_mm": entry.h_target_mm,
                "crossval_agreement": entry.quality.crossval_agreement,
                "crossval_delta_percent": entry.quality.crossval_delta_percent,
                "wave_speed_m_s": entry.wave_speed_m_s,
                # Section 5
                "n_modes_identified": entry.modal.n_modes_identified,
                "dominant_mode_freq_hz": entry.modal.dominant_mode_freq_hz,
                "dominant_mode_damping": entry.modal.dominant_mode_damping,
                "dominant_mode_Q": entry.modal.dominant_mode_Q,
                # Section 6
                "expanded_uncertainty": entry.errors.expanded_uncertainty,
                "E_uncertainty_percent": entry.errors.E_uncertainty_percent,
                "dominant_error_source": entry.errors.dominant_error_source,
                # Section 7
                "verdict": entry.quality.verdict,
                "error_count": entry.quality.error_count,
                "warning_count": entry.quality.warning_count,
                "confidence_score": entry.quality.confidence_score,
                "snr_db": entry.quality.snr_db,
                # Section 8
                "wolf_detected": entry.special.wolf.wolf_detected,
                "worst_wolf_severity": entry.special.wolf.worst_wolf_severity,
                "worst_wolf_freq_hz": entry.special.wolf.worst_wolf_freq_hz,
                # Section 9
                "entry_hash_sha256": entry.audit.entry_hash_sha256[:16] + "..." if entry.audit.entry_hash_sha256 else None,
                # Misc
                "instrument_type": entry.instrument_type,
                "preset_match_status": entry.preset_match_status,
                "warnings": "; ".join(entry.warnings) if entry.warnings else "",
            }
            writer.writerow(row)


def export_qa_lab_json(
    entries: List[QALabSpecEntry],
    json_path: str,
) -> None:
    """Export QA Lab Spec entries to JSON format."""
    path = Path(json_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    output = {
        "schema_id": "qa_lab_spec_collection_v1",
        "schema_version": SCHEMA_VERSION,
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "entry_count": len(entries),
        "entries": [e.to_dict() for e in entries],
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
