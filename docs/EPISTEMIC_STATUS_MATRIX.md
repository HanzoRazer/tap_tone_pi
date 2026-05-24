# Epistemic Status Matrix

Quick reference for developers. See ADR-0011 and ADR-0012 for full definitions.

---

## Field/Artifact Status Reference

| Field/Artifact | Epistemic Status | Authority Domain | Export Allowed |
|----------------|------------------|------------------|----------------|
| `audio.wav` | Observed | Measurement record | Yes |
| `analysis.json.peaks` | Derived | Measurement computation | Yes |
| `analysis.json.transfer_function` | Derived | Measurement computation | Yes |
| `quality_check.json` | Derived | Measurement validity | Yes |
| `coherence` | Derived | Measurement computation | Yes |
| `snr_estimate` | Estimated | Limited inference | Yes, with uncertainty |
| `session_timeline_v1.json` | Heuristic/Provenance | Advisory provenance | Yes, meta only |
| AGE directive | Heuristic | Decision support | Meta/advisory only |
| Wolf candidate | Heuristic | Decision support | Meta/advisory only |
| Toolbox target | Predicted | External interpretation | Import only / marked |
| Rayleigh-Ritz mode | Predicted | Model expectation | Marked as prediction |
| Operator note | Operator-Annotated | Human judgment | Yes, with attribution |
| Material DB lookup | Externally-Sourced | Source-bound | With source citation |
| Calibration cert | Externally-Sourced | Source-bound | With source citation |

---

## Status Quick Reference

| Status | One-Line Definition | Can Become Measurement? |
|--------|---------------------|-------------------------|
| Observed | Direct sensor capture | Already is |
| Derived | Computed from Observed | Yes |
| Estimated | Approximation with uncertainty | Yes, with bounds |
| Predicted | Model output | No |
| Heuristic | Rule-based suggestion | No |
| Operator-Annotated | Human input | No |
| Externally-Sourced | Imported data | No |

---

## Authority Inheritance Rules

```
Observed → Derived     ✓  (algorithm transforms observation)
Derived → Estimated    ✓  (uncertainty acknowledged)
Any → Heuristic        ✓  (explicit downgrade for advisory)
Predicted → Derived    ✗  (model cannot become measurement)
Heuristic → Derived    ✗  (advisory cannot become measurement)
Derived → Observed     ✗  (cannot upgrade authority)
```

---

## Export Boundary Summary

### Canonical Measurement Exports (`viewer_pack_v1`)

Allowed: Observed, Derived, Estimated (with uncertainty)

Forbidden: Heuristic, Predicted (as measurement), Operator-Annotated (as system output)

### Meta/Advisory Exports

Allowed: All statuses with appropriate attribution

Required: Status must be explicit in schema or filename convention

---

## Guidance System Constraints

AGE may consume:
- Observed data
- Derived data
- Estimated data
- Operator-Annotated data
- Externally-Sourced data

AGE may NOT:
- Convert any input to acoustic truth
- Claim measurement authority for its outputs
- Emit Observed or Derived status values

AGE outputs are always: Heuristic / Decision Support

---

## See Also

- [ADR-0011: Measurement Authority](ADR-0011-measurement-authority.md)
- [ADR-0012: Epistemic Status Taxonomy](ADR-0012-epistemic-status-taxonomy.md)
- [ADR-0010: Guidance Authority Boundary](ADR-0010-guidance-authority-boundary.md)
- [AGE Constitutional Contract](AGE_CONSTITUTIONAL_CONTRACT.md)
