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
    render_human,
    render_json,
    scan_session,
    validate_attempt,
)


# =============================================================================
# Helpers — build fake session structures
# =============================================================================

def _write_wav_stub(path: Path) -> None:
    """Write a minimal valid WAV file (44 bytes, no samples)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        data_size = 0
        fmt_chunk_size = 16
        riff_size = 4 + (8 + fmt_chunk_size) + (8 + data_size)
        f.write(b"RIFF")
        f.write(struct.pack("<I", riff_size))
        f.write(b"WAVE")
        f.write(b"fmt ")
        f.write(struct.pack("<I", fmt_chunk_size))
        f.write(struct.pack("<HHIIHH", 1, 1, 48000, 96000, 2, 16))
        f.write(b"data")
        f.write(struct.pack("<I", data_size))


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
        """quality_check.json with invalid verdict → E104."""
        attempt_dir = tmp_path / "point_001" / "attempt_001"
        _make_attempt(attempt_dir, bad_verdict="garbage")

        report = scan_session(tmp_path)
        fails = [f for f in report.findings if f.severity == FindingSeverity.FAIL]
        assert any(f.code == "E104" for f in fails)

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
    def test_sample_rate_mismatch(self, tmp_path):
        """capture_meta and analysis disagree on sample_rate → WARN."""
        _make_session(tmp_path, include_optionals=True)
        attempt_dir = tmp_path / "point_001" / "attempt_001"

        _write_json(attempt_dir / "capture_meta.json", {
            "sample_rate_hz": 44100,
            "device_id": "test_mic",
        })
        # analysis.json already has sample_rate: 48000

        report = scan_session(tmp_path)
        warns = [f for f in report.findings if f.severity == FindingSeverity.WARN]
        assert any(f.code == "E202" for f in warns)

    def test_attempt_numbering_gap(self, tmp_path):
        """Missing attempt_002 between 001 and 003 → WARN E210."""
        point_dir = tmp_path / "point_001"
        _make_attempt(point_dir / "attempt_001")
        _make_attempt(point_dir / "attempt_003")

        report = scan_session(tmp_path)
        warns = [f for f in report.findings if f.severity == FindingSeverity.WARN]
        assert any(f.code == "E210" for f in warns)


# =============================================================================
# WAV header validation
# =============================================================================

class TestWavValidation:
    def test_invalid_wav_header(self, tmp_path):
        """Not a WAV file → E201."""
        _make_session(tmp_path)
        wav = tmp_path / "point_001" / "attempt_001" / "audio.wav"
        wav.write_bytes(b"NOT A WAV FILE AT ALL!!!")

        report = scan_session(tmp_path)
        fails = [f for f in report.findings if f.severity == FindingSeverity.FAIL]
        assert any(f.code == "E201" and "WAV" in f.message for f in fails)

    def test_empty_wav(self, tmp_path):
        """Zero-byte WAV → E002."""
        _make_session(tmp_path)
        wav = tmp_path / "point_001" / "attempt_001" / "audio.wav"
        wav.write_bytes(b"")

        report = scan_session(tmp_path)
        fails = [f for f in report.findings if f.severity == FindingSeverity.FAIL]
        assert any(f.code == "E002" for f in fails)


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
