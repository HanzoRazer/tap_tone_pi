"""
WSI (Wolf Stress Index) curve parser.

Migrated from luthiers-toolbox WsiCurveRenderer.vue.
Handles CSV and JSON formats for wolf note analysis data.
"""

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, List, Tuple


@dataclass
class WsiCurveData:
    freq_hz: List[float] = field(default_factory=list)
    wsi: List[float] = field(default_factory=list)
    loc: List[float] = field(default_factory=list)
    grad: List[float] = field(default_factory=list)
    phase_disorder: List[float] = field(default_factory=list)
    coh_mean: List[float] = field(default_factory=list)
    admissible: List[bool] = field(default_factory=list)
    point_count: int = 0
    freq_range: Tuple[float, float] = (0.0, 0.0)

    def has_coherence(self) -> bool:
        return len(self.coh_mean) > 0

    def has_phase_disorder(self) -> bool:
        return len(self.phase_disorder) > 0

    def get_admissible_regions(self) -> List[Tuple[float, float]]:
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
        if in_region:
            regions.append((start_freq, self.freq_hz[-1]))
        return regions

    def get_problem_frequencies(
        self, wsi_threshold: float = 0.7
    ) -> List[Dict[str, float]]:
        problems = []
        for freq, wsi in zip(self.freq_hz, self.wsi):
            if wsi >= wsi_threshold:
                severity = "high" if wsi > 0.85 else "medium"
                problems.append({"freq_hz": freq, "wsi": wsi, "severity": severity})
        return problems


def parse_wsi_curve(source: str | Path | Dict[str, Any]) -> WsiCurveData:
    if isinstance(source, (str, Path)):
        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        if path.suffix.lower() == ".json":
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return _parse_json(data)
        else:
            return _parse_csv(path)
    else:
        return _parse_json(source)


def _parse_float_col(row, col_map, key):
    col = col_map.get(key)
    if not col or not row.get(col):
        return 0.0
    try:
        return float(row[col])
    except ValueError:
        return 0.0


def _parse_bool_col(row, col_map, key):
    col = col_map.get(key)
    if not col or not row.get(col):
        return False
    val = row[col].lower().strip()
    return val in ("true", "1", "yes", "t")


def _parse_csv(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        first_line = f.readline()
        delimiter = "\t" if first_line.count("\t") > first_line.count(",") else ","
    freq_hz, wsi, loc, grad = [], [], [], []
    phase_disorder, coh_mean, admissible = [], [], []
    with open(file_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        fieldnames = [fn.lower().strip() for fn in reader.fieldnames or []]
        col_map = _map_columns(fieldnames)
        for row in reader:
            row = {k.lower().strip(): v for k, v in row.items()}
            freq_col = col_map.get("freq_hz")
            if not freq_col or not row.get(freq_col):
                continue
            try:
                freq_hz.append(float(row[freq_col]))
            except ValueError:
                continue
            wsi.append(_parse_float_col(row, col_map, "wsi"))
            loc.append(_parse_float_col(row, col_map, "loc"))
            grad.append(_parse_float_col(row, col_map, "grad"))
            phase_disorder.append(_parse_float_col(row, col_map, "phase_disorder"))
            coh_mean.append(_parse_float_col(row, col_map, "coh_mean"))
            admissible.append(_parse_bool_col(row, col_map, "admissible"))
    return WsiCurveData(
        freq_hz=freq_hz,
        wsi=wsi,
        loc=loc,
        grad=grad,
        phase_disorder=phase_disorder,
        coh_mean=coh_mean,
        admissible=admissible,
        point_count=len(freq_hz),
        freq_range=(min(freq_hz), max(freq_hz)) if freq_hz else (0, 0),
    )


def _parse_json(data):
    if "data" in data and isinstance(data["data"], list):
        return _parse_json_array(data["data"])
    freq_hz = _get_float_array(data, ["freq_hz", "frequency", "freq", "f"])
    wsi = _get_float_array(data, ["wsi", "wolf_stress_index", "stress_index"])
    loc = _get_float_array(data, ["loc", "localization", "location"])
    grad = _get_float_array(data, ["grad", "gradient"])
    phase_disorder = _get_float_array(data, ["phase_disorder", "pd", "disorder"])
    coh_mean = _get_float_array(
        data, ["coh_mean", "coherence_mean", "coherence", "coh"]
    )
    admissible = _get_bool_array(data, ["admissible", "valid", "ok"])
    n = len(freq_hz)
    wsi.extend([0.0] * (n - len(wsi)))
    loc.extend([0.0] * (n - len(loc)))
    grad.extend([0.0] * (n - len(grad)))
    phase_disorder.extend([0.0] * (n - len(phase_disorder)))
    coh_mean.extend([0.0] * (n - len(coh_mean)))
    admissible.extend([False] * (n - len(admissible)))
    return WsiCurveData(
        freq_hz=freq_hz,
        wsi=wsi,
        loc=loc,
        grad=grad,
        phase_disorder=phase_disorder,
        coh_mean=coh_mean,
        admissible=admissible,
        point_count=n,
        freq_range=(min(freq_hz), max(freq_hz)) if freq_hz else (0, 0),
    )


def _parse_json_array(arr):
    freq_hz, wsi, loc, grad = [], [], [], []
    phase_disorder, coh_mean, admissible = [], [], []
    for obj in arr:
        freq = obj.get("freq_hz") or obj.get("frequency") or obj.get("freq")
        if freq is None:
            continue
        freq_hz.append(float(freq))
        w = obj.get("wsi") or obj.get("wolf_stress_index")
        wsi.append(float(w) if w is not None else 0.0)
        loc_val = obj.get("loc") or obj.get("localization")
        loc.append(float(loc_val) if l is not None else 0.0)
        g = obj.get("grad") or obj.get("gradient")
        grad.append(float(g) if g is not None else 0.0)
        pd = obj.get("phase_disorder") or obj.get("pd")
        phase_disorder.append(float(pd) if pd is not None else 0.0)
        c = obj.get("coh_mean") or obj.get("coherence")
        coh_mean.append(float(c) if c is not None else 0.0)
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
        freq_range=(min(freq_hz), max(freq_hz)) if freq_hz else (0, 0),
    )


_COLUMN_ALIASES = {
    "freq_hz": {"freq_hz", "frequency", "freq", "f"},
    "wsi": {"wsi", "wolf_stress_index", "stress_index"},
    "loc": {"loc", "localization", "location"},
    "grad": {"grad", "gradient"},
    "phase_disorder": {"phase_disorder", "pd", "disorder"},
    "coh_mean": {"coh_mean", "coherence_mean", "coherence", "coh"},
    "admissible": {"admissible", "valid", "ok"},
}


def _map_columns(fieldnames):
    col_map = {k: None for k in _COLUMN_ALIASES}
    for fn in fieldnames:
        fn_lower = fn.lower()
        for std_name, aliases in _COLUMN_ALIASES.items():
            if fn_lower in aliases:
                col_map[std_name] = fn
                break
    return col_map


def _get_float_array(data, keys):
    for key in keys:
        if isinstance(data.get(key), list):
            return [float(v) for v in data[key]]
    return []


def _get_bool_array(data, keys):
    for key in keys:
        if isinstance(data.get(key), list):
            return [bool(v) for v in data[key]]
    return []
