# NSF TTP E1 — Rig Bring-Up and Characterization Results

**STATUS: NOT EXECUTED — no rig has been built.**

No hardware exists. No component has been procured or specified. This document
contains the result structure only: no measured mass, no channel observation, no
transfer function, no coherence, no candidate band, and no gate disposition has
been produced.

Dev Order: DO-104 — E1 Hardware Bring-Up and Rig Characterization
Protocol: `docs/NSF_TTP_E1_RIG_CHARACTERIZATION_PROTOCOL.md`

---

## How this document gets filled in

**Only from persisted evidence.** After execution:

```bash
python scripts/ttp_hardware_campaign.py rig-check \
    --config campaigns/<id>/campaign.json \
    --experiment e1-rig \
    --runs campaigns/<id>/runs-e1.json \
    --evidence-origin HARDWARE --write

python scripts/ttp_hardware_campaign.py report \
    --config campaigns/<id>/campaign.json \
    --studies out/nsf/campaign \
    --artifacts campaigns/<id>/artifacts.json --write

python scripts/ttp_hardware_campaign_check.py out/nsf/campaign
```

No number below may be hand-entered, and no summary may be more favourable than
what the generated campaign document says. Every figure carries the digest of
the document it came from.

---

## 1. Rig identity

*Not executed.* Records `rig_configuration_id`, shaker, stinger, contact tip,
fixture, support condition, and drive point — each marked observed or unknown.

## 2. Hardware inventory

*Not executed.* Every component is TBD. Nothing has been selected, and no
specification is asserted here in advance of selection.

## 3. Measured masses

*Not executed.* Records `stinger_mass_g`, `contact_tip_mass_g`, and where
practical a separately measured `combined_contact_mass_g` — with the instrument
used for each. The combined figure is a measurement, not the sum of the parts.

## 4. Channel configuration

*Not executed.* Records both channels: identity, native unit, stated sensitivity
in the unit the device states it in, calibration traceability, and gain.

Force will be **measured**, which makes the excitation observable. It will not
be traceable unless a calibration reference is recorded, and this section must
say which of the two holds.

## 5. Capture attempts

*Not executed.* Every attempt appears here with its run id, acquisition sequence
index, timestamp, and elapsed time from the first capture. Order is recorded at
acquisition, never reconstructed by sorting timestamps.

## 6. Failed attempts

*Not executed.* Rejected runs keep their identity, artifacts, provenance, and
place in the acquisition order, and are counted in the denominator of attempts.

## 7. Observed resonances

*Not executed.* Fixture and stinger resonances are reported, not notched out. A
resonance that makes part of the band unusable is an E1 finding.

## 8. Force and response observations

*Not executed.* The measured transfer quantity is acoustic pressure per unit
measured force, `Pa/N`. It is not mobility, accelerance, or receptance.

## 9. Coherence observations

*Not executed.* Coherence is recorded per run and never compared against an
invented cutoff.

## 10. Frequency observations

*Not executed.* Each run records the nominal frequency asked for, the actual bin
that answered, and the signed offset between them, so a set of runs can never
imply that all values came from one exact frequency if they did not.

## 11. Candidate usable band

*Not executed.* The band is an E1 **result** derived from the observations
above, not a predeclared property of the rig. E2 inherits it by reference to
this witnessed evidence rather than copying a frequency range that could drift.

If no defensible region exists, that is recorded here and the campaign halts.

## 12. Limitations

*Not executed.* Whatever E1 produces establishes none of: accuracy,
traceability, external validity, modal truth, structural mobility, instrument
repeatability, build discrimination, or tone meaning.

## 13. Gate disposition

**Not executed — no disposition exists.** On execution this records one of:
proceed to E2, proceed with a limited band, halt for rig redesign, or abort on
hardware failure — with the campaign status the evidence derives.

E2 does not begin until this section says it may.

## 14. Capability promotion

**No capability has been promoted.** Every hardware-dependent capability remains
`NOT_VERIFIED_ON_HARDWARE`, and every study this repository can currently produce
is `FIXTURE` or `SYNTHETIC`.

## 15. Remaining risks

Nothing is narrowed by this document. **R10 — agreement with an external
reference method — remains entirely open**, and nothing in E1 can close it: every
figure it will produce compares this instrument against itself.
