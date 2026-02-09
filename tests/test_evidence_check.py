"""PR8: Evidence preflight validator tests.

Tests use tmp_path to create fake session structures — hermetic, no real audio.
Aligned with the frozen-report, attempt-based discovery API.
"""
import json
import struct
import pytest
from collections import defaultdict
from pathlib import Path

from tap_tone_pi.validate.evidence_check import (
    EvidenceReport,
    EvidenceSummary,
    Finding,
    FindingSeverity,
    _discover_attempt_dirs,
    _attempt_number,
    _point_id_for_attempt,
    _validate_wav_suspicious_size,
    _validate_analysis_semantics,
    _validate_quality_check_semantics,
    _validate_attempt_numbering_by_point,
    _validate_consistent_spectrum_bins,
    render_human,
    render_json,
    scan_session,
    validate_attempt,
)


# =============================================================================
# Helpers — build fake session structures
# =============================================================================

def _write_wav_stub(path: Path) -> None:
    """Write a minimal valid WAV file (>= 1024 bytes to avoid E201)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    # 1024 samples of silence → 2048 data bytes → well above E201 threshold
    num_samples = 1024
    data_size = num_samples * 2  # 16-bit mono
    fmt_chunk_size = 16
    riff_size = 4 + (8 + fmt_chunk_size) + (8 + data_size)
    with open(path, "wb") as f:
        f.write(b"RIFF")
        f.write(struct.pack("<I", riff_size))
        f.write(b"WAVE")
        f.write(b"fmt ")
        f.write(struct.pack("<I", fmt_chunk_size))
        f.write(struct.pack("<HHIIHH", 1, 1, 48000, 96000, 2, 16))
        f.write(b"data")
        f.write(struct.pack("<I", data_size))
        f.write(b"\x00" * data_size)


def _write_json(path: Path, data: dict) -> None:
    """Write a JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _make_attempt(
    attempt_dir: Path,
    *,
    skip: set[str] | None = None,
    corrupt_json: str | None = None,
    bad_verdict: str | None = None,
    include_optionals: bool = False,
) -> None:
    """Create a complete attempt directory.

    Args:
        attempt_dir: Directory to populate.
        skip: Set of filenames to omit.
        corrupt_json: Filename to write invalid JSON to.
        bad_verdict: Write this value as verdict in quality_check.json.
        include_optionals: Also create optional files.
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

    if include_optionals:
        if "capture_meta.json" not in skip:
            _write_json(attempt_dir / "capture_meta.json", {
                "sample_rate_hz": 48000,
                "device_id": "test_mic",
            })
        if "attempt_meta.json" not in skip:
            _write_json(attempt_dir / "attempt_meta.json", {
                "attempt_id": "test",
                "attempt_number": 1,
            })
        if "spectrum.csv" not in skip:
            (attempt_dir / "spectrum.csv").write_text(
                "freq_hz,magnitude\n100.0,0.5\n", encoding="utf-8",
            )
        if "spectrum.png" not in skip:
            (attempt_dir / "spectrum.png").write_bytes(b"\x89PNG\r\n")

    if corrupt_json:
        target = attempt_dir / corrupt_json
        target.write_text("{{{not json", encoding="utf-8")


def _make_session(
    session_dir: Path,
    *,
    points: int = 1,
    attempts_per_point: int = 1,
    flat: bool = False,
    skip_in_attempt: set[str] | None = None,
    include_optionals: bool = False,
    corrupt_json_in: tuple[int, int, str] | None = None,
) -> None:
    """Create a session with nested or flat layout.

    Args:
        flat: If True, use flat layout (attempt dirs directly under session).
        corrupt_json_in: (point_idx, attempt_idx, filename) — 1-based.
    """
    for pi in range(1, points + 1):
        for ai in range(1, attempts_per_point + 1):
            if flat:
                attempt_dir = session_dir / f"attempt_{ai:03d}"
            else:
                point_id = f"point_{pi:03d}"
                attempt_dir = session_dir / point_id / f"attempt_{ai:03d}"

            skip = set(skip_in_attempt) if skip_in_attempt else set()
            corrupt = None
            if corrupt_json_in and corrupt_json_in[0] == pi and corrupt_json_in[1] == ai:
                corrupt = corrupt_json_in[2]

            _make_attempt(
                attempt_dir,
                skip=skip,
                corrupt_json=corrupt,
                include_optionals=include_optionals,
            )


# =============================================================================
# Attempt discovery
# =============================================================================

class TestDiscoverAttemptDirs:
    def test_nested_layout(self, tmp_path):
        _make_session(tmp_path, points=2, attempts_per_point=2)
        dirs = _discover_attempt_dirs(tmp_path)
        assert len(dirs) == 4
        # Sorted by point_id then attempt number
        assert dirs[0].name == "attempt_001"
        assert dirs[0].parent.name == "point_001"

    def test_flat_layout(self, tmp_path):
        _make_session(tmp_path, points=1, attempts_per_point=3, flat=True)
        dirs = _discover_attempt_dirs(tmp_path)
        assert len(dirs) == 3

    def test_empty_dir(self, tmp_path):
        dirs = _discover_attempt_dirs(tmp_path)
        assert dirs == []

    def test_nonexistent(self, tmp_path):
        dirs = _discover_attempt_dirs(tmp_path / "nope")
        assert dirs == []

    def test_ignores_non_attempt_dirs(self, tmp_path):
        (tmp_path / "point_001" / "attempt_001").mkdir(parents=True)
        (tmp_path / "point_001" / "other_dir").mkdir()
        (tmp_path / "point_001" / "attempt_bad").mkdir()
        _make_attempt(tmp_path / "point_001" / "attempt_001")
        dirs = _discover_attempt_dirs(tmp_path)
        assert len(dirs) == 1


# =============================================================================
# Happy paths
# =============================================================================

class TestHappyPaths:
    """Required files present → exit 0, no FAIL findings."""

    def test_nested_single(self, tmp_path):
        _make_session(tmp_path)
        report = scan_session(tmp_path)

        assert report.session_type == "tap"
        assert report.summary.attempts_scanned == 1
        assert report.summary.fail_count == 0
        assert report.exit_code == 0

    def test_nested_multi(self, tmp_path):
        _make_session(tmp_path, points=2, attempts_per_point=2)
        report = scan_session(tmp_path)

        assert report.summary.attempts_scanned == 4
        assert report.summary.fail_count == 0
        assert report.exit_code == 0

    def test_flat_layout(self, tmp_path):
        _make_session(tmp_path, flat=True, attempts_per_point=3)
        report = scan_session(tmp_path)

        assert report.summary.attempts_scanned == 3
        assert report.summary.fail_count == 0
        assert report.exit_code == 0

    def test_phase2_detection(self, tmp_path):
        """Session with grid.json → session_type = 'phase2'."""
        _make_session(tmp_path)
        _write_json(tmp_path / "grid.json", {"points": [{"id": "A1"}]})
        report = scan_session(tmp_path)

        assert report.session_type == "phase2"
        assert report.exit_code == 0

    def test_all_optionals_present(self, tmp_path):
        _make_session(tmp_path, include_optionals=True)
        report = scan_session(tmp_path)

        assert report.summary.fail_count == 0
        assert report.summary.warn_count == 0
        assert report.exit_code == 0


# =============================================================================
# Missing required files → exit 1
# =============================================================================

class TestMissingRequired:
    """Missing required artifact → FAIL finding, exit 1."""

    def test_missing_analysis(self, tmp_path):
        _make_session(tmp_path, skip_in_attempt={"analysis.json"})
        report = scan_session(tmp_path)

        assert report.summary.fail_count >= 1
        assert report.exit_code == 1
        fails = [f for f in report.findings if f.severity == FindingSeverity.FAIL]
        assert any("analysis.json" in f.message for f in fails)
        assert any(f.code == "E001" for f in fails)

    def test_missing_audio(self, tmp_path):
        _make_session(tmp_path, skip_in_attempt={"audio.wav"})
        report = scan_session(tmp_path)

        assert report.summary.fail_count >= 1
        fails = [f for f in report.findings if f.severity == FindingSeverity.FAIL]
        assert any("audio.wav" in f.message for f in fails)

    def test_missing_quality_check(self, tmp_path):
        _make_session(tmp_path, skip_in_attempt={"quality_check.json"})
        report = scan_session(tmp_path)

        assert report.summary.fail_count >= 1
        fails = [f for f in report.findings if f.severity == FindingSeverity.FAIL]
        assert any("quality_check.json" in f.message for f in fails)

    def test_no_attempts_found(self, tmp_path):
        """Empty session directory → E003."""
        report = scan_session(tmp_path)
        assert report.summary.fail_count >= 1
        assert report.exit_code == 1
        fails = [f for f in report.findings if f.severity == FindingSeverity.FAIL]
        assert any(f.code == "E003" for f in fails)


# =============================================================================
# Bad JSON → exit 2
# =============================================================================

class TestBadJSON:
    """Corrupt or invalid JSON → FAIL finding, exit 2."""

    def test_corrupt_analysis_json(self, tmp_path):
        _make_session(tmp_path, corrupt_json_in=(1, 1, "analysis.json"))
        report = scan_session(tmp_path)

        assert report.summary.fail_count >= 1
        assert report.exit_code == 2
        fails = [f for f in report.findings if f.severity == FindingSeverity.FAIL]
        assert any(f.code == "E101" for f in fails)

    def test_corrupt_quality_check(self, tmp_path):
        _make_session(tmp_path, corrupt_json_in=(1, 1, "quality_check.json"))
        report = scan_session(tmp_path)

        assert report.exit_code == 2
        fails = [f for f in report.findings if f.severity == FindingSeverity.FAIL]
        assert any(f.code == "E101" for f in fails)

    def test_missing_required_key(self, tmp_path):
        """analysis.json without 'peaks' key → E103."""
        _make_session(tmp_path)
        analysis = tmp_path / "point_001" / "attempt_001" / "analysis.json"
        _write_json(analysis, {"rms": 0.01})  # missing "peaks"

        report = scan_session(tmp_path)
        fails = [f for f in report.findings if f.severity == FindingSeverity.FAIL]
        assert any(f.code == "E103" and "peaks" in f.message for f in fails)

    def test_invalid_verdict_value(self, tmp_path):
        """quality_check.json with invalid verdict → E203 WARN."""
        attempt_dir = tmp_path / "point_001" / "attempt_001"
        _make_attempt(attempt_dir, bad_verdict="garbage")

        report = scan_session(tmp_path)
        warns = [f for f in report.findings if f.severity == FindingSeverity.WARN]
        assert any(f.code == "E203" for f in warns)

    def test_json_not_dict(self, tmp_path):
        """JSON that parses but is a list → E102."""
        _make_session(tmp_path)
        analysis = tmp_path / "point_001" / "attempt_001" / "analysis.json"
        analysis.write_text("[1, 2, 3]", encoding="utf-8")

        report = scan_session(tmp_path)
        fails = [f for f in report.findings if f.severity == FindingSeverity.FAIL]
        assert any(f.code == "E102" for f in fails)


# =============================================================================
# Optional missing → exit 0 with WARN
# =============================================================================

class TestOptionalMissing:
    """Optional files missing → WARN findings, exit 0."""

    def test_missing_spectrum_csv(self, tmp_path):
        """spectrum.csv is optional → WARN, exit 0."""
        _make_session(tmp_path)
        report = scan_session(tmp_path)

        # spectrum.csv is optional and not created by default
        assert report.exit_code == 0
        warns = [f for f in report.findings if f.severity == FindingSeverity.WARN]
        assert any("spectrum.csv" in f.message for f in warns)

    def test_missing_capture_meta(self, tmp_path):
        """capture_meta.json is optional → WARN, exit 0."""
        _make_session(tmp_path)
        report = scan_session(tmp_path)

        assert report.exit_code == 0
        warns = [f for f in report.findings if f.severity == FindingSeverity.WARN]
        assert any("capture_meta.json" in f.message for f in warns)


# =============================================================================
# Strict mode
# =============================================================================

class TestStrictMode:
    """--strict makes WARN findings produce exit 1."""

    def test_strict_promotes_warn_to_failure(self, tmp_path):
        """Optional missing + strict → exit 1."""
        _make_session(tmp_path)  # won't have optionals
        report = scan_session(tmp_path, strict=True)

        assert report.strict is True
        assert report.exit_code == 1

    def test_strict_clean_session_still_0(self, tmp_path):
        """All required AND optional files → exit 0 even with strict."""
        _make_session(tmp_path, include_optionals=True)
        report = scan_session(tmp_path, strict=True)

        assert report.summary.warn_count == 0, (
            f"Unexpected WARNs: {[f.message for f in report.findings if f.severity == FindingSeverity.WARN]}"
        )
        assert report.exit_code == 0

    def test_fail_on_warn_alias(self, tmp_path):
        """--fail-on-warn behaves identically to --strict."""
        _make_session(tmp_path)
        report = scan_session(tmp_path, fail_on_warn=True)

        assert report.strict is True
        assert report.exit_code == 1  # optionals missing → warn → strict → 1


# =============================================================================
# Cross-file invariants
# =============================================================================

class TestCrossFileInvariants:
    def test_attempt_numbering_gap(self, tmp_path):
        """Missing attempt_002 between 001 and 003 → WARN E210."""
        point_dir = tmp_path / "point_001"
        _make_attempt(point_dir / "attempt_001")
        _make_attempt(point_dir / "attempt_003")

        report = scan_session(tmp_path)
        warns = [f for f in report.findings if f.severity == FindingSeverity.WARN]
        assert any(f.code == "E210" for f in warns)

    def test_e210_flat_numbering_gap(self, tmp_path):
        """Flat layout: attempt_001 and attempt_003 but no 002 → E210."""
        _make_attempt(tmp_path / "attempt_001")
        _make_attempt(tmp_path / "attempt_003")

        report = scan_session(tmp_path)
        warns = [f for f in report.findings if f.severity == FindingSeverity.WARN]
        e210 = [f for f in warns if f.code == "E210"]
        assert len(e210) == 1
        assert "flat" in e210[0].message


# =============================================================================
# WAV header validation
# =============================================================================

class TestWavValidation:
    def test_tiny_wav_e201(self, tmp_path):
        """WAV exists but too small → E201 WARN."""
        _make_session(tmp_path)
        wav = tmp_path / "point_001" / "attempt_001" / "audio.wav"
        wav.write_bytes(b"RIFF" + b"\x00" * 40)  # 44 bytes, below 1024

        report = scan_session(tmp_path)
        warns = [f for f in report.findings if f.severity == FindingSeverity.WARN]
        assert any(f.code == "E201" for f in warns)

    def test_empty_wav(self, tmp_path):
        """Zero-byte WAV → E002 FAIL."""
        _make_session(tmp_path)
        wav = tmp_path / "point_001" / "attempt_001" / "audio.wav"
        wav.write_bytes(b"")

        report = scan_session(tmp_path)
        fails = [f for f in report.findings if f.severity == FindingSeverity.FAIL]
        assert any(f.code == "E002" for f in fails)

    def test_large_wav_no_e201(self, tmp_path):
        """WAV ≥ 1024 bytes → no E201."""
        _make_session(tmp_path)
        wav = tmp_path / "point_001" / "attempt_001" / "audio.wav"
        wav.write_bytes(b"RIFF" + b"\x00" * 1020)  # 1024 bytes exactly

        report = scan_session(tmp_path)
        e201s = [f for f in report.findings if f.code == "E201"]
        assert len(e201s) == 0


# =============================================================================
# Edge cases
# =============================================================================

class TestEdgeCases:
    def test_nonexistent_path(self, tmp_path):
        report = scan_session(tmp_path / "does_not_exist")
        assert report.summary.fail_count >= 1
        assert report.exit_code == 1

    def test_file_not_directory(self, tmp_path):
        fpath = tmp_path / "not_a_dir.txt"
        fpath.write_text("hello")
        report = scan_session(fpath)
        assert report.summary.fail_count >= 1
        assert report.exit_code == 1

    def test_multi_point_multi_attempt(self, tmp_path):
        """Large session: 3 points, 3 attempts each."""
        _make_session(tmp_path, points=3, attempts_per_point=3)
        report = scan_session(tmp_path)

        assert report.summary.attempts_scanned == 9
        assert report.summary.fail_count == 0
        assert report.exit_code == 0


# =============================================================================
# E2xx unit tests
# =============================================================================

class TestE201WavSuspiciousSize:
    """E201: WAV file suspiciously small."""

    def test_missing_wav_no_e201(self, tmp_path):
        """Missing WAV doesn't trigger E201 (handled by E001)."""
        attempt = tmp_path / "attempt_001"
        attempt.mkdir(parents=True)
        assert _validate_wav_suspicious_size(attempt) == []

    def test_tiny_wav_triggers(self, tmp_path):
        attempt = tmp_path / "attempt_001"
        attempt.mkdir(parents=True)
        (attempt / "audio.wav").write_bytes(b"X" * 100)
        findings = _validate_wav_suspicious_size(attempt)
        assert len(findings) == 1
        assert findings[0].code == "E201"
        assert findings[0].severity == FindingSeverity.WARN
        assert findings[0].meta["size_bytes"] == 100

    def test_normal_wav_no_trigger(self, tmp_path):
        attempt = tmp_path / "attempt_001"
        attempt.mkdir(parents=True)
        (attempt / "audio.wav").write_bytes(b"X" * 2048)
        assert _validate_wav_suspicious_size(attempt) == []


class TestE202AnalysisSemantics:
    """E202: analysis.json missing expected semantic keys."""

    def test_all_keys_present(self, tmp_path):
        attempt = tmp_path / "attempt_001"
        attempt.mkdir(parents=True)
        _write_json(attempt / "analysis.json", {
            "dominant_hz": 192.3, "rms": 0.02, "confidence": 0.8,
            "clipped": False, "peaks": [],
        })
        assert _validate_analysis_semantics(attempt) == []

    def test_missing_keys(self, tmp_path):
        attempt = tmp_path / "attempt_001"
        attempt.mkdir(parents=True)
        _write_json(attempt / "analysis.json", {"peaks": []})
        findings = _validate_analysis_semantics(attempt)
        assert len(findings) == 1
        assert findings[0].code == "E202"
        assert findings[0].severity == FindingSeverity.WARN
        assert set(findings[0].meta["missing_keys"]) == {
            "dominant_hz", "rms", "confidence", "clipped"
        }

    def test_no_file_no_finding(self, tmp_path):
        attempt = tmp_path / "attempt_001"
        attempt.mkdir(parents=True)
        assert _validate_analysis_semantics(attempt) == []

    def test_corrupt_json_no_e202(self, tmp_path):
        """E202 skips if parse fails (E101 handles that)."""
        attempt = tmp_path / "attempt_001"
        attempt.mkdir(parents=True)
        (attempt / "analysis.json").write_text("{bad", encoding="utf-8")
        assert _validate_analysis_semantics(attempt) == []

    def test_e202_via_scan_session(self, tmp_path):
        """Integrated: analysis.json with only 'peaks' → E202 WARN, exit 0."""
        _make_session(tmp_path)
        analysis = tmp_path / "point_001" / "attempt_001" / "analysis.json"
        _write_json(analysis, {"peaks": []})
        report = scan_session(tmp_path)
        warns = [f for f in report.findings if f.code == "E202"]
        assert len(warns) == 1
        assert report.exit_code == 0  # WARN doesn't cause failure


class TestE203QualityCheckSemantics:
    """E203: quality_check.json semantic validation."""

    def test_valid_qc_no_finding(self, tmp_path):
        attempt = tmp_path / "attempt_001"
        attempt.mkdir(parents=True)
        _write_json(attempt / "quality_check.json", {
            "verdict": "pass", "triggered_rules": [],
        })
        assert _validate_quality_check_semantics(attempt) == []

    def test_invalid_verdict(self, tmp_path):
        attempt = tmp_path / "attempt_001"
        attempt.mkdir(parents=True)
        _write_json(attempt / "quality_check.json", {
            "verdict": "garbage", "triggered_rules": [],
        })
        findings = _validate_quality_check_semantics(attempt)
        assert len(findings) == 1
        assert findings[0].code == "E203"
        assert "verdict" in findings[0].message

    def test_triggered_rules_not_list(self, tmp_path):
        attempt = tmp_path / "attempt_001"
        attempt.mkdir(parents=True)
        _write_json(attempt / "quality_check.json", {
            "verdict": "pass", "triggered_rules": "not_a_list",
        })
        findings = _validate_quality_check_semantics(attempt)
        assert len(findings) == 1
        assert findings[0].code == "E203"
        assert "triggered_rules" in findings[0].message

    def test_both_invalid(self, tmp_path):
        attempt = tmp_path / "attempt_001"
        attempt.mkdir(parents=True)
        _write_json(attempt / "quality_check.json", {
            "verdict": 42, "triggered_rules": "nope",
        })
        findings = _validate_quality_check_semantics(attempt)
        assert len(findings) == 1
        assert "verdict" in findings[0].message
        assert "triggered_rules" in findings[0].message

    def test_no_file_no_finding(self, tmp_path):
        attempt = tmp_path / "attempt_001"
        attempt.mkdir(parents=True)
        assert _validate_quality_check_semantics(attempt) == []

    def test_e203_via_scan_session(self, tmp_path):
        """Integrated: bad verdict type → E203 WARN."""
        _make_session(tmp_path)
        qc = tmp_path / "point_001" / "attempt_001" / "quality_check.json"
        _write_json(qc, {"verdict": "unknown", "triggered_rules": []})
        report = scan_session(tmp_path)
        warns = [f for f in report.findings if f.code == "E203"]
        assert len(warns) == 1


class TestE210AttemptNumberingByPoint:
    """E210: Attempt numbering gap detection."""

    def test_no_gap(self, tmp_path):
        dirs = []
        for n in (1, 2, 3):
            d = tmp_path / "point_A" / f"attempt_{n:03d}"
            d.mkdir(parents=True)
            dirs.append(d)
        assert _validate_attempt_numbering_by_point(tmp_path, dirs) == []

    def test_gap_detected(self, tmp_path):
        dirs = []
        for n in (1, 3):
            d = tmp_path / "point_A" / f"attempt_{n:03d}"
            d.mkdir(parents=True)
            dirs.append(d)
        findings = _validate_attempt_numbering_by_point(tmp_path, dirs)
        assert len(findings) == 1
        assert findings[0].code == "E210"
        assert 2 in findings[0].meta["missing"]

    def test_multiple_points_independent(self, tmp_path):
        """Gap in point_A but not point_B."""
        dirs = []
        for n in (1, 3):
            d = tmp_path / "point_A" / f"attempt_{n:03d}"
            d.mkdir(parents=True)
            dirs.append(d)
        for n in (1, 2):
            d = tmp_path / "point_B" / f"attempt_{n:03d}"
            d.mkdir(parents=True)
            dirs.append(d)
        findings = _validate_attempt_numbering_by_point(tmp_path, dirs)
        assert len(findings) == 1
        assert "point_A" in findings[0].message

    def test_flat_layout_gap(self, tmp_path):
        dirs = []
        for n in (1, 4):
            d = tmp_path / f"attempt_{n:03d}"
            d.mkdir(parents=True)
            dirs.append(d)
        findings = _validate_attempt_numbering_by_point(tmp_path, dirs)
        assert len(findings) == 1
        assert "flat" in findings[0].message


class TestE212InconsistentSpectrumBins:
    """E212: Inconsistent spectrum bin counts across attempts."""

    def test_consistent_bins_no_finding(self, tmp_path):
        dirs = []
        for n in (1, 2):
            d = tmp_path / "point_A" / f"attempt_{n:03d}"
            d.mkdir(parents=True)
            _write_json(d / "analysis.json", {
                "peaks": [], "spectrum_freq_hz": [100, 200, 300],
            })
            dirs.append(d)
        assert _validate_consistent_spectrum_bins(tmp_path, dirs) == []

    def test_inconsistent_bins_warns(self, tmp_path):
        dirs = []
        d1 = tmp_path / "point_A" / "attempt_001"
        d1.mkdir(parents=True)
        _write_json(d1 / "analysis.json", {
            "peaks": [], "spectrum_freq_hz": [100, 200, 300],
        })
        dirs.append(d1)

        d2 = tmp_path / "point_A" / "attempt_002"
        d2.mkdir(parents=True)
        _write_json(d2 / "analysis.json", {
            "peaks": [], "spectrum_freq_hz": [100, 200],
        })
        dirs.append(d2)

        findings = _validate_consistent_spectrum_bins(tmp_path, dirs)
        assert len(findings) == 1
        assert findings[0].code == "E212"
        assert findings[0].severity == FindingSeverity.WARN
        assert findings[0].meta["baseline_bins"] in (2, 3)

    def test_no_spectrum_data_no_finding(self, tmp_path):
        dirs = []
        for n in (1, 2):
            d = tmp_path / "point_A" / f"attempt_{n:03d}"
            d.mkdir(parents=True)
            _write_json(d / "analysis.json", {"peaks": []})
            dirs.append(d)
        assert _validate_consistent_spectrum_bins(tmp_path, dirs) == []

    def test_spectrum_mag_field(self, tmp_path):
        """Falls back to spectrum_mag when spectrum_freq_hz absent."""
        dirs = []
        d1 = tmp_path / "attempt_001"
        d1.mkdir(parents=True)
        _write_json(d1 / "analysis.json", {
            "peaks": [], "spectrum_mag": [0.1, 0.2],
        })
        dirs.append(d1)

        d2 = tmp_path / "attempt_002"
        d2.mkdir(parents=True)
        _write_json(d2 / "analysis.json", {
            "peaks": [], "spectrum_mag": [0.1, 0.2, 0.3],
        })
        dirs.append(d2)

        findings = _validate_consistent_spectrum_bins(tmp_path, dirs)
        assert len(findings) == 1
        assert findings[0].code == "E212"

    def test_e212_via_scan_session(self, tmp_path):
        """Integrated: mismatched bins across points → E212 WARN."""
        point_a = tmp_path / "point_001"
        _make_attempt(point_a / "attempt_001")
        _write_json(point_a / "attempt_001" / "analysis.json", {
            "peaks": [], "dominant_hz": 100, "rms": 0.01,
            "confidence": 0.8, "clipped": False,
            "spectrum_freq_hz": [100, 200, 300],
        })

        point_b = tmp_path / "point_002"
        _make_attempt(point_b / "attempt_001")
        _write_json(point_b / "attempt_001" / "analysis.json", {
            "peaks": [], "dominant_hz": 100, "rms": 0.01,
            "confidence": 0.8, "clipped": False,
            "spectrum_freq_hz": [100, 200],
        })

        report = scan_session(tmp_path)
        warns = [f for f in report.findings if f.code == "E212"]
        assert len(warns) == 1


class TestE2xxStrictMode:
    """E2xx WARNs promote to exit 1 under --strict."""

    def test_e201_strict_exit_1(self, tmp_path):
        """Tiny WAV + strict → exit 1."""
        _make_session(tmp_path, include_optionals=True)
        wav = tmp_path / "point_001" / "attempt_001" / "audio.wav"
        wav.write_bytes(b"R" * 100)
        report = scan_session(tmp_path, strict=True)
        assert report.exit_code == 1
        warns = [f for f in report.findings if f.code == "E201"]
        assert len(warns) == 1

    def test_e202_strict_exit_1(self, tmp_path):
        """analysis.json missing keys + strict → exit 1."""
        _make_session(tmp_path, include_optionals=True)
        analysis = tmp_path / "point_001" / "attempt_001" / "analysis.json"
        _write_json(analysis, {"peaks": []})
        report = scan_session(tmp_path, strict=True)
        assert report.exit_code == 1

    def test_e203_strict_exit_1(self, tmp_path):
        """Bad verdict + strict → exit 1."""
        _make_session(tmp_path, include_optionals=True)
        qc = tmp_path / "point_001" / "attempt_001" / "quality_check.json"
        _write_json(qc, {"verdict": "PASS", "triggered_rules": []})
        report = scan_session(tmp_path, strict=True)
        e203 = [f for f in report.findings if f.code == "E203"]
        assert len(e203) == 1
        assert report.exit_code == 1


class TestHelperFunctions:
    """Unit tests for _attempt_number and _point_id_for_attempt."""

    def test_attempt_number_valid(self, tmp_path):
        d = tmp_path / "attempt_001"
        d.mkdir()
        assert _attempt_number(d) == 1

    def test_attempt_number_large(self, tmp_path):
        d = tmp_path / "attempt_0042"
        d.mkdir()
        assert _attempt_number(d) == 42

    def test_attempt_number_invalid(self, tmp_path):
        d = tmp_path / "not_attempt"
        d.mkdir()
        assert _attempt_number(d) is None

    def test_point_id_nested(self, tmp_path):
        d = tmp_path / "point_A" / "attempt_001"
        d.mkdir(parents=True)
        assert _point_id_for_attempt(tmp_path, d) == "point_A"

    def test_point_id_flat(self, tmp_path):
        d = tmp_path / "attempt_001"
        d.mkdir(parents=True)
        assert _point_id_for_attempt(tmp_path, d) == ""


# =============================================================================
# Renderers
# =============================================================================

class TestRenderers:
    def test_human_output_ok(self, tmp_path):
        _make_session(tmp_path, include_optionals=True)
        report = scan_session(tmp_path)
        output = render_human(report)

        assert "Evidence check:" in output
        assert "tap" in output
        assert "FAIL=0" in output

    def test_human_output_failures(self, tmp_path):
        _make_session(tmp_path, skip_in_attempt={"analysis.json"})
        report = scan_session(tmp_path)
        output = render_human(report)

        assert "[FAIL]" in output
        assert "analysis.json" in output

    def test_human_hint_shown(self, tmp_path):
        """Findings with hints show them in human renderer."""
        _make_session(tmp_path, skip_in_attempt={"audio.wav"})
        report = scan_session(tmp_path)
        output = render_human(report)

        assert "hint:" in output

    def test_json_output_schema(self, tmp_path):
        _make_session(tmp_path, include_optionals=True)
        report = scan_session(tmp_path)
        output = json.loads(render_json(report))

        assert output["tool"] == "evidence-check"
        assert output["version"] == "1.0.0"
        assert output["session_type"] == "tap"
        assert "summary" in output
        assert "findings" in output
        assert output["summary"]["fail_count"] == 0

    def test_json_output_with_findings(self, tmp_path):
        _make_session(tmp_path, skip_in_attempt={"analysis.json"})
        report = scan_session(tmp_path)
        output = json.loads(render_json(report))

        assert output["exit_code"] == 1
        assert output["summary"]["fail_count"] >= 1
        assert len(output["findings"]) >= 1
        assert output["findings"][0]["severity"] == "fail"


# =============================================================================
# Report / Finding dataclass
# =============================================================================

class TestEvidenceReport:
    def test_report_is_frozen(self):
        r = EvidenceReport()
        with pytest.raises(AttributeError):
            r.exit_code = 99  # type: ignore[misc]

    def test_report_has_slots(self):
        r = EvidenceReport()
        assert hasattr(r, "__slots__")

    def test_to_dict_shape(self):
        r = EvidenceReport(
            session_dir="/tmp/s",
            session_type="tap",
            summary=EvidenceSummary(5, 0, 0, 0),
        )
        d = r.to_dict()
        assert d["tool"] == "evidence-check"
        assert d["session_type"] == "tap"
        assert d["summary"]["attempts_scanned"] == 5

    def test_default_exit_code(self):
        r = EvidenceReport()
        assert r.exit_code == 0


class TestFindingFields:
    def test_hint_in_to_dict(self):
        f = Finding("E001", FindingSeverity.WARN, "missing", hint="Re-record")
        d = f.to_dict()
        assert d["hint"] == "Re-record"

    def test_hint_omitted_when_none(self):
        f = Finding("E001", FindingSeverity.WARN, "missing")
        d = f.to_dict()
        assert "hint" not in d

    def test_meta_in_to_dict(self):
        f = Finding("E202", FindingSeverity.INFO, "mismatch",
                    meta={"expected": 48000, "actual": 44100})
        d = f.to_dict()
        assert d["meta"] == {"expected": 48000, "actual": 44100}

    def test_meta_omitted_when_empty(self):
        f = Finding("E202", FindingSeverity.INFO, "mismatch")
        d = f.to_dict()
        assert "meta" not in d

    def test_finding_is_frozen(self):
        f = Finding("E001", FindingSeverity.FAIL, "msg")
        with pytest.raises(AttributeError):
            f.message = "changed"  # type: ignore[misc]

    def test_finding_has_slots(self):
        f = Finding("E001", FindingSeverity.FAIL, "msg")
        assert hasattr(f, "__slots__")


# =============================================================================
# Deterministic ordering
# =============================================================================

class TestDeterministicOrdering:
    def test_findings_sorted_severity_then_code(self, tmp_path):
        """Findings are ordered: FAIL first, then WARN, then INFO."""
        _make_session(tmp_path, skip_in_attempt={"analysis.json"})
        report = scan_session(tmp_path)

        if len(report.findings) >= 2:
            severity_rank = {
                FindingSeverity.FAIL: 0,
                FindingSeverity.WARN: 1,
                FindingSeverity.INFO: 2,
            }
            ranks = [severity_rank[f.severity] for f in report.findings]
            assert ranks == sorted(ranks), "Findings not sorted by severity"

    def test_multiple_runs_same_output(self, tmp_path):
        """scan_session is deterministic across multiple calls."""
        _make_session(tmp_path, points=2, attempts_per_point=2)
        r1 = scan_session(tmp_path)
        r2 = scan_session(tmp_path)

        assert r1.to_dict() == r2.to_dict()
