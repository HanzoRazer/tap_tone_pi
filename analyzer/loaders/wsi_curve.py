"""
WSI (Wolf Stress Index) curve parser.

Migrated from luthiers-toolbox WsiCurveRenderer.vue.
Handles CSV and JSON formats for wolf note analysis data.
"""

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple


@dataclass
class WsiCurveData:
    """
    Normalized WSI curve data.

    WSI (Wolf Stress Index) identifies problem frequencies where
    the instrument may have wolf notes or other acoustic issues.
    """
    freq_hz: List[float] = field(default_factory=list)
    wsi: List[float] = field(default_factory=list)              # Wolf Stress Index
    loc: List[float] = field(default_factory=list)              # Localization
    grad: List[float] = field(default_factory=list)             # Gradient
    phase_disorder: List[float] = field(default_factory=list)   # Phase disorder
    coh_mean: List[float] = field(default_factory=list)         # Mean coherence
    admissible: List[bool] = field(default_factory=list)        # Admissible region
    point_count: int = 0
    freq_range: Tuple[float, float] = (0.0, 0.0)

    def has_coherence(self) -> bool:
        """Check if coherence data is present."""
        return len(self.coh_mean) > 0

    def has_phase_disorder(self) -> bool:
        """Check if phase disorder data is present."""
        return len(self.phase_disorder) > 0

    def get_admissible_regions(self) -> List[Tuple[float, float]]:
        """
        Get contiguous frequency ranges where signal is admissible.

        Returns:
            List of (start_freq, end_freq) tuples
        """
        if not self.admissible or len(self.admissible) != len(self.freq_hz):
            return []

        regions = []
        in_region = False
        start_freq = 0.0

        for freq, adm in zip(self.freq_hz, self.admissible):
            if adm and not in_region:
                in_region = True
                start_freq = freq
            elif not adm and in_region:
                in_region = False
                regions.append((start_freq, freq))

        # Close final region if still open
        if in_region:
            regions.append((start_freq, self.freq_hz[-1]))

        return regions

    def get_problem_frequencies(self, wsi_threshold: float = 0.7) -> List[Dict[str, float]]:
        """
        Find frequencies with high WSI values (potential wolf notes).

        Args:
            wsi_threshold: Minimum WSI value to flag (0-1)

        Returns:
            List of problem frequency dicts with freq_hz, wsi, severity
        """
        problems = []
        for freq, wsi in zip(self.freq_hz, self.wsi):
            if wsi >= wsi_threshold:
                severity = "high" if wsi > 0.85 else "medium"
                problems.append({
                    "freq_hz": freq,
                    "wsi": wsi,
                    "severity": severity
                })
        return problems


def parse_wsi_curve(source: str | Path | Dict[str, Any]) -> WsiCurveData:
    """
    Parse WSI curve data from file or dictionary.

    Handles both CSV and JSON formats:

    CSV format:
        freq_hz,wsi,loc,grad,phase_disorder,coh_mean,admissible
        100.0,0.2,0.1,0.05,0.3,0.85,true
        ...

    JSON format:
        { "freq_hz": [], "wsi": [], "loc": [], ... }

    Args:
        source: File path or dictionary containing WSI data

    Returns:
        Normalized WsiCurveData
    """
    if isinstance(source, (str, Path)):
        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        if path.suffix.lower() == ".json":
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return _parse_json(data)
        else:
            return _parse_csv(path)
    else:
        return _parse_json(source)


def _parse_csv(file_path: Path) -> WsiCurveData:
    """Parse WSI curve from CSV file."""
    # Detect delimiter
    with open(file_path, 'r', encoding='utf-8') as f:
        first_line = f.readline()
        delimiter = '\t' if first_line.count('\t') > first_line.count(',') else ','

    freq_hz = []
    wsi = []
    loc = []
    grad = []
    phase_disorder = []
    coh_mean = []
    admissible = []

    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter=delimiter)

        # Normalize field names
        fieldnames = [fn.lower().strip() for fn in reader.fieldnames or []]
        col_map = _map_columns(fieldnames)

        for row in reader:
            # Normalize row keys
            row = {k.lower().strip(): v for k, v in row.items()}

            # Frequency (required)
            freq_col = col_map.get("freq_hz")
            if not freq_col or not row.get(freq_col):
                continue

            try:
                freq_hz.append(float(row[freq_col]))
            except ValueError:
                continue

            # WSI
            wsi_col = col_map.get("wsi")
            if wsi_col and row.get(wsi_col):
                try:
                    wsi.append(float(row[wsi_col]))
                except ValueError:
                    wsi.append(0.0)
            else:
                wsi.append(0.0)

            # Localization
            loc_col = col_map.get("loc")
            if loc_col and row.get(loc_col):
                try:
                    loc.append(float(row[loc_col]))
                except ValueError:
                    loc.append(0.0)
            else:
                loc.append(0.0)

            # Gradient
            grad_col = col_map.get("grad")
            if grad_col and row.get(grad_col):
                try:
                    grad.append(float(row[grad_col]))
                except ValueError:
                    grad.append(0.0)
            else:
                grad.append(0.0)

            # Phase disorder
            pd_col = col_map.get("phase_disorder")
            if pd_col and row.get(pd_col):
                try:
                    phase_disorder.append(float(row[pd_col]))
                except ValueError:
                    phase_disorder.append(0.0)
            else:
                phase_disorder.append(0.0)

            # Coherence mean
            coh_col = col_map.get("coh_mean")
            if coh_col and row.get(coh_col):
                try:
                    coh_mean.append(float(row[coh_col]))
                except ValueError:
                    coh_mean.append(0.0)
            else:
                coh_mean.append(0.0)

            # Admissible
            adm_col = col_map.get("admissible")
            if adm_col and row.get(adm_col):
                val = row[adm_col].lower().strip()
                admissible.append(val in ("true", "1", "yes", "t"))
            else:
                admissible.append(False)

    return WsiCurveData(
        freq_hz=freq_hz,
        wsi=wsi,
        loc=loc,
        grad=grad,
        phase_disorder=phase_disorder,
        coh_mean=coh_mean,
        admissible=admissible,
        point_count=len(freq_hz),
        freq_range=(min(freq_hz), max(freq_hz)) if freq_hz else (0, 0)
    )


def _parse_json(data: Dict[str, Any]) -> WsiCurveData:
    """Parse WSI curve from JSON data."""
    # Handle nested data structure
    if "data" in data and isinstance(data["data"], list):
        return _parse_json_array(data["data"])

    # Direct array format
    freq_hz = _get_float_array(data, ["freq_hz", "frequency", "freq", "f"])
    wsi = _get_float_array(data, ["wsi", "wolf_stress_index", "stress_index"])
    loc = _get_float_array(data, ["loc", "localization", "location"])
    grad = _get_float_array(data, ["grad", "gradient"])
    phase_disorder = _get_float_array(data, ["phase_disorder", "pd", "disorder"])
    coh_mean = _get_float_array(data, ["coh_mean", "coherence_mean", "coherence", "coh"])
    admissible = _get_bool_array(data, ["admissible", "valid", "ok"])

    # Ensure arrays match frequency length
    n = len(freq_hz)
    while len(wsi) < n:
        wsi.append(0.0)
    while len(loc) < n:
        loc.append(0.0)
    while len(grad) < n:
        grad.append(0.0)
    while len(phase_disorder) < n:
        phase_disorder.append(0.0)
    while len(coh_mean) < n:
        coh_mean.append(0.0)
    while len(admissible) < n:
        admissible.append(False)

    return WsiCurveData(
        freq_hz=freq_hz,
        wsi=wsi,
        loc=loc,
        grad=grad,
        phase_disorder=phase_disorder,
        coh_mean=coh_mean,
        admissible=admissible,
        point_count=n,
        freq_range=(min(freq_hz), max(freq_hz)) if freq_hz else (0, 0)
    )


def _parse_json_array(arr: List[Dict[str, Any]]) -> WsiCurveData:
    """Parse WSI curve from array of objects."""
    freq_hz = []
    wsi = []
    loc = []
    grad = []
    phase_disorder = []
    coh_mean = []
    admissible = []

    for obj in arr:
        # Frequency
        freq = obj.get("freq_hz") or obj.get("frequency") or obj.get("freq")
        if freq is None:
            continue

        freq_hz.append(float(freq))

        # WSI
        w = obj.get("wsi") or obj.get("wolf_stress_index")
        wsi.append(float(w) if w is not None else 0.0)

        # Localization
        l = obj.get("loc") or obj.get("localization")
        loc.append(float(l) if l is not None else 0.0)

        # Gradient
        g = obj.get("grad") or obj.get("gradient")
        grad.append(float(g) if g is not None else 0.0)

        # Phase disorder
        pd = obj.get("phase_disorder") or obj.get("pd")
        phase_disorder.append(float(pd) if pd is not None else 0.0)

        # Coherence mean
        c = obj.get("coh_mean") or obj.get("coherence")
        coh_mean.append(float(c) if c is not None else 0.0)

        # Admissible
        a = obj.get("admissible") or obj.get("valid")
        admissible.append(bool(a) if a is not None else False)

    return WsiCurveData(
        freq_hz=freq_hz,
        wsi=wsi,
        loc=loc,
        grad=grad,
        phase_disorder=phase_disorder,
        coh_mean=coh_mean,
        admissible=admissible,
        point_count=len(freq_hz),
        freq_range=(min(freq_hz), max(freq_hz)) if freq_hz else (0, 0)
    )


def _map_columns(fieldnames: List[str]) -> Dict[str, Optional[str]]:
    """Map column names to standard names."""
    col_map: Dict[str, Optional[str]] = {
        "freq_hz": None,
        "wsi": None,
        "loc": None,
        "grad": None,
        "phase_disorder": None,
        "coh_mean": None,
        "admissible": None
    }

    freq_names = {"freq_hz", "frequency", "freq", "f"}
    wsi_names = {"wsi", "wolf_stress_index", "stress_index"}
    loc_names = {"loc", "localization", "location"}
    grad_names = {"grad", "gradient"}
    pd_names = {"phase_disorder", "pd", "disorder"}
    coh_names = {"coh_mean", "coherence_mean", "coherence", "coh"}
    adm_names = {"admissible", "valid", "ok"}

    for fn in fieldnames:
        fn_lower = fn.lower()

        if fn_lower in freq_names:
            col_map["freq_hz"] = fn
        elif fn_lower in wsi_names:
            col_map["wsi"] = fn
        elif fn_lower in loc_names:
            col_map["loc"] = fn
        elif fn_lower in grad_names:
            col_map["grad"] = fn
        elif fn_lower in pd_names:
            col_map["phase_disorder"] = fn
        elif fn_lower in coh_names:
            col_map["coh_mean"] = fn
        elif fn_lower in adm_names:
            col_map["admissible"] = fn

    return col_map


def _get_float_array(data: Dict[str, Any], keys: List[str]) -> List[float]:
    """Get float array from data using multiple possible keys."""
    for key in keys:
        if isinstance(data.get(key), list):
            return [float(v) for v in data[key]]
    return []


def _get_bool_array(data: Dict[str, Any], keys: List[str]) -> List[bool]:
    """Get boolean array from data using multiple possible keys."""
    for key in keys:
        if isinstance(data.get(key), list):
            return [bool(v) for v in data[key]]
    return []
