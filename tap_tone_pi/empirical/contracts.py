# INSTRUMENT CLASS: MEASUREMENT
"""Empirical model contracts (DO-101A).

These contracts let every scientific equation in the Tap Tone Pi Analyzer exist
as an *empirical model* — carrying assumptions, measurement linkage, validity
domain, uncertainty *references*, calibration history, and evidence references
— without owning or replacing the mathematical implementation.

Constitutional boundary:
- This package owns empirical model *metadata*.
- It does not own mathematical implementations, measurements, laboratory
  workflows, advisory logic, interpretation, or evidence acquisition.
- It does not create a third UncertaintyBudget. Uncertainty is referenced by
  identifier and optional summary only; reconciliation of
  ``tap_tone_pi.uncertainty.budget.UncertaintyBudget`` and
  ``tap_tone_pi.core.statistics.UncertaintyBudget`` is a separate follow-up.

Identity rule: once published, ``(model_id, version)`` never changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


EMPIRICAL_MODEL_DEFINITION_SCHEMA_VERSION = "empirical_model_definition_v1"

#: Schema version for the already-proven formula validation envelope (DO-95),
#: now housed in the empirical package and re-exported from luthiery.
FORMULA_VALIDATION_ENVELOPE_SCHEMA_VERSION = "formula_validation_envelope_v1"

#: Terms that must never appear in empirical model prose (advisory boundary).
FORBIDDEN_ADVISORY_TERMS: frozenset[str] = frozenset(
    {
        "best",
        "optimal",
        "recommended",
        "approved",
        "use_this",
        "prescription",
        "recommend",
        "optimize",
        "grade",
        "good",
        "bad",
        "better",
        "worse",
    }
)


@dataclass(frozen=True)
class ModelInputDefinition:
    """One declared input of an empirical model.

    Describes what the equation consumes. It does not supply a value.
    """

    name: str
    unit: str | None = None
    description: str | None = None
    required: bool = True
    quantity_kind: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "name": self.name,
            "required": self.required,
        }
        if self.unit is not None:
            d["unit"] = self.unit
        if self.description is not None:
            d["description"] = self.description
        if self.quantity_kind is not None:
            d["quantity_kind"] = self.quantity_kind
        return d


@dataclass(frozen=True)
class ModelOutputDefinition:
    """One declared output of an empirical model.

    Describes what the equation produces. It does not supply a value.
    """

    name: str
    unit: str | None = None
    description: str | None = None
    quantity_kind: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"name": self.name}
        if self.unit is not None:
            d["unit"] = self.unit
        if self.description is not None:
            d["description"] = self.description
        if self.quantity_kind is not None:
            d["quantity_kind"] = self.quantity_kind
        return d


@dataclass(frozen=True)
class ValidityDomain:
    """Declared domain of applicability for a model (factual bounds only).

    Generalizes the observed/declared primary-variable range pattern proven in
    DO-95's formula validation envelope. No pass/fail judgement is implied.
    """

    primary_variable_name: str | None = None
    observed_range: tuple[float, float] | None = None
    declared_range: tuple[float, float] | None = None
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {}
        if self.primary_variable_name is not None:
            d["primary_variable_name"] = self.primary_variable_name
        if self.observed_range is not None:
            d["observed_range"] = list(self.observed_range)
        if self.declared_range is not None:
            d["declared_range"] = list(self.declared_range)
        if self.notes:
            d["notes"] = list(self.notes)
        return d


@dataclass(frozen=True)
class MeasurementLink:
    """Reference from a model to a measurement campaign or design.

    Holds identifiers only. It never embeds measurement payloads.
    """

    link_id: str
    role: str
    experiment_design_id: str | None = None
    campaign_id: str | None = None
    session_id: str | None = None
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "link_id": self.link_id,
            "role": self.role,
        }
        if self.experiment_design_id is not None:
            d["experiment_design_id"] = self.experiment_design_id
        if self.campaign_id is not None:
            d["campaign_id"] = self.campaign_id
        if self.session_id is not None:
            d["session_id"] = self.session_id
        if self.notes is not None:
            d["notes"] = self.notes
        return d


@dataclass(frozen=True)
class EvidenceReference:
    """External evidence pointer. Models reference evidence; they never own it."""

    reference_id: str
    kind: str
    citation: str | None = None
    uri: str | None = None
    formula_id: str | None = None
    regression_evidence_id: str | None = None
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "reference_id": self.reference_id,
            "kind": self.kind,
        }
        if self.citation is not None:
            d["citation"] = self.citation
        if self.uri is not None:
            d["uri"] = self.uri
        if self.formula_id is not None:
            d["formula_id"] = self.formula_id
        if self.regression_evidence_id is not None:
            d["regression_evidence_id"] = self.regression_evidence_id
        if self.notes is not None:
            d["notes"] = self.notes
        return d


@dataclass(frozen=True)
class CalibrationRecord:
    """One calibration event in a model's history (metadata only).

    Does not perform calibration or store fitted coefficients as authoritative
    science — those remain with their owning evidence records.
    """

    record_id: str
    calibrated_at_utc: str | None = None
    method: str | None = None
    evidence_reference_id: str | None = None
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"record_id": self.record_id}
        if self.calibrated_at_utc is not None:
            d["calibrated_at_utc"] = self.calibrated_at_utc
        if self.method is not None:
            d["method"] = self.method
        if self.evidence_reference_id is not None:
            d["evidence_reference_id"] = self.evidence_reference_id
        if self.notes is not None:
            d["notes"] = self.notes
        return d


@dataclass(frozen=True)
class UncertaintyReference:
    """Neutral reference to an existing uncertainty record.

    Deliberately *not* an UncertaintyBudget. The repository already has two
    UncertaintyBudget implementations; DO-101A must not invent a third.
    """

    uncertainty_model_id: str | None = None
    uncertainty_record_id: str | None = None
    uncertainty_summary: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {}
        if self.uncertainty_model_id is not None:
            d["uncertainty_model_id"] = self.uncertainty_model_id
        if self.uncertainty_record_id is not None:
            d["uncertainty_record_id"] = self.uncertainty_record_id
        if self.uncertainty_summary is not None:
            d["uncertainty_summary"] = self.uncertainty_summary
        return d


@dataclass(frozen=True)
class EmpiricalModelDefinitionV1:
    """Versioned empirical model metadata around an external equation.

    The mathematical implementation remains wherever it already lives
    (``equation_module`` / ``equation_symbol`` are optional references only).
    """

    model_id: str
    version: int
    title: str
    description: str = ""
    assumptions: tuple[str, ...] = ()
    inputs: tuple[ModelInputDefinition, ...] = ()
    outputs: tuple[ModelOutputDefinition, ...] = ()
    validity_domain: ValidityDomain = field(default_factory=ValidityDomain)
    measurement_links: tuple[MeasurementLink, ...] = ()
    evidence_references: tuple[EvidenceReference, ...] = ()
    calibration_history: tuple[CalibrationRecord, ...] = ()
    uncertainty: UncertaintyReference | None = None
    equation_module: str | None = None
    equation_symbol: str | None = None
    domain: str | None = None
    notes: str | None = None
    epistemic_status: str = field(default="derived", init=False)
    schema_version: str = field(
        default=EMPIRICAL_MODEL_DEFINITION_SCHEMA_VERSION, init=False
    )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dictionary (deterministic keys)."""
        d: dict[str, Any] = {
            "schema_version": self.schema_version,
            "model_id": self.model_id,
            "version": self.version,
            "title": self.title,
            "description": self.description,
            "assumptions": list(self.assumptions),
            "inputs": [item.to_dict() for item in self.inputs],
            "outputs": [item.to_dict() for item in self.outputs],
            "validity_domain": self.validity_domain.to_dict(),
            "measurement_links": [item.to_dict() for item in self.measurement_links],
            "evidence_references": [
                item.to_dict() for item in self.evidence_references
            ],
            "calibration_history": [
                item.to_dict() for item in self.calibration_history
            ],
            "epistemic_status": self.epistemic_status,
        }
        if self.uncertainty is not None:
            d["uncertainty"] = self.uncertainty.to_dict()
        if self.equation_module is not None:
            d["equation_module"] = self.equation_module
        if self.equation_symbol is not None:
            d["equation_symbol"] = self.equation_symbol
        if self.domain is not None:
            d["domain"] = self.domain
        if self.notes is not None:
            d["notes"] = self.notes
        return d


@dataclass(frozen=True)
class FormulaValidationEnvelopeV1:
    """Error-detection envelope around a formula candidate's evidence (DO-95).

    Moved into the empirical package as the shared validation-envelope
    authority. Luthiery re-exports this type unchanged. Every boolean is a
    factual statement about supporting evidence, not a judgement of the
    formula.
    """

    schema_version: str = field(
        default=FORMULA_VALIDATION_ENVELOPE_SCHEMA_VERSION, init=False
    )
    validation_id: str = ""
    formula_id: str = ""
    target_id: str | None = None
    regression_evidence_id: str | None = None
    experiment_design_id: str | None = None
    campaign_id: str | None = None
    sample_count: int = 0
    minimum_sample_count: int = 0
    sample_count_sufficient: bool = False
    process_variance_available: bool = False
    repeatability_available: bool = False
    covariates_present: bool = False
    residual_std_available: bool = False
    r_squared_available: bool = False
    observed_primary_variable_range: tuple[float, float] | None = None
    declared_primary_variable_range: tuple[float, float] | None = None
    extrapolation_detected: bool = False
    validation_notes: tuple[str, ...] = ()
    epistemic_status: str = field(default="derived", init=False)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dictionary for JSON export (byte-stable field set)."""
        d: dict[str, Any] = {
            "schema_version": self.schema_version,
            "validation_id": self.validation_id,
            "formula_id": self.formula_id,
            "sample_count": self.sample_count,
            "minimum_sample_count": self.minimum_sample_count,
            "sample_count_sufficient": self.sample_count_sufficient,
            "process_variance_available": self.process_variance_available,
            "repeatability_available": self.repeatability_available,
            "covariates_present": self.covariates_present,
            "residual_std_available": self.residual_std_available,
            "r_squared_available": self.r_squared_available,
            "extrapolation_detected": self.extrapolation_detected,
            "validation_notes": list(self.validation_notes),
            "epistemic_status": self.epistemic_status,
        }
        if self.target_id is not None:
            d["target_id"] = self.target_id
        if self.regression_evidence_id is not None:
            d["regression_evidence_id"] = self.regression_evidence_id
        if self.experiment_design_id is not None:
            d["experiment_design_id"] = self.experiment_design_id
        if self.campaign_id is not None:
            d["campaign_id"] = self.campaign_id
        if self.observed_primary_variable_range is not None:
            d["observed_primary_variable_range"] = list(
                self.observed_primary_variable_range
            )
        if self.declared_primary_variable_range is not None:
            d["declared_primary_variable_range"] = list(
                self.declared_primary_variable_range
            )
        return d

    def validity_domain(self) -> ValidityDomain:
        """Project the envelope's range pair onto the shared ValidityDomain."""
        return ValidityDomain(
            observed_range=self.observed_primary_variable_range,
            declared_range=self.declared_primary_variable_range,
            notes=self.validation_notes,
        )
