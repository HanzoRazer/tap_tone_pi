"""
Tests for tap_tone_pi.core.session_diff module.
"""

import pytest
import json


class TestPeakDiff:
    """Test PeakDiff dataclass."""

    def test_freq_delta(self):
        """Test frequency delta calculation."""
        from tap_tone_pi.core.session_diff import PeakDiff

        diff = PeakDiff(label="P1", freq_a=440.0, freq_b=445.0)
        assert diff.freq_delta == 5.0

    def test_freq_delta_none_when_missing(self):
        """Delta is None when either frequency is missing."""
        from tap_tone_pi.core.session_diff import PeakDiff

        diff = PeakDiff(label="P1", freq_a=440.0, freq_b=None)
        assert diff.freq_delta is None

    def test_freq_delta_pct(self):
        """Test frequency delta percentage."""
        from tap_tone_pi.core.session_diff import PeakDiff

        diff = PeakDiff(label="P1", freq_a=100.0, freq_b=110.0)
        assert diff.freq_delta_pct == 10.0

    def test_status_added(self):
        """Peak added when only in B."""
        from tap_tone_pi.core.session_diff import PeakDiff

        diff = PeakDiff(label="P1", freq_a=None, freq_b=440.0)
        assert diff.status == "added"

    def test_status_removed(self):
        """Peak removed when only in A."""
        from tap_tone_pi.core.session_diff import PeakDiff

        diff = PeakDiff(label="P1", freq_a=440.0, freq_b=None)
        assert diff.status == "removed"

    def test_status_changed(self):
        """Peak changed when delta > 1 Hz."""
        from tap_tone_pi.core.session_diff import PeakDiff

        diff = PeakDiff(label="P1", freq_a=440.0, freq_b=445.0)
        assert diff.status == "changed"

    def test_status_unchanged(self):
        """Peak unchanged when delta <= 1 Hz."""
        from tap_tone_pi.core.session_diff import PeakDiff

        diff = PeakDiff(label="P1", freq_a=440.0, freq_b=440.5)
        assert diff.status == "unchanged"


class TestMetricDiff:
    """Test MetricDiff dataclass."""

    def test_delta(self):
        """Test metric delta calculation."""
        from tap_tone_pi.core.session_diff import MetricDiff

        diff = MetricDiff(name="RMS", value_a=0.5, value_b=0.6)
        assert diff.delta == pytest.approx(0.1)

    def test_delta_pct(self):
        """Test metric delta percentage."""
        from tap_tone_pi.core.session_diff import MetricDiff

        diff = MetricDiff(name="RMS", value_a=0.5, value_b=0.6)
        assert diff.delta_pct == pytest.approx(20.0)


class TestSessionDiff:
    """Test SessionDiff dataclass."""

    def test_summary(self):
        """Test summary statistics."""
        from tap_tone_pi.core.session_diff import SessionDiff, PeakDiff

        diff = SessionDiff(
            session_a="before",
            session_b="after",
            peaks=[
                PeakDiff(label="P1", freq_a=440.0, freq_b=445.0),  # changed
                PeakDiff(label="P2", freq_a=880.0, freq_b=None),  # removed
                PeakDiff(label="P3", freq_a=None, freq_b=660.0),  # added
            ],
        )

        summary = diff.summary
        assert summary["peaks_changed"] == 1
        assert summary["peaks_removed"] == 1
        assert summary["peaks_added"] == 1
        assert summary["total_peaks_a"] == 2
        assert summary["total_peaks_b"] == 2

    def test_to_dict(self):
        """Test serialization to dict."""
        from tap_tone_pi.core.session_diff import SessionDiff, PeakDiff

        diff = SessionDiff(
            session_a="before",
            session_b="after",
            peaks=[PeakDiff(label="P1", freq_a=440.0, freq_b=445.0)],
        )

        d = diff.to_dict()
        assert d["session_a"] == "before"
        assert d["session_b"] == "after"
        assert len(d["peaks"]) == 1
        assert d["peaks"][0]["label"] == "P1"


class TestCompareSessionsIntegration:
    """Integration tests for compare_sessions function."""

    def test_compare_with_dict_peaks(self, tmp_path):
        """Test comparing sessions with dict-format peaks."""
        from tap_tone_pi.core.session_diff import compare_sessions

        # Create session A
        session_a = tmp_path / "session_a"
        session_a.mkdir()
        with open(session_a / "analysis.json", "w") as f:
            json.dump(
                {
                    "peaks": {
                        "A4": {"freq_hz": 440.0, "amp": 1000},
                        "A5": {"freq_hz": 880.0, "amp": 500},
                    }
                },
                f,
            )

        # Create session B
        session_b = tmp_path / "session_b"
        session_b.mkdir()
        with open(session_b / "analysis.json", "w") as f:
            json.dump(
                {
                    "peaks": {
                        "A4": {"freq_hz": 445.0, "amp": 1100},  # Changed
                        "E5": {"freq_hz": 660.0, "amp": 600},  # New peak
                    }
                },
                f,
            )

        diff = compare_sessions(session_a, session_b)

        assert diff.session_a == "session_a"
        assert diff.session_b == "session_b"
        assert len(diff.peaks) == 3  # A4, A5, E5
        assert not diff.errors

    def test_compare_with_list_peaks(self, tmp_path):
        """Test comparing sessions with list-format peaks."""
        from tap_tone_pi.core.session_diff import compare_sessions

        # Create session A
        session_a = tmp_path / "session_a"
        session_a.mkdir()
        with open(session_a / "analysis.json", "w") as f:
            json.dump(
                {
                    "dominant_hz": 440.0,
                    "rms": 0.5,
                    "peaks": [
                        {"freq_hz": 440.0, "magnitude": 0.8},
                        {"freq_hz": 880.0, "magnitude": 0.4},
                    ],
                },
                f,
            )

        # Create session B
        session_b = tmp_path / "session_b"
        session_b.mkdir()
        with open(session_b / "analysis.json", "w") as f:
            json.dump(
                {
                    "dominant_hz": 445.0,
                    "rms": 0.6,
                    "peaks": [
                        {"freq_hz": 445.0, "magnitude": 0.9},
                    ],
                },
                f,
            )

        diff = compare_sessions(session_a, session_b)

        # Should have dominant peak + list peaks
        assert len(diff.peaks) >= 2
        assert len(diff.metrics) >= 1  # At least RMS

    def test_compare_missing_analysis(self, tmp_path):
        """Test comparing when analysis file is missing."""
        from tap_tone_pi.core.session_diff import compare_sessions

        session_a = tmp_path / "session_a"
        session_a.mkdir()
        # No analysis.json

        session_b = tmp_path / "session_b"
        session_b.mkdir()

        diff = compare_sessions(session_a, session_b)

        assert len(diff.errors) == 2


class TestFormatDiffReport:
    """Test format_diff_report function."""

    def test_format_report(self):
        """Test text report formatting."""
        from tap_tone_pi.core.session_diff import (
            SessionDiff,
            PeakDiff,
            format_diff_report,
        )

        diff = SessionDiff(
            session_a="before",
            session_b="after",
            peaks=[
                PeakDiff(label="A4", freq_a=440.0, freq_b=445.0),
            ],
        )

        report = format_diff_report(diff)

        assert "Session Comparison Report" in report
        assert "before" in report
        assert "after" in report
        assert "A4" in report
        assert "440.0" in report
        assert "445.0" in report
