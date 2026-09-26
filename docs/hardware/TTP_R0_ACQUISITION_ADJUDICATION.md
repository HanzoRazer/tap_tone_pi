# TTP R0 — Acquisition-Chain Adjudication (DO-104O / ADC-001)

**This document is a decision input, not an authorization.** It exists to get the
project from a *prepared repository* to the point where a human can authorize the
**first real-material acquisition (R0)** on an informed basis. It orders nothing,
buys nothing, and grants nothing.

| Field | Value |
| --- | --- |
| `adjudication_id` | `TTP-R0-ADJ-001` |
| `governing_gate` | DO-104O / `TTP-AUTH-001` (`SELECTION_DEFERRED`) |
| `scope` | **R0 only** — first physical acoustic evidence gate |
| `acquisition_chain_selection` | **P-A** — recorded 2026-09-26 by the repository owner (see next section) |
| `authorizes_procurement` | **NO** |
| `authorizes_measurement` | **NO** |
| `authorizes_R1_R2_exciter_amp_pcb` | **NO** |
| `supersedes` | nothing (a granted authorization would create a new record, per `TTP-AUTH-001`'s own rule) |

> **Core boundary.** Releasing the `SELECTION_DEFERRED` ruling, selecting the
> acquisition chain, authorizing spend, and accepting bench/handling risk are
> **human decisions**. This document surfaces exactly the facts and open questions
> those decisions need. The acquisition-chain selection recorded in the next
> section was made by the repository owner; **procurement authorization remains a
> separate, outstanding human sign-off** and is not granted here.

---

## 0. Adjudicated decision (D1–D4)

**Decided by:** the repository owner (the human authority named in
`TTP-AUTH-001`, Ross Echols), 2026-09-26.
**Engineering analysis:** the option space and reasoning in §5 were
assistant-prepared and carry no authority; they inform the decision, they do not
make it. The assistant is not the repository owner and not the procurement
authority.

This section records the repository owner's decision against the analysis in §5.

```text
TTP-R0-ADJ-001 — DECISION

D1  ACQUISITION PATH        SELECT P-A
    self-contained USB measurement microphone with its own (integrated) ADC

D2  E0 DEPENDENCY           NOT A PREDECESSOR FOR R0 UNDER P-A
    E0 remains on the E1 / reference-track path

D3  MICROPHONE             SELECT USB measurement-mic class
    exact make/model fail-closed until D5 market/spec re-verification

D4  SPECIMEN / SUPPORT      AUTHORIZE existing real-wood specimen + free-free foam
    exact execution identity (see D4) recorded before execution

D5                         MANDATORY BEFORE PROCUREMENT

P-B                        DEFERRED TO E1 TRACK
E0                         NOT REQUIRED FOR R0
R0 PROCUREMENT             NOT YET AUTHORIZED
NEXT RECORD                TTP-AUTH-002 (R0 subset only)
```

This resolves the acquisition-chain **selection** (the first of the two §7
sign-offs). It does **not** authorize procurement or measurement: the second
sign-off (`TTP-AUTH-002`) is still required, with the exact USB-microphone model
held fail-closed until D5 is complete.

---

## 1. What R0 is (and is not)

R0 is the **first physical evidence gate**, not the program endpoint:

```
manual tap  ->  microphone  ->  ADC  ->  TTP acquisition  ->  saved measurement + provenance
```

- **Is:** a real specimen's response to a hand tap, captured through TTP's own
  acquisition path, analyzed deterministically, saved with provenance, and
  repeated. Recorded as a `ttp_prototype_run_v1` run with `stage: R0`,
  `excitation_mode: MANUAL`, microphone-only response, and **no measured force**.
- **Is not:** controlled excitation (R2), an added-mass challenge (R1), any
  measured force, any reference-grade or calibrated claim, or any hardware
  qualification. Those are out of scope here.

R0 makes no calibrated claim. Its evidence is `evidence_origin: HARDWARE` and, if
attributable, `witnessed` — nothing stronger.

---

## 2. Inventory — owned vs required

Ownership state is taken from
[`TTP_E1_HARDWARE_IDENTITY_REGISTER.md`](TTP_E1_HARDWARE_IDENTITY_REGISTER.md) and
[`TTP_E1_PROCUREMENT_AUTHORIZATION.md`](TTP_E1_PROCUREMENT_AUTHORIZATION.md).

| R0 element | Role id | Owned? | Notes |
| --- | --- | --- | --- |
| Host (Raspberry Pi 5 16 GB) | `HOST-001` | **Owned** (`CONFIRMED_PRESENT`, `TTP-ASSET-001`) | The only possessed component. |
| Audio input device (ADC) | `ADC-001` | **Absent** (`CONFIRMED_ABSENT`) | Design-selected only (HiFiBerry DAC+ ADC Pro); see B-015. |
| Microphone (non-contact) | `MIC-001` | **Absent** (`CONFIRMED_ABSENT`) | Model never locked. |
| Mic preamp (electret path only) | `PREAMP-001` | **Absent** (`CONFIRMED_ABSENT`) | Needed only if the chosen mic is an unpowered capsule. |
| Real wood specimen | — | **Unconfirmed** | Not in the register; inventory question below. |
| Free-free support (foam blocks) | — | **Unconfirmed** | Trivial to source; confirm on hand. |
| Striker (dowel / pencil / knuckle) | — | **Trivial** | No procurement. |
| Pi power / cooling / storage / cabling | — | **Unconfirmed** | Confirm adequacy for headless bench use. |

Exact model/specification gaps to resolve are listed in §5.

---

## 3. Software-ready vs procurement-dependent

The software half of R0 is already merged to `main` and needs no purchase. The
gap is entirely equipment.

### Software-ready (in `main`, no procurement)

| Capability | Where |
| --- | --- |
| Device enumeration / preflight | `ttp devices`, `ttp preflight`; `tap_tone_pi.capture.list_devices` |
| Capture | `ttp record`; `tap_tone_pi.capture.record_audio` |
| Deterministic analysis (FFT peaks, dominant, confidence, clipping, RMS) | `tap_tone_pi.core.analysis` |
| Quality gate | `quality_check.json` (verdict / triggered rules / policy version) |
| Run artifacts + provenance | `audio.wav`, `analysis.json`, `spectrum.csv`, session provenance |
| R0 evidence contract | `contracts/ttp_prototype_run_v1.schema.json` (`stage: R0`) |
| Read-only evidence checker | `scripts/ttp_prototype_check.py` |
| Operator procedure | `docs/hardware/TTP_PROTOTYPE_BENCH_PROTOCOL.md` (R0 section) |
| Synthetic end-to-end proof (no hardware) | `ttp demo` |

### Procurement-dependent (blocks physical R0)

| Item | Decision needed |
| --- | --- |
| Audio input device | §5 D1 (which ADC / input path) |
| Microphone | §5 D3 (which non-contact mic) |
| Preamp | only if an unpowered capsule is chosen (§5 D3) |
| Real wood specimen + support | §5 D4 |
| Pi power/cooling/storage/cabling | confirm adequacy |

---

## 4. The in-repo capture / provenance path R0 will exercise

R0 does not need new acquisition code. The existing path is:

```
ttp devices                 enumerate input device, sample rate, channels
ttp preflight               quiet/level sanity on the selected device
ttp record --device <n>     capture one tap window and analyze it
   -> audio.wav             raw evidence (retained)
   -> analysis.json         dominant_hz, peaks, rms, clipped, confidence
   -> spectrum.csv          spectrum
   -> quality_check.json    deterministic verdict (pass/warn/fail), policy version
   -> session provenance    device id, sample rate, label, timestamp (UTC)
```

Each captured run is then recorded as a `ttp_prototype_run_v1` document
(`stage: R0`, `excitation_mode: MANUAL`, `response_path: MICROPHONE`,
`force.measured_force_claimed: false`) with the raw `audio.wav` linked by SHA-256,
and validated read-only with `scripts/ttp_prototype_check.py`. Repeatability is
observed by repeating the tap at a marked location (no calibrated-force claim).

This path is proven end-to-end against a synthetic source (`ttp demo`) and against
a virtual microphone in the Cloud Agent image; it has **not** been exercised
against a real specimen, which is what R0 is.

---

## 5. Unresolved DO-104O / ADC-001 decisions (the human sign-off set)

Each item below framed the option space. **D1–D4 are now decided (see §0);** the
analysis is retained so the decision can be read against its reasoning. D5 remains
mandatory before any purchase, and procurement authorization (§7 sign-off 2) is
still outstanding.

### D1 — Audio input device / ADC path  *(central, and where DO-104O is blocked)*

The build sequence in `CURRENT.md` is blocked at `ADC-001` (`CONFIRMED_ABSENT`),
and **B-015** records that the design-selected HiFiBerry **DAC+ ADC Pro** is
vendor-superseded; its successor (**DAC2 ADC Pro**, the model named as a prototype
candidate) does **not** publish the same input specification and is unverified.
`TTP-AUTH-001`'s substitution policy is fail-closed: any change to input range,
gain, coupling, sample architecture, channel count, or simultaneous-acquisition
assumptions **requires the architecture gate to be re-run first**.

Before adjudication, two candidate minimum-R0 input paths were considered:

| Candidate path | What it is | What it requires | Governance touched |
| --- | --- | --- | --- |
| **P-A: self-contained USB measurement mic** | a mic with its own ADC (e.g. a UMIK-class measurement microphone) | one device; no HAT, no preamp | Decouples R0 from the **E1 registry role `ADC-001`** (and from B-015 / E0). The USB mic still contains an ADC *function*; it simply does not instantiate the E1 `ADC-001` role. R0 makes no calibrated claim. Still a `MIC-001` selection (D3). |
| **P-B: HiFiBerry ADC HAT + separate mic** | the E1-style HAT ADC plus an electret/measurement mic (+ preamp if unpowered) | `ADC-001` procured; possibly `PREAMP-001` | Couples R0 to the deferred `ADC-001` selection (B-015), the aliasing question (B-014), and the E0 dependency (D2). |

> **Decision recorded in §0:** P-A selected (fastest to first evidence, avoids the
> deferred ADC selection); P-B deferred to the E1 track.

### D2 — Is R0 gated on E0 execution?

E0 (ADC bench characterization) is `PREPARED / NOT EXECUTED`, gated on `ADC-001`
being received, and it produces the aliasing (B-014) and successor (B-015)
evidence. E0 involves **no microphone and no plate**. Whether R0 must wait for E0
was considered as:

- Under **P-A**, R0 does not instantiate the E1 registry role `ADC-001` (its ADC
  function is integrated in the USB mic), so E0 is not on the R0 path — E0 remains
  a separate E1-track prerequisite.
- Under **P-B**, R0 rides the un-characterized `ADC-001`. R0 claims nothing
  calibrated, but B-014 (no anti-alias filter) and B-015 (unverified successor)
  are open against that board. Decision: run E0 first, or accept an
  uncharacterized board for uncalibrated R0 captures and record the limitation.

> **Decision recorded in §0:** with P-A selected, E0 is not an R0 predecessor; it
> remains on the E1/reference track. (The P-B analysis is retained for the E1
> track's later use.)

### D3 — Microphone (`MIC-001`, non-contact per prototype decision D3)

`MIC-001` model is unlocked. Reference-tier microphones are quote-only in the E1
BOM. Prototype candidates named to date are an electret / EM272-class capsule
(needs `PREAMP-001`) or a self-contained USB measurement mic (P-A).

> **Decision recorded in §0:** USB measurement-mic class selected; the exact
> make/model remains fail-closed pending D5 market/spec re-verification.

### D4 — Specimen and support

R0 needs at least one **real wood specimen** and a **free-free support** (foam
blocks). Neither is in the identity register. "Real wood specimen" is too loose
once R0 is executable, so before procurement authorization the **minimum
execution identity** must be recorded. These are repeatability/provenance facts,
not calibration claims:

- specimen ID;
- material / species (if known);
- dimensions;
- support locations / condition;
- marked tap location;
- microphone position / distance;
- orientation.

Decided (§0): the existing real-wood specimen plus a simple free-free foam
support are authorized *as the class*; the concrete execution identity above is
recorded in the `TTP-AUTH-002` run sheet before any capture.

### D5 — Market data is perishable

Every price/stock/lead time in the BOM is dated **2026-08-25** and must be
re-verified before any purchase, per `TTP-AUTH-001`. Nothing here re-verifies it.

---

## 6. Explicitly out of scope (not decided or authorized here)

```
R1 (added-mass challenge)        NOT AUTHORIZED
R2 (commanded excitation)        NOT AUTHORIZED
exciter / shaker                 NOT AUTHORIZED
amplifier                        NOT AUTHORIZED
force-measurement chain          NOT AUTHORIZED
custom AFE / PCB development      NOT AUTHORIZED
E0 execution                     NOT AUTHORIZED HERE; NOT REQUIRED FOR R0 UNDER P-A
procurement / purchase           NOT AUTHORIZED
```

The digital gram scale and known masses (an R1 need) are deliberately excluded
from the R0 inventory.

---

## 7. Required human sign-offs (hard stops)

R0 stops here until a human records both, in that order:

1. **Acquisition-chain selection.** — **RECORDED (§0), 2026-09-26.** P-A selected;
   USB measurement-mic class; existing real-wood specimen + free-free foam;
   E0 not required for R0; exact mic model and specimen execution identity held
   for the run sheet.
2. **Procurement authorization.** — **OUTSTANDING.** Release `SELECTION_DEFERRED`
   for the R0 subset only, with market data re-verified (D5). Per `TTP-AUTH-001`'s
   own rule, this is recorded as a **new** authorization record (`TTP-AUTH-002`),
   not by editing the deferral.

Only after both does R0 move from *authorized* to *executed*, and execution
itself requires physical hardware and an operator — neither of which this
repository or a Cloud Agent possesses.

---

## 8. What changes this document

A human acquisition-chain selection and procurement authorization. At that point a
new authorization record supersedes `TTP-AUTH-001` for the R0 subset, and this
adjudication is retained as the decision input it was — not edited — on the same
rule the census and the procurement record follow.
