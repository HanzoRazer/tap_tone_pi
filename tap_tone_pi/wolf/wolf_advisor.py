"""
Wolf Beat Advisor - Agentic decision support for wolf tone mitigation.

Provides physics-grounded recommendations for laboratory operators based on
the dimensionless avoided-crossing model and measured wolf beat parameters.

The advisor does NOT make decisions - it provides structured recommendations
that require operator validation and laboratory proficiency to interpret.

Decision Framework:
    1. Analyze measurement → Extract physics parameters
    2. Model current state → Avoided-crossing curve
    3. Simulate interventions → Mass/damping/structural
    4. Rank recommendations → Physics-grounded confidence
    5. Generate directive → Structured decision support

Usage:
    from tap_tone_pi.wolf import WolfAdvisor, generate_wolf_directive

    advisor = WolfAdvisor(wolf_result)
    recommendations = advisor.get_recommendations()
    directive = generate_wolf_directive(advisor)
"""

# INSTRUMENT CLASS: DECISION SUPPORT
# Outputs from this module are physics-grounded recommendations,
# NOT calibrated measurement results.
# They MUST NOT appear in viewer_pack_v1 or the provenance chain.
# Operator expertise is required to interpret recommendations.
# See docs/ADR-0009-advisory-boundary.md

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Dict, Any
import uuid

from .wolf_beat import (
    WolfBeatResult,
    PeakPair,
    AvoidedCrossingModel,
    simulate_mass_addition,
    simulate_damping_increase,
)


# -----------------------------------------------------------------------------
# Recommendation Types
# -----------------------------------------------------------------------------


class MitigationType(str, Enum):
    """Types of wolf mitigation strategies."""

    ADD_MASS = "add_mass"  # Wolf eliminator / damper mass
    INCREASE_DAMPING = "increase_damping"  # Soundpost adjustment, dampers
    SHIFT_BODY_MODE = "shift_body_mode"  # Plate thickness, bass bar
    SHIFT_STRING_TUNING = "shift_string"  # Retune string (temporary)
    NO_ACTION = "no_action"  # Wolf is acceptable
    FURTHER_MEASUREMENT = "measure_more"  # Insufficient data


class ConfidenceLevel(str, Enum):
    """Confidence in recommendation based on physics model fit."""

    HIGH = "high"  # Strong physics basis, clear measurement
    MEDIUM = "medium"  # Reasonable model fit, some uncertainty
    LOW = "low"  # Weak model fit, needs validation
    SPECULATIVE = "speculative"  # Physics suggests, but unclear measurement


@dataclass
class MitigationRecommendation:
    """Single mitigation recommendation with physics rationale."""

    mitigation_type: MitigationType
    confidence: ConfidenceLevel
    priority: int  # 1 = highest priority

    # Quantitative prediction
    predicted_effect: str  # "Reduces beat to ~5 Hz (from 10 Hz)"
    predicted_severity: str  # "moderate" -> "mild"
    predicted_merge_ratio: float  # New merge ratio after intervention

    # Action details
    action_summary: str  # "Add 5g wolf eliminator at bridge"
    action_details: List[str]  # Step-by-step guidance

    # Physics rationale
    physics_basis: str  # "Mass reduces coupling: Ω' = Ω/√(1+m'/m)"
    assumptions: List[str]  # What must be true for this to work

    # Validation guidance
    validation_steps: List[str]  # How to verify the intervention worked
    rollback_guidance: str  # What to do if it doesn't work

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for JSON output."""
        return {
            "mitigation_type": self.mitigation_type.value,
            "confidence": self.confidence.value,
            "priority": self.priority,
            "predicted_effect": self.predicted_effect,
            "predicted_severity": self.predicted_severity,
            "predicted_merge_ratio": self.predicted_merge_ratio,
            "action_summary": self.action_summary,
            "action_details": self.action_details,
            "physics_basis": self.physics_basis,
            "assumptions": self.assumptions,
            "validation_steps": self.validation_steps,
            "rollback_guidance": self.rollback_guidance,
        }


@dataclass
class WolfAdvisorResult:
    """Complete advisor output with recommendations."""

    # Analysis summary
    wolf_detected: bool
    worst_severity: str
    worst_freq_hz: Optional[float]
    worst_beat_hz: Optional[float]

    # Physics model
    model: Optional[AvoidedCrossingModel]
    model_confidence: ConfidenceLevel

    # Recommendations (priority-ordered)
    recommendations: List[MitigationRecommendation]

    # Avoided-crossing curve data (for visualization)
    curve_data: Optional[Dict[str, Any]] = None

    # Decision summary
    decision_summary: str = ""
    requires_operator_judgment: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for JSON output."""
        return {
            "schema_id": "wolf_advisor_result_v1",
            "wolf_detected": self.wolf_detected,
            "worst_severity": self.worst_severity,
            "worst_freq_hz": self.worst_freq_hz,
            "worst_beat_hz": self.worst_beat_hz,
            "model": self.model.to_dict() if self.model else None,
            "model_confidence": self.model_confidence.value,
            "recommendations": [r.to_dict() for r in self.recommendations],
            "curve_data": self.curve_data,
            "decision_summary": self.decision_summary,
            "requires_operator_judgment": self.requires_operator_judgment,
        }


# -----------------------------------------------------------------------------
# Wolf Advisor Engine
# -----------------------------------------------------------------------------


class WolfAdvisor:
    """
    Physics-based decision support for wolf tone mitigation.

    This advisor uses the dimensionless avoided-crossing model to:
    1. Understand the current wolf state
    2. Simulate potential interventions
    3. Rank recommendations by predicted effectiveness
    4. Provide physics-grounded guidance

    IMPORTANT: Recommendations require operator validation. The advisor
    provides decision SUPPORT, not decisions.
    """

    def __init__(
        self,
        wolf_result: WolfBeatResult,
        string_linewidth_hz: float = 2.0,
        effective_mass_kg: float = 0.01,
    ):
        """
        Initialize advisor from wolf beat analysis.

        Args:
            wolf_result: Output from analyze_wolf_beat()
            string_linewidth_hz: Estimated string linewidth (default 2 Hz)
            effective_mass_kg: Estimated effective mass (default 10g)
        """
        self.wolf_result = wolf_result
        self.string_linewidth_hz = string_linewidth_hz
        self.effective_mass_kg = effective_mass_kg

        # Build model from worst wolf pair
        self.model: Optional[AvoidedCrossingModel] = None
        self.model_confidence = ConfidenceLevel.LOW
        self._worst_pair: Optional[PeakPair] = None

        if wolf_result.pairs:
            self._worst_pair = self._find_worst_pair()
            if self._worst_pair:
                self.model = AvoidedCrossingModel.from_measurement(
                    self._worst_pair,
                    string_linewidth_hz=string_linewidth_hz,
                )
                self.model_confidence = self._assess_model_confidence()

    def _find_worst_pair(self) -> Optional[PeakPair]:
        """Find the most severe wolf pair."""
        if not self.wolf_result.pairs:
            return None

        severity_order = {"severe": 0, "moderate": 1, "mild": 2, "none": 3}
        sorted_pairs = sorted(
            self.wolf_result.pairs,
            key=lambda p: (severity_order.get(p.wolf_severity, 3), -p.merge_ratio),
        )
        return sorted_pairs[0]

    def _assess_model_confidence(self) -> ConfidenceLevel:
        """Assess confidence in the physics model based on measurement quality."""
        if not self._worst_pair:
            return ConfidenceLevel.LOW

        pair = self._worst_pair

        # Check merge ratio (well-resolved pairs are more reliable)
        if pair.merge_ratio > 2.0:
            base_confidence = ConfidenceLevel.HIGH
        elif pair.merge_ratio > 1.0:
            base_confidence = ConfidenceLevel.MEDIUM
        elif pair.merge_ratio > 0.5:
            base_confidence = ConfidenceLevel.LOW
        else:
            base_confidence = ConfidenceLevel.SPECULATIVE

        # Check fit quality if available
        avg_r_sq = (pair.lower.fit_r_squared + pair.upper.fit_r_squared) / 2
        if avg_r_sq < 0.5:
            # Downgrade confidence if fits are poor
            if base_confidence == ConfidenceLevel.HIGH:
                return ConfidenceLevel.MEDIUM
            elif base_confidence == ConfidenceLevel.MEDIUM:
                return ConfidenceLevel.LOW

        return base_confidence

    def get_recommendations(self) -> List[MitigationRecommendation]:
        """
        Generate prioritized mitigation recommendations.

        Returns:
            List of recommendations ordered by priority (1 = highest)
        """
        recommendations: List[MitigationRecommendation] = []

        # No wolf detected
        if not self._worst_pair or self._worst_pair.wolf_severity == "none":
            recommendations.append(
                MitigationRecommendation(
                    mitigation_type=MitigationType.NO_ACTION,
                    confidence=ConfidenceLevel.HIGH,
                    priority=1,
                    predicted_effect="No intervention needed",
                    predicted_severity="none",
                    predicted_merge_ratio=0.0,
                    action_summary="No wolf tone detected - instrument is acceptable",
                    action_details=[
                        "Continue with normal setup procedures",
                        "Consider archiving this measurement as baseline",
                    ],
                    physics_basis="Merge ratio < 0.5 indicates peaks are not resolvable",
                    assumptions=["Measurement is representative of playing conditions"],
                    validation_steps=["Play test in wolf-prone register"],
                    rollback_guidance="If wolf appears during play, re-measure",
                )
            )
            return recommendations

        # Generate intervention recommendations
        recommendations.extend(self._recommend_mass_addition())
        recommendations.extend(self._recommend_damping_increase())
        recommendations.extend(self._recommend_structural_change())

        # Sort by priority
        recommendations.sort(key=lambda r: r.priority)

        return recommendations

    def _recommend_mass_addition(self) -> List[MitigationRecommendation]:
        """Generate mass addition (wolf eliminator) recommendations."""
        if not self.model or not self._worst_pair:
            return []

        recs = []
        pair = self._worst_pair

        # Test different mass additions
        mass_options = [
            (1.25, "2-3g"),  # 25% mass increase
            (1.5, "5g"),  # 50% mass increase
            (2.0, "10g"),  # 100% mass increase
        ]

        for mass_factor, mass_desc in mass_options:
            new_model = simulate_mass_addition(self.model, mass_factor)
            new_beat = new_model.min_split_hz()
            new_merge = new_beat / (new_model.gamma_b_hz + new_model.gamma_s_hz + 1e-12)
            new_severity = self._classify_predicted_severity(new_merge, new_beat)

            # Skip if no improvement
            if new_severity == pair.wolf_severity:
                continue

            # Determine priority based on predicted improvement
            if new_merge < 0.5:
                priority = 1  # Full elimination
                confidence = ConfidenceLevel.HIGH
            elif new_merge < 1.0:
                priority = 2  # Significant reduction
                confidence = ConfidenceLevel.MEDIUM
            else:
                priority = 3  # Partial reduction
                confidence = ConfidenceLevel.LOW

            recs.append(
                MitigationRecommendation(
                    mitigation_type=MitigationType.ADD_MASS,
                    confidence=confidence,
                    priority=priority,
                    predicted_effect=f"Reduces beat from {pair.delta_f_hz:.1f} Hz to ~{new_beat:.1f} Hz",
                    predicted_severity=new_severity,
                    predicted_merge_ratio=new_merge,
                    action_summary=f"Add {mass_desc} wolf eliminator at bridge",
                    action_details=[
                        f"Attach {mass_desc} wolf eliminator between bridge and tailpiece",
                        "Position 2-3cm from bridge on problematic string",
                        "Fine-tune position by ear while bowing",
                        "Secure with minimal clamping force",
                    ],
                    physics_basis=f"Mass reduces coupling: Ω' = Ω/√{mass_factor:.2f} = {new_model.coupling_omega:.4f}",
                    assumptions=[
                        "Effective mass estimate is accurate (±50%)",
                        "Wolf eliminator couples to string motion",
                        "String frequency near resonance (ξ ≈ 1)",
                    ],
                    validation_steps=[
                        "Re-measure tap tone response with eliminator attached",
                        "Play test in wolf register - check for reduction",
                        "Verify no new unwanted resonances introduced",
                    ],
                    rollback_guidance="Remove wolf eliminator and re-test",
                )
            )

        return recs

    def _recommend_damping_increase(self) -> List[MitigationRecommendation]:
        """Generate damping increase recommendations."""
        if not self.model or not self._worst_pair:
            return []

        recs = []
        pair = self._worst_pair

        # Test damping increase
        damping_factor = 1.5  # 50% more damping
        new_model = simulate_damping_increase(self.model, damping_factor)
        new_linewidth = new_model.gamma_b_hz + new_model.gamma_s_hz
        new_merge = pair.delta_f_hz / (new_linewidth + 1e-12)
        new_severity = self._classify_predicted_severity(new_merge, pair.delta_f_hz)

        if new_severity != pair.wolf_severity:
            recs.append(
                MitigationRecommendation(
                    mitigation_type=MitigationType.INCREASE_DAMPING,
                    confidence=ConfidenceLevel.MEDIUM,
                    priority=2,
                    predicted_effect=f"Increases linewidth from {pair.combined_linewidth_hz:.1f} to ~{new_linewidth:.1f} Hz",
                    predicted_severity=new_severity,
                    predicted_merge_ratio=new_merge,
                    action_summary="Increase body damping via soundpost or internal damper",
                    action_details=[
                        "Option A: Adjust soundpost position (tighter fit = more damping)",
                        "Option B: Add small internal damper on back plate",
                        "Option C: Use different string type with higher internal damping",
                    ],
                    physics_basis="Increased damping widens peaks, promoting merger",
                    assumptions=[
                        "Damping can be modified without changing resonant frequency",
                        "50% damping increase is achievable",
                        "Tonal quality remains acceptable",
                    ],
                    validation_steps=[
                        "Re-measure tap tone - check increased linewidth",
                        "Play test - verify wolf reduction and acceptable tone",
                    ],
                    rollback_guidance="Restore original soundpost position / remove damper",
                )
            )

        return recs

    def _recommend_structural_change(self) -> List[MitigationRecommendation]:
        """Generate structural modification recommendations."""
        if not self._worst_pair:
            return []

        pair = self._worst_pair

        # Only recommend if other methods insufficient
        recs = []

        recs.append(
            MitigationRecommendation(
                mitigation_type=MitigationType.SHIFT_BODY_MODE,
                confidence=ConfidenceLevel.LOW,
                priority=4,  # Last resort
                predicted_effect=f"Shifts body mode away from {pair.center_freq_hz:.0f} Hz",
                predicted_severity="none",  # If successful
                predicted_merge_ratio=0.0,
                action_summary="Modify body mode frequency via structural change",
                action_details=[
                    "CAUTION: Irreversible modifications",
                    "Consult luthier before proceeding",
                    "Options: bass bar adjustment, plate graduation, brace modification",
                ],
                physics_basis="Moving ω_b away from string frequency eliminates coupling",
                assumptions=[
                    "Target frequency shift is achievable (±10-20 Hz typical)",
                    "Structural change doesn't create new problems",
                    "Professional luthier available",
                ],
                validation_steps=[
                    "Full tap tone remeasurement after modification",
                    "Extended play testing across all registers",
                ],
                rollback_guidance="Structural changes are generally irreversible",
            )
        )

        return recs

    def _classify_predicted_severity(self, merge_ratio: float, beat_hz: float) -> str:
        """Classify predicted severity from model."""
        if merge_ratio < 0.5:
            return "none"
        elif merge_ratio < 1.0:
            return "mild"
        elif beat_hz < 1.0:
            return "mild"
        elif beat_hz < 4.0:
            return "severe"
        elif beat_hz < 10.0:
            return "moderate"
        else:
            return "mild"

    def get_result(self) -> WolfAdvisorResult:
        """Generate complete advisor result."""
        recommendations = self.get_recommendations()

        # Generate decision summary
        if not self._worst_pair or self._worst_pair.wolf_severity == "none":
            summary = "No actionable wolf detected. Instrument is acceptable."
        elif (
            recommendations
            and recommendations[0].mitigation_type == MitigationType.ADD_MASS
        ):
            summary = (
                f"Wolf detected at {self._worst_pair.center_freq_hz:.0f} Hz "
                f"(beat: {self._worst_pair.delta_f_hz:.1f} Hz, "
                f"severity: {self._worst_pair.wolf_severity}). "
                f"Recommended: {recommendations[0].action_summary}"
            )
        else:
            summary = (
                f"Wolf detected at {self._worst_pair.center_freq_hz:.0f} Hz. "
                "Multiple mitigation options available - operator judgment required."
            )

        # Generate curve data if model available
        curve_data = None
        if self.model:
            curve_data = self.model.sweep_curve()

        return WolfAdvisorResult(
            wolf_detected=self._worst_pair is not None
            and self._worst_pair.wolf_severity != "none",
            worst_severity=self._worst_pair.wolf_severity
            if self._worst_pair
            else "none",
            worst_freq_hz=self._worst_pair.center_freq_hz if self._worst_pair else None,
            worst_beat_hz=self._worst_pair.delta_f_hz if self._worst_pair else None,
            model=self.model,
            model_confidence=self.model_confidence,
            recommendations=recommendations,
            curve_data=curve_data,
            decision_summary=summary,
            requires_operator_judgment=True,
        )


# -----------------------------------------------------------------------------
# Attention Directive Generation
# -----------------------------------------------------------------------------


@dataclass
class WolfDirective:
    """
    Attention directive for wolf beat decision support.

    This directive can be consumed by the agentic layer to:
    - Focus UI on relevant data
    - Present recommendations to operator
    - Track operator response
    """

    directive_id: str
    directive_type: str = "wolf_mitigation"

    # Context
    session_id: str = ""
    measurement_point_id: str = ""

    # Wolf summary
    wolf_freq_hz: Optional[float] = None
    wolf_beat_hz: Optional[float] = None
    wolf_severity: str = "none"

    # Primary recommendation
    recommendation: Optional[MitigationRecommendation] = None
    alternative_count: int = 0

    # Action prompt
    action_prompt: str = ""
    urgency: str = "normal"  # "normal", "high", "critical"

    # Decision tracking
    requires_response: bool = True
    timeout_seconds: int = 0  # 0 = no timeout

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for JSON output."""
        return {
            "schema_id": "wolf_directive_v1",
            "directive_id": self.directive_id,
            "directive_type": self.directive_type,
            "session_id": self.session_id,
            "measurement_point_id": self.measurement_point_id,
            "wolf_freq_hz": self.wolf_freq_hz,
            "wolf_beat_hz": self.wolf_beat_hz,
            "wolf_severity": self.wolf_severity,
            "recommendation": self.recommendation.to_dict()
            if self.recommendation
            else None,
            "alternative_count": self.alternative_count,
            "action_prompt": self.action_prompt,
            "urgency": self.urgency,
            "requires_response": self.requires_response,
            "timeout_seconds": self.timeout_seconds,
        }


def generate_wolf_directive(
    advisor: WolfAdvisor,
    session_id: str = "",
    measurement_point_id: str = "",
) -> WolfDirective:
    """
    Generate attention directive from advisor result.

    Args:
        advisor: WolfAdvisor instance with analysis complete
        session_id: Optional session identifier
        measurement_point_id: Optional measurement point identifier

    Returns:
        WolfDirective ready for agentic layer consumption
    """
    result = advisor.get_result()
    recommendations = result.recommendations

    # Determine urgency
    if result.worst_severity == "severe":
        urgency = "high"
    elif result.worst_severity == "moderate":
        urgency = "normal"
    else:
        urgency = "normal"

    # Build action prompt
    if not result.wolf_detected:
        action_prompt = "No wolf tone detected. Proceed with normal setup."
    elif recommendations:
        top_rec = recommendations[0]
        action_prompt = (
            f"Wolf detected ({result.worst_severity}). "
            f"Recommendation: {top_rec.action_summary}. "
            f"Confidence: {top_rec.confidence.value}."
        )
    else:
        action_prompt = (
            "Wolf detected but no clear mitigation path. Further measurement needed."
        )

    return WolfDirective(
        directive_id=f"wolf_{uuid.uuid4().hex[:12]}",
        session_id=session_id,
        measurement_point_id=measurement_point_id,
        wolf_freq_hz=result.worst_freq_hz,
        wolf_beat_hz=result.worst_beat_hz,
        wolf_severity=result.worst_severity,
        recommendation=recommendations[0] if recommendations else None,
        alternative_count=len(recommendations) - 1 if recommendations else 0,
        action_prompt=action_prompt,
        urgency=urgency,
        requires_response=result.wolf_detected,
    )


# -----------------------------------------------------------------------------
# Convenience Functions
# -----------------------------------------------------------------------------


def advise_on_wolf(
    wolf_result: WolfBeatResult,
    string_linewidth_hz: float = 2.0,
) -> WolfAdvisorResult:
    """
    One-call convenience function for wolf advice.

    Args:
        wolf_result: Output from analyze_wolf_beat()
        string_linewidth_hz: Estimated string linewidth

    Returns:
        Complete WolfAdvisorResult with recommendations
    """
    advisor = WolfAdvisor(wolf_result, string_linewidth_hz=string_linewidth_hz)
    return advisor.get_result()
