"""
Data models for plate tuning deflection profile.

Manual entry of multi-point deflection readings across panel locations.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


@dataclass
class DeflectionReading:
    """Single deflection measurement at a specific panel location.

    Attributes:
        location: Descriptive location name (e.g., "center", "lower_bout", "waist_L")
        thickness_mm: Panel thickness at this location
        deflection_mm: Measured deflection under load
        notes: Optional notes about this reading
    """

    location: str
    thickness_mm: float
    deflection_mm: float
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "location": self.location,
            "thickness_mm": self.thickness_mm,
            "deflection_mm": self.deflection_mm,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, d: dict) -> DeflectionReading:
        return cls(
            location=d["location"],
            thickness_mm=d["thickness_mm"],
            deflection_mm=d["deflection_mm"],
            notes=d.get("notes", ""),
        )


@dataclass
class TuningSession:
    """One tuning session (after a thinning pass).

    Contains panel-level measurements (mass, frequency) and
    per-location deflection readings.

    Attributes:
        timestamp: ISO format UTC timestamp
        mass_g: Panel mass in grams (constant across all locations)
        freq_hz: Optional tap frequency measurement
        readings: List of deflection readings at various locations
        notes: Optional session notes
    """

    timestamp: str
    mass_g: float
    freq_hz: Optional[float] = None
    readings: list[DeflectionReading] = field(default_factory=list)
    notes: str = ""

    @classmethod
    def create_now(
        cls,
        mass_g: float,
        freq_hz: Optional[float] = None,
        readings: Optional[list[DeflectionReading]] = None,
        notes: str = "",
    ) -> TuningSession:
        """Create a new session with current timestamp."""
        return cls(
            timestamp=datetime.now(timezone.utc).isoformat(),
            mass_g=mass_g,
            freq_hz=freq_hz,
            readings=readings or [],
            notes=notes,
        )

    def add_reading(
        self,
        location: str,
        thickness_mm: float,
        deflection_mm: float,
        notes: str = "",
    ) -> DeflectionReading:
        """Add a deflection reading to this session."""
        reading = DeflectionReading(
            location=location,
            thickness_mm=thickness_mm,
            deflection_mm=deflection_mm,
            notes=notes,
        )
        self.readings.append(reading)
        return reading

    def avg_thickness_mm(self) -> Optional[float]:
        """Average thickness across all readings."""
        if not self.readings:
            return None
        return sum(r.thickness_mm for r in self.readings) / len(self.readings)

    def get_reading(self, location: str) -> Optional[DeflectionReading]:
        """Get reading by location name."""
        for r in self.readings:
            if r.location == location:
                return r
        return None

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "mass_g": self.mass_g,
            "freq_hz": self.freq_hz,
            "readings": [r.to_dict() for r in self.readings],
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, d: dict) -> TuningSession:
        return cls(
            timestamp=d["timestamp"],
            mass_g=d["mass_g"],
            freq_hz=d.get("freq_hz"),
            readings=[DeflectionReading.from_dict(r) for r in d.get("readings", [])],
            notes=d.get("notes", ""),
        )


@dataclass
class TuningHistory:
    """Complete tuning history for a panel.

    Tracks all sessions (thinning iterations) for one panel.

    Attributes:
        panel_id: Identifier for this panel (e.g., "top_001", "back_spruce_A")
        panel_type: "top" or "back"
        wood_species: Wood species name
        length_mm: Panel length (constant)
        width_mm: Panel width (constant)
        sessions: List of tuning sessions in chronological order
    """

    panel_id: str
    panel_type: str  # "top" or "back"
    wood_species: str
    length_mm: float
    width_mm: float
    sessions: list[TuningSession] = field(default_factory=list)

    def add_session(self, session: TuningSession) -> None:
        """Add a session to the history."""
        self.sessions.append(session)

    def latest_session(self) -> Optional[TuningSession]:
        """Get the most recent session."""
        return self.sessions[-1] if self.sessions else None

    def mass_trajectory(self) -> list[float]:
        """Get mass values across all sessions."""
        return [s.mass_g for s in self.sessions]

    def freq_trajectory(self) -> list[Optional[float]]:
        """Get frequency values across all sessions."""
        return [s.freq_hz for s in self.sessions]

    def thickness_trajectory(self, location: str = "center") -> list[Optional[float]]:
        """Get thickness at a specific location across sessions."""
        result = []
        for s in self.sessions:
            reading = s.get_reading(location)
            result.append(reading.thickness_mm if reading else None)
        return result

    def to_dict(self) -> dict:
        return {
            "schema_id": "tuning_history_v1",
            "panel_id": self.panel_id,
            "panel_type": self.panel_type,
            "wood_species": self.wood_species,
            "length_mm": self.length_mm,
            "width_mm": self.width_mm,
            "sessions": [s.to_dict() for s in self.sessions],
        }

    @classmethod
    def from_dict(cls, d: dict) -> TuningHistory:
        return cls(
            panel_id=d["panel_id"],
            panel_type=d["panel_type"],
            wood_species=d["wood_species"],
            length_mm=d["length_mm"],
            width_mm=d["width_mm"],
            sessions=[TuningSession.from_dict(s) for s in d.get("sessions", [])],
        )

    def save(self, path: Path) -> None:
        """Save history to JSON file."""
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> TuningHistory:
        """Load history from JSON file."""
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls.from_dict(data)
