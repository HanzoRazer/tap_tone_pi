#!/usr/bin/env python3
"""
Tests for Phase 1/2 cross-validation module.

M5 Audit: No Cross-Validation Between Phase 1 and Phase 2
Fix: Mode-linking function that correlates Phase 1 peaks with Phase 2 ODS results.
"""

import pytest

from tap_tone_pi.core.phase_crossval import (
    Phase1Peak,
    Phase2Mode,
    MatchStatus,
    ConfidenceLevel,
    compute_tolerance_hz,
    match_phases,
    load_p1_peaks_from_json,
    load_p2_modes_from_json,
    crossval_from_json,
)


class TestToleranceComputation:
    """Test frequency-relative tolerance calculation."""

    def test_tolerance_at_100hz(self):
        """100 Hz @ 2% = 2 Hz tolerance."""
        tol = compute_tolerance_hz(100.0, tolerance_pct=2.0)
        assert tol == pytest.approx(2.0, rel=1e-3)

    def test_tolerance_at_1000hz(self):
        """1000 Hz @ 2% = 20 Hz tolerance."""
        tol = compute_tolerance_hz(1000.0, tolerance_pct=2.0)
        assert tol == pytest.approx(20.0, rel=1e-3)

    def test_tolerance_has_minimum_floor(self):
        """Very low frequencies should have minimum 1 Hz tolerance."""
        tol = compute_tolerance_hz(20.0, tolerance_pct=2.0)  # 20 * 0.02 = 0.4 Hz
        assert tol >= 1.0  # Floor applied

    def test_tolerance_custom_percentage(self):
        """Custom tolerance percentage should work."""
        tol = compute_tolerance_hz(500.0, tolerance_pct=5.0)
        assert tol == pytest.approx(25.0, rel=1e-3)


class TestMatchPhases:
    """Test the main phase matching algorithm."""

    def test_empty_inputs(self):
        """Empty inputs should return consistent result."""
        result = match_phases([], [])
        assert result.n_p1_peaks == 0
        assert result.n_p2_modes == 0
        assert result.n_matched == 0
        assert result.is_consistent is True
        assert result.agreement_ratio == 1.0

    def test_perfect_match_single_mode(self):
        """Single mode at exact same frequency should match."""
        p1 = [Phase1Peak(freq_hz=150.0, magnitude=0.9, confidence=0.95)]
        p2 = [Phase2Mode(freq_hz=150.0, n_points=25, max_magnitude=1.0)]

        result = match_phases(p1, p2)

        assert result.n_matched == 1
        assert result.n_p1_only == 0
        assert result.n_p2_only == 0
        assert result.is_consistent is True
        assert result.matches[0].status == MatchStatus.MATCHED
        assert result.matches[0].confidence == ConfidenceLevel.HIGH

    def test_match_within_tolerance(self):
        """Modes within tolerance should match."""
        p1 = [Phase1Peak(freq_hz=150.0, magnitude=0.9, confidence=0.95)]
        p2 = [Phase2Mode(freq_hz=152.0, n_points=25, max_magnitude=1.0)]  # 2 Hz diff

        result = match_phases(p1, p2, tolerance_pct=2.0)  # 150 * 2% = 3 Hz

        assert result.n_matched == 1
        match = result.matches[0]
        assert match.status == MatchStatus.MATCHED
        assert match.freq_delta_hz == pytest.approx(2.0, abs=0.01)

    def test_no_match_outside_tolerance(self):
        """Modes outside tolerance should not match."""
        p1 = [Phase1Peak(freq_hz=150.0, magnitude=0.9, confidence=0.95)]
        p2 = [Phase2Mode(freq_hz=160.0, n_points=25, max_magnitude=1.0)]  # 10 Hz diff

        result = match_phases(p1, p2, tolerance_pct=2.0)  # 150 * 2% = 3 Hz

        assert result.n_matched == 0
        assert result.n_p1_only == 1
        assert result.n_p2_only == 1

    def test_multiple_modes_correct_pairing(self):
        """Multiple modes should pair correctly (not greedy)."""
        p1 = [
            Phase1Peak(freq_hz=100.0, magnitude=0.9, confidence=0.95),
            Phase1Peak(freq_hz=200.0, magnitude=0.8, confidence=0.90),
            Phase1Peak(freq_hz=300.0, magnitude=0.7, confidence=0.85),
        ]
        p2 = [
            Phase2Mode(freq_hz=101.0, n_points=25, max_magnitude=1.0),
            Phase2Mode(freq_hz=199.0, n_points=25, max_magnitude=0.9),
            Phase2Mode(freq_hz=302.0, n_points=25, max_magnitude=0.8),
        ]

        result = match_phases(p1, p2, tolerance_pct=2.0)

        assert result.n_matched == 3
        assert result.n_p1_only == 0
        assert result.n_p2_only == 0
        assert result.is_consistent is True

    def test_p1_only_mode_flagged(self):
        """P1 peak with no P2 match should be flagged."""
        p1 = [
            Phase1Peak(freq_hz=100.0, magnitude=0.9, confidence=0.95),
            Phase1Peak(freq_hz=500.0, magnitude=0.5, confidence=0.80),  # No P2 match
        ]
        p2 = [Phase2Mode(freq_hz=101.0, n_points=25, max_magnitude=1.0)]

        result = match_phases(p1, p2, tolerance_pct=2.0)

        assert result.n_matched == 1
        assert result.n_p1_only == 1
        assert any("500" in w and "not confirmed" in w for w in result.warnings)

    def test_p2_only_mode_flagged(self):
        """P2 mode with no P1 match should be flagged."""
        p1 = [Phase1Peak(freq_hz=100.0, magnitude=0.9, confidence=0.95)]
        p2 = [
            Phase2Mode(freq_hz=101.0, n_points=25, max_magnitude=1.0),
            Phase2Mode(freq_hz=400.0, n_points=25, max_magnitude=0.7),  # No P1 match
        ]

        result = match_phases(p1, p2, tolerance_pct=2.0)

        assert result.n_matched == 1
        assert result.n_p2_only == 1
        assert any("400" in w and "not detected" in w for w in result.warnings)

    def test_weak_match_low_confidence(self):
        """Low P1 confidence should result in weak match."""
        p1 = [Phase1Peak(freq_hz=150.0, magnitude=0.3, confidence=0.2)]  # Low conf
        p2 = [Phase2Mode(freq_hz=150.0, n_points=25, max_magnitude=1.0)]

        result = match_phases(p1, p2, weak_match_threshold=0.3)

        assert result.n_weak_match == 1
        assert result.matches[0].status == MatchStatus.WEAK_MATCH
        assert result.matches[0].confidence == ConfidenceLevel.LOW

    def test_low_coherence_reduces_confidence(self):
        """Low P2 coherence should reduce match confidence."""
        p1 = [Phase1Peak(freq_hz=150.0, magnitude=0.9, confidence=0.95)]
        p2 = [Phase2Mode(freq_hz=150.0, n_points=25, max_magnitude=1.0, coherence_mean=0.5)]

        result = match_phases(p1, p2)

        match = result.matches[0]
        assert match.confidence in [ConfidenceLevel.MEDIUM, ConfidenceLevel.LOW]
        assert any("coherence" in n.lower() for n in match.notes)

    def test_inconsistency_flagged_many_unmatched(self):
        """Too many unmatched modes should flag inconsistency."""
        p1 = [
            Phase1Peak(freq_hz=100.0, magnitude=0.9, confidence=0.95),
            Phase1Peak(freq_hz=200.0, magnitude=0.8, confidence=0.90),
            Phase1Peak(freq_hz=300.0, magnitude=0.7, confidence=0.85),
            Phase1Peak(freq_hz=400.0, magnitude=0.6, confidence=0.80),  # No match
        ]
        p2 = [Phase2Mode(freq_hz=100.0, n_points=25, max_magnitude=1.0)]  # Only 1

        result = match_phases(p1, p2, tolerance_pct=2.0)

        assert result.is_consistent is False
        assert any("inconsistency" in w.lower() for w in result.warnings)


class TestToDict:
    """Test result serialization."""

    def test_result_serializes_correctly(self):
        """CrossValidationResult.to_dict should produce valid JSON structure."""
        p1 = [Phase1Peak(freq_hz=150.0, magnitude=0.9, confidence=0.95)]
        p2 = [Phase2Mode(freq_hz=152.0, n_points=25, max_magnitude=1.0)]

        result = match_phases(p1, p2)
        d = result.to_dict()

        assert isinstance(d, dict)
        assert d["n_p1_peaks"] == 1
        assert d["n_p2_modes"] == 1
        assert d["n_matched"] == 1
        assert "matches" in d
        assert len(d["matches"]) == 1
        assert d["matches"][0]["status"] == "matched"

    def test_none_values_serialize_as_null(self):
        """None values should serialize correctly."""
        p1 = [Phase1Peak(freq_hz=150.0, magnitude=0.9, confidence=0.95)]
        p2 = [Phase2Mode(freq_hz=500.0, n_points=25, max_magnitude=1.0)]  # No match

        result = match_phases(p1, p2, tolerance_pct=2.0)
        d = result.to_dict()

        p1_only_match = next(m for m in d["matches"] if m["status"] == "phase1_only")
        assert p1_only_match["p2_freq_hz"] is None
        assert p1_only_match["freq_delta_hz"] is None


class TestLoadFromJson:
    """Test JSON loading functions."""

    def test_load_p1_peaks_analysis_format(self):
        """Load P1 peaks from standard analysis JSON."""
        data = {
            "dominant_hz": 150.0,
            "peaks": [
                {"freq_hz": 150.0, "magnitude": 0.9},
                {"freq_hz": 280.0, "magnitude": 0.6},
            ],
            "confidence": 0.85,
        }

        peaks = load_p1_peaks_from_json(data)

        assert len(peaks) == 2
        assert peaks[0].freq_hz == 150.0
        assert peaks[0].confidence == 0.85
        assert peaks[1].freq_hz == 280.0

    def test_load_p1_peaks_empty(self):
        """Empty peaks list should return empty."""
        data = {"peaks": []}
        peaks = load_p1_peaks_from_json(data)
        assert peaks == []

    def test_load_p1_peaks_no_peaks_key(self):
        """Missing peaks key should return empty."""
        data = {"dominant_hz": 150.0}
        peaks = load_p1_peaks_from_json(data)
        assert peaks == []

    def test_load_p2_modes_ods_summary(self):
        """Load P2 modes from ODS summary JSON."""
        data = {
            "target_frequencies_hz": [100.0, 150.0, 220.0],
            "n_points": 25,
            "ods_files": ["ods_f_100.0Hz.json", "ods_f_150.0Hz.json", "ods_f_220.0Hz.json"],
        }

        modes = load_p2_modes_from_json(data)

        assert len(modes) == 3
        assert modes[0].freq_hz == 100.0
        assert modes[0].n_points == 25
        assert modes[2].freq_hz == 220.0

    def test_load_p2_modes_empty(self):
        """Empty target frequencies should return empty."""
        data = {"target_frequencies_hz": [], "n_points": 25}
        modes = load_p2_modes_from_json(data)
        assert modes == []


class TestCrossvalFromJson:
    """Test convenience function."""

    def test_crossval_from_json_happy_path(self):
        """crossval_from_json should work end-to-end."""
        p1_json = {
            "peaks": [
                {"freq_hz": 150.0, "magnitude": 0.9},
                {"freq_hz": 280.0, "magnitude": 0.6},
            ],
            "confidence": 0.85,
        }
        p2_json = {
            "target_frequencies_hz": [151.0, 279.0],
            "n_points": 25,
        }

        result = crossval_from_json(p1_json, p2_json, tolerance_pct=2.0)

        assert result.n_matched == 2
        assert result.is_consistent is True


class TestPhysicalRealism:
    """Tests based on real-world tonewood measurement scenarios."""

    def test_typical_spruce_top_modes(self):
        """Typical spruce top should have matching modes."""
        # Realistic P1 peaks from tap test
        p1 = [
            Phase1Peak(freq_hz=85.0, magnitude=0.95, confidence=0.92),  # First mode
            Phase1Peak(freq_hz=152.0, magnitude=0.88, confidence=0.90),  # (1,0)
            Phase1Peak(freq_hz=248.0, magnitude=0.75, confidence=0.85),  # (0,1)
            Phase1Peak(freq_hz=310.0, magnitude=0.65, confidence=0.82),  # (1,1)
        ]
        # P2 ODS at slightly different frequencies (measurement variation)
        p2 = [
            Phase2Mode(freq_hz=84.5, n_points=25, max_magnitude=1.0, coherence_mean=0.95),
            Phase2Mode(freq_hz=151.0, n_points=25, max_magnitude=0.9, coherence_mean=0.92),
            Phase2Mode(freq_hz=250.0, n_points=25, max_magnitude=0.8, coherence_mean=0.88),
            Phase2Mode(freq_hz=308.0, n_points=25, max_magnitude=0.7, coherence_mean=0.85),
        ]

        result = match_phases(p1, p2, tolerance_pct=2.0)

        assert result.n_matched == 4
        assert result.is_consistent is True
        assert result.agreement_ratio >= 0.95

    def test_spurious_p1_peak_detected(self):
        """P1 electrical noise peak should not match P2."""
        p1 = [
            Phase1Peak(freq_hz=150.0, magnitude=0.9, confidence=0.92),
            Phase1Peak(freq_hz=60.0, magnitude=0.3, confidence=0.7),  # 60Hz hum
        ]
        p2 = [Phase2Mode(freq_hz=151.0, n_points=25, max_magnitude=1.0, coherence_mean=0.95)]

        result = match_phases(p1, p2, tolerance_pct=2.0)

        assert result.n_matched == 1
        assert result.n_p1_only == 1
        # 60 Hz spurious peak flagged
        p1_only = [m for m in result.matches if m.status == MatchStatus.P1_ONLY]
        assert len(p1_only) == 1
        assert p1_only[0].p1_freq_hz == pytest.approx(60.0, abs=0.1)
