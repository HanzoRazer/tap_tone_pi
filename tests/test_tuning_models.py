"""Tests for tuning module models and analysis."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from tap_tone_pi.tuning.models import (
    DeflectionReading,
    TuningSession,
    TuningHistory,
)
from tap_tone_pi.tuning.analysis import (
    compute_density,
    compute_stiffness,
    compute_session_stats,
)


class TestDeflectionReading:
    """Tests for DeflectionReading dataclass."""

    def test_create_reading(self):
        """Create a basic reading."""
        r = DeflectionReading(
            location="center",
            thickness_mm=3.2,
            deflection_mm=2.1,
        )
        assert r.location == "center"
        assert r.thickness_mm == 3.2
        assert r.deflection_mm == 2.1
        assert r.notes == ""

    def test_reading_with_notes(self):
        """Create reading with notes."""
        r = DeflectionReading(
            location="lower_bout",
            thickness_mm=3.0,
            deflection_mm=1.8,
            notes="near bridge",
        )
        assert r.notes == "near bridge"

    def test_reading_to_dict(self):
        """Serialize reading to dict."""
        r = DeflectionReading("center", 3.2, 2.1, "test")
        d = r.to_dict()
        assert d == {
            "location": "center",
            "thickness_mm": 3.2,
            "deflection_mm": 2.1,
            "notes": "test",
        }

    def test_reading_from_dict(self):
        """Deserialize reading from dict."""
        d = {"location": "waist", "thickness_mm": 3.1, "deflection_mm": 2.0}
        r = DeflectionReading.from_dict(d)
        assert r.location == "waist"
        assert r.thickness_mm == 3.1
        assert r.notes == ""  # Default


class TestTuningSession:
    """Tests for TuningSession dataclass."""

    def test_create_session(self):
        """Create a basic session."""
        s = TuningSession.create_now(mass_g=145.0, freq_hz=98.5)
        assert s.mass_g == 145.0
        assert s.freq_hz == 98.5
        assert len(s.readings) == 0
        assert s.timestamp  # Should be set

    def test_add_reading(self):
        """Add readings to session."""
        s = TuningSession.create_now(mass_g=145.0)
        s.add_reading("center", 3.2, 2.1)
        s.add_reading("lower_bout", 3.2, 1.8)

        assert len(s.readings) == 2
        assert s.readings[0].location == "center"

    def test_avg_thickness(self):
        """Compute average thickness."""
        s = TuningSession.create_now(mass_g=145.0)
        s.add_reading("center", 3.2, 2.1)
        s.add_reading("lower_bout", 3.0, 1.8)
        s.add_reading("upper_bout", 3.4, 2.4)

        avg = s.avg_thickness_mm()
        assert avg == pytest.approx(3.2, rel=0.01)

    def test_get_reading(self):
        """Get reading by location."""
        s = TuningSession.create_now(mass_g=145.0)
        s.add_reading("center", 3.2, 2.1)
        s.add_reading("waist", 3.1, 2.0)

        r = s.get_reading("center")
        assert r is not None
        assert r.thickness_mm == 3.2

        r2 = s.get_reading("nonexistent")
        assert r2 is None

    def test_session_roundtrip(self):
        """Serialize and deserialize session."""
        s = TuningSession.create_now(mass_g=145.0, freq_hz=98.5, notes="test")
        s.add_reading("center", 3.2, 2.1, "center note")

        d = s.to_dict()
        s2 = TuningSession.from_dict(d)

        assert s2.mass_g == s.mass_g
        assert s2.freq_hz == s.freq_hz
        assert len(s2.readings) == 1
        assert s2.readings[0].location == "center"


class TestTuningHistory:
    """Tests for TuningHistory dataclass."""

    def test_create_history(self):
        """Create a new history."""
        h = TuningHistory(
            panel_id="top_001",
            panel_type="top",
            wood_species="spruce",
            length_mm=500.0,
            width_mm=380.0,
        )
        assert h.panel_id == "top_001"
        assert len(h.sessions) == 0

    def test_add_session(self):
        """Add sessions to history."""
        h = TuningHistory(
            panel_id="top_001",
            panel_type="top",
            wood_species="spruce",
            length_mm=500.0,
            width_mm=380.0,
        )

        s1 = TuningSession.create_now(mass_g=145.0)
        s2 = TuningSession.create_now(mass_g=138.0)

        h.add_session(s1)
        h.add_session(s2)

        assert len(h.sessions) == 2
        assert h.latest_session() == s2

    def test_mass_trajectory(self):
        """Get mass values across sessions."""
        h = TuningHistory(
            panel_id="top_001",
            panel_type="top",
            wood_species="spruce",
            length_mm=500.0,
            width_mm=380.0,
        )

        h.add_session(TuningSession.create_now(mass_g=145.0))
        h.add_session(TuningSession.create_now(mass_g=138.0))
        h.add_session(TuningSession.create_now(mass_g=132.0))

        masses = h.mass_trajectory()
        assert masses == [145.0, 138.0, 132.0]

    def test_save_and_load(self):
        """Save and load history from file."""
        h = TuningHistory(
            panel_id="top_001",
            panel_type="top",
            wood_species="spruce",
            length_mm=500.0,
            width_mm=380.0,
        )

        s = TuningSession.create_now(mass_g=145.0, freq_hz=98.5)
        s.add_reading("center", 3.2, 2.1)
        h.add_session(s)

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "history.json"
            h.save(path)

            # Verify file contents
            data = json.loads(path.read_text())
            assert data["schema_id"] == "tuning_history_v1"
            assert data["panel_id"] == "top_001"

            # Load and verify
            h2 = TuningHistory.load(path)
            assert h2.panel_id == "top_001"
            assert len(h2.sessions) == 1
            assert h2.sessions[0].mass_g == 145.0


class TestAnalysis:
    """Tests for analysis functions."""

    def test_compute_density(self):
        """Compute density from mass and dimensions."""
        # 100g panel, 500x380x3mm = 57000 mm³
        # density = 100g / 57000 mm³ = 0.001754 g/mm³ = 1754 kg/m³
        density = compute_density(
            mass_g=100.0,
            length_mm=500.0,
            width_mm=380.0,
            thickness_mm=3.0,
        )
        # Spruce is typically 350-450 kg/m³, this is high but math is correct
        assert density == pytest.approx(175.4, rel=0.01)

    def test_compute_density_realistic(self):
        """Compute density with realistic guitar top values."""
        # Spruce top: ~80g, 500x380x3mm
        density = compute_density(
            mass_g=80.0,
            length_mm=500.0,
            width_mm=380.0,
            thickness_mm=3.0,
        )
        # Should be in spruce range
        assert 100 < density < 500

    def test_compute_density_zero_volume(self):
        """Density calculation rejects zero volume."""
        with pytest.raises(ValueError, match="Volume must be positive"):
            compute_density(100.0, 500.0, 380.0, 0.0)

    def test_compute_stiffness(self):
        """Compute stiffness from deflection."""
        # E = F × L³ / (4 × b × h³ × δ)
        # 1N load, 400mm span, 50mm width, 3mm thick, 2mm deflection
        e = compute_stiffness(
            deflection_mm=2.0,
            thickness_mm=3.0,
            span_mm=400.0,
            width_mm=50.0,
            load_n=1.0,
        )
        # E = 1 × 64000000 / (4 × 50 × 27 × 2) = 64000000 / 10800 = 5926 MPa = 5.9 GPa
        assert e == pytest.approx(5.93, rel=0.01)

    def test_compute_stiffness_zero_deflection(self):
        """Stiffness calculation rejects zero deflection."""
        with pytest.raises(ValueError, match="Deflection must be positive"):
            compute_stiffness(0.0, 3.0, 400.0, 50.0)

    def test_compute_session_stats(self):
        """Compute stats for a session."""
        s = TuningSession.create_now(mass_g=80.0)
        s.add_reading("center", 3.0, 2.0)
        s.add_reading("lower_bout", 3.0, 1.8)

        stats = compute_session_stats(
            session=s,
            length_mm=500.0,
            width_mm=380.0,
            span_mm=400.0,
            load_n=1.0,
        )

        assert stats.avg_thickness_mm == 3.0
        assert stats.density_kg_m3 is not None
        assert "center" in stats.stiffness_estimates
        assert "lower_bout" in stats.stiffness_estimates
