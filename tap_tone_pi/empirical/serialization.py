# INSTRUMENT CLASS: MEASUREMENT
"""Deterministic serialization for empirical model contracts (DO-101A).

``to_dict`` / ``from_dict`` round-trips must be identical for every public
contract that crosses a persistence, CLI, export, or repository boundary.

Loaders are at least as strict as the JSON Schema:

* required fields must be present (no silent defaults for required keys);
* unknown keys are rejected (``additionalProperties: false``);
* whitespace-only identifiers are rejected;
* ``empirical_model_from_dict`` runs semantic ``validate_model`` by default.
"""

from __future__ import annotations

from typing import Any, Iterable

from tap_tone_pi.empirical.contracts import (
    EMPIRICAL_MODEL_DEFINITION_SCHEMA_VERSION,
    FORMULA_VALIDATION_ENVELOPE_SCHEMA_VERSION,
    CalibrationRecord,
    EmpiricalModelDefinitionV1,
    EvidenceReference,
    FormulaValidationEnvelopeV1,
    MeasurementLink,
    ModelInputDefinition,
    ModelOutputDefinition,
    UncertaintyReference,
    ValidityDomain,
)
from tap_tone_pi.empirical.errors import EmpiricalErrorCode, ValidationError
from tap_tone_pi.empirical.validation import validate_model


def _require_mapping(payload: Any, *, label: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValidationError(
            EmpiricalErrorCode.PAYLOAD_MALFORMED,
            f"{label} must be a JSON object",
            {"label": label, "got_type": type(payload).__name__},
        )
    return payload


def _reject_unknown_keys(
    payload: dict[str, Any], allowed: Iterable[str], *, label: str
) -> None:
    allowed_set = set(allowed)
    unknown = sorted(key for key in payload if key not in allowed_set)
    if unknown:
        raise ValidationError(
            EmpiricalErrorCode.PAYLOAD_MALFORMED,
            f"{label} contains unknown properties",
            {"label": label, "unknown": unknown},
        )


def _require_present(payload: dict[str, Any], key: str) -> Any:
    if key not in payload:
        raise ValidationError(
            EmpiricalErrorCode.MISSING_REQUIRED_FIELD,
            f"missing required field {key!r}",
            {"field": key},
        )
    return payload[key]


def _require_str(
    payload: dict[str, Any],
    key: str,
    *,
    allow_empty: bool = False,
    strip: bool = True,
) -> str:
    value = _require_present(payload, key)
    if not isinstance(value, str):
        raise ValidationError(
            EmpiricalErrorCode.TYPE_MISMATCH,
            f"{key!r} must be a string",
            {"field": key, "got_type": type(value).__name__},
        )
    if not allow_empty and value.strip() == "":
        raise ValidationError(
            EmpiricalErrorCode.MISSING_REQUIRED_FIELD,
            f"{key!r} must be a non-empty string",
            {"field": key},
        )
    return value.strip() if strip else value


def _optional_str(
    payload: dict[str, Any], key: str, *, collapse_blank: bool = True
) -> str | None:
    if key not in payload or payload[key] is None:
        return None
    value = payload[key]
    if not isinstance(value, str):
        raise ValidationError(
            EmpiricalErrorCode.TYPE_MISMATCH,
            f"{key!r} must be a string or null",
            {"field": key, "got_type": type(value).__name__},
        )
    if collapse_blank and value.strip() == "":
        return None
    return value.strip() if collapse_blank else value


def _require_bool(payload: dict[str, Any], key: str) -> bool:
    value = _require_present(payload, key)
    if not isinstance(value, bool):
        raise ValidationError(
            EmpiricalErrorCode.TYPE_MISMATCH,
            f"{key!r} must be a boolean",
            {"field": key, "got_type": type(value).__name__},
        )
    return value


def _optional_bool(payload: dict[str, Any], key: str, default: bool) -> bool:
    if key not in payload or payload[key] is None:
        return default
    value = payload[key]
    if not isinstance(value, bool):
        raise ValidationError(
            EmpiricalErrorCode.TYPE_MISMATCH,
            f"{key!r} must be a boolean",
            {"field": key, "got_type": type(value).__name__},
        )
    return value


def _require_int(payload: dict[str, Any], key: str) -> int:
    value = _require_present(payload, key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(
            EmpiricalErrorCode.TYPE_MISMATCH,
            f"{key!r} must be an integer",
            {"field": key, "got_type": type(value).__name__},
        )
    return value


def _optional_int(payload: dict[str, Any], key: str, default: int = 0) -> int:
    if key not in payload or payload[key] is None:
        return default
    value = payload[key]
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(
            EmpiricalErrorCode.TYPE_MISMATCH,
            f"{key!r} must be an integer",
            {"field": key, "got_type": type(value).__name__},
        )
    return value


def _optional_range(
    payload: dict[str, Any], key: str
) -> tuple[float, float] | None:
    if key not in payload or payload[key] is None:
        return None
    value = payload[key]
    if not isinstance(value, list) or len(value) != 2:
        raise ValidationError(
            EmpiricalErrorCode.TYPE_MISMATCH,
            f"{key!r} must be a two-element numeric array",
            {"field": key},
        )
    lo, hi = value
    if isinstance(lo, bool) or isinstance(hi, bool):
        raise ValidationError(
            EmpiricalErrorCode.TYPE_MISMATCH,
            f"{key!r} elements must be numbers",
            {"field": key},
        )
    if not isinstance(lo, (int, float)) or not isinstance(hi, (int, float)):
        raise ValidationError(
            EmpiricalErrorCode.TYPE_MISMATCH,
            f"{key!r} elements must be numbers",
            {"field": key},
        )
    return (float(lo), float(hi))


def _require_str_list(payload: dict[str, Any], key: str) -> tuple[str, ...]:
    value = _require_present(payload, key)
    if not isinstance(value, list):
        raise ValidationError(
            EmpiricalErrorCode.TYPE_MISMATCH,
            f"{key!r} must be an array of strings",
            {"field": key, "got_type": type(value).__name__},
        )
    out: list[str] = []
    for i, item in enumerate(value):
        if not isinstance(item, str) or item.strip() == "":
            raise ValidationError(
                EmpiricalErrorCode.TYPE_MISMATCH,
                f"{key!r}[{i}] must be a non-empty string",
                {"field": key, "index": i},
            )
        out.append(item)
    return tuple(out)


def _optional_str_list(payload: dict[str, Any], key: str) -> tuple[str, ...]:
    if key not in payload or payload[key] is None:
        return ()
    value = payload[key]
    if not isinstance(value, list):
        raise ValidationError(
            EmpiricalErrorCode.TYPE_MISMATCH,
            f"{key!r} must be an array of strings",
            {"field": key, "got_type": type(value).__name__},
        )
    out: list[str] = []
    for i, item in enumerate(value):
        if not isinstance(item, str) or item.strip() == "":
            raise ValidationError(
                EmpiricalErrorCode.TYPE_MISMATCH,
                f"{key!r}[{i}] must be a non-empty string",
                {"field": key, "index": i},
            )
        out.append(item)
    return tuple(out)


def _require_list(payload: dict[str, Any], key: str) -> list[Any]:
    value = _require_present(payload, key)
    if not isinstance(value, list):
        raise ValidationError(
            EmpiricalErrorCode.TYPE_MISMATCH,
            f"{key!r} must be an array",
            {"field": key, "got_type": type(value).__name__},
        )
    return value


_MODEL_INPUT_KEYS = frozenset(
    {"name", "unit", "description", "required", "quantity_kind"}
)
_MODEL_OUTPUT_KEYS = frozenset({"name", "unit", "description", "quantity_kind"})
_VALIDITY_DOMAIN_KEYS = frozenset(
    {"primary_variable_name", "observed_range", "declared_range", "notes"}
)
_MEASUREMENT_LINK_KEYS = frozenset(
    {
        "link_id",
        "role",
        "experiment_design_id",
        "campaign_id",
        "session_id",
        "notes",
    }
)
_EVIDENCE_REFERENCE_KEYS = frozenset(
    {
        "reference_id",
        "kind",
        "citation",
        "uri",
        "formula_id",
        "regression_evidence_id",
        "notes",
    }
)
_CALIBRATION_RECORD_KEYS = frozenset(
    {
        "record_id",
        "calibrated_at_utc",
        "method",
        "evidence_reference_id",
        "notes",
    }
)
_UNCERTAINTY_KEYS = frozenset(
    {"uncertainty_model_id", "uncertainty_record_id", "uncertainty_summary"}
)
_EMPIRICAL_MODEL_KEYS = frozenset(
    {
        "schema_version",
        "model_id",
        "version",
        "title",
        "description",
        "assumptions",
        "inputs",
        "outputs",
        "validity_domain",
        "measurement_links",
        "evidence_references",
        "calibration_history",
        "uncertainty",
        "equation_module",
        "equation_symbol",
        "domain",
        "notes",
        "epistemic_status",
    }
)


def model_input_from_dict(payload: Any) -> ModelInputDefinition:
    d = _require_mapping(payload, label="ModelInputDefinition")
    _reject_unknown_keys(d, _MODEL_INPUT_KEYS, label="ModelInputDefinition")
    return ModelInputDefinition(
        name=_require_str(d, "name", strip=True),
        unit=_optional_str(d, "unit"),
        description=_optional_str(d, "description"),
        required=_require_bool(d, "required"),
        quantity_kind=_optional_str(d, "quantity_kind"),
    )


def model_output_from_dict(payload: Any) -> ModelOutputDefinition:
    d = _require_mapping(payload, label="ModelOutputDefinition")
    _reject_unknown_keys(d, _MODEL_OUTPUT_KEYS, label="ModelOutputDefinition")
    return ModelOutputDefinition(
        name=_require_str(d, "name", strip=True),
        unit=_optional_str(d, "unit"),
        description=_optional_str(d, "description"),
        quantity_kind=_optional_str(d, "quantity_kind"),
    )


def validity_domain_from_dict(payload: Any) -> ValidityDomain:
    if payload is None:
        raise ValidationError(
            EmpiricalErrorCode.MISSING_REQUIRED_FIELD,
            "missing required field 'validity_domain'",
            {"field": "validity_domain"},
        )
    d = _require_mapping(payload, label="ValidityDomain")
    _reject_unknown_keys(d, _VALIDITY_DOMAIN_KEYS, label="ValidityDomain")
    return ValidityDomain(
        primary_variable_name=_optional_str(d, "primary_variable_name"),
        observed_range=_optional_range(d, "observed_range"),
        declared_range=_optional_range(d, "declared_range"),
        notes=_optional_str_list(d, "notes"),
    )


def measurement_link_from_dict(payload: Any) -> MeasurementLink:
    d = _require_mapping(payload, label="MeasurementLink")
    _reject_unknown_keys(d, _MEASUREMENT_LINK_KEYS, label="MeasurementLink")
    return MeasurementLink(
        link_id=_require_str(d, "link_id", strip=True),
        role=_require_str(d, "role", strip=True),
        experiment_design_id=_optional_str(d, "experiment_design_id"),
        campaign_id=_optional_str(d, "campaign_id"),
        session_id=_optional_str(d, "session_id"),
        notes=_optional_str(d, "notes"),
    )


def evidence_reference_from_dict(payload: Any) -> EvidenceReference:
    d = _require_mapping(payload, label="EvidenceReference")
    _reject_unknown_keys(d, _EVIDENCE_REFERENCE_KEYS, label="EvidenceReference")
    return EvidenceReference(
        reference_id=_require_str(d, "reference_id", strip=True),
        kind=_require_str(d, "kind", strip=True),
        citation=_optional_str(d, "citation"),
        uri=_optional_str(d, "uri"),
        formula_id=_optional_str(d, "formula_id"),
        regression_evidence_id=_optional_str(d, "regression_evidence_id"),
        notes=_optional_str(d, "notes"),
    )


def calibration_record_from_dict(payload: Any) -> CalibrationRecord:
    d = _require_mapping(payload, label="CalibrationRecord")
    _reject_unknown_keys(d, _CALIBRATION_RECORD_KEYS, label="CalibrationRecord")
    return CalibrationRecord(
        record_id=_require_str(d, "record_id", strip=True),
        calibrated_at_utc=_optional_str(d, "calibrated_at_utc"),
        method=_optional_str(d, "method"),
        evidence_reference_id=_optional_str(d, "evidence_reference_id"),
        notes=_optional_str(d, "notes"),
    )


def uncertainty_reference_from_dict(payload: Any) -> UncertaintyReference | None:
    if payload is None:
        return None
    d = _require_mapping(payload, label="UncertaintyReference")
    _reject_unknown_keys(d, _UNCERTAINTY_KEYS, label="UncertaintyReference")
    ref = UncertaintyReference(
        uncertainty_model_id=_optional_str(d, "uncertainty_model_id"),
        uncertainty_record_id=_optional_str(d, "uncertainty_record_id"),
        uncertainty_summary=_optional_str(d, "uncertainty_summary"),
    )
    if (
        ref.uncertainty_model_id is None
        and ref.uncertainty_record_id is None
        and ref.uncertainty_summary is None
    ):
        return None
    return ref


def empirical_model_to_dict(model: EmpiricalModelDefinitionV1) -> dict[str, Any]:
    """Serialize an empirical model definition."""
    return model.to_dict()


def empirical_model_from_dict(
    payload: Any, *, validate: bool = True
) -> EmpiricalModelDefinitionV1:
    """Deserialize an empirical model definition; strict against the schema.

    Args:
        payload: JSON-compatible mapping.
        validate: When True (default), run semantic ``validate_model`` after
            structural load so persistence boundaries reject advisory prose,
            duplicate names, and inverted ranges.
    """
    d = _require_mapping(payload, label="EmpiricalModelDefinitionV1")
    _reject_unknown_keys(d, _EMPIRICAL_MODEL_KEYS, label="EmpiricalModelDefinitionV1")

    schema_version = _require_str(d, "schema_version")
    if schema_version != EMPIRICAL_MODEL_DEFINITION_SCHEMA_VERSION:
        raise ValidationError(
            EmpiricalErrorCode.UNKNOWN_SCHEMA_VERSION,
            "unsupported empirical model schema_version",
            {
                "schema_version": schema_version,
                "expected": EMPIRICAL_MODEL_DEFINITION_SCHEMA_VERSION,
            },
        )

    # epistemic_status is const "derived" when present.
    if "epistemic_status" in d and d["epistemic_status"] != "derived":
        raise ValidationError(
            EmpiricalErrorCode.TYPE_MISMATCH,
            "epistemic_status must be 'derived'",
            {"field": "epistemic_status", "got": d["epistemic_status"]},
        )

    version = _require_int(d, "version")
    if version < 1:
        raise ValidationError(
            EmpiricalErrorCode.INVALID_VERSION,
            "version must be an integer >= 1",
            {"version": version},
        )

    description = _require_present(d, "description")
    if not isinstance(description, str):
        raise ValidationError(
            EmpiricalErrorCode.TYPE_MISMATCH,
            "'description' must be a string",
            {"field": "description", "got_type": type(description).__name__},
        )

    model = EmpiricalModelDefinitionV1(
        model_id=_require_str(d, "model_id", strip=True),
        version=version,
        title=_require_str(d, "title", strip=True),
        description=description,
        assumptions=_require_str_list(d, "assumptions"),
        inputs=tuple(
            model_input_from_dict(item) for item in _require_list(d, "inputs")
        ),
        outputs=tuple(
            model_output_from_dict(item) for item in _require_list(d, "outputs")
        ),
        validity_domain=validity_domain_from_dict(_require_present(d, "validity_domain")),
        measurement_links=tuple(
            measurement_link_from_dict(item)
            for item in _require_list(d, "measurement_links")
        ),
        evidence_references=tuple(
            evidence_reference_from_dict(item)
            for item in _require_list(d, "evidence_references")
        ),
        calibration_history=tuple(
            calibration_record_from_dict(item)
            for item in _require_list(d, "calibration_history")
        ),
        uncertainty=uncertainty_reference_from_dict(d.get("uncertainty")),
        equation_module=_optional_str(d, "equation_module"),
        equation_symbol=_optional_str(d, "equation_symbol"),
        domain=_optional_str(d, "domain"),
        notes=_optional_str(d, "notes"),
    )
    if validate:
        validate_model(model, raise_on_error=True)
    return model


def formula_validation_envelope_from_dict(payload: Any) -> FormulaValidationEnvelopeV1:
    """Deserialize a formula validation envelope (shared DO-95 contract)."""
    d = _require_mapping(payload, label="FormulaValidationEnvelopeV1")
    schema_version = _require_str(d, "schema_version")
    if schema_version != FORMULA_VALIDATION_ENVELOPE_SCHEMA_VERSION:
        raise ValidationError(
            EmpiricalErrorCode.UNKNOWN_SCHEMA_VERSION,
            "unsupported formula validation envelope schema_version",
            {
                "schema_version": schema_version,
                "expected": FORMULA_VALIDATION_ENVELOPE_SCHEMA_VERSION,
            },
        )
    return FormulaValidationEnvelopeV1(
        validation_id=_require_str(d, "validation_id", strip=True),
        formula_id=_require_str(d, "formula_id", strip=True),
        target_id=_optional_str(d, "target_id"),
        regression_evidence_id=_optional_str(d, "regression_evidence_id"),
        experiment_design_id=_optional_str(d, "experiment_design_id"),
        campaign_id=_optional_str(d, "campaign_id"),
        sample_count=_optional_int(d, "sample_count", 0),
        minimum_sample_count=_optional_int(d, "minimum_sample_count", 0),
        sample_count_sufficient=_optional_bool(d, "sample_count_sufficient", False),
        process_variance_available=_optional_bool(
            d, "process_variance_available", False
        ),
        repeatability_available=_optional_bool(d, "repeatability_available", False),
        covariates_present=_optional_bool(d, "covariates_present", False),
        residual_std_available=_optional_bool(d, "residual_std_available", False),
        r_squared_available=_optional_bool(d, "r_squared_available", False),
        observed_primary_variable_range=_optional_range(
            d, "observed_primary_variable_range"
        ),
        declared_primary_variable_range=_optional_range(
            d, "declared_primary_variable_range"
        ),
        extrapolation_detected=_optional_bool(d, "extrapolation_detected", False),
        validation_notes=_optional_str_list(d, "validation_notes"),
    )


# Public aliases matching the DO-101 handoff names.
to_dict = empirical_model_to_dict
from_dict = empirical_model_from_dict
