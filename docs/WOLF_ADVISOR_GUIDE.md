# Wolf Advisor - Decision Support Guide

**Document ID:** LOM-WBA-002
**Version:** 1.0
**Effective Date:** 2026-02-16
**Classification:** Technical Operations

---

## 1. Overview

The Wolf Advisor provides physics-grounded decision support using the **dimensionless avoided-crossing model**. It does NOT make decisions autonomously - it provides structured recommendations that require operator validation and laboratory proficiency.

This guide supplements `LAB_MANUAL_WOLF_BEAT_ANALYSIS.md` with detailed usage of the decision support capabilities.

---

## 2. Avoided-Crossing Physics Model

### 2.1 Theoretical Foundation

The advisor uses the characteristic equation for coupled oscillators:

```
λ±(ξ) = [1 + ξ² ± √((1 - ξ²)² + 4Ω²ξ²)] / 2
```

Where:
- `ξ = ωs/ωb` (string-to-body frequency ratio, detuning parameter)
- `Ω² = κ²/(4ωb²mb)` (dimensionless coupling strength)
- `λ = ω²/ωb²` (normalized eigenfrequency squared)

### 2.2 Key Physics

At resonance (ξ = 1):
- **Minimum gap:** Δλ = 2Ω (the avoided crossing)
- **Beat frequency:** f_beat ≈ Ω × f_body

The **damping collapse criterion** determines when peaks merge:
```
Δf < (γ_body + γ_string)  →  Peaks unresolvable (wolf masked)
```

---

## 3. Using the Wolf Advisor

### 3.1 Basic Usage

```python
from tap_tone.wolf_beat import analyze_wolf_beat
from tap_tone.wolf_advisor import WolfAdvisor, advise_on_wolf

# First, run wolf beat analysis
result = analyze_wolf_beat(frequencies, magnitude, phase)

# Create advisor from result
advisor = WolfAdvisor(result, string_linewidth_hz=2.0)

# Get recommendations
recommendations = advisor.get_recommendations()

for rec in recommendations:
    print(f"Priority {rec.priority}: {rec.action_summary}")
    print(f"  Confidence: {rec.confidence.value}")
    print(f"  Predicted effect: {rec.predicted_effect}")
    print(f"  Physics basis: {rec.physics_basis}")
```

### 3.2 Convenience Function

```python
advisor_result = advise_on_wolf(result)
print(advisor_result.decision_summary)
```

### 3.3 Full Result Structure

```python
result = advisor.get_result()

# Access structured output
print(f"Wolf detected: {result.wolf_detected}")
print(f"Worst severity: {result.worst_severity}")
print(f"Worst frequency: {result.worst_freq_hz} Hz")
print(f"Model confidence: {result.model_confidence.value}")
print(f"Decision summary: {result.decision_summary}")

# Serialize for storage/transmission
import json
print(json.dumps(result.to_dict(), indent=2))
```

---

## 4. Mitigation Recommendations

### 4.1 Recommendation Types

| Type | Physics | Typical Action |
|------|---------|----------------|
| **ADD_MASS** | Ω' = Ω/√(1+m'/m) | Wolf eliminator 2-10g |
| **INCREASE_DAMPING** | γ' = γ × factor | Soundpost, internal damper |
| **SHIFT_BODY_MODE** | Move ωb | Structural modification |
| **NO_ACTION** | - | Wolf acceptable |
| **FURTHER_MEASUREMENT** | - | Insufficient data |

### 4.2 Recommendation Fields

Each `MitigationRecommendation` includes:

```python
rec = recommendations[0]

# Core fields
rec.mitigation_type      # MitigationType enum
rec.confidence           # ConfidenceLevel enum
rec.priority             # 1 = highest

# Predictions
rec.predicted_effect     # "Reduces beat to ~5 Hz (from 10 Hz)"
rec.predicted_severity   # "mild"
rec.predicted_merge_ratio  # 0.7

# Action guidance
rec.action_summary       # "Add 5g wolf eliminator at bridge"
rec.action_details       # ["Step 1", "Step 2", ...]

# Physics rationale
rec.physics_basis        # "Mass reduces coupling: Ω' = Ω/√1.5"
rec.assumptions          # ["Effective mass estimate accurate", ...]

# Validation
rec.validation_steps     # ["Re-measure tap tone", ...]
rec.rollback_guidance    # "Remove wolf eliminator and re-test"
```

---

## 5. Physics Model Operations

### 5.1 Building a Model from Measurement

```python
from tap_tone.wolf_beat import AvoidedCrossingModel

if result.pairs:
    pair = result.pairs[0]
    model = AvoidedCrossingModel.from_measurement(pair)

    print(f"Body mode: {model.omega_b_hz:.1f} Hz")
    print(f"Coupling: Ω = {model.coupling_omega:.4f}")
    print(f"Body linewidth: {model.gamma_b_hz:.1f} Hz")
    print(f"String linewidth: {model.gamma_s_hz:.1f} Hz")
    print(f"Min split: {model.min_split_hz():.1f} Hz")
    print(f"Resolvable: {model.is_resolvable_at(1.0)}")
```

### 5.2 Simulating Mass Addition

```python
from tap_tone.wolf_beat import simulate_mass_addition

# Double the effective mass
heavier = simulate_mass_addition(model, mass_factor=2.0)

print(f"Original coupling: Ω = {model.coupling_omega:.4f}")
print(f"New coupling: Ω = {heavier.coupling_omega:.4f}")
print(f"Original split: {model.min_split_hz():.1f} Hz")
print(f"New split: {heavier.min_split_hz():.1f} Hz")
print(f"Still resolvable: {heavier.is_resolvable_at(1.0)}")
```

### 5.3 Simulating Damping Increase

```python
from tap_tone.wolf_beat import simulate_damping_increase

# 50% more damping
damped = simulate_damping_increase(model, damping_factor=1.5)

original_linewidth = model.gamma_b_hz + model.gamma_s_hz
new_linewidth = damped.gamma_b_hz + damped.gamma_s_hz

print(f"Original linewidth: {original_linewidth:.1f} Hz")
print(f"New linewidth: {new_linewidth:.1f} Hz")
print(f"Still resolvable: {damped.is_resolvable_at(1.0)}")
```

### 5.4 Generating Avoided-Crossing Curves

```python
# Sweep across detuning range
curve_data = model.sweep_curve(xi_min=0.7, xi_max=1.3, n_points=200)

# Available data:
#   curve_data["xi"]           - detuning values
#   curve_data["f_minus_hz"]   - lower branch frequencies
#   curve_data["f_plus_hz"]    - upper branch frequencies
#   curve_data["beat_hz"]      - beat frequency
#   curve_data["merge_ratio"]  - resolvability metric
#   curve_data["resolvable"]   - boolean array
#   curve_data["severity"]     - severity classification

# For plotting
import matplotlib.pyplot as plt
xi = curve_data["xi"]
plt.plot(xi, curve_data["f_minus_hz"], label="f-")
plt.plot(xi, curve_data["f_plus_hz"], label="f+")
plt.axvline(1.0, linestyle="--", label="Resonance")
plt.xlabel("ξ = ωs/ωb")
plt.ylabel("Frequency (Hz)")
plt.legend()
plt.title("Avoided Crossing Curve")
```

---

## 6. Attention Directives

For integration with agentic systems, generate structured directives:

```python
from tap_tone.wolf_advisor import generate_wolf_directive

directive = generate_wolf_directive(
    advisor,
    session_id="session_001",
    measurement_point_id="A1"
)

print(f"Directive ID: {directive.directive_id}")
print(f"Directive type: {directive.directive_type}")
print(f"Urgency: {directive.urgency}")
print(f"Action prompt: {directive.action_prompt}")
print(f"Requires response: {directive.requires_response}")
print(f"Alternative count: {directive.alternative_count}")

# Wolf summary
print(f"Wolf frequency: {directive.wolf_freq_hz} Hz")
print(f"Wolf beat: {directive.wolf_beat_hz} Hz")
print(f"Wolf severity: {directive.wolf_severity}")

# Primary recommendation
if directive.recommendation:
    rec = directive.recommendation
    print(f"Top recommendation: {rec.action_summary}")

# Serialize
import json
print(json.dumps(directive.to_dict(), indent=2))
```

### 6.1 Directive Fields

```python
# Schema: wolf_directive_v1
{
    "directive_id": "wolf_abc123def456",
    "directive_type": "wolf_mitigation",
    "session_id": "session_001",
    "measurement_point_id": "A1",
    "wolf_freq_hz": 200.0,
    "wolf_beat_hz": 3.5,
    "wolf_severity": "severe",
    "recommendation": { ... },
    "alternative_count": 2,
    "action_prompt": "Wolf detected (severe). Recommendation: Add 5g wolf eliminator. Confidence: high.",
    "urgency": "high",
    "requires_response": true,
    "timeout_seconds": 0
}
```

---

## 7. Confidence Levels

### 7.1 Level Definitions

| Level | Merge Ratio | Fit Quality | Interpretation |
|-------|-------------|-------------|----------------|
| **HIGH** | >2.0 | R² >0.8 | Strong physics basis |
| **MEDIUM** | 1.0-2.0 | R² >0.5 | Reasonable model fit |
| **LOW** | 0.5-1.0 | R² <0.5 | Needs validation |
| **SPECULATIVE** | <0.5 | - | Model unclear |

### 7.2 Factors Affecting Confidence

- **Merge ratio**: Well-resolved peaks (>2.0) give high confidence
- **Lorentzian fit R²**: Good fits (>0.8) confirm peak shapes
- **Peak amplitude balance**: Similar amplitudes suggest true coupling
- **Frequency proximity**: Pairs too close may be fitting artifacts

---

## 8. Operator Responsibility

### 8.1 Critical Notice

**The Wolf Advisor provides decision SUPPORT, not decisions.**

### 8.2 Operator Checklist

Before acting on recommendations:

- [ ] Validate physics assumptions match the instrument
- [ ] Verify measurement quality (coherence >0.85)
- [ ] Check model confidence level
- [ ] Consider instrument-specific factors not in model
- [ ] Review all alternatives, not just top recommendation

After intervention:

- [ ] Re-measure to validate effectiveness
- [ ] Compare predicted vs actual effect
- [ ] Document any deviations from model predictions
- [ ] Update assumptions if needed

### 8.3 Model Assumptions

The advisor assumes:
- Effective mass estimate is approximate (±50%)
- String frequency is near body mode (ξ ≈ 1)
- Linear coupling (small amplitude regime)
- No additional coupled modes interfering
- Lorentzian peak shapes (single-mode approximation)

---

## 9. Complete Example

```python
#!/usr/bin/env python3
"""Complete wolf advisor workflow."""

from pathlib import Path
import numpy as np
import json

from tap_tone.wolf_beat import analyze_wolf_beat, AvoidedCrossingModel
from tap_tone.wolf_advisor import (
    WolfAdvisor,
    advise_on_wolf,
    generate_wolf_directive,
)

# Load data
session_dir = Path("runs/gold/2026-02-16/violin_01/session_001")
data = np.load(session_dir / "derived" / "transfer_functions.npz")
freqs = data["freqs"]
H = data["H_real"] + 1j * data["H_imag"]
magnitude = np.abs(H[0, :])
phase = np.angle(H[0, :], deg=True)

# 1. Run wolf beat analysis
result = analyze_wolf_beat(
    freqs, magnitude, phase,
    min_freq_hz=180.0,
    max_freq_hz=350.0,
)

print(f"=== Wolf Beat Analysis ===")
print(f"Peaks: {result.n_peaks}")
print(f"Pairs: {result.n_pairs}")
print(f"Worst wolf: {result.worst_wolf_freq_hz:.1f} Hz ({result.worst_wolf_severity})")

# 2. Get advisor recommendations
advisor = WolfAdvisor(result, string_linewidth_hz=2.0)
advisor_result = advisor.get_result()

print(f"\n=== Wolf Advisor ===")
print(f"Model confidence: {advisor_result.model_confidence.value}")
print(f"Decision summary: {advisor_result.decision_summary}")

# 3. Review recommendations
print(f"\n=== Recommendations ===")
for i, rec in enumerate(advisor_result.recommendations, 1):
    print(f"\n[{i}] {rec.action_summary}")
    print(f"    Priority: {rec.priority}, Confidence: {rec.confidence.value}")
    print(f"    Predicted: {rec.predicted_effect}")
    print(f"    Physics: {rec.physics_basis}")

# 4. Simulate interventions
if advisor.model:
    model = advisor.model
    print(f"\n=== Simulation ===")

    from tap_tone.wolf_beat import simulate_mass_addition, simulate_damping_increase

    # Test mass additions
    for mass_desc, factor in [("5g", 1.5), ("10g", 2.0)]:
        sim = simulate_mass_addition(model, factor)
        print(f"+ {mass_desc}: split {sim.min_split_hz():.1f} Hz, resolvable: {sim.is_resolvable_at(1.0)}")

# 5. Generate directive for agentic systems
directive = generate_wolf_directive(advisor, session_id="session_001")
print(f"\n=== Attention Directive ===")
print(f"ID: {directive.directive_id}")
print(f"Urgency: {directive.urgency}")
print(f"Prompt: {directive.action_prompt}")

# 6. Save reports
output_dir = session_dir / "derived"
with open(output_dir / "wolf_advisor_result.json", "w") as f:
    json.dump(advisor_result.to_dict(), f, indent=2)

with open(output_dir / "wolf_directive.json", "w") as f:
    json.dump(directive.to_dict(), f, indent=2)

print(f"\n=== Reports saved to {output_dir} ===")
```

---

## 10. Schema Reference

### 10.1 wolf_advisor_result_v1

```json
{
  "schema_id": "wolf_advisor_result_v1",
  "wolf_detected": true,
  "worst_severity": "severe",
  "worst_freq_hz": 200.0,
  "worst_beat_hz": 3.5,
  "model": {
    "omega_b_hz": 200.0,
    "coupling_omega": 0.0175,
    "gamma_b_hz": 4.5,
    "gamma_s_hz": 2.0,
    "min_split_hz": 3.5,
    "damping_collapse_threshold_xi": 1.0
  },
  "model_confidence": "high",
  "recommendations": [ ... ],
  "curve_data": { ... },
  "decision_summary": "Wolf detected at 200 Hz...",
  "requires_operator_judgment": true
}
```

### 10.2 wolf_directive_v1

```json
{
  "schema_id": "wolf_directive_v1",
  "directive_id": "wolf_abc123",
  "directive_type": "wolf_mitigation",
  "session_id": "session_001",
  "measurement_point_id": "A1",
  "wolf_freq_hz": 200.0,
  "wolf_beat_hz": 3.5,
  "wolf_severity": "severe",
  "recommendation": { ... },
  "alternative_count": 2,
  "action_prompt": "Wolf detected (severe)...",
  "urgency": "high",
  "requires_response": true,
  "timeout_seconds": 0
}
```

---

## 11. Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-02-16 | Tap Tone Team | Initial release |

---

*End of Document*
