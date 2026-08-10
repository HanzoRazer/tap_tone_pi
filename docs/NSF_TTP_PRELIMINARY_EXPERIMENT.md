# TTP Preliminary Repeatability Experiment

**Status:** defined, not executed. The physical campaign is a deferred
execution gate (DO-102 Stage 9) that has not run.

---

## Purpose

Estimate the short-term variation of a repeated TTP measurement, and expose the
ways a capture fails, using the measurement path that already exists.

This experiment is bounded on purpose. It is not a validation campaign, not a
multi-instrument study, and not a Gage R&R. It is the smallest experiment that
produces a defensible number and an honest list of failure modes.

## What it can and cannot support

It can support a statement of the form:

> Repeated measurements of one point on one instrument, by one operator, in one
> session, produced an observed coefficient of variation of X% in the dominant
> frequency under the recorded conditions.

It cannot support:

> TTP is accurate to X%.

Accuracy requires a reference. None has been used, and none is available. See
`NSF_TTP_REFERENCE_VALIDATION_PLAN.md`.

---

## Design

One instrument. One nominal measurement point. One nominal support condition.
One nominal sensor position. One operator. One session. Multiple independent
captures.

| Parameter | Value |
| --- | --- |
| Instrument | one, identified by `instrument_id` |
| Measurement point | one, identified by `measurement_point_id` |
| Planned repeats | at least 2 (contract floor); 20–30 recommended |
| Analysis profile | `phase1_tap_analysis_v1` |
| Excitation | recorded generically; see below |
| Support condition | fixed for the whole session, recorded verbatim |
| Sensor position | fixed for the whole session, recorded verbatim |

**The repeat count is not a target.** The contract floor of 2 is what makes a
spread computable. DO-102 sets no required repeat count and no required
repeatability figure, because the baseline observations that would justify one
do not exist yet. Twenty to thirty is a practical recommendation for a first
session, not a threshold.

**Independent captures.** Each repeat is a full re-excitation. The instrument is
not moved and the microphone is not moved; only the excitation is repeated.
That is deliberate — it isolates the narrowest source of variation first, and
leaves re-seating (R3) and repositioning (R2) as separate questions.

### Excitation

Excitation is recorded through `ExcitationContextV1`, which describes the
mechanical arrangement rather than a signal:

```
excitation_method        manual_tap | instrumented_hammer | shaker_stinger | ...
excitation_device_id     identifier of the device, where one is used
excitation_point         where the structure is driven
contact_condition        what touches the structure, and through what
fixture_id               the fixture holding device or specimen
excitation_contract_id   links to ExcitationContractV1 for a driven source
```

`manual_tap` is one permitted value. It is **not** privileged as the canonical
method, and the field default is `unspecified`. The grounded shaker-and-stinger
architecture is recordable today without a schema change and without the
hardware program existing. An unlisted method is recorded verbatim rather than
rejected.

### Recorded conditions

Recorded where known, left unknown where not:

- temperature (C)
- relative humidity (%)
- specimen moisture (%)
- ambient-noise note
- support condition
- sensor position
- excitation point
- operator
- time (UTC)

**No environmental correction is applied anywhere.** Environment is a Phase I
risk (R4), not a term in a formula. A field that was not supplied is recorded
as unknown and reported as unknown; it is never imputed.

---

## Measured quantities

Read out of the Phase 1 analysis result. None is computed by the grant-readiness
layer:

| Quantity | Unit | Source field |
| --- | --- | --- |
| `dominant_frequency` | Hz | `analysis.dominant_hz` |
| `peak_magnitude` | normalized | magnitude of the peak matching `dominant_hz` |
| `snr` | dB | `analysis.confidence_components.snr_db` |
| `confidence` | unitless | `analysis.confidence` |

These are **spectral feature candidates**, not identified structural modes. See
R5 and R6.

---

## Failure handling

A failed run is evidence. Every attempt is recorded, and rejected runs are
counted in the study and excluded only from the statistics.

Rejection reasons come from the quality gate's own rule identifiers, not from
inference:

| Reason | Source |
| --- | --- |
| `CLIPPING` | quality rule Q001 (hard) |
| `INSUFFICIENT_SIGNAL` | quality rule Q002 (hard) |
| `ANALYSIS_FAILURE` | quality rule Q003, or a null dominant frequency |
| `INVALID_METADATA` | quality rule Q005, or a wrong/unreadable contract |
| `QUALITY_GATE_REJECTED` | any other hard rule — the gate failed and named no cause this table covers |
| `MISSING_ARTIFACT` | the capture produced no file |

A capture that produced no file is still an attempt and is recorded through
`record_missing_run`. Dropping it would quietly improve the apparent success
rate.

---

## Statistical treatment

Descriptive only:

count, mean, median, sample standard deviation, coefficient of variation,
minimum, maximum, range, median absolute deviation.

- **Standard deviation** is the sample standard deviation with Bessel's
  correction (n−1), computed by `tap_tone_pi.core.statistics`. Every generated
  report states this.
- **Median absolute deviation** is unscaled — no 1.4826 consistency factor,
  because that factor assumes a normality this evidence has not established.
- **Coefficient of variation** is undefined for a mean of zero and is refused
  (`NSF-304`) rather than reported as 0.0.
- **No acceptance flag.** The metric contract has no `is_acceptable`, no
  threshold, and no verdict field. The DO-085 repeatability gate stays in
  `tap_tone_pi.core.repeatability`; a study may cross-reference that evidence by
  identifier but does not inherit its gate, and that gate is not an NSF success
  criterion.
- **No confidence interval** is reported. If one is added later, its method must
  be stated and it must be described as an interval for the observed sample
  statistic, not for instrument accuracy.

Every statistic names the runs that produced it. A metric drawing on a rejected
run, or on a run the study does not contain, is refused.

---

## Running it

The runner analyzes results already collected. It performs no capture, and
adding a capture mode requires its own authorization.

```bash
python scripts/nsf_ttp_repeatability.py \
    --experiment experiment.json \
    --runs path/to/analysis-results \
    --evidence-origin HARDWARE \
    --write
```

`--evidence-origin` defaults to `FIXTURE`. Claiming `HARDWARE` for a result
marked as generated from synthetic audio fails with `NSF-305`, as does a study
whose runs do not all share the claimed origin.

Outputs go to `out/nsf/`.

---

## Limitations

Carried on every generated study:

1. The figures describe repeatability, not accuracy. No agreement with any
   reference method has been established.
2. The sample is one measurement point on one instrument by one operator in one
   session. It says nothing about between-point, between-instrument,
   between-operator, or between-session variation.
3. Environmental conditions are recorded as supplied and are not corrected for.
4. Extracted peaks are spectral feature candidates, not identified structural
   modes.
5. A study built from fixture or synthetic data is labelled as such and is not
   hardware evidence.

---

## Current execution status

**Not executed.** No hardware campaign has been run, so no repeatability figure
for this instrument exists.

The contract and the analysis path are proven against deterministic
non-hardware fixtures, and the system can ingest a real hardware dataset without
a schema or architecture change once the campaign is executed. Until then, the
capability is recorded `NOT_VERIFIED_ON_HARDWARE`, and every study this
repository can currently produce is labelled `FIXTURE` or `SYNTHETIC` in its
title, its header, and its first limitation.

---

*Related: `NSF_TTP_TECHNICAL_BASELINE.md`,
`NSF_TTP_PHASE_I_TECHNICAL_RISKS.md`,
`NSF_TTP_REFERENCE_VALIDATION_PLAN.md`.*
