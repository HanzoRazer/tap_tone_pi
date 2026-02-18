"""
Wood species material database for acoustic analysis.

Provides physical, thermal, and acoustic properties for tonewoods
commonly used in guitar construction.

Example:
    >>> from tap_tone_pi.materials import get_species, list_species
    >>> spruce = get_species("spruce_sitka")
    >>> print(f"Density: {spruce['physical']['density_kg_m3']} kg/m³")
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_DATA_DIR = Path(__file__).parent
_WOOD_SPECIES_PATH = _DATA_DIR / "wood_species.json"

# Cache for loaded data
_wood_species_cache: dict[str, Any] | None = None


def _load_wood_species() -> dict[str, Any]:
    """Load wood species database (cached)."""
    global _wood_species_cache
    if _wood_species_cache is None:
        with open(_WOOD_SPECIES_PATH, "r", encoding="utf-8") as f:
            _wood_species_cache = json.load(f)
    return _wood_species_cache


def get_species(species_id: str) -> dict[str, Any] | None:
    """Get wood species data by ID.

    Args:
        species_id: Species identifier (e.g., "spruce_sitka", "alder")

    Returns:
        Species data dict or None if not found

    Example:
        >>> spruce = get_species("spruce_sitka")
        >>> spruce["physical"]["density_kg_m3"]
        425
    """
    data = _load_wood_species()
    return data.get("species", {}).get(species_id)


def list_species(
    category: str | None = None,
    guitar_relevance: str | None = None,
) -> list[str]:
    """List available species IDs.

    Args:
        category: Filter by category ("hardwood", "softwood")
        guitar_relevance: Filter by relevance ("primary", "established",
                          "emerging", "exploratory")

    Returns:
        List of species IDs matching filters

    Example:
        >>> primary_woods = list_species(guitar_relevance="primary")
        >>> softwoods = list_species(category="softwood")
    """
    data = _load_wood_species()
    species = data.get("species", {})

    result = []
    for species_id, info in species.items():
        if category and info.get("category") != category:
            continue
        if guitar_relevance and info.get("guitar_relevance") != guitar_relevance:
            continue
        result.append(species_id)

    return sorted(result)


def get_acoustic_properties(species_id: str) -> dict[str, Any] | None:
    """Get acoustic-relevant properties for a species.

    Extracts properties most relevant for acoustic analysis:
    - density, specific_gravity
    - Janka hardness
    - grain characteristics
    - lutherie properties

    Args:
        species_id: Species identifier

    Returns:
        Dict with acoustic properties or None if not found
    """
    species = get_species(species_id)
    if species is None:
        return None

    physical = species.get("physical", {})
    lutherie = species.get("lutherie", {})

    return {
        "id": species_id,
        "name": species.get("name"),
        "scientific_name": species.get("scientific_name"),
        "category": species.get("category"),
        # Physical
        "density_kg_m3": physical.get("density_kg_m3"),
        "specific_gravity": physical.get("specific_gravity"),
        "janka_hardness_lbf": physical.get("janka_hardness_lbf"),
        "grain": physical.get("grain"),
        "resinous": physical.get("resinous"),
        # Lutherie
        "guitar_relevance": species.get("guitar_relevance"),
        "typical_uses": lutherie.get("typical_uses", []),
        "tone_character": lutherie.get("tone_character"),
        "sustainability": lutherie.get("sustainability"),
    }


def get_physical_properties(species_id: str) -> dict[str, Any] | None:
    """Get physical properties for inverse design calculations.

    Returns properties needed for plate physics calculations:
    - density (ρ)
    - specific_gravity
    - For wood, E_L and E_C must be estimated or measured

    Args:
        species_id: Species identifier

    Returns:
        Dict with physical properties or None if not found
    """
    species = get_species(species_id)
    if species is None:
        return None

    physical = species.get("physical", {})

    return {
        "id": species_id,
        "name": species.get("name"),
        "category": species.get("category"),
        "density_kg_m3": physical.get("density_kg_m3"),
        "specific_gravity": physical.get("specific_gravity"),
        "janka_hardness_lbf": physical.get("janka_hardness_lbf"),
        "janka_hardness_n": physical.get("janka_hardness_n"),
        "grain": physical.get("grain"),
        "resinous": physical.get("resinous"),
        "workability": physical.get("workability"),
    }


def get_metadata() -> dict[str, Any]:
    """Get database metadata (version, sources, units)."""
    data = _load_wood_species()
    return data.get("_meta", {})


def species_count() -> int:
    """Return total number of species in database."""
    data = _load_wood_species()
    return len(data.get("species", {}))


def search_species(query: str) -> list[str]:
    """Search species by name or alias.

    Args:
        query: Search string (case-insensitive)

    Returns:
        List of matching species IDs
    """
    data = _load_wood_species()
    species = data.get("species", {})
    query_lower = query.lower()

    results = []
    for species_id, info in species.items():
        # Check ID
        if query_lower in species_id.lower():
            results.append(species_id)
            continue
        # Check name
        if query_lower in info.get("name", "").lower():
            results.append(species_id)
            continue
        # Check aliases
        for alias in info.get("aliases", []):
            if query_lower in alias.lower():
                results.append(species_id)
                break

    return sorted(set(results))


__all__ = [
    "get_species",
    "list_species",
    "get_acoustic_properties",
    "get_physical_properties",
    "get_metadata",
    "species_count",
    "search_species",
]
