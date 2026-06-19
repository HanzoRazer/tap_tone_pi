# INSTRUMENT CLASS: MEASUREMENT
"""Experiment design contracts for cohort planning (Dev Order 89A).

This package provides first-class experiment design capabilities:
- ExperimentDesignV1: governing object for cohort studies
- DeclaredResponseVariableV1: what outcomes are being measured
- CovariateDefinitionV1: what variables are being tracked
- RandomizationPlanV1: how randomization is handled
- BaselineRebuildPlanV1: when baseline rebuilds occur
- DesignValidationEvidenceV1: completeness validation

No advisory behavior. No formula generation. No statistical recommendations.
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

__all__ = [
    # Response variables
    "MinimumInterestingEffectV1",
    "DeclaredResponseVariableV1",
    "create_response_variable",
    "create_minimum_interesting_effect",
    # Covariates
    "CovariateDefinitionV1",
    "create_covariate",
    # Randomization
    "RandomizationPlanV1",
    "create_randomization_plan",
    # Baseline plan
    "BaselineRebuildPlanV1",
    "create_baseline_rebuild_plan",
    # Experiment design
    "ExperimentDesignV1",
    "create_experiment_design",
    # Validation
    "DesignValidationEvidenceV1",
    "validate_experiment_design",
]
