# Radiation-Ratio Interoperability Contract

**Contract ID:** `tonewood_radiation_ratio`
**Version:** 1
**Output convention:** `unscaled_si_derived`
**Scale factor:** `1.0`
**Authority repository:** `HanzoRazer/tap_tone_pi`
**Authority artifact:** `contracts/tonewood_radiation_ratio_v1.json`
**Bug / remediation family:** BR-045 (cross-repository fragmentation)

---

## Purpose

Define one versioned scientific interoperability contract for the Schelleng
tonewood radiation ratio so Tap Tone Pi and Luthier’s Toolbox calculate and
communicate the same physical quantity on the same numerical scale.

Each repository implements the calculation locally. Neither repository imports
runtime code from the other.

---

## Formula

Canonical:

```text
R = c / ρ
c = √(E / ρ)
```

Equivalent:

```text
R = √(E / ρ³)
```

### Units

| Quantity | Symbol | Unit |
|---|---|---|
| Dynamic modulus | E | Pa |
| Density | ρ | kg/m³ |
| Wave speed | c | m/s |
| Radiation ratio | R | m⁴/(kg·s) (SI-derived) |

Convenience APIs may accept GPa only when the API name explicitly includes
`_gpa` and converts internally. No function may infer Pa / MPa / GPa from
magnitude.

### Scale

```text
scale_factor = 1.0
output_convention = unscaled_si_derived
```

Do **not** apply ×1,000 or ×1,000,000 in V1 calculation or serialization.
Representative tonewood fixtures fall near approximately 5–15.

### Rounding

Calculation returns the unrounded float. Default display rounding is
`rounding_decimals = 2`. Scientific comparison uses explicit tolerance, not
formatted strings.

---

## Repository roles

| Repository | Role |
|---|---|
| Tap Tone Pi | Scientific-method reference for the formula definition |
| Luthier’s Toolbox | Conforming consumer / independent implementation |

Mirrored contract files may include repository-local provenance fields:

```text
authority_repository
authority_contract_path
authority_commit
synchronized_at
```

Those fields are excluded from `semantic_digest_sha256`.

---

## Conformance fixtures (V1)

Exact inputs come from shipped reference data used by both repositories:

| Specimen | ρ (kg/m³) | E (GPa) | R (rounded, 2 dp) |
|---|---:|---:|---:|
| American Basswood | 415.0 | 10.07 | 11.87 |
| Western Red Cedar | 370.0 | 7.78 | 12.39 |
| Bubinga | 890.0 | 18.41 | 5.11 |

---

## Synchronization process

1. Edit the authority contract in Tap Tone Pi.
2. Recompute `semantic_digest_sha256` via
   `tap_tone_pi.bending.radiation_ratio.radiation_ratio_contract_digest`.
3. Update the approved digest pin in
   `tests/test_radiation_ratio_contract.py` and
   `scripts/check_radiation_ratio_contract_parity.py`.
4. Mirror the semantic content into Luthier’s Toolbox.
5. Run:

```bash
python scripts/check_radiation_ratio_contract_parity.py
python scripts/check_radiation_ratio_contract_parity.py \
  --authority contracts/tonewood_radiation_ratio_v1.json \
  --candidate /path/to/toolbox/contract.json
```

CI must fail when the semantic digest or fixture expectations drift.

### Digest normalization (intentional ordering)

`normalize_radiation_ratio_contract` / `radiation_ratio_contract_digest`:

* sort object keys;
* sort `conformance_fixtures` by `fixture_id`;
* **preserve** the published order of `input_quantities`,
  `equivalent_expressions`, and `validity_requirements`.

Those list orders are part of the semantic contract. A mirror that reorders
them will change the digest and fail CI, even if the set of values is
unchanged.

---

## Tap Tone Pi disposition (BR-045)

Tap Tone Pi’s existing `c / density` implementation is **conforming evidence**,
not a defect. BR-045 on this repository adds the contract, helpers, provenance
comments, and conformance tests. No production numerical correction was
required. BR-043 / BR-044 were Toolbox-side scale defects and must not be
attributed to Tap Tone Pi.

---

## Non-goals

- Material quality judgments or rankings
- Threshold science redesign
- `specific_moe` reconciliation
- Runtime cross-repository imports
- Shared Python / TypeScript packages
- Formula fitting or environmental normalization
- Empirical-registry work (DO-101B)

---

## Related code

- Helpers: `tap_tone_pi/bending/radiation_ratio.py`
- Gore spreadsheet: `tap_tone_pi/bending/gore_spreadsheet.py`
- QA lab spec: `tap_tone_pi/bending/qa_lab_spec.py`
- Schema: `contracts/tonewood_radiation_ratio_v1.schema.json`
- Tests: `tests/test_radiation_ratio_contract.py`
