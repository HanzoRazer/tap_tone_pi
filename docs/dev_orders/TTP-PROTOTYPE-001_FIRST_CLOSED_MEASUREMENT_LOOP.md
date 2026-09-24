# TTP-PROTOTYPE-001 — First Closed Measurement Loop

**Workstream:** PHYSICAL PROTOTYPE (preparatory)
**Repository:** `HanzoRazer/tap_tone_pi`
**State:** software + documentation preparation complete; **physical execution NOT authorized**
**Release/tag work:** DEFERRED (not part of this order)
**Custom TTP amplifier PCB:** DEFERRED until bench evidence exists

---

## Governing instruction

> Stop designing the Analyzer in abstraction. Assemble the minimum physical
> chain, make TTP interact with real wood, record what actually happens, and let
> those measurements determine the next engineering decisions.

This order **prepares** the repository so that when hardware arrives the bench
work can begin immediately without inventing evidence or prematurely changing
acquisition/excitation code.

---

## Relationship to DO-104O (physical authority)

**TTP-PROTOTYPE-001 is a hardware-free preparatory order. It does not supersede,
satisfy, bypass, or modify DO-104O.** DO-104O remains the governing physical
gate, with hardware paused, `SELECTION_DEFERRED`, blocked at `ADC-001`, and E0
`NOT EXECUTED`. Nothing in this order authorizes procurement, hardware
selection, assembly, or execution of R0/R1/R2. Physical prototype execution
requires a subsequent explicit authorization after the governing gate is
adjudicated.

```
DO-104O                      TTP-PROTOTYPE-001
hardware        PAUSED       purpose      prepare future bench execution
selection       DEFERRED     order        YES
blocking point  ADC-001      contract     YES (ttp_prototype_run_v1)
E0              NOT EXECUTED  checker      YES (read-only)
authorization   NOT GRANTED  protocol     YES (bench protocol)
                             P01-P10      YES (tests)
                             procurement  NO
                             R0/R1/R2     NOT EXECUTED
                             gate change  NO
```

The distinction this preserves: **preparing to measure ≠ authorization to
measure ≠ executing a measurement ≠ obtaining evidence.**

---

## Architecture relationship (PROTOTYPE vs E1 reference-grade)

The TTP-PROTOTYPE-001 signal chain is an **additive `PROTOTYPE` track** intended
to establish an economical physical closed measurement loop and collect
engineering evidence. It does not replace, revise, or claim equivalence to the
existing E1 reference-grade architecture. Existing E1 authority
(`docs/hardware/TTP_E1_*`) remains unchanged. Prototype components remain
candidates until separately promoted through the applicable evidence and
governance process.

```
E1 REFERENCE-GRADE TRACK              PROTOTYPE TRACK (this order)
metrology / reference architecture    economical closed-loop proof
measured force (force transducer)     NO measured force (deferred)
custom preamp / conditioner           off-the-shelf Class-D amplifier
                                       Dayton-class exciter
UNCHANGED by this order               non-contact microphone response
                                       Pi/TTP -> audio I/O -> amp -> exciter
                                       -> specimen -> microphone -> ADC/TTP
                                       PROTOTYPE CANDIDATE, NOT E1 REPLACEMENT,
                                       NOT PRODUCTION BASELINE, NOT REFERENCE-GRADE
```

Later prototype success establishes that the prototype chain works for its
demonstrated purpose. It does not, by itself, invalidate E1, establish
equivalence to the reference-grade chain, or promote prototype components to
production selections.

---

## Binding decisions

| ID | Decision |
| --- | --- |
| D1 | Prototype before custom PCB: use an off-the-shelf Class-D amplifier; the custom PCB comes after bench measurements establish drive voltage/current/power, gain, noise floor, clipping, thermal, protection, and envelope. |
| D2 | Reference hardware (B&K 4810, PCB 208C01, force conditioner, reference shaker) is validation equipment, not prototype hardware. |
| D3 | Response sensing starts non-contact (microphone), to avoid adding sensor mass to the spatial measurement. The microphone candidate is not production authority merely because it works. |
| D4 | Commanded electrical signal ≠ applied mechanical force. R2 may establish repeatable excitation without traceable input force. |
| D5 | Fixed excitation + roving non-contact microphone is preferred for spatial modal work; multiple discrete drive points may later avoid nodal blindness. |
| D6 | The known-mass sweep is an early physical experiment to estimate local effective modal sensitivity, not merely fixture checkout. No fixed mass limit is promoted before that evidence. |
| D7 | Physical truth is outside agent/guidance authority. Deterministic measurement and quality gates remain authoritative. |

---

## Evidence-contract ruling (reuse-first)

TTP-PROTOTYPE-001 preferentially reuses the existing `ttp_hardware_campaign_v1`
contract and established evidence-path machinery. Existing fields and status
vocabulary remain authoritative wherever they can truthfully represent
prototype activity. **A new schema was introduced only after a documented gap
analysis identified prototype-specific facts that cannot be represented without
changing the meaning of the existing campaign contract.**

### Gap analysis (why `ttp_prototype_run_v1` exists)

`ttp_hardware_campaign_v1` and its validator
(`tap_tone_pi/grant_readiness/validation.py`) encode the DO-103 **measured-force,
two-channel** architecture:

- `validate_campaign_config()` requires a non-null measured **force channel** and
  exactly one `EXCITATION` and one `RESPONSE` channel, and states outright that
  *"DO-103 requires the excitation to be measured rather than commanded."*
- `validate_run_acquisition_provenance()` requires every **HARDWARE-origin** run
  to identify both an `EXCITATION` and a `RESPONSE` channel.

The prototype (D3/D4) is force-free, microphone-only, and manual-or-commanded.
Such a run cannot validate against the campaign contract — not even in a
prepared state — and cannot claim `HARDWARE` origin there. Stretching the
campaign contract to permit a force-free/commanded configuration would make it
**semantically false**, because its purpose is to mandate measured force.

Therefore a separate, additive contract is warranted:

> `ttp_hardware_campaign_v1` remains the DO-103 measured-force campaign contract.
> `ttp_prototype_run_v1` represents prototype commissioning runs that may use
> manual or commanded excitation without a measured force channel. The two
> contracts share provenance vocabulary and artifact conventions, but they do
> not share the same physical claim.

```
PROTOTYPE RUN                 HARDWARE CAMPAIGN
may be commanded              retains measured-force meaning
may be microphone-only        (unchanged by this order)
may have NO measured force
```

### What is reused, not reinvented

`ttp_prototype_run_v1` reuses `EvidenceOrigin` (`HARDWARE`/`FIXTURE`/`SYNTHETIC`),
the witnessed standard, the run-status vocabulary
(`NOT_EXECUTED`/`EXECUTED`/`HALTED_AT_GATE`/`BLOCKED_BY_GATE`), calibration
traceability, and SHA-256 `ExternalArtifactV1` identity — imported from
`tap_tone_pi.grant_readiness`, never re-defined. R1's added-mass concept mirrors
the campaign's `mass_loading_observation` (measured mass, `> 0`). No parallel
vocabulary for status, provenance, witnessing, artifact identity, or hardware
maturity is introduced.

---

## Prototype stages

```
R0  REAL-WOOD ACQUISITION      manual tap -> microphone -> ADC -> TTP
R1  KNOWN PHYSICAL PERTURBATION same plate + measured added mass -> repeat
R2  CLOSED EXCITATION LOOP      TTP waveform -> DAC -> amp -> exciter
                                -> plate -> microphone -> ADC -> TTP
```

R0 and R1 are manual-tap acquisitions (R1 is R0 under a known added mass); R2 is
the commanded loop. The stage bounds what a run may claim — enforced by the
read-only checker and the P01-P10 tests.

---

## Maturity ladder (do not collapse into "working")

A component or capability moves through explicit, separately-witnessed states.
No single word stands in for the ladder:

```
DESIGNED -> PROCURED -> ASSEMBLED -> POWERED -> DETECTED -> EXECUTED -> WITNESSED -> QUALIFIED
```

Hardware identities live in `docs/hardware/TTP_E1_HARDWARE_IDENTITY_REGISTER.md`
and are promoted only as physical components actually become known. This order
populated **none** of them: no prototype component has been purchased or
received, so every prototype component remains a candidate
(`CONFIRMED_ABSENT` / `NOT_RECEIVED`) in the existing register.

---

## Evidence artifacts produced by this order (software + documentation only)

| Artifact | Path |
| --- | --- |
| Governing order | `docs/dev_orders/TTP-PROTOTYPE-001_FIRST_CLOSED_MEASUREMENT_LOOP.md` |
| Evidence contract | `contracts/ttp_prototype_run_v1.schema.json` |
| Schema-registry entry | `contracts/schema_registry.json` (`ttp_prototype_run`) |
| Evidence model / validator | `tap_tone_pi/prototype/` |
| Read-only checker | `scripts/ttp_prototype_check.py` |
| Operator bench protocol | `docs/hardware/TTP_PROTOTYPE_BENCH_PROTOCOL.md` |
| P01-P10 tests | `tests/test_prototype_check.py` |
| Contract tests | `tests/test_prototype_run_contract.py` |

---

## Invariants (P01-P10)

| ID | Invariant | Where enforced |
| --- | --- | --- |
| P01 | R0 cannot claim controlled excitation | checker + `TestP01_*` |
| P02 | R1 requires an actual measured added mass | schema (`> 0`) + checker + `TestP02_*` |
| P03 | R2 requires valid emission provenance | checker + `TestP03_*` |
| P04 | No stage may claim measured force without a force-chain record | checker + `TestP04_*` |
| P05 | Hardware candidate ≠ qualified hardware | schema (no promotion field) + checker notes + `TestP05_*` |
| P06 | Fixture/synthetic run ≠ hardware-witnessed | checker + `TestP06_*` |
| P07 | Changing disclosure/guidance does not change measurement result | validator ignores narrative; `TestP07_*` |
| P08 | A failed physical run remains recorded, not silently deleted | checker + `TestP08_*` |
| P09 | Raw capture/artifacts remain linked to the run | checker + `TestP09_*` |
| P10 | Prototype evidence cannot promote production-PCB readiness automatically | checker notes never grant; `TestP10_*` |

Promotion rule (P05/P10): the checker **reports** that prototype evidence never
qualifies a component and never promotes PCB/production readiness, and it never
grants either. Promotion is a separate decision this tooling does not make.

---

## Stop conditions (bench, when authorized)

Stop the affected test if: amplifier or exciter overheats; audible mechanical
damage; coupling begins to detach; ADC clips repeatedly; output contains
unexpected DC; the Pi/audio device resets; signal routing is uncertain; specimen
damage becomes plausible; device identity cannot be established; or results are
being generated without saved raw evidence. **Do not work around a failed
physical gate by weakening a software check.** See the bench protocol for the
operator procedure.

---

## Rollout order

Steps 01 and the software/documentation preparation are complete. Steps that
touch physical hardware (procurement, assembly, R0/R1/R2 execution,
characterization) are **NOT authorized** under this order and require the DO-104O
gate to be adjudicated first.

```
01 create TTP-PROTOTYPE-001 order                      DONE
   prepare evidence contract + checker + tests          DONE
   prepare operator bench protocol                       DONE
02 inventory what is actually owned                     operator action pending
03 lock prototype BOM candidates                        pending (candidate-only)
04 order missing hardware                               NOT AUTHORIZED (DO-104O)
05-22 Pi image, enumeration, R0/R1/R2, characterization NOT EXECUTED
23-29 compile findings, patch demonstrated defects,     pending physical evidence
      evidence pack, adjudicate custom-PCB inputs
30 STOP
```

Software defects in `tap_tone_pi/excitation/` and `tap_tone_pi/capture/` are
**not** patched by this order on the strength of an imagined improvement: those
modules must encounter the actual Pi/audio hardware first. Any concrete
contradiction found during hardware-free review is recorded below as a bench
blocker rather than triggering a speculative patch.

### Bench blockers / findings from hardware-free review

- None that prevent the evidence contract from functioning. The single
  structural finding — that `ttp_hardware_campaign_v1` mandates measured force
  and so cannot represent a force-free prototype run — is resolved additively by
  `ttp_prototype_run_v1` (see gap analysis) and is not a defect in existing code.

---

## Close-out state (this preparatory order)

```
TTP-PROTOTYPE-001

BENCH ARCHITECTURE          defined
EVIDENCE CONTRACT           ready (ttp_prototype_run_v1)
READ-ONLY CHECKER           ready (scripts/ttp_prototype_check.py)
OPERATOR BENCH PROTOCOL     ready
P01-P10                     green

HARDWARE INVENTORY          operator action pending
PROCUREMENT                 not executed
R0                          NOT EXECUTED
R1                          NOT EXECUTED
R2                          NOT EXECUTED

EXCITATION CODE PATCH       none
CAPTURE CODE PATCH          none
HARDWARE CAPABILITY CLAIM   none
DO-104O GATE                unchanged
```

Physical close-out (R0/R1/R2 executed, evidence saved, repeatability observed,
exciter/amplifier range characterized, custom-PCB inputs established) is the
subject of a **future, separately authorized** execution order, not this one.

---

*Prepared under TTP-PROTOTYPE-001. Governing physical authority remains DO-104O.*
