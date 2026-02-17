"""Tests for pre-export viewer_pack_v1 validator."""

from __future__ import annotations
import json
from pathlib import Path
import pytest

from tap_tone.validate.viewer_pack_v1 import validate_pack


@pytest.fixture
def valid_pack(tmp_path: Path) -> Path:
    """Create a minimal valid pack structure."""
    pack = tmp_path / "valid_pack"
    pack.mkdir()

    # Create manifest
    manifest = {
        "schema_id": "viewer_pack_v1",
        "schema_version": "v1",
        "created_at_utc": "2026-01-17T12:00:00Z",
        "source_capdir": "session_001",
        "detected_phase": "phase2",
        "measurement_only": True,
        "interpretation": "deferred",
        "points": ["P1", "P2"],
        "contents": {
            "audio": True,
            "spectra": True,
            "coherence": False,
            "ods": False,
            "wolf": False,
            "plots": False,
        },
        "files": [],
        "bundle_sha256": "0" * 64,
    }
    (pack / "viewer_pack.json").write_text(json.dumps(manifest), encoding="utf-8")

    # Create spectrum files
    for pid in ["P1", "P2"]:
        spec_dir = pack / "spectra" / "points" / pid
        spec_dir.mkdir(parents=True)

        # Spectrum CSV with identical frequency grid
        spectrum_csv = "freq_hz,H_mag,coherence,phase_deg\n"
        spectrum_csv += "100.0,0.1,0.9,0.0\n"
        spectrum_csv += "200.0,0.2,0.85,5.0\n"
        spectrum_csv += "300.0,0.15,0.88,10.0\n"
        (spec_dir / "spectrum.csv").write_text(spectrum_csv, encoding="utf-8")

        # Analysis JSON with peaks aligned to grid
        analysis = {
            "peaks": [
                {"freq_hz": 100.0, "label": "peak1"},
                {"freq_hz": 200.0, "label": "peak2"},
            ]
        }
        (spec_dir / "analysis.json").write_text(json.dumps(analysis), encoding="utf-8")

    # Create audio files
    audio_dir = pack / "audio" / "points"
    audio_dir.mkdir(parents=True)
    for pid in ["P1", "P2"]:
        (audio_dir / f"{pid}.wav").write_bytes(b"RIFF" + b"\x00" * 100)

    return pack


def test_valid_pack_passes(valid_pack: Path):
    """A valid pack should pass validation."""
    report = validate_pack(valid_pack)
    assert report.passed, f"Errors: {report.errors}"
    assert len(report.errors) == 0
    assert report.stats["points_checked"] == 2
    assert report.stats["spectra_valid"] == 2


def test_missing_manifest_fails(tmp_path: Path):
    """Pack without manifest should fail with M-001."""
    pack = tmp_path / "no_manifest"
    pack.mkdir()

    report = validate_pack(pack)
    assert not report.passed
    assert any(e["rule"] == "M-001" for e in report.errors)


def test_wrong_schema_id_fails(valid_pack: Path):
    """Wrong schema_id should fail with M-002."""
    manifest_path = valid_pack / "viewer_pack.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["schema_id"] = "wrong_id"
    manifest_path.write_text(json.dumps(manifest))

    report = validate_pack(valid_pack)
    assert not report.passed
    assert any(e["rule"] == "M-002" for e in report.errors)


def test_empty_points_fails(valid_pack: Path):
    """Empty points list should fail with M-003."""
    manifest_path = valid_pack / "viewer_pack.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["points"] = []
    manifest_path.write_text(json.dumps(manifest))

    report = validate_pack(valid_pack)
    assert not report.passed
    assert any(e["rule"] == "M-003" for e in report.errors)


def test_missing_spectrum_fails(valid_pack: Path):
    """Missing spectrum file should fail with S-001."""
    # Remove P2 spectrum
    spec_path = valid_pack / "spectra" / "points" / "P2" / "spectrum.csv"
    spec_path.unlink()

    report = validate_pack(valid_pack)
    assert not report.passed
    assert any(e["rule"] == "S-001" and "P2" in e["message"] for e in report.errors)


def test_non_monotonic_freq_fails(valid_pack: Path):
    """Non-monotonic freq_hz should fail with S-003."""
    spec_path = valid_pack / "spectra" / "points" / "P1" / "spectrum.csv"
    # Write non-monotonic frequencies
    spectrum_csv = "freq_hz,H_mag,coherence,phase_deg\n"
    spectrum_csv += "100.0,0.1,0.9,0.0\n"
    spectrum_csv += "200.0,0.2,0.85,5.0\n"
    spectrum_csv += "150.0,0.15,0.88,10.0\n"  # Out of order!
    spec_path.write_text(spectrum_csv, encoding="utf-8")

    report = validate_pack(valid_pack)
    assert not report.passed
    assert any(e["rule"] == "S-003" for e in report.errors)


def test_frequency_grid_mismatch_fails(valid_pack: Path):
    """Different frequency grids should fail with S-006."""
    spec_path = valid_pack / "spectra" / "points" / "P2" / "spectrum.csv"
    # Write different frequency grid
    spectrum_csv = "freq_hz,H_mag,coherence,phase_deg\n"
    spectrum_csv += "100.0,0.1,0.9,0.0\n"
    spectrum_csv += "250.0,0.2,0.85,5.0\n"  # Different from P1's 200.0
    spectrum_csv += "300.0,0.15,0.88,10.0\n"
    spec_path.write_text(spectrum_csv, encoding="utf-8")

    report = validate_pack(valid_pack)
    assert not report.passed
    assert any(e["rule"] == "S-006" for e in report.errors)


def test_peak_not_in_grid_fails(valid_pack: Path):
    """Peak frequency not in grid should fail with P-003."""
    analysis_path = valid_pack / "spectra" / "points" / "P1" / "analysis.json"
    analysis = {
        "peaks": [
            {"freq_hz": 155.5, "label": "off_grid_peak"},  # Not in 100, 200, 300
        ]
    }
    analysis_path.write_text(json.dumps(analysis), encoding="utf-8")

    report = validate_pack(valid_pack)
    assert not report.passed
    assert any(e["rule"] == "P-003" for e in report.errors)


def test_peak_with_tolerance_passes(valid_pack: Path):
    """Peak within tolerance should pass with P-003."""
    analysis_path = valid_pack / "spectra" / "points" / "P1" / "analysis.json"
    analysis = {
        "peaks": [
            {"freq_hz": 100.3, "label": "near_peak"},  # 0.3 Hz off from 100.0
        ]
    }
    analysis_path.write_text(json.dumps(analysis), encoding="utf-8")

    # With 0.5 Hz tolerance, this should pass
    report = validate_pack(valid_pack, peak_tolerance_hz=0.5)
    # Should not have P-003 error for this peak
    p003_errors = [
        e for e in report.errors if e["rule"] == "P-003" and "100.3" in e["message"]
    ]
    assert len(p003_errors) == 0


def test_missing_audio_is_warning_by_default(valid_pack: Path):
    """Missing audio should be WARN by default."""
    audio_path = valid_pack / "audio" / "points" / "P1.wav"
    audio_path.unlink()

    report = validate_pack(valid_pack)
    # Should pass (warnings don't fail)
    # But should have warning
    assert any(w["rule"] == "A-001" and "P1" in w["message"] for w in report.warnings)


def test_missing_audio_is_error_when_required(valid_pack: Path):
    """Missing audio should be ERROR when audio_required=True."""
    audio_path = valid_pack / "audio" / "points" / "P1.wav"
    audio_path.unlink()

    report = validate_pack(valid_pack, audio_required=True)
    assert not report.passed
    assert any(e["rule"] == "A-001" and "P1" in e["message"] for e in report.errors)


def test_wsi_curve_validation(valid_pack: Path):
    """WSI curve with correct columns should pass."""
    wolf_dir = valid_pack / "wolf"
    wolf_dir.mkdir(parents=True)

    # Create valid WSI curve
    wsi_csv = "freq_hz,wsi,loc,grad,phase_disorder,coh_mean,admissible\n"
    wsi_csv += "100.0,0.5,0.1,0.2,0.3,0.9,true\n"
    wsi_csv += "200.0,0.6,0.15,0.25,0.35,0.85,false\n"
    wsi_csv += "300.0,0.4,0.12,0.22,0.32,0.88,true\n"
    (wolf_dir / "wsi_curve.csv").write_text(wsi_csv, encoding="utf-8")

    report = validate_pack(valid_pack)
    # Should not have W-xxx errors
    w_errors = [e for e in report.errors if e["rule"].startswith("W-")]
    assert len(w_errors) == 0


def test_wsi_missing_column_fails(valid_pack: Path):
    """WSI curve missing column should fail with W-001."""
    wolf_dir = valid_pack / "wolf"
    wolf_dir.mkdir(parents=True)

    # Missing 'admissible' column
    wsi_csv = "freq_hz,wsi,loc,grad,phase_disorder,coh_mean\n"
    wsi_csv += "100.0,0.5,0.1,0.2,0.3,0.9\n"
    (wolf_dir / "wsi_curve.csv").write_text(wsi_csv, encoding="utf-8")

    report = validate_pack(valid_pack)
    assert any(
        e["rule"] == "W-001" and "admissible" in e["message"] for e in report.errors
    )


def test_wsi_invalid_admissible_fails(valid_pack: Path):
    """WSI curve with invalid admissible value should fail with W-002."""
    wolf_dir = valid_pack / "wolf"
    wolf_dir.mkdir(parents=True)

    # Invalid admissible value
    wsi_csv = "freq_hz,wsi,loc,grad,phase_disorder,coh_mean,admissible\n"
    wsi_csv += "100.0,0.5,0.1,0.2,0.3,0.9,yes\n"  # "yes" is invalid
    (wolf_dir / "wsi_curve.csv").write_text(wsi_csv, encoding="utf-8")

    report = validate_pack(valid_pack)
    assert any(e["rule"] == "W-002" for e in report.errors)


def test_report_to_dict(valid_pack: Path):
    """Report should serialize to dict correctly."""
    report = validate_pack(valid_pack)
    d = report.to_dict()

    assert "schema_id" in d
    assert d["schema_id"] == "validation_report_v1"
    assert "passed" in d
    assert "errors" in d
    assert "warnings" in d
    assert "stats" in d


# ------------------------------------------------------------------
# T-001: Session Timeline validation
# ------------------------------------------------------------------


def _write_valid_timeline(pack: Path) -> None:
    """Write a minimally valid session_timeline_v1.json."""
    meta = pack / "meta"
    meta.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_id": "session_timeline_v1",
        "schema_version": 2,
        "session_id": "valid_pack",
        "paths": {
            "events_jsonl": "events.jsonl",
            "shadow_latest": "spine_shadow_latest.json",
            "advisory_state": "meta/advisory_state.json",
        },
        "moment_latest": None,
        "directive_events": [
            {
                "timestamp": "t1",
                "event_type": "attention_acknowledged",
                "directive_id": "d1",
                "component": "cli",
            }
        ],
        "counts": {
            "attention_requested": 0,
            "attention_acknowledged": 1,
            "attention_dismissed": 0,
        },
        "ui_state": {},
        "latest_policy_trace": None,
    }
    (meta / "session_timeline_v1.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )


def test_pack_without_timeline_passes(valid_pack: Path):
    """Pack without timeline should pass (backward compat)."""
    timeline = valid_pack / "meta" / "session_timeline_v1.json"
    if timeline.exists():
        timeline.unlink()
    report = validate_pack(valid_pack)
    assert report.passed, f"Errors: {report.errors}"
    assert report.stats.get("timeline_present") == 0


def test_pack_with_valid_timeline_passes(valid_pack: Path):
    """Valid timeline should not introduce errors."""
    _write_valid_timeline(valid_pack)
    report = validate_pack(valid_pack)
    assert report.passed, f"Errors: {report.errors}"
    assert report.stats.get("timeline_present") == 1


def test_invalid_timeline_schema_id_fails(valid_pack: Path):
    """Wrong schema_id should fail T-001 (if schema file available)."""
    _write_valid_timeline(valid_pack)
    p = valid_pack / "meta" / "session_timeline_v1.json"
    doc = json.loads(p.read_text(encoding="utf-8"))
    doc["schema_id"] = "wrong"
    p.write_text(json.dumps(doc), encoding="utf-8")

    report = validate_pack(valid_pack)
    schema_missing = any(w["rule"] == "T-000" for w in report.warnings)
    if not schema_missing:
        assert not report.passed
        assert any(e["rule"] == "T-001" for e in report.errors)


def test_timeline_not_json_object_fails(valid_pack: Path):
    """Timeline that is not a JSON object should fail T-001."""
    meta = valid_pack / "meta"
    meta.mkdir(parents=True, exist_ok=True)
    (meta / "session_timeline_v1.json").write_text(
        '"just a string"',
        encoding="utf-8",
    )

    report = validate_pack(valid_pack)
    assert not report.passed
    assert any(e["rule"] == "T-001" for e in report.errors)


def test_timeline_invalid_json_fails(valid_pack: Path):
    """Timeline with broken JSON should fail T-001."""
    meta = valid_pack / "meta"
    meta.mkdir(parents=True, exist_ok=True)
    (meta / "session_timeline_v1.json").write_text(
        "{broken json",
        encoding="utf-8",
    )

    report = validate_pack(valid_pack)
    assert not report.passed
    assert any(e["rule"] == "T-001" for e in report.errors)


def test_missing_timeline_schema_is_error_in_ci(valid_pack: Path, monkeypatch):
    """In CI, schema presence is mandatory when timeline exists."""
    _write_valid_timeline(valid_pack)
    monkeypatch.setenv("CI", "true")

    import tap_tone.validate.viewer_pack_v1 as vp

    monkeypatch.setattr(vp, "_load_contract_schema", lambda _p: None)

    report = vp.validate_pack(valid_pack)
    assert not report.passed
    assert any(e["rule"] == "T-000" for e in report.errors)


def test_ci_requires_timeline_valid_when_present(valid_pack: Path, monkeypatch):
    """CI gate: timeline_present==1 requires timeline_valid==1."""
    _write_valid_timeline(valid_pack)
    monkeypatch.setenv("CI", "true")

    # Valid timeline + schema available → should pass with timeline_valid==1
    report = validate_pack(valid_pack)
    # If schema is loadable, timeline_valid should be 1 and T-002 should not fire
    schema_missing = any(w["rule"] == "T-000" for w in report.warnings) or any(
        e["rule"] == "T-000" for e in report.errors
    )
    if not schema_missing:
        assert report.stats.get("timeline_valid") == 1
        assert not any(e["rule"] == "T-002" for e in report.errors)


def test_ci_fires_t002_when_timeline_invalid(valid_pack: Path, monkeypatch):
    """CI gate: invalid timeline doc fires T-002 (in addition to T-001)."""
    _write_valid_timeline(valid_pack)
    monkeypatch.setenv("CI", "true")

    # Corrupt the doc so schema validation fails
    p = valid_pack / "meta" / "session_timeline_v1.json"
    doc = json.loads(p.read_text(encoding="utf-8"))
    doc["schema_id"] = "wrong"
    p.write_text(json.dumps(doc), encoding="utf-8")

    report = validate_pack(valid_pack)
    schema_missing = any(w["rule"] == "T-000" for w in report.warnings) or any(
        e["rule"] == "T-000" for e in report.errors
    )
    if not schema_missing:
        assert not report.passed
        assert any(e["rule"] == "T-001" for e in report.errors)
        assert any(e["rule"] == "T-002" for e in report.errors)
