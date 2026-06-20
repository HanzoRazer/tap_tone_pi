# INSTRUMENT CLASS: MEASUREMENT
"""Experiment design, process variance, and regression contracts (DO-89A, 89B, 89C).

This package provides first-class experiment design capabilities:
- ExperimentDesignV1: governing object for cohort studies
- DeclaredResponseVariableV1: what outcomes are being measured
- CovariateDefinitionV1: what variables are being tracked
- RandomizationPlanV1: how randomization is handled
- BaselineRebuildPlanV1: when baseline rebuilds occur
- DesignValidationEvidenceV1: completeness validation

Process variance evidence (DO-89B):
- ReferenceBodyRecordV1: metrology standard for σ_measurement isolation
- ProcessVarianceEvidenceV1: variance decomposition with raw values
- VarianceDecompositionV1: σ_total → σ_measurement + σ_build
- FeasibilitySummaryV1: cohort-level variance summary with bands

Cohort regression evidence (DO-89C):
- CohortRegressionEvidenceV1: coefficients, R², residuals from OLS
- FormulaCandidateEvidenceV1: descriptive formula with limitations
- RegressionCoefficientV1: individual coefficient with standard error

No advisory behavior. No formula recommendations. No optimization.
"""

from tap_tone_pi.experiment.response_variables import (
    MinimumInterestingEffectV1,
    DeclaredResponseVariableV1,
    create_response_variable,
    create_minimum_interesting_effect,
)
from tap_tone_pi.experiment.covariates import (
    CovariateDefinitionV1,
    create_covariate,
)
from tap_tone_pi.experiment.randomization import (
    RandomizationPlanV1,
    create_randomization_plan,
)
from tap_tone_pi.experiment.baseline_plan import (
    BaselineRebuildPlanV1,
    create_baseline_rebuild_plan,
)
from tap_tone_pi.experiment.experiment_design import (
    ExperimentDesignV1,
    create_experiment_design,
)
from tap_tone_pi.experiment.validation import (
    DesignValidationEvidenceV1,
    validate_experiment_design,
)
from tap_tone_pi.experiment.reference_body import (
    ReferenceBodyRecordV1,
    create_reference_body,
)
from tap_tone_pi.experiment.process_variance import (
    VarianceDecompositionV1,
    ProcessVarianceEvidenceV1,
    decompose_variance,
    compute_process_variance_evidence,
)
from tap_tone_pi.experiment.feasibility_summary import (
    VarianceBandThresholdsV1,
    FeasibilitySummaryV1,
    classify_variance_band,
    create_feasibility_summary,
)
from tap_tone_pi.experiment.cohort_regression import (
    RegressionInputV1,
    RegressionCoefficientV1,
    CohortRegressionEvidenceV1,
    FormulaCandidateEvidenceV1,
    fit_linear_cohort_regression,
    create_formula_candidate_evidence,
)

__all__ = [
    # Response variables (DO-89A)
    "MinimumInterestingEffectV1",
    "DeclaredResponseVariableV1",
    "create_response_variable",
    "create_minimum_interesting_effect",
    # Covariates (DO-89A)
    "CovariateDefinitionV1",
    "create_covariate",
    # Randomization (DO-89A)
    "RandomizationPlanV1",
    "create_randomization_plan",
    # Baseline plan (DO-89A)
    "BaselineRebuildPlanV1",
    "create_baseline_rebuild_plan",
    # Experiment design (DO-89A)
    "ExperimentDesignV1",
    "create_experiment_design",
    # Validation (DO-89A)
    "DesignValidationEvidenceV1",
    "validate_experiment_design",
    # Reference body (DO-89B)
    "ReferenceBodyRecordV1",
    "create_reference_body",
    # Process variance (DO-89B)
    "VarianceDecompositionV1",
    "ProcessVarianceEvidenceV1",
    "decompose_variance",
    "compute_process_variance_evidence",
    # Feasibility summary (DO-89B)
    "VarianceBandThresholdsV1",
    "FeasibilitySummaryV1",
    "classify_variance_band",
    "create_feasibility_summary",
    # Cohort regression (DO-89C)
    "RegressionInputV1",
    "RegressionCoefficientV1",
    "CohortRegressionEvidenceV1",
    "FormulaCandidateEvidenceV1",
    "fit_linear_cohort_regression",
    "create_formula_candidate_evidence",
]
