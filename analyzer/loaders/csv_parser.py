"""
CSV parser for spectrum data files.
"""

import csv
from pathlib import Path
from typing import Dict, Any, List, Optional


class SpectrumCSVParser:
    """
    Parser for spectrum CSV files.

    Expected format:
        freq_hz,H_mag,coherence,phase_deg
        10.0,0.00123,0.95,45.2
        20.0,0.00234,0.97,52.1
        ...

    Or tab-separated:
        freq_hz	H_mag	coherence	phase_deg
        10.0	0.00123	0.95	45.2
        ...
    """

    # Known column name variations
    FREQ_NAMES = {"freq_hz", "frequency", "freq", "f", "frequency_hz"}
    MAG_NAMES = {"h_mag", "magnitude", "mag", "h", "amplitude", "amp"}
    COH_NAMES = {"coherence", "coh", "gamma", "coherence_squared", "coh2"}
    PHASE_NAMES = {"phase_deg", "phase", "phase_degrees", "phi"}

    def parse(self, file_path: Path) -> Dict[str, Any]:
        """
        Parse a spectrum CSV file.

        Args:
            file_path: Path to the CSV file

        Returns:
            Dictionary with freq_hz, H_mag, coherence, phase_deg arrays
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"CSV file not found: {file_path}")

        # Detect delimiter
        delimiter = self._detect_delimiter(file_path)

        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter=delimiter)

            # Map column names
            fieldnames = [fn.lower().strip() for fn in reader.fieldnames or []]
            col_map = self._map_columns(fieldnames)

            freq_hz: List[float] = []
            h_mag: List[float] = []
            coherence: List[float] = []
            phase_deg: List[float] = []

            for row in reader:
                # Normalize row keys
                row = {k.lower().strip(): v for k, v in row.items()}

                # Parse frequency (required)
                freq_col = col_map.get("freq_hz")
                if freq_col and row.get(freq_col):
                    try:
                        freq_hz.append(float(row[freq_col]))
                    except ValueError:
                        continue  # Skip invalid rows

                    # Parse magnitude
                    mag_col = col_map.get("H_mag")
                    if mag_col and row.get(mag_col):
                        try:
                            h_mag.append(float(row[mag_col]))
                        except ValueError:
                            h_mag.append(0.0)
                    else:
                        h_mag.append(0.0)

                    # Parse coherence
                    coh_col = col_map.get("coherence")
                    if coh_col and row.get(coh_col):
                        try:
                            coherence.append(float(row[coh_col]))
                        except ValueError:
                            coherence.append(0.0)
                    else:
                        coherence.append(0.0)

                    # Parse phase
                    phase_col = col_map.get("phase_deg")
                    if phase_col and row.get(phase_col):
                        try:
                            phase_deg.append(float(row[phase_col]))
                        except ValueError:
                            phase_deg.append(0.0)
                    else:
                        phase_deg.append(0.0)

        return {
            "freq_hz": freq_hz,
            "H_mag": h_mag,
            "coherence": coherence,
            "phase_deg": phase_deg,
            "point_count": len(freq_hz),
            "freq_range": [min(freq_hz), max(freq_hz)] if freq_hz else [0, 0]
        }

    def _detect_delimiter(self, file_path: Path) -> str:
        """Detect CSV delimiter (comma or tab)."""
        with open(file_path, 'r', encoding='utf-8') as f:
            first_line = f.readline()

            # Count delimiters
            comma_count = first_line.count(',')
            tab_count = first_line.count('\t')

            return '\t' if tab_count > comma_count else ','

    def _map_columns(self, fieldnames: List[str]) -> Dict[str, Optional[str]]:
        """Map detected column names to standard names."""
        col_map = {
            "freq_hz": None,
            "H_mag": None,
            "coherence": None,
            "phase_deg": None
        }

        for fn in fieldnames:
            fn_lower = fn.lower()

            if fn_lower in self.FREQ_NAMES:
                col_map["freq_hz"] = fn
            elif fn_lower in self.MAG_NAMES:
                col_map["H_mag"] = fn
            elif fn_lower in self.COH_NAMES:
                col_map["coherence"] = fn
            elif fn_lower in self.PHASE_NAMES:
                col_map["phase_deg"] = fn

        return col_map


def parse_spectrum_csv(file_path: str) -> Dict[str, Any]:
    """Convenience function to parse a spectrum CSV file."""
    parser = SpectrumCSVParser()
    return parser.parse(Path(file_path))
