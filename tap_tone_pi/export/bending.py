# INSTRUMENT CLASS: MEASUREMENT
"""
Bending Data Export — Integrates bending MOE data into viewer_pack_v1.

Reads bending_moe.json from a bending session directory and formats it
for inclusion in the viewer pack manifest. This enables the Production Shop
inverse brace engine to use measured E_L and E_C values instead of species averages.

Usage:
    from tap_tone_pi.export.bending import load_bending_data, BendingData

    # Load from bending session
    bending = load_bending_data("out/bending_session_001")
    
    # Get dict for viewer pack manifest
    manifest_section = bending.to_manifest_dict()
    
    # Or use the integration function
    from tap_tone_pi.export.bending import add_bending_to_manifest
    manifest = add_bending_to_manifest(manifest, bending_dir)
"""

from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Optional, Literal


@dataclass
class BendingData:
    """
    Bending stiffness measurement data.
    
    All values are measurements — no interpretation or grading.
    The orthotropic_ratio is computed for convenience but is not
    an interpretation; it's a derived measurement.
    """
    
    # Core measurements
    E_L_GPa: float  # Longitudinal (along-grain) Young's modulus
    E_C_GPa: Optional[float] = None  # Cross-grain (transverse) Young's modulus
    
    # Derived values
    specific_modulus_GPa_per_gcm3: Optional[float] = None  # E/density
    c_m_s: Optional[float] = None  # Speed of sound in material
    density_g_cm3: Optional[float] = None
    
    # Test parameters
    span_mm: float = 400.0
    method: Literal["3point", "4point"] = "3point"
    
    # Provenance
    source_bundle: Optional[str] = None  # Path or SHA256 of source data
    
    @property
    def orthotropic_ratio(self) -> Optional[float]:
        """E_L / E_C ratio. Good acoustic wood is 8:1 to 18:1."""
        if self.E_C_GPa and self.E_C_GPa > 0:
            return self.E_L_GPa / self.E_C_GPa
        return None
    
    def to_manifest_dict(self) -> Dict[str, Any]:
        """Convert to dict for viewer_pack_v1 manifest bending section."""
        d: Dict[str, Any] = {
            "E_L_GPa": round(self.E_L_GPa, 3),
        }
        
        if self.E_C_GPa is not None:
            d["E_C_GPa"] = round(self.E_C_GPa, 3)
        
        if self.specific_modulus_GPa_per_gcm3 is not None:
            d["specific_modulus_GPa_per_gcm3"] = round(self.specific_modulus_GPa_per_gcm3, 3)
        
        if self.c_m_s is not None:
            d["c_m_s"] = round(self.c_m_s, 1)
        
        if self.density_g_cm3 is not None:
            d["density_g_cm3"] = round(self.density_g_cm3, 4)
        
        d["span_mm"] = self.span_mm
        d["method"] = self.method
        
        if self.source_bundle is not None:
            d["source_bundle"] = self.source_bundle
        
        if self.orthotropic_ratio is not None:
            d["orthotropic_ratio"] = round(self.orthotropic_ratio, 1)
        
        return d
    
    @classmethod
    def from_moe_json(cls, data: Dict[str, Any], source_path: Optional[str] = None) -> "BendingData":
        """
        Create BendingData from bending_moe.json format.
        
        Expected format (from merge_and_moe.py output):
        {
            "E_GPa": 10.5,
            "specific_modulus_GPa_per_gcm3": 26.25,
            "c_m_s": 5123.0,
            "density_g_cm3": 0.40,
            "span_mm": 400,
            "method": "3point",
            ...
        }
        """
        return cls(
            E_L_GPa=data.get("E_GPa", data.get("E_L_GPa", 0.0)),
            E_C_GPa=data.get("E_C_GPa"),
            specific_modulus_GPa_per_gcm3=data.get("specific_modulus_GPa_per_gcm3"),
            c_m_s=data.get("c_m_s"),
            density_g_cm3=data.get("density_g_cm3"),
            span_mm=data.get("span_mm", 400.0),
            method=data.get("method", "3point"),
            source_bundle=source_path,
        )


def load_bending_data(bending_dir: Path | str) -> BendingData:
    """
    Load bending data from a bending session directory.
    
    Looks for bending_moe.json in the directory.
    
    Args:
        bending_dir: Path to bending session directory
    
    Returns:
        BendingData object
    
    Raises:
        FileNotFoundError: If bending_moe.json not found
        json.JSONDecodeError: If JSON is invalid
    """
    bending_dir = Path(bending_dir)
    moe_file = bending_dir / "bending_moe.json"
    
    if not moe_file.exists():
        raise FileNotFoundError(f"bending_moe.json not found in {bending_dir}")
    
    with open(moe_file, "r") as f:
        data = json.load(f)
    
    # Compute source bundle hash for provenance
    with open(moe_file, "rb") as f:
        source_hash = hashlib.sha256(f.read()).hexdigest()
    
    source_path = f"{bending_dir.name}/bending_moe.json:{source_hash[:16]}"
    
    return BendingData.from_moe_json(data, source_path=source_path)


def load_bending_pair(
    along_grain_dir: Path | str,
    cross_grain_dir: Optional[Path | str] = None,
) -> BendingData:
    """
    Load bending data from paired along-grain and cross-grain sessions.
    
    Args:
        along_grain_dir: Path to along-grain bending session (E_L)
        cross_grain_dir: Optional path to cross-grain session (E_C)
    
    Returns:
        BendingData with both E_L and E_C if cross_grain_dir provided
    """
    along_data = load_bending_data(along_grain_dir)
    
    if cross_grain_dir is not None:
        cross_data = load_bending_data(cross_grain_dir)
        along_data.E_C_GPa = cross_data.E_L_GPa  # Cross-grain E is the "E_L" of that test
    
    return along_data


def add_bending_to_manifest(
    manifest: Dict[str, Any],
    bending_dir: Optional[Path | str] = None,
    bending_data: Optional[BendingData] = None,
) -> Dict[str, Any]:
    """
    Add bending section to a viewer_pack_v1 manifest.
    
    Modifies the manifest in place and returns it.
    
    Args:
        manifest: The viewer pack manifest dict
        bending_dir: Path to bending session directory (loads data)
        bending_data: Pre-loaded BendingData (takes precedence over bending_dir)
    
    Returns:
        Modified manifest dict
    
    Raises:
        ValueError: If neither bending_dir nor bending_data provided
    """
    if bending_data is None:
        if bending_dir is None:
            raise ValueError("Must provide either bending_dir or bending_data")
        bending_data = load_bending_data(bending_dir)
    
    # Add bending section to manifest
    manifest["bending"] = bending_data.to_manifest_dict()
    
    # Update contents flags
    if "contents" in manifest:
        manifest["contents"]["bending"] = True
    
    return manifest


def validate_bending_section(bending: Dict[str, Any]) -> tuple[bool, list[str]]:
    """
    Validate a bending section against expected constraints.
    
    Args:
        bending: The bending section dict from manifest
    
    Returns:
        (is_valid, list_of_errors)
    """
    errors = []
    
    # Required field
    if "E_L_GPa" not in bending:
        errors.append("Missing required field: E_L_GPa")
    elif not isinstance(bending["E_L_GPa"], (int, float)):
        errors.append("E_L_GPa must be a number")
    elif not (0.1 <= bending["E_L_GPa"] <= 50.0):
        errors.append(f"E_L_GPa={bending['E_L_GPa']} out of valid range (0.1-50.0)")
    
    # Optional E_C validation
    if "E_C_GPa" in bending and bending["E_C_GPa"] is not None:
        if not isinstance(bending["E_C_GPa"], (int, float)):
            errors.append("E_C_GPa must be a number")
        elif not (0.01 <= bending["E_C_GPa"] <= 10.0):
            errors.append(f"E_C_GPa={bending['E_C_GPa']} out of valid range (0.01-10.0)")
    
    # Method validation
    if "method" in bending:
        if bending["method"] not in ("3point", "4point"):
            errors.append(f"Invalid method: {bending['method']}")
    
    # Orthotropic ratio sanity check
    if "orthotropic_ratio" in bending:
        ratio = bending["orthotropic_ratio"]
        if ratio < 1:
            errors.append(f"orthotropic_ratio={ratio} < 1 (E_L should be > E_C)")
        elif ratio > 50:
            errors.append(f"orthotropic_ratio={ratio} > 50 (implausibly high)")
    
    return len(errors) == 0, errors


def demo():
    """Demo bending export functionality."""
    import tempfile
    import os
    
    # Create synthetic bending_moe.json
    test_data = {
        "E_GPa": 10.5,
        "specific_modulus_GPa_per_gcm3": 26.25,
        "c_m_s": 5123.0,
        "density_g_cm3": 0.40,
        "span_mm": 400,
        "method": "3point",
    }
    
    with tempfile.TemporaryDirectory() as tmpdir:
        bending_dir = Path(tmpdir) / "bending_session"
        bending_dir.mkdir()
        
        moe_file = bending_dir / "bending_moe.json"
        with open(moe_file, "w") as f:
            json.dump(test_data, f, indent=2)
        
        # Load and display
        bending = load_bending_data(bending_dir)
        print("Loaded bending data:")
        print(f"  E_L = {bending.E_L_GPa:.2f} GPa")
        print(f"  Specific modulus = {bending.specific_modulus_GPa_per_gcm3:.2f} GPa/(g/cm³)")
        print(f"  c = {bending.c_m_s:.0f} m/s")
        print()
        
        # Show manifest format
        manifest_dict = bending.to_manifest_dict()
        print("Manifest section:")
        print(json.dumps(manifest_dict, indent=2))
        print()
        
        # Validate
        is_valid, errors = validate_bending_section(manifest_dict)
        print(f"Valid: {is_valid}")
        if errors:
            for e in errors:
                print(f"  Error: {e}")


if __name__ == "__main__":
    demo()
