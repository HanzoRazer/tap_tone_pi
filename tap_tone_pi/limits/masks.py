"""
Frequency masks for excluding regions from limit testing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np


@dataclass
class MaskRegion:
    """
    A frequency region to exclude from testing.

    Useful for:
    - Known resonances to ignore
    - Frequency ranges outside measurement scope
    - AC hum frequencies (50/60 Hz)
    """

    freq_min_hz: float
    freq_max_hz: float
    reason: str = ""

    def __post_init__(self):
        if self.freq_min_hz > self.freq_max_hz:
            self.freq_min_hz, self.freq_max_hz = self.freq_max_hz, self.freq_min_hz

    def contains(self, freq_hz: float) -> bool:
        """Check if frequency is within this mask region."""
        return self.freq_min_hz <= freq_hz <= self.freq_max_hz

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "freq_min_hz": self.freq_min_hz,
            "freq_max_hz": self.freq_max_hz,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MaskRegion":
        """Create from dictionary."""
        return cls(
            freq_min_hz=data["freq_min_hz"],
            freq_max_hz=data["freq_max_hz"],
            reason=data.get("reason", ""),
        )


@dataclass
class FrequencyMask:
    """
    Collection of mask regions.

    Defines which frequency ranges to exclude from limit testing.
    """

    name: str
    regions: List[MaskRegion] = field(default_factory=list)
    description: str = ""

    def is_masked(self, freq_hz: float) -> bool:
        """Check if a frequency is masked (should be excluded)."""
        return any(region.contains(freq_hz) for region in self.regions)

    def get_mask_reason(self, freq_hz: float) -> Optional[str]:
        """Get the reason for masking a frequency, if masked."""
        for region in self.regions:
            if region.contains(freq_hz):
                return region.reason
        return None

    def add_region(
        self,
        freq_min_hz: float,
        freq_max_hz: float,
        reason: str = "",
    ) -> "FrequencyMask":
        """Add a mask region (returns self for chaining)."""
        self.regions.append(
            MaskRegion(
                freq_min_hz=freq_min_hz,
                freq_max_hz=freq_max_hz,
                reason=reason,
            )
        )
        return self

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "regions": [r.to_dict() for r in self.regions],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FrequencyMask":
        """Create from dictionary."""
        regions = [MaskRegion.from_dict(r) for r in data.get("regions", [])]
        return cls(
            name=data["name"],
            regions=regions,
            description=data.get("description", ""),
        )


def create_mask_region(
    freq_min_hz: float,
    freq_max_hz: float,
    reason: str = "",
) -> MaskRegion:
    """Create a single mask region."""
    return MaskRegion(
        freq_min_hz=freq_min_hz,
        freq_max_hz=freq_max_hz,
        reason=reason,
    )


def apply_mask(
    frequencies_hz: np.ndarray,
    values: np.ndarray,
    mask: FrequencyMask,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Apply mask to frequency/value arrays, returning only unmasked data.

    Args:
        frequencies_hz: Array of frequencies
        values: Array of corresponding values
        mask: FrequencyMask to apply

    Returns:
        Tuple of (unmasked_frequencies, unmasked_values)
    """
    if len(frequencies_hz) != len(values):
        raise ValueError("Frequencies and values must have same length")

    keep_mask = np.array([not mask.is_masked(f) for f in frequencies_hz])

    return frequencies_hz[keep_mask], values[keep_mask]


def create_ac_hum_mask(
    include_50hz: bool = True,
    include_60hz: bool = True,
    harmonics: int = 3,
    bandwidth_hz: float = 5.0,
) -> FrequencyMask:
    """
    Create a mask for AC power line hum and harmonics.

    Args:
        include_50hz: Include 50 Hz (European) mains
        include_60hz: Include 60 Hz (US) mains
        harmonics: Number of harmonics to mask
        bandwidth_hz: Width of each mask region

    Returns:
        FrequencyMask for AC hum
    """
    mask = FrequencyMask(name="ac_hum", description="AC power line interference")

    fundamentals = []
    if include_50hz:
        fundamentals.append(50.0)
    if include_60hz:
        fundamentals.append(60.0)

    for fund in fundamentals:
        for h in range(1, harmonics + 1):
            freq = fund * h
            mask.add_region(
                freq_min_hz=freq - bandwidth_hz / 2,
                freq_max_hz=freq + bandwidth_hz / 2,
                reason=f"AC hum: {int(freq)} Hz ({int(fund)} Hz × {h})",
            )

    return mask


def create_subsonic_mask(
    cutoff_hz: float = 20.0,
) -> FrequencyMask:
    """
    Create a mask for subsonic frequencies.

    Args:
        cutoff_hz: Frequencies below this are masked

    Returns:
        FrequencyMask for subsonic
    """
    return FrequencyMask(
        name="subsonic",
        description=f"Subsonic frequencies below {cutoff_hz} Hz",
        regions=[
            MaskRegion(
                freq_min_hz=0.1,  # Effectively 0
                freq_max_hz=cutoff_hz,
                reason="Subsonic (below audible range)",
            )
        ],
    )


def create_ultrasonic_mask(
    cutoff_hz: float = 20000.0,
    sample_rate: int = 48000,
) -> FrequencyMask:
    """
    Create a mask for ultrasonic frequencies.

    Args:
        cutoff_hz: Frequencies above this are masked
        sample_rate: Sample rate (for Nyquist reference)

    Returns:
        FrequencyMask for ultrasonic
    """
    nyquist = sample_rate / 2
    return FrequencyMask(
        name="ultrasonic",
        description=f"Ultrasonic frequencies above {cutoff_hz} Hz",
        regions=[
            MaskRegion(
                freq_min_hz=cutoff_hz,
                freq_max_hz=nyquist,
                reason="Ultrasonic (above audible range)",
            )
        ],
    )


def combine_masks(*masks: FrequencyMask, name: str = "combined") -> FrequencyMask:
    """
    Combine multiple masks into one.

    Args:
        *masks: Masks to combine
        name: Name for combined mask

    Returns:
        Combined FrequencyMask
    """
    combined = FrequencyMask(
        name=name,
        description="Combined mask",
    )

    for mask in masks:
        for region in mask.regions:
            combined.regions.append(region)

    return combined
