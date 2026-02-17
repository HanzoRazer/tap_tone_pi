#!/usr/bin/env python3
"""
Generate a sample viewer pack with realistic tap tone data.

This creates synthetic data that mimics real wood acoustic measurements
for testing the analyzer application.
"""

import json
import csv
import zipfile
import numpy as np
from pathlib import Path
from datetime import datetime


def generate_spectrum_data(
    fundamental_freq: float = 180.0,
    num_modes: int = 8,
    freq_range: tuple = (10, 2000),
    num_points: int = 1000,
    noise_level: float = 0.05,
    coherence_base: float = 0.92,
) -> dict:
    """
    Generate realistic spectrum data for a wood sample.

    Args:
        fundamental_freq: Fundamental frequency in Hz
        num_modes: Number of resonance modes to simulate
        freq_range: (min, max) frequency range
        num_points: Number of frequency points
        noise_level: Background noise level
        coherence_base: Base coherence level

    Returns:
        Dictionary with freq_hz, H_mag, coherence, phase_deg
    """
    freq_hz = np.linspace(freq_range[0], freq_range[1], num_points)

    # Start with noise floor
    magnitude = (
        np.ones(num_points) * noise_level * np.random.uniform(0.5, 1.5, num_points)
    )

    # Add resonance peaks
    mode_freqs = []
    for i in range(num_modes):
        if i == 0:
            mode_freq = fundamental_freq
        else:
            # Modes roughly follow harmonic series with some deviation
            mode_freq = fundamental_freq * (i + 1) * np.random.uniform(0.9, 1.1)

        mode_freqs.append(mode_freq)

        # Peak amplitude decreases with mode number
        amplitude = 1.0 / (i + 1) ** 0.5 * np.random.uniform(0.7, 1.3)

        # Q factor varies
        q_factor = np.random.uniform(30, 100)
        bandwidth = mode_freq / q_factor

        # Lorentzian peak shape
        peak = amplitude / (1 + ((freq_hz - mode_freq) / (bandwidth / 2)) ** 2)
        magnitude += peak

    # Convert to log scale (dB-like)
    magnitude = magnitude / magnitude.max()

    # Generate coherence (higher near peaks, lower in valleys)
    coherence = np.ones(num_points) * coherence_base
    for mode_freq in mode_freqs:
        # Boost coherence near peaks
        peak_boost = 0.08 * np.exp(-(((freq_hz - mode_freq) / 50) ** 2))
        coherence += peak_boost

    # Add some noise to coherence
    coherence += np.random.uniform(-0.05, 0.05, num_points)
    coherence = np.clip(coherence, 0.3, 1.0)

    # Generate phase (wraps around at peaks)
    phase = np.zeros(num_points)
    for mode_freq in mode_freqs:
        # Phase shifts near resonances
        phase += np.arctan2(freq_hz - mode_freq, 10) * 30
    phase = phase % 360 - 180  # Wrap to -180 to 180

    return {
        "freq_hz": freq_hz.tolist(),
        "H_mag": magnitude.tolist(),
        "coherence": coherence.tolist(),
        "phase_deg": phase.tolist(),
        "mode_frequencies": mode_freqs,
    }


def generate_peaks_data(spectrum_data: dict) -> list:
    """Extract peaks from spectrum data."""
    freq_hz = np.array(spectrum_data["freq_hz"])
    magnitude = np.array(spectrum_data["H_mag"])
    coherence = np.array(spectrum_data["coherence"])

    peaks = []
    for i, mode_freq in enumerate(spectrum_data["mode_frequencies"]):
        # Find closest index
        idx = np.argmin(np.abs(freq_hz - mode_freq))

        peaks.append(
            {
                "freq_hz": float(freq_hz[idx]),
                "magnitude": float(magnitude[idx]),
                "coherence": float(coherence[idx]),
                "mode": f"Mode {i + 1}" if i > 0 else "Fundamental",
                "q_factor": float(np.random.uniform(30, 100)),
            }
        )

    return peaks


def generate_session_meta(specimen_name: str = "Sitka Spruce #42") -> dict:
    """Generate session metadata."""
    return {
        "schema_version": "1.0",
        "specimen_id": specimen_name,
        "species": "Sitka Spruce",
        "grade": "Master",
        "dimensions_mm": {"length": 520, "width": 180, "thickness": 3.2},
        "weight_g": 82.5,
        "moisture_content_pct": 6.8,
        "created_at_utc": datetime.utcnow().isoformat() + "Z",
        "device_id": "tap_tone_pi_v1",
        "operator": "Sample Generator",
        "notes": "Synthetic test data for analyzer development",
    }


def generate_capture_meta() -> dict:
    """Generate capture metadata."""
    return {
        "schema_version": "1.0",
        "created_at_utc": datetime.utcnow().isoformat() + "Z",
        "sample_rate_hz": 48000,
        "channels": 2,
        "tap_count": 10,
        "averaging_method": "linear",
        "excitation": {"type": "impulse", "tool": "wooden_dowel", "location": "center"},
        "microphone": {"type": "condenser", "position_mm": [100, 0, 50]},
        "environment": {"temp_c": 22.5, "humidity_rh": 45},
    }


def generate_transfer_function_json(spectrum_data: dict) -> dict:
    """
    Generate transfer function data in JSON format (parallel arrays).

    This format is used by many acoustic analysis tools.
    """
    return {
        "schema_id": "transfer_function_v1",
        "frequencies": spectrum_data["freq_hz"],
        "magnitude": spectrum_data["H_mag"],
        "phase": spectrum_data["phase_deg"],
        "coherence": spectrum_data["coherence"],
        "metadata": {
            "units": {"frequency": "Hz", "magnitude": "linear", "phase": "degrees"},
            "averaging": "10 averages",
        },
    }


def generate_wsi_curve_data(spectrum_data: dict, peaks: list) -> dict:
    """
    Generate Wolf Stress Index (WSI) curve data.

    WSI identifies problematic frequencies where wolf notes might occur.
    """
    freq_hz = np.array(spectrum_data["freq_hz"])
    coherence = np.array(spectrum_data["coherence"])
    num_points = len(freq_hz)

    # Generate synthetic WSI curve
    # Higher WSI near certain frequency regions (simulating wolf note zones)
    wsi = np.zeros(num_points)

    # Add some problem zones
    problem_freqs = [np.random.uniform(150, 250), np.random.uniform(350, 450)]

    for prob_freq in problem_freqs:
        # Create a peak in WSI at problem frequency
        wsi += 0.8 * np.exp(-(((freq_hz - prob_freq) / 30) ** 2))

    # Add baseline variation
    wsi += np.random.uniform(0.05, 0.2, num_points)
    wsi = np.clip(wsi, 0, 1)

    # Localization (how localized the energy is)
    loc = np.random.uniform(0.1, 0.5, num_points)

    # Gradient
    grad = np.gradient(wsi)
    grad = (grad - grad.min()) / (grad.max() - grad.min() + 0.001)

    # Phase disorder (higher near problem zones)
    phase_disorder = 0.3 + 0.5 * wsi + np.random.uniform(-0.1, 0.1, num_points)
    phase_disorder = np.clip(phase_disorder, 0, 1)

    # Coherence mean
    coh_mean = coherence

    # Admissible regions (where WSI is low)
    admissible = (wsi < 0.5).tolist()

    return {
        "schema_id": "wsi_curve_v1",
        "freq_hz": freq_hz.tolist(),
        "wsi": wsi.tolist(),
        "loc": loc.tolist(),
        "grad": grad.tolist(),
        "phase_disorder": phase_disorder.tolist(),
        "coh_mean": coh_mean.tolist(),
        "admissible": admissible,
        "problem_frequencies": [
            {
                "freq_hz": float(f),
                "severity": "high" if np.random.random() > 0.5 else "medium",
            }
            for f in problem_freqs
        ],
    }


def generate_derived_data(peaks: list, session_meta: dict) -> dict:
    """Generate derived analysis data."""
    # Wood property estimates based on peaks
    fundamental = peaks[0]["freq_hz"] if peaks else 180

    # Simplified wood property estimation formulas
    # (These are illustrative, not scientifically accurate)
    dimensions = session_meta.get("dimensions_mm", {})
    length_m = dimensions.get("length", 500) / 1000
    thickness_m = dimensions.get("thickness", 3) / 1000
    weight_kg = session_meta.get("weight_g", 80) / 1000

    # Estimate density
    volume_m3 = length_m * (dimensions.get("width", 150) / 1000) * thickness_m
    density = weight_kg / volume_m3 if volume_m3 > 0 else 400

    # Estimate stiffness (Young's modulus) from fundamental frequency
    # E ≈ (2 * L * f)^2 * ρ / (1.875^4 * t^2) for cantilever beam
    stiffness_gpa = (
        (2 * length_m * fundamental) ** 2 * density / (1.875**4 * thickness_m**2)
    ) / 1e9

    # Sound radiation coefficient
    radiation_coeff = np.sqrt(stiffness_gpa * 1e9 / density) / 1000

    return {
        "wood_properties": {
            "estimated_density_kg_m3": round(density, 1),
            "estimated_stiffness_gpa": round(stiffness_gpa, 2),
            "radiation_coefficient": round(radiation_coeff, 2),
            "fundamental_hz": round(fundamental, 1),
            "quality_grade": "A"
            if radiation_coeff > 12
            else "B"
            if radiation_coeff > 10
            else "C",
        },
        "mode_analysis": {
            "num_modes_detected": len(peaks),
            "mode_spacing_quality": "regular" if len(peaks) > 3 else "sparse",
            "highest_coherence": max(p["coherence"] for p in peaks) if peaks else 0,
        },
    }


def create_sample_pack(output_dir: Path, specimen_name: str = "Sitka Spruce #42"):
    """Create a complete sample viewer pack."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate data
    spectrum = generate_spectrum_data(
        fundamental_freq=np.random.uniform(150, 220), num_modes=np.random.randint(6, 10)
    )
    peaks = generate_peaks_data(spectrum)
    session_meta = generate_session_meta(specimen_name)
    capture_meta = generate_capture_meta()
    derived = generate_derived_data(peaks, session_meta)
    transfer_function = generate_transfer_function_json(spectrum)
    wsi_curve = generate_wsi_curve_data(spectrum, peaks)

    # Create directory structure
    spectra_dir = output_dir / "spectra"
    peaks_dir = output_dir / "peaks"
    derived_dir = output_dir / "derived"

    spectra_dir.mkdir(exist_ok=True)
    peaks_dir.mkdir(exist_ok=True)
    derived_dir.mkdir(exist_ok=True)

    # Write manifest
    manifest = {
        "schema_id": "viewer_pack_v1",
        "schema_version": "1.0",
        "created_at_utc": datetime.utcnow().isoformat() + "Z",
        "specimen_id": specimen_name,
        "contents": {
            "spectra": [
                "spectra/transfer_function.csv",
                "spectra/transfer_function.json",
            ],
            "peaks": ["peaks/detected_peaks.json"],
            "derived": ["derived/wood_properties.json", "derived/wsi_curve.json"],
        },
    }
    with open(output_dir / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)

    # Write metadata
    with open(output_dir / "session_meta.json", "w") as f:
        json.dump(session_meta, f, indent=2)

    with open(output_dir / "capture_meta.json", "w") as f:
        json.dump(capture_meta, f, indent=2)

    # Write spectrum CSV
    with open(spectra_dir / "transfer_function.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["freq_hz", "H_mag", "coherence", "phase_deg"])
        for i in range(len(spectrum["freq_hz"])):
            writer.writerow(
                [
                    f"{spectrum['freq_hz'][i]:.2f}",
                    f"{spectrum['H_mag'][i]:.6f}",
                    f"{spectrum['coherence'][i]:.4f}",
                    f"{spectrum['phase_deg'][i]:.2f}",
                ]
            )

    # Write transfer function JSON (alternative format)
    with open(spectra_dir / "transfer_function.json", "w") as f:
        json.dump(transfer_function, f, indent=2)

    # Write peaks JSON
    with open(peaks_dir / "detected_peaks.json", "w") as f:
        json.dump({"peaks": peaks}, f, indent=2)

    # Write derived data
    with open(derived_dir / "wood_properties.json", "w") as f:
        json.dump(derived, f, indent=2)

    # Write WSI curve JSON
    with open(derived_dir / "wsi_curve.json", "w") as f:
        json.dump(wsi_curve, f, indent=2)

    # Write WSI curve CSV
    with open(derived_dir / "wsi_curve.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "freq_hz",
                "wsi",
                "loc",
                "grad",
                "phase_disorder",
                "coh_mean",
                "admissible",
            ]
        )
        for i in range(len(wsi_curve["freq_hz"])):
            writer.writerow(
                [
                    f"{wsi_curve['freq_hz'][i]:.2f}",
                    f"{wsi_curve['wsi'][i]:.4f}",
                    f"{wsi_curve['loc'][i]:.4f}",
                    f"{wsi_curve['grad'][i]:.4f}",
                    f"{wsi_curve['phase_disorder'][i]:.4f}",
                    f"{wsi_curve['coh_mean'][i]:.4f}",
                    str(wsi_curve["admissible"][i]).lower(),
                ]
            )

    print(f"Created sample pack at: {output_dir}")
    return output_dir


def create_sample_zip(output_path: Path, specimen_name: str = "Sitka Spruce #42"):
    """Create a sample viewer pack as a ZIP file."""
    import tempfile

    # Create in temp directory first
    with tempfile.TemporaryDirectory() as tmpdir:
        pack_dir = Path(tmpdir) / "viewer_pack"
        create_sample_pack(pack_dir, specimen_name)

        # Create ZIP
        output_path = Path(output_path)
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file in pack_dir.rglob("*"):
                if file.is_file():
                    arcname = file.relative_to(pack_dir)
                    zf.write(file, arcname)

    print(f"Created sample ZIP at: {output_path}")
    return output_path


if __name__ == "__main__":
    # Generate sample packs
    sample_dir = Path(__file__).parent

    # Create folder-based pack
    create_sample_pack(sample_dir / "sample_sitka_spruce", "Sitka Spruce #42")

    # Create ZIP pack
    create_sample_zip(sample_dir / "sample_sitka_spruce.zip", "Sitka Spruce #42")

    # Create a second sample with different characteristics
    create_sample_zip(sample_dir / "sample_cedar_top.zip", "Western Red Cedar #17")

    print("\nSample packs created successfully!")
