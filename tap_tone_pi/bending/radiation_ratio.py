# INSTRUMENT CLASS: MEASUREMENT
"""Tonewood radiation-ratio formula helpers and V1 contract utilities (BR-045).

Canonical quantity (unscaled SI-derived):

    R = c / ρ
    c = √(E / ρ)
    R = √(E / ρ³)

Tap Tone Pi is the scientific-method reference for this formula definition.
Luthier’s Toolbox is a conforming independent implementation — there is no
runtime import either way.

This module does **not** rank materials, set thresholds, or interpret tone
quality. It calculates and validates the interoperability contract only.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any

FORMULA_ID = "tonewood_radiation_ratio"
FORMULA_VERSION = 1
OUTPUT_CONVENTION = "unscaled_si_derived"
SCALE_FACTOR = 1.0
ROUNDING_DECIMALS = 2
CONTRACT_SCHEMA_VERSION = "tonewood_radiation_ratio_contract_v1"

# Provenance keys excluded from the cross-repository semantic digest.
_PROVENANCE_KEYS = frozenset(
    {
        "authority_repository",
        "authority_contract_path",
        "authority_commit",
        "synchronized_at",
        "semantic_digest_sha256",
    }
)

_CONTRACT_PATH = (
    Path(__file__).resolve().parents[2]
    / "contracts"
    / "tonewood_radiation_ratio_v1.json"
)


class RadiationRatioError(ValueError):
    """Invalid radiation-ratio inputs or contract payload."""


def validate_radiation_ratio_inputs(
    *,
    density_kg_m3: float | None = None,
    wave_speed_m_s: float | None = None,
    dynamic_modulus_pa: float | None = None,
) -> None:
    """Reject non-finite, zero, or negative physical inputs."""
    for name, value in (
        ("density_kg_m3", density_kg_m3),
        ("wave_speed_m_s", wave_speed_m_s),
        ("dynamic_modulus_pa", dynamic_modulus_pa),
    ):
        if value is None:
            continue
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise RadiationRatioError(f"{name} must be a finite number")
        if not math.isfinite(float(value)):
            raise RadiationRatioError(f"{name} must be finite")
        if float(value) <= 0.0:
            raise RadiationRatioError(f"{name} must be > 0")


def calculate_radiation_ratio(
    *,
    wave_speed_m_s: float,
    density_kg_m3: float,
) -> float:
    """Return unrounded R = c / ρ (scale_factor = 1.0)."""
    validate_radiation_ratio_inputs(
        wave_speed_m_s=wave_speed_m_s,
        density_kg_m3=density_kg_m3,
    )
    return float(wave_speed_m_s) / float(density_kg_m3)


def calculate_radiation_ratio_from_modulus(
    *,
    dynamic_modulus_pa: float,
    density_kg_m3: float,
) -> float:
    """Return unrounded R = √(E / ρ³) with E in pascals."""
    validate_radiation_ratio_inputs(
        dynamic_modulus_pa=dynamic_modulus_pa,
        density_kg_m3=density_kg_m3,
    )
    rho = float(density_kg_m3)
    return math.sqrt(float(dynamic_modulus_pa) / (rho**3))


def calculate_radiation_ratio_from_modulus_gpa(
    *,
    dynamic_modulus_gpa: float,
    density_kg_m3: float,
) -> float:
    """Convenience wrapper: converts explicit GPa input to pascals internally."""
    validate_radiation_ratio_inputs(
        dynamic_modulus_pa=float(dynamic_modulus_gpa) * 1e9,
        density_kg_m3=density_kg_m3,
    )
    return calculate_radiation_ratio_from_modulus(
        dynamic_modulus_pa=float(dynamic_modulus_gpa) * 1e9,
        density_kg_m3=density_kg_m3,
    )


def wave_speed_m_s_from_modulus_pa(
    *,
    dynamic_modulus_pa: float,
    density_kg_m3: float,
) -> float:
    """Return unrounded c = √(E / ρ) with E in pascals."""
    validate_radiation_ratio_inputs(
        dynamic_modulus_pa=dynamic_modulus_pa,
        density_kg_m3=density_kg_m3,
    )
    return math.sqrt(float(dynamic_modulus_pa) / float(density_kg_m3))


def formula_identity() -> dict[str, Any]:
    """Additive formula-identity metadata for extensible serialized records."""
    return {
        "formula_id": FORMULA_ID,
        "formula_version": FORMULA_VERSION,
        "output_convention": OUTPUT_CONVENTION,
        "scale_factor": SCALE_FACTOR,
    }


def normalize_radiation_ratio_contract(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Strip repository-local provenance and normalize for digesting."""
    if not isinstance(payload, Mapping):
        raise RadiationRatioError("contract payload must be an object")

    def _normalize(value: Any) -> Any:
        if isinstance(value, Mapping):
            return {
                str(k): _normalize(v)
                for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))
                if str(k) not in _PROVENANCE_KEYS
            }
        if isinstance(value, list):
            return [_normalize(v) for v in value]
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            if not math.isfinite(value):
                raise RadiationRatioError("non-finite numeric value in contract")
            return value
        if value is None or isinstance(value, str):
            return value
        raise RadiationRatioError(
            f"unsupported contract value type: {type(value).__name__}"
        )

    normalized = _normalize(dict(payload))
    fixtures = normalized.get("conformance_fixtures")
    if isinstance(fixtures, list):
        normalized["conformance_fixtures"] = sorted(
            fixtures,
            key=lambda item: (
                str(item.get("fixture_id", "")) if isinstance(item, Mapping) else ""
            ),
        )
    return normalized


def radiation_ratio_contract_digest(payload: Mapping[str, Any]) -> str:
    """SHA-256 over canonical UTF-8 JSON of the normalized semantic contract."""
    normalized = normalize_radiation_ratio_contract(payload)
    encoded = json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_radiation_ratio_contract(
    path: Path | None = None,
) -> dict[str, Any]:
    """Load the published V1 authority contract from disk."""
    contract_path = path or _CONTRACT_PATH
    with contract_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise RadiationRatioError("contract root must be an object")
    return payload


def require_matching_semantic_digest(
    payload: Mapping[str, Any] | None = None,
) -> str:
    """Return the digest; raise if embedded digest disagrees with content."""
    contract = payload if payload is not None else load_radiation_ratio_contract()
    computed = radiation_ratio_contract_digest(contract)
    embedded = contract.get("semantic_digest_sha256")
    if embedded is None:
        raise RadiationRatioError("contract missing semantic_digest_sha256")
    if embedded != computed:
        raise RadiationRatioError(
            "semantic_digest_sha256 does not match normalized contract content"
        )
    return computed
