"""Backward-compat + opt-in secondary tests for modes/tap_tone/offline_from_wav.py.

Confirms the primary CLI output is unchanged (plus additive provenance) when
--secondary is omitted, and that --secondary writes a schema-valid
secondary_peak_analysis_v1 artifact without affecting the primary result.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import jsonschema

import modes.tap_tone.offline_from_wav as offline
from modes._shared.wav_io import write_wav_mono
from tests.fixtures.audio import damped_sine

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = (
    REPO_ROOT / "contracts" / "schemas" / "secondary_peak_analysis_v1.schema.json"
)
SR = 48_000


def _write_wav(tmp_path: Path) -> Path:
    sig = damped_sine(440.0, 0.12, SR, duration_s=1.0)
    wav = tmp_path / "tap.wav"
    write_wav_mono(wav, sig, SR)
    return wav


def _run(monkeypatch, argv):
    monkeypatch.setattr("sys.argv", ["offline_from_wav.py", *argv])
    offline.main()


def test_primary_output_backward_compatible_and_additive(tmp_path, monkeypatch):
    wav = _write_wav(tmp_path)
    out = tmp_path / "primary.json"
    _run(monkeypatch, ["--wav", str(wav), "--outfile", str(out)])
    data = json.loads(out.read_text())

    # Legacy fields unchanged
    assert data["artifact_type"] == "tap_tone"
    assert data["sample_rate"] == SR
    assert "duration_s" in data and "peaks" in data
    assert data["source_wav"] == str(wav)

    # Additive provenance
    expected_sha = hashlib.sha256(wav.read_bytes()).hexdigest()
    assert data["source_wav_sha256"] == expected_sha
    assert data["analysis_version"] == offline.ANALYSIS_VERSION

    # No secondary artifact when not requested
    assert not (tmp_path / "secondary_peak_analysis.json").exists()


def test_secondary_flag_writes_valid_artifact(tmp_path, monkeypatch):
    wav = _write_wav(tmp_path)
    out = tmp_path / "primary.json"
    sec = tmp_path / "secondary.json"
    _run(
        monkeypatch,
        [
            "--wav",
            str(wav),
            "--outfile",
            str(out),
            "--secondary",
            "--peak-id",
            "p1",
            "--secondary-out",
            str(sec),
        ],
    )
    assert sec.exists()
    rec = json.loads(sec.read_text())
    schema = json.loads(SCHEMA_PATH.read_text())
    jsonschema.validate(rec, schema)
    assert rec["schema_version"] == "secondary_peak_analysis_v1"
    assert rec["peak_id"] == "p1"
    assert rec["status"] in ("RESOLVED", "PARTIAL", "NOT_RESOLVED")

    # Provenance links primary and secondary to the same WAV bytes.
    primary = json.loads(out.read_text())
    assert rec["source_wav_sha256"] == primary["source_wav_sha256"]


def test_secondary_missing_peak_id_is_nonblocking(tmp_path, monkeypatch, capsys):
    wav = _write_wav(tmp_path)
    out = tmp_path / "primary.json"
    sec = tmp_path / "secondary.json"
    _run(
        monkeypatch,
        [
            "--wav",
            str(wav),
            "--outfile",
            str(out),
            "--secondary",
            "--peak-id",
            "does_not_exist",
            "--secondary-out",
            str(sec),
        ],
    )
    # Primary still written; secondary skipped without raising.
    assert out.exists()
    assert not sec.exists()
    assert "skipping secondary" in capsys.readouterr().out


def test_secondary_default_output_path(tmp_path, monkeypatch):
    wav = _write_wav(tmp_path)
    out = tmp_path / "primary.json"
    _run(
        monkeypatch,
        [
            "--wav",
            str(wav),
            "--outfile",
            str(out),
            "--secondary",
            "--peak-id",
            "p1",
        ],
    )
    sec = tmp_path / "secondary_peak_analysis.json"
    assert sec.exists()
    rec = json.loads(sec.read_text())
    assert rec["schema_version"] == "secondary_peak_analysis_v1"
    assert rec["peak_id"] == "p1"
