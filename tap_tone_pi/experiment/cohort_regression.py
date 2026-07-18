# INSTRUMENT CLASS: MEASUREMENT
"""Cohort regression evidence contracts (Dev Order 89C).

Implements covariate-aware linear regression for deriving formula candidates
from cohort data. Output is evidence (coefficients, R², residuals), not
recommendations.

The regression helper produces:
- Coefficient estimates with standard errors
- R² and adjusted R²
- Residual standard deviation
- Formula candidate text (descriptive only)

No optimization. No "best" selection. No build prescriptions.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

import numpy as np


@dataclass(frozen=True)
class RegressionInputV1:
    """Input specification for a cohort regression.

    Records what data was used for regression analysis.

    Attributes:
        experiment_design_id: Link to experiment design
        campaign_id: Link to campaign containing cohort
        response_variable_name: Name of response variable
        primary_variable_name: Name of primary predictor
        covariate_names: Names of covariates (alphabetical)
        sample_count: Number of samples
    """

    schema_version: str = field(default="regression_input_v1", init=False)
    experiment_design_id: str = ""
    campaign_id: str = ""
    response_variable_name: str = ""
    primary_variable_name: str = ""
    covariate_names: tuple[str, ...] = ()
    sample_count: int = 0
    epistemic_status: str = field(default="derived", init=False)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON export."""
        return {
            "schema_version": self.schema_version,
            "experiment_design_id": self.experiment_design_id,
            "campaign_id": self.campaign_id,
            "response_variable_name": self.response_variable_name,
            "primary_variable_name": self.primary_variable_name,
            "covariate_names": list(self.covariate_names),
            "sample_count": self.sample_count,
            "epistemic_status": self.epistemic_status,
        }


@dataclass(frozen=True)
class RegressionCoefficientV1:
    """A single regression coefficient with uncertainty.

    Attributes:
        term_name: Name of the term (variable name or "intercept")
        coefficient: Estimated coefficient value
        standard_error: Standard error of the coefficient
        t_statistic: t-statistic (deferred, always None for now)
        p_value: p-value (deferred, always None for now)
    """

    schema_version: str = field(default="regression_coefficient_v1", init=False)
    term_name: str = ""
    coefficient: float = 0.0
    standard_error: float | None = None
    t_statistic: float | None = None
    p_value: float | None = None
    epistemic_status: str = field(default="derived", init=False)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON export."""
        d: dict[str, Any] = {
            "schema_version": self.schema_version,
            "term_name": self.term_name,
            "coefficient": self.coefficient,
            "epistemic_status": self.epistemic_status,
        }
        if self.standard_error is not None:
            d["standard_error"] = self.standard_error
        if self.t_statistic is not None:
            d["t_statistic"] = self.t_statistic
        if self.p_value is not None:
            d["p_value"] = self.p_value
        return d


@dataclass(frozen=True)
class CohortRegressionEvidenceV1:
    """Evidence from a cohort regression analysis.

    Records coefficients, fit statistics, and input metadata.
    This is measurement evidence, not a recommendation.

    Attributes:
        evidence_id: Unique identifier
        experiment_design_id: Link to experiment design
        campaign_id: Link to campaign
        response_variable_name: Name of response variable
        primary_variable_name: Name of primary predictor
        coefficients: Regression coefficients (including intercept)
        intercept: Intercept value (also in coefficients)
        r_squared: Coefficient of determination (None if undefined)
        adjusted_r_squared: Adjusted R² for covariate models
        residual_std: Standard deviation of residuals
        sample_count: Number of samples
        covariate_names: Names of covariates used (alphabetical)
        computed_at_utc: Computation timestamp
    """

    schema_version: str = field(default="cohort_regression_evidence_v1", init=False)
    evidence_id: str = ""
    experiment_design_id: str = ""
    campaign_id: str = ""
    response_variable_name: str = ""
    primary_variable_name: str = ""
    coefficients: tuple[RegressionCoefficientV1, ...] = ()
    intercept: float = 0.0
    r_squared: float | None = None
    adjusted_r_squared: float | None = None
    residual_std: float | None = None
    sample_count: int = 0
    covariate_names: tuple[str, ...] = ()
    computed_at_utc: str | None = None
    epistemic_status: str = field(default="derived", init=False)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON export."""
        d: dict[str, Any] = {
            "schema_version": self.schema_version,
            "evidence_id": self.evidence_id,
            "experiment_design_id": self.experiment_design_id,
            "campaign_id": self.campaign_id,
            "response_variable_name": self.response_variable_name,
            "primary_variable_name": self.primary_variable_name,
            "coefficients": [c.to_dict() for c in self.coefficients],
            "intercept": self.intercept,
            "sample_count": self.sample_count,
            "covariate_names": list(self.covariate_names),
            "epistemic_status": self.epistemic_status,
        }
        if self.r_squared is not None:
            d["r_squared"] = self.r_squared
        if self.adjusted_r_squared is not None:
            d["adjusted_r_squared"] = self.adjusted_r_squared
        if self.residual_std is not None:
            d["residual_std"] = self.residual_std
        if self.computed_at_utc is not None:
            d["computed_at_utc"] = self.computed_at_utc
        return d


@dataclass(frozen=True)
class FormulaCandidateEvidenceV1:
    """A formula candidate derived from regression evidence.

    The formula text is descriptive only — it describes the relationship
    found in the data. It is NOT a recommendation or build instruction.

    Attributes:
        formula_id: Unique identifier
        experiment_design_id: Link to experiment design
        campaign_id: Link to campaign
        response_variable_name: Name of response variable
        formula_text: Descriptive formula (math notation)
        regression_evidence: The underlying regression evidence
        limitations: Known limitations of this formula
    """

    schema_version: str = field(default="formula_candidate_evidence_v1", init=False)
    formula_id: str = ""
    experiment_design_id: str = ""
    campaign_id: str = ""
    response_variable_name: str = ""
    formula_text: str = ""
    regression_evidence: CohortRegressionEvidenceV1 | None = None
    limitations: tuple[str, ...] = ()
    epistemic_status: str = field(default="derived", init=False)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON export."""
        d: dict[str, Any] = {
            "schema_version": self.schema_version,
            "formula_id": self.formula_id,
            "experiment_design_id": self.experiment_design_id,
            "campaign_id": self.campaign_id,
            "response_variable_name": self.response_variable_name,
            "formula_text": self.formula_text,
            "limitations": list(self.limitations),
            "epistemic_status": self.epistemic_status,
        }
        if self.regression_evidence is not None:
            d["regression_evidence"] = self.regression_evidence.to_dict()
        return d


def fit_linear_cohort_regression(
    *,
    evidence_id: str,
    experiment_design_id: str,
    campaign_id: str,
    response_variable_name: str,
    primary_variable_name: str,
    response_values: Sequence[float],
    primary_variable_values: Sequence[float],
    covariates: Mapping[str, Sequence[float]] | None = None,
    timestamp_utc: str | None = None,
) -> CohortRegressionEvidenceV1:
    """Fit a linear regression model to cohort data.

    Uses ordinary least squares (OLS) to fit:
        response = intercept + β_primary × primary + Σ β_cov × covariate

    Args:
        evidence_id: Unique identifier for this evidence
        experiment_design_id: Link to experiment design
        campaign_id: Link to campaign
        response_variable_name: Name of response variable
        primary_variable_name: Name of primary predictor
        response_values: Response variable values
        primary_variable_values: Primary predictor values
        covariates: Optional dict of covariate_name -> values
        timestamp_utc: Computation timestamp (defaults to now)

    Returns:
        CohortRegressionEvidenceV1 with fitted coefficients

    Raises:
        ValueError: If lengths mismatch or fewer than 2 samples
    """
    if timestamp_utc is None:
        timestamp_utc = datetime.now(timezone.utc).isoformat()

    # Convert to arrays
    y = np.array(response_values, dtype=float)
    x_primary = np.array(primary_variable_values, dtype=float)

    n = len(y)

    # Validate lengths
    if len(x_primary) != n:
        raise ValueError(
            f"Length mismatch: response has {n} values, "
            f"primary variable has {len(x_primary)}"
        )

    if n < 2:
        raise ValueError(f"At least 2 samples required, got {n}")

    # Build covariate names (alphabetical) and matrix
    covariate_names: tuple[str, ...] = ()
    covariate_arrays: list[np.ndarray] = []

    if covariates:
        sorted_names = sorted(covariates.keys())
        covariate_names = tuple(sorted_names)
        for name in sorted_names:
            cov_vals = np.array(covariates[name], dtype=float)
            if len(cov_vals) != n:
                raise ValueError(
                    f"Length mismatch: response has {n} values, "
                    f"covariate '{name}' has {len(cov_vals)}"
                )
            covariate_arrays.append(cov_vals)

    # Build design matrix: [1, primary, cov1, cov2, ...]
    X_columns = [np.ones(n), x_primary] + covariate_arrays
    X = np.column_stack(X_columns)

    # Number of predictors (excluding intercept)
    p = X.shape[1] - 1

    # Fit using least squares
    coeffs, residuals_sum, rank, singular_values = np.linalg.lstsq(X, y, rcond=None)

    # Extract coefficients
    intercept = float(coeffs[0])
    primary_coeff = float(coeffs[1])
    covariate_coeffs = [float(c) for c in coeffs[2:]]

    # Compute predictions and residuals
    y_pred = X @ coeffs
    residuals = y - y_pred

    # Compute residual standard deviation
    if n > p + 1:
        residual_std = float(np.sqrt(np.sum(residuals**2) / (n - p - 1)))
    else:
        residual_std = None

    # Compute R² and adjusted R²
    y_mean = np.mean(y)
    ss_tot = np.sum((y - y_mean) ** 2)
    ss_res = np.sum(residuals**2)

    r_squared: float | None = None
    adjusted_r_squared: float | None = None

    if ss_tot > 1e-12:  # Avoid division by zero for constant response
        r_squared = float(1.0 - ss_res / ss_tot)
        if n > p + 1:
            adjusted_r_squared = float(1.0 - (1.0 - r_squared) * (n - 1) / (n - p - 1))
    # else: r_squared remains None (zero response variance)

    # Compute standard errors if possible
    standard_errors: list[float | None] = [None] * len(coeffs)
    if residual_std is not None and n > p + 1:
        try:
            XtX_inv = np.linalg.inv(X.T @ X)
            var_coeffs = (residual_std**2) * np.diag(XtX_inv)
            standard_errors = [
                float(np.sqrt(v)) if v >= 0 else None for v in var_coeffs
            ]
        except np.linalg.LinAlgError:
            pass  # Singular matrix, leave as None

    # Build coefficient records
    all_coefficients: list[RegressionCoefficientV1] = []

    # Intercept
    all_coefficients.append(
        RegressionCoefficientV1(
            term_name="intercept",
            coefficient=intercept,
            standard_error=standard_errors[0],
        )
    )

    # Primary variable
    all_coefficients.append(
        RegressionCoefficientV1(
            term_name=primary_variable_name,
            coefficient=primary_coeff,
            standard_error=standard_errors[1],
        )
    )

    # Covariates
    for i, name in enumerate(covariate_names):
        all_coefficients.append(
            RegressionCoefficientV1(
                term_name=name,
                coefficient=covariate_coeffs[i],
                standard_error=standard_errors[2 + i],
            )
        )

    return CohortRegressionEvidenceV1(
        evidence_id=evidence_id,
        experiment_design_id=experiment_design_id,
        campaign_id=campaign_id,
        response_variable_name=response_variable_name,
        primary_variable_name=primary_variable_name,
        coefficients=tuple(all_coefficients),
        intercept=intercept,
        r_squared=r_squared,
        adjusted_r_squared=adjusted_r_squared,
        residual_std=residual_std,
        sample_count=n,
        covariate_names=covariate_names,
        computed_at_utc=timestamp_utc,
    )


def _format_coefficient_term(coeff: float, var_name: str) -> str:
    """Format a coefficient term for formula text."""
    if coeff >= 0:
        return f"(+{coeff:.4g} × {var_name})"
    else:
        return f"({coeff:.4g} × {var_name})"


def create_formula_candidate_evidence(
    *,
    formula_id: str,
    regression_evidence: CohortRegressionEvidenceV1,
    additional_limitations: Sequence[str] = (),
) -> FormulaCandidateEvidenceV1:
    """Create a formula candidate from regression evidence.

    Generates descriptive formula text in math notation.
    Auto-adds standard limitations.

    Args:
        formula_id: Unique identifier
        regression_evidence: The underlying regression evidence
        additional_limitations: Additional limitations to include

    Returns:
        FormulaCandidateEvidenceV1 with formula text and limitations
    """
    # Build formula text: response = intercept + (coeff × var) + ...
    response_name = regression_evidence.response_variable_name
    intercept = regression_evidence.intercept

    terms = [f"{intercept:.4g}"]

    for coeff in regression_evidence.coefficients:
        if coeff.term_name == "intercept":
            continue
        terms.append(_format_coefficient_term(coeff.coefficient, coeff.term_name))

    formula_text = f"{response_name} = " + " + ".join(terms)

    # Build limitations
    limitations: list[str] = [
        "linear model only",
        f"N={regression_evidence.sample_count} samples",
    ]

    if regression_evidence.r_squared is None:
        limitations.append("R² undefined: zero response variance")

    limitations.extend(additional_limitations)

    return FormulaCandidateEvidenceV1(
        formula_id=formula_id,
        experiment_design_id=regression_evidence.experiment_design_id,
        campaign_id=regression_evidence.campaign_id,
        response_variable_name=response_name,
        formula_text=formula_text,
        regression_evidence=regression_evidence,
        limitations=tuple(limitations),
    )
