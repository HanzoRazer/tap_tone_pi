<!-- GENERATED BASELINE OUTPUT — do not hand-edit.
     Source: examples/acoustic_lab/flat_plate_resonance_pilot_v1.py
     Regenerate: python examples/acoustic_lab/flat_plate_resonance_pilot_v1.py
     This is the unmodified render of the existing cohort execution-plan
     renderer for the synthetic Flat Plate Resonance Pilot V1 fixture. -->

# Cohort Execution Plan: Flat Plate Resonance Pilot V1

**INSTRUMENT CLASS: MEASUREMENT**

## 1. Plan Identity

| Field | Value |
|-------|-------|
| Plan ID | `flat_plate_resonance_pilot_v1_plan` |
| Experiment Design ID | `flat_plate_resonance_pilot_v1` |
| Plan Version | 1 |
| Created (UTC) | 2026-06-29T07:43:35.028142+00:00 |
| Cohort Size | 12 |

## 2. Declared Response Variables

| Variable | Unit | Workflow | MIE |
|----------|------|----------|-----|
| T1 frequency | Hz | tap_modal_capture_v1 | 3.0 percent |
| Q | ratio | tap_modal_capture_v1 | 10.0 percent |
| decay time | s | tap_modal_capture_v1 | 10.0 percent |

## 3. Required Covariates

| Covariate | Unit | Source |
|-----------|------|--------|
| density | kg/m3 | wood_database |
| moisture content | percent | measured |
| species | category | wood_database |
| support method | category | fixture_log |
| humidity | percent_rh | environment_log |
| temperature | deg_C | environment_log |

## 4. Cohort Build Plan

- **Cohort size:** 12
- **Randomization strategy:** blocked

## 5. Baseline Rebuild Schedule

No baseline rebuild schedule defined.

## 6. Reference Body / Repeatability Check

- **Reference body ID:** `flat_plate_ref_001`
- **Body style:** flat_plate_reference
- **State:** free_free_unclamped
- **Description:** Kept reference flat plate, re-measured each session for repeatability.

## 7. Required Measurement Workflows

| Workflow ID | Required For |
|-------------|--------------|
| tap_modal_capture_v1 | Q, T1 frequency, decay time |

## 8. Execution Checklist

| Step | Action | Timing |
|------|--------|--------|
| 1 | Record covariates: density, moisture content, species, support method, humidity, temperature | per_specimen |
| 2 | Measure T1 frequency using tap_modal_capture_v1 | per_specimen |
| 3 | Measure Q using tap_modal_capture_v1 | per_specimen |
| 4 | Measure decay time using tap_modal_capture_v1 | per_specimen |
| 5 | Perform repeatability check on reference body | per_baseline_interval |
| 6 | Export measurement provenance and artifacts | per_specimen |

## 9. Export / Provenance Requirements

### measurement_session

- **Format:** JSON
- **Required fields:** session_id, timestamp_utc, specimen_id, environment_temp_c, environment_rh_pct

### response_T1 frequency

- **Format:** JSON
- **Required fields:** value, unit, workflow_id, timestamp_utc

### response_Q

- **Format:** JSON
- **Required fields:** value, unit, workflow_id, timestamp_utc

### response_decay time

- **Format:** JSON
- **Required fields:** value, unit, workflow_id, timestamp_utc

### covariate_density

- **Format:** JSON
- **Required fields:** value, unit, source, timestamp_utc

### covariate_moisture content

- **Format:** JSON
- **Required fields:** value, unit, source, timestamp_utc

### covariate_species

- **Format:** JSON
- **Required fields:** value, unit, source, timestamp_utc

### covariate_support method

- **Format:** JSON
- **Required fields:** value, unit, source, timestamp_utc

### covariate_humidity

- **Format:** JSON
- **Required fields:** value, unit, source, timestamp_utc

### covariate_temperature

- **Format:** JSON
- **Required fields:** value, unit, source, timestamp_utc

---

*Generated from schema version: cohort_execution_plan_v1*
