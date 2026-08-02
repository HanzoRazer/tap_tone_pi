# INSTRUMENT CLASS: MEASUREMENT
"""Luthiery formula target layer (Dev Order 94 / DO-101A consumer).

Connects TTP's measurement stack to empirical luthiery formula development by
attaching luthiery-specific domain meaning (top graduation, bracing, soundhole,
bridge, body air, plate stiffness) to the generic cohort-regression evidence
from DO-89C.

Shared validation-envelope authority now lives in ``tap_tone_pi.empirical``
and is re-exported here so existing imports keep working. Project targets onto
``EmpiricalModelDefinitionV1`` via ``tap_tone_pi.empirical.luthiery_compat``.

This package produces luthiery formula *target evidence*, not luthiery
instructions. No optimization, no design selection, no build prescriptions.
"""

from tap_tone_pi.luthiery.formula_targets import (
    KNOWN_LUTHIERY_FORMULA_DOMAINS,
    LuthieryFormulaDomain,
    LuthieryFormulaEvidenceLinkV1,
    LuthieryFormulaTargetV1,
)
from tap_tone_pi.luthiery.target_helpers import (
    create_luthiery_formula_target,
    link_formula_candidate_to_target,
)
from tap_tone_pi.luthiery.formula_validation import (
    FormulaValidationEnvelopeV1,
    validate_formula_candidate,
    validate_formula_candidate_from_evidence,
)

__all__ = [
    "LuthieryFormulaDomain",
    "KNOWN_LUTHIERY_FORMULA_DOMAINS",
    "LuthieryFormulaTargetV1",
    "LuthieryFormulaEvidenceLinkV1",
    "create_luthiery_formula_target",
    "link_formula_candidate_to_target",
    # Formula validation (DO-95)
    "FormulaValidationEnvelopeV1",
    "validate_formula_candidate",
    "validate_formula_candidate_from_evidence",
]
