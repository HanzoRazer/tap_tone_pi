"""PR8: Evidence preflight validator tests.

Tests use tmp_path to create fake session structures — hermetic, no real audio.
"""
import json
import struct
import pytest
from pathlib import Path

from tap_tone_pi.validate.evidence_check import (
    EvidenceReport,
    Finding,
    SessionType,
    Severity,
    detect_session_type,
    render_human,
    render_json,
    scan_session,
    validate_phase1_attempt,
    validate_phase2_point,
    validate_record_capture,
)


# =============================================================================
# Helpers — build fake session structures
# =============================================================================

def _write_wav_stub(path: Path) -> None:
    """Write a minimal valid WAV file (44 bytes, no samples)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    # RIFF header + WAVE + fmt chunk + data chunk (no samples)
    with open(path, "wb") as f:
        data_size = 0
        fmt_chunk_size = 16
        riff_size = 4 + (8 + fmt_chunk_size) + (8 + data_size)
        f.write(b"RIFF")
        f.write(struct.pack("<I", riff_size))
        f.write(b"WAVE")
        # fmt chunk
        f.write(b"fmt ")
        f.write(struct.pack("<I", fmt_chunk_size))
        f.write(struct.pack("<HHIIHH", 1, 1, 48000, 96000, 2, 16))
        # data chunk
        f.write(b"data")
        f.write(struct.pack("<I", data_size))


def _write_json(path: Path, data: dict) -> None:
    """Write a JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _make_phase1_attempt(
    attempt_dir: Path,
    *,
    skip: set[str] | None = None,
    corrupt_json: str | None = None,
    bad_verdict: str | None = None,
) -> None:
    """Create a complete Phase 1 attempt directory.

    Args:
        attempt_dir: Directory to populate.
        skip: Set of filenames to omit.
        corrupt_json: Filename to write invalid JSON to.
        bad_verdict: Write this value as verdict in quality_check.json.
    """
    skip = skip or set()
    attempt_dir.mkdir(parents=True, exist_ok=True)

    if "audio.wav" not in skip:
        _write_wav_stub(attempt_dir / "audio.wav")

    if "analysis.json" not in skip:
        _write_json(attempt_dir / "analysis.json", {
            "peaks": [{"freq_hz": 192.3, "magnitude": 0.88}],
            "dominant_hz": 192.3,
            "rms": 0.023,
            "confidence": 0.74,
            "clipped": False,
            "sample_rate": 48000,
        })

    if "quality_check.json" not in skip:
        verdict = bad_verdict or "pass"
        _write_json(attempt_dir / "quality_check.json", {
            "verdict": verdict,
            "triggered_rules": [],
            "policy_version": "1.0.0",
        })

    if "attempt_meta.json" not in skip:
        _write_json(attempt_dir / "attempt_meta.json", {
            "attempt_id": "point_001_attempt_001",
            "point_id": "point_001",
            "attempt_number": 1,
        })

    if corrupt_json and (attempt_dir / corrupt_json).exists():
        (attempt_dir / corrupt_json).write_text("{{{not json", encoding="utf-8")
    elif corrupt_json:
        (attempt_dir / corrupt_json).write_text("{{{not json", encoding="utf-8")


def _make_phase1_session(
    session_dir: Path,
    *,
    points: int = 1,
    attempts_per_point: int = 1,
    skip_in_attempt: set[str] | None = None,
    corrupt_json_in: tuple[int, int, str] | None = None,
) -> None:
    """Create a complete Phase 1 session.

    Args:
        corrupt_json_in: (point_idx, attempt_idx, filename) to corrupt.
    """
    for pi in range(1, points + 1):
        point_id = f"point_{pi:03d}"
        for ai in range(1, attempts_per_point + 1):
            attempt_dir = session_dir / point_id / f"attempt_{ai:03d}"
            skip = set()
            corrupt = None
            if skip_in_attempt:
                skip = skip_in_attempt
            if corrupt_json_in and corrupt_json_in[0] == pi and corrupt_json_in[1] == ai:
                corrupt = corrupt_json_in[2]
            _make_phase1_attempt(attempt_dir, skip=skip, corrupt_json=corrupt)


def _make_phase2_session(
    session_dir: Path,
    *,
    point_ids: list[str] | None = None,
    skip_grid: bool = False,
    skip_in_point: set[str] | None = None,
) -> None:
    """Create a Phase 2 session."""
    if not skip_grid:
        _write_json(session_dir / "grid.json", {
            "points": [{"id": pid, "x": 0, "y": 0} for pid in (point_ids or ["A1"])],
        })

    _write_json(session_dir / "metadata.json", {
        "session_id": "test_session",
        "sample_rate": 48000,
    })

    for pid in (point_ids or ["A1"]):
        point_dir = session_dir / "points" / f"point_{pid}"
        point_dir.mkdir(parents=True, exist_ok=True)

        skip = skip_in_point or set()

        if "audio.wav" not in skip:
            _write_wav_stub(point_dir / "audio.wav")

        if "analysis.json" not in skip:
            _write_json(point_dir / "analysis.json", {
                "peaks": [],
                "band_hz": [30, 2000],
            })

        if "capture_meta.json" not in skip:
            _write_json(point_dir / "capture_meta.json", {
                "point_id": pid,
                "sample_rate_hz": 48000,
            })

        if "spectrum.csv" not in skip:
            (point_dir / "spectrum.csv").write_text(
                "freq_hz,H_mag,coherence,phase_deg\n30.0,0.001,0.9,12.3\n",
                encoding="utf-8",
            )


def _make_record_session(
    session_dir: Path,
    *,
    captures: int = 1,
    skip_in_capture: set[str] | None = None,
) -> None:
    """Create a ttp record session."""
    for i in range(captures):
        cap_dir = session_dir / f"capture_20260101T{i:06d}Z"
        cap_dir.mkdir(parents=True, exist_ok=True)

        skip = skip_in_capture or set()

        if "audio.wav" not in skip:
            _write_wav_stub(cap_dir / "audio.wav")

        if "analysis.json" not in skip:
            _write_json(cap_dir / "analysis.json", {
                "peaks": [],
                "dominant_hz": None,
                "rms": 0.001,
                "confidence": 0.1,
                "clipped": False,
            })

        if "spectrum.csv" not in skip:
            (cap_dir / "spectrum.csv").write_text(
                "freq_hz,magnitude\n100.0,0.5\n",
                encoding="utf-8",
            )


# =============================================================================
# Session type detection
# =============================================================================

class TestDetectSessionType:
    def test_phase1(self, tmp_path):
        _make_phase1_session(tmp_path)
        assert detect_session_type(tmp_path) == SessionType.PHASE1

    def test_phase2_with_grid(self, tmp_path):
        _make_phase2_session(tmp_path)
        assert detect_session_type(tmp_path) == SessionType.PHASE2

    def test_phase2_with_points_dir(self, tmp_path):
        (tmp_path / "points").mkdir()
        assert detect_session_type(tmp_path) == SessionType.PHASE2

    def test_record(self, tmp_path):
        _make_record_session(tmp_path)
        assert detect_session_type(tmp_path) == SessionType.RECORD

    def test_unknown_empty(self, tmp_path):
        assert detect_session_type(tmp_path) == SessionType.UNKNOWN


# =============================================================================
# Happy paths — all session types
# =============================================================================

class TestHappyPaths:
    """Required files present → exit 0, no FAIL findings."""

    def test_phase1_happy(self, tmp_path):
        _make_phase1_session(tmp_path, points=2, attempts_per_point=2)
        report = scan_session(tmp_path)

        assert report.session_type == SessionType.PHASE1
        assert report.points_scanned == 2
        assert report.attempts_scanned == 4
        assert report.fail_count == 0
        assert report.exit_code() == 0

    def test_phase2_happy(self, tmp_path):
        _make_phase2_session(tmp_path, point_ids=["A1", "A2", "B1"])
        report = scan_session(tmp_path)

        assert report.session_type == SessionType.PHASE2
        assert report.points_scanned == 3
        assert report.fail_count == 0
        assert report.exit_code() == 0

    def test_record_happy(self, tmp_path):
        _make_record_session(tmp_path, captures=3)
        report = scan_session(tmp_path)

        assert report.session_type == SessionType.RECORD
        assert report.points_scanned == 3
        assert report.fail_count == 0
        assert report.exit_code() == 0


# =============================================================================
# Missing required files → exit 1
# =============================================================================

class TestMissingRequired:
    """Missing required artifact → FAIL finding, exit 1."""

    def test_phase1_missing_analysis(self, tmp_path):
        _make_phase1_session(tmp_path, skip_in_attempt={"analysis.json"})
        report = scan_session(tmp_path)

        assert report.fail_count >= 1
        assert report.exit_code() == 1

        fails = [f for f in report.findings if f.severity == Severity.FAIL]
        assert any("analysis.json" in f.message for f in fails)
        assert any(f.code == "E001" for f in fails)

    def test_phase1_missing_audio(self, tmp_path):
        _make_phase1_session(tmp_path, skip_in_attempt={"audio.wav"})
        report = scan_session(tmp_path)

        assert report.fail_count >= 1
        fails = [f for f in report.findings if f.severity == Severity.FAIL]
        assert any("audio.wav" in f.message for f in fails)

    def test_phase1_missing_quality_check(self, tmp_path):
        _make_phase1_session(tmp_path, skip_in_attempt={"quality_check.json"})
        report = scan_session(tmp_path)

        assert report.fail_count >= 1
        fails = [f for f in report.findings if f.severity == Severity.FAIL]
        assert any("quality_check.json" in f.message for f in fails)

    def test_phase2_missing_audio(self, tmp_path):
        _make_phase2_session(tmp_path, skip_in_point={"audio.wav"})
        report = scan_session(tmp_path)

        assert report.fail_count >= 1
        assert report.exit_code() == 1

    def test_phase2_missing_grid(self, tmp_path):
        """Phase 2 without grid.json → still detected as phase2 via points/ dir."""
        _make_phase2_session(tmp_path, skip_grid=True)
        report = scan_session(tmp_path)

        # grid.json is required for phase2
        fails = [f for f in report.findings if f.severity == Severity.FAIL]
        assert any("grid.json" in f.message for f in fails)

    def test_record_missing_spectrum(self, tmp_path):
        _make_record_session(tmp_path, skip_in_capture={"spectrum.csv"})
        report = scan_session(tmp_path)

        assert report.fail_count >= 1
        fails = [f for f in report.findings if f.severity == Severity.FAIL]
        assert any("spectrum.csv" in f.message for f in fails)

    def test_no_points_found(self, tmp_path):
        """Empty session directory → E301 or E302."""
        report = scan_session(tmp_path)
        assert report.fail_count >= 1
        assert report.exit_code() == 1


# =============================================================================
# Bad JSON → exit 2
# =============================================================================

class TestBadJSON:
    """Corrupt or invalid JSON → FAIL finding, exit 2."""

    def test_corrupt_analysis_json(self, tmp_path):
        _make_phase1_session(
            tmp_path,
            corrupt_json_in=(1, 1, "analysis.json"),
        )
        report = scan_session(tmp_path)

        assert report.fail_count >= 1
        assert report.exit_code() == 2

        fails = [f for f in report.findings if f.severity == Severity.FAIL]
        assert any(f.code == "E100" for f in fails)

    def test_corrupt_quality_check(self, tmp_path):
        _make_phase1_session(
            tmp_path,
            corrupt_json_in=(1, 1, "quality_check.json"),
        )
        report = scan_session(tmp_path)

        assert report.exit_code() == 2
        fails = [f for f in report.findings if f.severity == Severity.FAIL]
        assert any(f.code == "E100" for f in fails)

    def test_missing_required_key(self, tmp_path):
        """analysis.json without 'peaks' key → E102."""
        _make_phase1_session(tmp_path)
        analysis = tmp_path / "point_001" / "attempt_001" / "analysis.json"
        _write_json(analysis, {"rms": 0.01})  # missing "peaks"

        report = scan_session(tmp_path)

        fails = [f for f in report.findings if f.severity == Severity.FAIL]
        assert any(f.code == "E102" and "peaks" in f.message for f in fails)

    def test_invalid_verdict_value(self, tmp_path):
        """quality_check.json with invalid verdict → E103."""
        attempt_dir = tmp_path / "point_001" / "attempt_001"
        _make_phase1_attempt(attempt_dir, bad_verdict="garbage")

        report = scan_session(tmp_path)

        fails = [f for f in report.findings if f.severity == Severity.FAIL]
        assert any(f.code == "E103" for f in fails)

    def test_json_not_dict(self, tmp_path):
        """JSON that parses but is a list → E101."""
        _make_phase1_session(tmp_path)
        analysis = tmp_path / "point_001" / "attempt_001" / "analysis.json"
        analysis.write_text("[1, 2, 3]", encoding="utf-8")

        report = scan_session(tmp_path)

        fails = [f for f in report.findings if f.severity == Severity.FAIL]
        assert any(f.code == "E101" for f in fails)


# =============================================================================
# Optional missing → exit 0 with WARN
# =============================================================================

class TestOptionalMissing:
    """Optional files missing → WARN findings, exit 0."""

    def test_phase1_missing_optional_spectrum(self, tmp_path):
        _make_phase1_session(tmp_path, skip_in_attempt={"spectrum.csv"})
        report = scan_session(tmp_path)

        # spectrum.csv is optional for phase1
        assert report.exit_code() == 0
        warns = [f for f in report.findings if f.severity == Severity.WARN]
        assert any("spectrum.csv" in f.message for f in warns)

    def test_phase2_missing_optional_analysis(self, tmp_path):
        _make_phase2_session(tmp_path, skip_in_point={"analysis.json"})
        report = scan_session(tmp_path)

        # analysis.json is optional for phase2
        assert report.exit_code() == 0
        warns = [f for f in report.findings if f.severity == Severity.WARN]
        assert any("analysis.json" in f.message for f in warns)

    def test_record_missing_optional_qc(self, tmp_path):
        _make_record_session(tmp_path, skip_in_capture={"quality_check.json"})
        report = scan_session(tmp_path)

        assert report.exit_code() == 0
        warns = [f for f in report.findings if f.severity == Severity.WARN]
        assert any("quality_check.json" in f.message for f in warns)


# =============================================================================
# Strict mode
# =============================================================================

class TestStrictMode:
    """--strict makes WARN findings produce exit 1."""

    def test_strict_promotes_warn_to_failure(self, tmp_path):
        _make_phase1_session(tmp_path, skip_in_attempt={"spectrum.csv"})
        report = scan_session(tmp_path)

        # Normal: exit 0 (only warns)
        assert report.exit_code(strict=False) == 0

        # Strict: exit 1
        assert report.exit_code(strict=True) == 1

    def test_strict_clean_session_still_0(self, tmp_path):
        """All required AND optional files present → exit 0 even with --strict."""
        _make_phase1_session(tmp_path)
        # Add optional files so there are zero WARN findings
        attempt_dir = tmp_path / "point_001" / "attempt_001"
        (attempt_dir / "spectrum.csv").write_text(
            "freq_hz,magnitude\n100.0,0.5\n", encoding="utf-8"
        )
        (attempt_dir / "spectrum.png").write_bytes(b"\x89PNG\r\n")
        report = scan_session(tmp_path)

        assert report.warn_count == 0, (
            f"Unexpected WARNs: {[f.message for f in report.findings if f.severity == Severity.WARN]}"
        )
        assert report.exit_code(strict=True) == 0


# =============================================================================
# Cross-file invariants
# =============================================================================

class TestCrossFileInvariants:
    def test_sample_rate_mismatch(self, tmp_path):
        """capture_meta and analysis disagree on sample_rate → WARN."""
        _make_phase2_session(tmp_path)
        point_dir = tmp_path / "points" / "point_A1"

        # Override capture_meta with different sample rate
        _write_json(point_dir / "capture_meta.json", {
            "point_id": "A1",
            "sample_rate_hz": 44100,
        })
        _write_json(point_dir / "analysis.json", {
            "peaks": [],
            "sample_rate": 48000,
        })

        report = scan_session(tmp_path)

        warns = [f for f in report.findings if f.severity == Severity.WARN]
        assert any(f.code == "E200" for f in warns)

    def test_attempt_numbering_gap(self, tmp_path):
        """Missing attempt_002 between 001 and 003 → WARN E201."""
        point_dir = tmp_path / "point_001"
        _make_phase1_attempt(point_dir / "attempt_001")
        _make_phase1_attempt(point_dir / "attempt_003")

        report = scan_session(tmp_path)

        warns = [f for f in report.findings if f.severity == Severity.WARN]
        assert any(f.code == "E201" for f in warns)


# =============================================================================
# WAV header validation
# =============================================================================

class TestWavValidation:
    def test_invalid_wav_header(self, tmp_path):
        """Not a WAV file → E100."""
        _make_phase1_session(tmp_path)
        wav = tmp_path / "point_001" / "attempt_001" / "audio.wav"
        wav.write_bytes(b"NOT A WAV FILE AT ALL!!!")

        report = scan_session(tmp_path)

        fails = [f for f in report.findings if f.severity == Severity.FAIL]
        assert any(f.code == "E100" and "WAV" in f.message for f in fails)

    def test_empty_wav(self, tmp_path):
        """Zero-byte WAV → E002."""
        _make_phase1_session(tmp_path)
        wav = tmp_path / "point_001" / "attempt_001" / "audio.wav"
        wav.write_bytes(b"")

        report = scan_session(tmp_path)

        fails = [f for f in report.findings if f.severity == Severity.FAIL]
        assert any(f.code == "E002" for f in fails)


# =============================================================================
# Edge cases
# =============================================================================

class TestEdgeCases:
    def test_nonexistent_path(self, tmp_path):
        report = scan_session(tmp_path / "does_not_exist")
        assert report.fail_count >= 1
        assert report.exit_code() == 1

    def test_file_not_directory(self, tmp_path):
        fpath = tmp_path / "not_a_dir.txt"
        fpath.write_text("hello")
        report = scan_session(fpath)
        assert report.fail_count >= 1

    def test_multi_point_multi_attempt(self, tmp_path):
        """Large session: 3 points, 3 attempts each."""
        _make_phase1_session(tmp_path, points=3, attempts_per_point=3)
        report = scan_session(tmp_path)

        assert report.points_scanned == 3
        assert report.attempts_scanned == 9
        assert report.fail_count == 0
        assert report.exit_code() == 0


# =============================================================================
# Renderers
# =============================================================================

class TestRenderers:
    def test_human_output_ok(self, tmp_path):
        _make_phase1_session(tmp_path)
        report = scan_session(tmp_path)
        output = render_human(report)

        assert "Evidence Check:" in output
        assert "phase1" in output
        assert "OK" in output

    def test_human_output_failures(self, tmp_path):
        _make_phase1_session(tmp_path, skip_in_attempt={"analysis.json"})
        report = scan_session(tmp_path)
        output = render_human(report)

        assert "PROBLEMS FOUND" in output
        assert "FAIL:" in output
        assert "analysis.json" in output

    def test_json_output_schema(self, tmp_path):
        _make_phase1_session(tmp_path)
        report = scan_session(tmp_path)
        output = json.loads(render_json(report))

        assert output["tool"] == "evidence-check"
        assert output["version"] == "1.0.0"
        assert output["session_type"] == "phase1"
        assert "summary" in output
        assert "findings" in output
        assert output["summary"]["ok"] is True

    def test_json_output_with_findings(self, tmp_path):
        _make_phase1_session(tmp_path, skip_in_attempt={"analysis.json"})
        report = scan_session(tmp_path)
        output = json.loads(render_json(report))

        assert output["summary"]["ok"] is False
        assert output["summary"]["fail"] >= 1
        assert len(output["findings"]) >= 1
        assert output["findings"][0]["severity"] == "fail"
        assert output["findings"][0]["code"] == "E001"


# =============================================================================
# Report dataclass
# =============================================================================

class TestEvidenceReport:
    def test_exit_code_ok(self):
        r = EvidenceReport(session_path="/tmp/s", session_type=SessionType.PHASE1)
        assert r.exit_code() == 0

    def test_exit_code_missing(self):
        r = EvidenceReport(session_path="/tmp/s", session_type=SessionType.PHASE1)
        r.findings.append(Finding(Severity.FAIL, "E001", "/p", "missing"))
        assert r.exit_code() == 1

    def test_exit_code_parse(self):
        r = EvidenceReport(session_path="/tmp/s", session_type=SessionType.PHASE1)
        r.findings.append(Finding(Severity.FAIL, "E100", "/p", "parse error"))
        assert r.exit_code() == 2

    def test_exit_code_strict_warn(self):
        r = EvidenceReport(session_path="/tmp/s", session_type=SessionType.PHASE1)
        r.findings.append(Finding(Severity.WARN, "E001", "/p", "optional"))
        assert r.exit_code(strict=False) == 0
        assert r.exit_code(strict=True) == 1

    def test_to_dict(self):
        r = EvidenceReport(
            session_path="/tmp/s",
            session_type=SessionType.PHASE2,
            points_scanned=5,
            attempts_scanned=5,
        )
        d = r.to_dict()
        assert d["tool"] == "evidence-check"
        assert d["session_type"] == "phase2"
        assert d["summary"]["points"] == 5
