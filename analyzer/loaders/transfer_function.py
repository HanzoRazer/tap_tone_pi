"""
Transfer function parser for multiple JSON formats.

Migrated from luthiers-toolbox TransferFunctionRenderer.vue.
Supports 4 different JSON formats commonly used in acoustic analysis tools.
"""

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple


@dataclass
class TransferFunctionData:
    """
    Normalized transfer function data.

    All formats are converted to this common representation.
    """
    frequencies: List[float] = field(default_factory=list)  # Hz
    magnitude: List[float] = field(default_factory=list)    # Linear scale
    magnitude_db: List[float] = field(default_factory=list) # dB scale
    phase: List[float] = field(default_factory=list)        # Degrees
    coherence: List[float] = field(default_factory=list)    # Optional
    point_count: int = 0
    freq_range: Tuple[float, float] = (0.0, 0.0)
    source_format: str = "unknown"

    def has_coherence(self) -> bool:
        """Check if coherence data is present."""
        return len(self.coherence) > 0 and any(c > 0 for c in self.coherence)


def linear_to_db(linear: float, ref: float = 1.0) -> float:
    """
    Convert linear magnitude to dB.

    Args:
        linear: Linear magnitude value
        ref: Reference value (default 1.0)

    Returns:
        Value in decibels
    """
    if linear <= 0:
        return -120.0  # Floor for log
    return 20.0 * math.log10(linear / ref)


def db_to_linear(db: float, ref: float = 1.0) -> float:
    """
    Convert dB to linear magnitude.

    Args:
        db: Value in decibels
        ref: Reference value (default 1.0)

    Returns:
        Linear magnitude
    """
    return ref * (10.0 ** (db / 20.0))


def parse_transfer_function(
    source: str | Path | Dict[str, Any]
) -> TransferFunctionData:
    """
    Parse transfer function data from file or dictionary.

    Automatically detects and handles 4 JSON formats:

    Format 1 - Parallel arrays:
        { "frequencies": [], "magnitude": [], "phase": [] }

    Format 2 - Array of objects:
        { "data": [{ "freq": 100, "mag": 0.5, "phase": 45 }, ...] }

    Format 3 - ODS modes:
        { "modes": [{ "freq": 100, "amplitude": 0.5, "phase": 45 }, ...] }

    Format 4 - FRF complex (real/imag):
        { "frf": { "real": [], "imag": [], "freq": [] } }

    Args:
        source: File path or dictionary containing transfer function data

    Returns:
        Normalized TransferFunctionData
    """
    # Load from file if path given
    if isinstance(source, (str, Path)):
        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    else:
        data = source

    # Detect and parse format
    if _is_format_parallel_arrays(data):
        return _parse_parallel_arrays(data)
    elif _is_format_object_array(data):
        return _parse_object_array(data)
    elif _is_format_ods_modes(data):
        return _parse_ods_modes(data)
    elif _is_format_frf_complex(data):
        return _parse_frf_complex(data)
    else:
        # Try to parse as generic with common field names
        return _parse_generic(data)


def _is_format_parallel_arrays(data: Dict[str, Any]) -> bool:
    """Check if data is Format 1: parallel arrays."""
    return (
        isinstance(data.get("frequencies"), list) and
        isinstance(data.get("magnitude"), list)
    )


def _is_format_object_array(data: Dict[str, Any]) -> bool:
    """Check if data is Format 2: array of objects."""
    arr = data.get("data")
    if not isinstance(arr, list) or len(arr) == 0:
        return False
    first = arr[0]
    return isinstance(first, dict) and ("freq" in first or "frequency" in first)


def _is_format_ods_modes(data: Dict[str, Any]) -> bool:
    """Check if data is Format 3: ODS modes."""
    modes = data.get("modes")
    if not isinstance(modes, list) or len(modes) == 0:
        return False
    first = modes[0]
    return isinstance(first, dict) and ("freq" in first or "frequency" in first)


def _is_format_frf_complex(data: Dict[str, Any]) -> bool:
    """Check if data is Format 4: FRF complex."""
    frf = data.get("frf")
    if not isinstance(frf, dict):
        return False
    return (
        isinstance(frf.get("real"), list) and
        isinstance(frf.get("imag"), list) and
        isinstance(frf.get("freq"), list)
    )


def _parse_parallel_arrays(data: Dict[str, Any]) -> TransferFunctionData:
    """Parse Format 1: parallel arrays."""
    frequencies = [float(f) for f in data.get("frequencies", [])]
    magnitude = [float(m) for m in data.get("magnitude", [])]
    phase = [float(p) for p in data.get("phase", [])]
    coherence = [float(c) for c in data.get("coherence", [])]

    # Ensure arrays match length
    n = len(frequencies)
    while len(magnitude) < n:
        magnitude.append(0.0)
    while len(phase) < n:
        phase.append(0.0)

    # Convert to dB
    magnitude_db = [linear_to_db(m) for m in magnitude]

    return TransferFunctionData(
        frequencies=frequencies,
        magnitude=magnitude,
        magnitude_db=magnitude_db,
        phase=phase,
        coherence=coherence,
        point_count=n,
        freq_range=(min(frequencies), max(frequencies)) if frequencies else (0, 0),
        source_format="parallel_arrays"
    )


def _parse_object_array(data: Dict[str, Any]) -> TransferFunctionData:
    """Parse Format 2: array of objects."""
    arr = data.get("data", [])

    frequencies = []
    magnitude = []
    phase = []
    coherence = []

    for obj in arr:
        # Frequency
        freq = obj.get("freq") or obj.get("frequency") or obj.get("f")
        if freq is not None:
            frequencies.append(float(freq))

            # Magnitude
            mag = obj.get("mag") or obj.get("magnitude") or obj.get("amp") or obj.get("amplitude")
            magnitude.append(float(mag) if mag is not None else 0.0)

            # Phase
            ph = obj.get("phase") or obj.get("phase_deg") or obj.get("phi")
            phase.append(float(ph) if ph is not None else 0.0)

            # Coherence
            coh = obj.get("coherence") or obj.get("coh") or obj.get("gamma")
            if coh is not None:
                coherence.append(float(coh))

    magnitude_db = [linear_to_db(m) for m in magnitude]

    return TransferFunctionData(
        frequencies=frequencies,
        magnitude=magnitude,
        magnitude_db=magnitude_db,
        phase=phase,
        coherence=coherence,
        point_count=len(frequencies),
        freq_range=(min(frequencies), max(frequencies)) if frequencies else (0, 0),
        source_format="object_array"
    )


def _parse_ods_modes(data: Dict[str, Any]) -> TransferFunctionData:
    """Parse Format 3: ODS modes."""
    modes = data.get("modes", [])

    frequencies = []
    magnitude = []
    phase = []

    for mode in modes:
        freq = mode.get("freq") or mode.get("frequency")
        if freq is not None:
            frequencies.append(float(freq))

            amp = mode.get("amplitude") or mode.get("mag") or mode.get("magnitude")
            magnitude.append(float(amp) if amp is not None else 0.0)

            ph = mode.get("phase") or mode.get("phase_deg")
            phase.append(float(ph) if ph is not None else 0.0)

    magnitude_db = [linear_to_db(m) for m in magnitude]

    return TransferFunctionData(
        frequencies=frequencies,
        magnitude=magnitude,
        magnitude_db=magnitude_db,
        phase=phase,
        coherence=[],
        point_count=len(frequencies),
        freq_range=(min(frequencies), max(frequencies)) if frequencies else (0, 0),
        source_format="ods_modes"
    )


def _parse_frf_complex(data: Dict[str, Any]) -> TransferFunctionData:
    """Parse Format 4: FRF complex (real/imag)."""
    frf = data.get("frf", {})

    real = [float(r) for r in frf.get("real", [])]
    imag = [float(i) for i in frf.get("imag", [])]
    frequencies = [float(f) for f in frf.get("freq", [])]

    # Convert complex to magnitude and phase
    magnitude = []
    phase = []

    for r, i in zip(real, imag):
        mag = math.sqrt(r * r + i * i)
        magnitude.append(mag)
        # Phase in degrees
        phase.append(math.degrees(math.atan2(i, r)))

    magnitude_db = [linear_to_db(m) for m in magnitude]

    return TransferFunctionData(
        frequencies=frequencies,
        magnitude=magnitude,
        magnitude_db=magnitude_db,
        phase=phase,
        coherence=[],
        point_count=len(frequencies),
        freq_range=(min(frequencies), max(frequencies)) if frequencies else (0, 0),
        source_format="frf_complex"
    )


def _parse_generic(data: Dict[str, Any]) -> TransferFunctionData:
    """Try to parse generic format with common field names."""
    frequencies = []
    magnitude = []
    phase = []
    coherence = []

    # Try to find frequency array
    for key in ["frequencies", "frequency", "freq", "freq_hz", "f"]:
        if isinstance(data.get(key), list):
            frequencies = [float(f) for f in data[key]]
            break

    if not frequencies:
        raise ValueError("Cannot detect transfer function format: no frequency data found")

    # Try to find magnitude array
    for key in ["magnitude", "mag", "amplitude", "amp", "H_mag", "h_mag"]:
        if isinstance(data.get(key), list):
            magnitude = [float(m) for m in data[key]]
            break

    # If magnitude is in dB, convert
    if "magnitude_db" in data or "mag_db" in data:
        db_key = "magnitude_db" if "magnitude_db" in data else "mag_db"
        db_vals = [float(d) for d in data[db_key]]
        magnitude = [db_to_linear(d) for d in db_vals]

    # Try to find phase array
    for key in ["phase", "phase_deg", "phi"]:
        if isinstance(data.get(key), list):
            phase = [float(p) for p in data[key]]
            break

    # Try to find coherence array
    for key in ["coherence", "coh", "gamma"]:
        if isinstance(data.get(key), list):
            coherence = [float(c) for c in data[key]]
            break

    # Ensure arrays match
    n = len(frequencies)
    while len(magnitude) < n:
        magnitude.append(0.0)
    while len(phase) < n:
        phase.append(0.0)

    magnitude_db = [linear_to_db(m) for m in magnitude]

    return TransferFunctionData(
        frequencies=frequencies,
        magnitude=magnitude,
        magnitude_db=magnitude_db,
        phase=phase,
        coherence=coherence,
        point_count=n,
        freq_range=(min(frequencies), max(frequencies)) if frequencies else (0, 0),
        source_format="generic"
    )
