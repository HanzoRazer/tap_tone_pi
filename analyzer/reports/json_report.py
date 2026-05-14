"""
JSON report generation for tap tone analysis.

Produces machine-readable analysis results for integration
with other tools and databases.
"""

import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path


def generate_json_report(
    session_meta: Dict[str, Any],
    spectrum_data: Dict[str, Any],
    peaks: List[Dict[str, float]],
    wood_properties: Optional[Dict[str, Any]] = None,
    coherence_stats: Optional[Dict[str, Any]] = None,
    output_path: Optional[str] = None,
    include_spectrum: bool = False,
) -> Dict[str, Any]:
    """
    Generate a JSON report for tap tone analysis.

    Args:
        session_meta: Session metadata
        spectrum_data: Spectrum data
        peaks: List of detected peaks
        wood_properties: Estimated wood properties
        coherence_stats: Coherence quality statistics
        output_path: Optional path to save the report
        include_spectrum: Whether to include full spectrum data (large)

    Returns:
        Report dictionary
    """
    report = {
        "schema_id": "tap_tone_analysis_report",
        "schema_version": "1.0",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "generator": "tap_tone_pi_analyzer",
        "generator_version": "0.1.0",
        "specimen": {
            "id": session_meta.get("specimen_id"),
            "species": session_meta.get("species"),
            "grade": session_meta.get("grade"),
            "dimensions_mm": session_meta.get("dimensions_mm"),
            "weight_g": session_meta.get("weight_g"),
            "moisture_content_pct": session_meta.get("moisture_content_pct"),
        },
        "measurement": {
            "device_id": session_meta.get("device_id"),
            "captured_at": session_meta.get("created_at_utc"),
            "operator": session_meta.get("operator"),
            "notes": session_meta.get("notes"),
        },
        "analysis": {
            "peaks": _sanitize_peaks(peaks),
            "peak_count": len(peaks),
            "frequency_range_hz": _get_freq_range(spectrum_data),
            "coherence_quality": coherence_stats,
        },
    }

    # Add wood properties if available
    if wood_properties:
        report["wood_properties"] = wood_properties

    # Optionally include full spectrum (warning: large)
    if include_spectrum:
        report["spectrum"] = {
            "freq_hz": spectrum_data.get("freq_hz"),
            "H_mag": spectrum_data.get("H_mag"),
            "coherence": spectrum_data.get("coherence"),
            "phase_deg": spectrum_data.get("phase_deg"),
            "point_count": len(spectrum_data.get("freq_hz", [])),
        }

    # Add summary
    report["summary"] = _generate_summary(peaks, wood_properties, coherence_stats)

    if output_path:
        Path(output_path).write_text(json.dumps(report, indent=2), encoding="utf-8")

    return report


def _sanitize_peaks(peaks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Ensure peaks are JSON-serializable and contain expected fields."""
    sanitized = []
    for peak in peaks:
        sanitized.append(
            {
                "freq_hz": round(peak.get("freq_hz", 0), 2),
                "magnitude": round(peak.get("magnitude", 0), 6),
                "coherence": round(peak.get("coherence", 0), 4)
                if peak.get("coherence")
                else None,
                "mode": peak.get("mode"),
                "q_factor": round(peak.get("q_factor", 0), 1)
                if peak.get("q_factor")
                else None,
            }
        )
    return sanitized


def _get_freq_range(spectrum_data: Dict[str, Any]) -> Dict[str, float]:
    """Get frequency range from spectrum data."""
    freq = spectrum_data.get("freq_hz", [])
    if freq:
        return {"min_hz": min(freq), "max_hz": max(freq)}
    return {"min_hz": 0, "max_hz": 0}


def _generate_summary(
    peaks: List[Dict[str, float]],
    wood_properties: Optional[Dict[str, Any]],
    coherence_stats: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Generate a human-readable summary."""
    summary = {
        "measurement_quality": "unknown",
        "wood_quality": "unknown",
        "key_findings": [],
    }

    # Assess measurement quality
    if coherence_stats:
        grade = coherence_stats.get("quality_grade", "?")
        if grade in ["A", "B"]:
            summary["measurement_quality"] = "good"
            summary["key_findings"].append("Measurement coherence is good")
        elif grade == "C":
            summary["measurement_quality"] = "acceptable"
            summary["key_findings"].append("Measurement has moderate noise")
        else:
            summary["measurement_quality"] = "poor"
            summary["key_findings"].append(
                "Measurement quality is low - consider re-measuring"
            )

    # Assess wood quality
    if wood_properties:
        grade = wood_properties.get("quality_grade", "?")
        rad_coeff = wood_properties.get("radiation_coefficient", 0)

        if grade in ["AAA", "AA"]:
            summary["wood_quality"] = "excellent"
            summary["key_findings"].append(
                f"Excellent radiation coefficient: {rad_coeff}"
            )
        elif grade == "A":
            summary["wood_quality"] = "good"
            summary["key_findings"].append(f"Good radiation coefficient: {rad_coeff}")
        elif grade == "B":
            summary["wood_quality"] = "average"
            summary["key_findings"].append(
                f"Average radiation coefficient: {rad_coeff}"
            )
        else:
            summary["wood_quality"] = "below_average"
            summary["key_findings"].append(
                f"Below average radiation coefficient: {rad_coeff}"
            )

    # Add peak findings
    if peaks:
        fundamental = peaks[0]["freq_hz"] if peaks else 0
        summary["key_findings"].append(f"Fundamental frequency: {fundamental:.1f} Hz")
        summary["key_findings"].append(f"Detected {len(peaks)} resonance modes")

    return summary


def load_json_report(file_path: str) -> Dict[str, Any]:
    """Load a JSON report from file."""
    return json.loads(Path(file_path).read_text(encoding="utf-8"))
