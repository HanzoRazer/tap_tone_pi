# TTP R0 — Procurement Authorization Record

**This record is prepared, not granted.** It exists so a human can authorize the
minimum R0 acquisition purchase truthfully once D5 has resolved the exact device.
It authorizes nothing in its current state.

| Field | Value |
| --- | --- |
| `authorization_id` | `TTP-AUTH-002` |
| `authorization_date` | *(not granted)* |
| `authorization_status` | `PREPARED_NOT_AUTHORIZED` |
| `authorizing_human` | *(not yet recorded)* |
| `scope` | R0 acquisition subset only |
| `source_decision` | `TTP-R0-ADJ-001` |
| `acquisition_path` | P-A — USB measurement microphone with integrated ADC |
| `exact_microphone` | `UNRESOLVED` |
| `market_reverification` | `OUTSTANDING` |
| `procurement_authorized` | `NO` |
| `measurement_authorized` | `NO` |
| `supersedes` | nothing while authorization is not granted |

Once D5 (§3) and explicit human authorization (§5) occur, the record may be
completed with actual facts. Until then, every physical specific stays blank or
`UNRESOLVED` — a future need for a field is not evidence that a value exists today.

---

## §1 Authority boundary

This record covers procurement for the **minimum R0 acquisition subset only**.

It does **not** authorize:

```text
R1
R2
E0
E1 ADC-001
exciter
amplifier
force chain
custom PCB / AFE
production qualification
```

---

## §2 Selected architecture

The R0 acquisition path selected in `TTP-R0-ADJ-001` (§0) is **P-A**:

```text
USB measurement microphone
with integrated ADC
connected to Pi/TTP
```

> The microphone contains an ADC **function** but does **not** instantiate the E1
> registry role `ADC-001`. P-A is not "no ADC"; it is an ADC that is not the E1
> role. E0, B-014, and B-015 remain on the E1/reference track and are not R0
> predecessors under P-A.

---

## §3 D5 verification table

**Not populated.** No product is assumed here. Blank means *not yet verified* —
it does not mean "a TBD product exists." D5 is performed separately (§ handoff
D5); this record only holds the place for its results.

| Fact | Verified value |
| --- | --- |
| manufacturer | |
| exact model | |
| manufacturer product URL/source | |
| verification date | |
| current availability | |
| current price | |
| Linux compatibility | |
| Raspberry Pi / ARM compatibility | |
| USB Audio Class behavior | |
| driver requirement | |
| supported sample rate(s) | |
| channel count | |
| bit depth, if documented | |
| calibration file availability, if applicable | |
| serial-specific calibration, if applicable | |
| vendor status / discontinued? | |
| seller / purchase source | |

If any material compatibility point remains unresolved after D5, procurement
authorization is `BLOCKED`; uncertainty is not filled with a "probably compatible"
model.

---

## §4 Procurement subset

Structure only; no item is authorized merely because a future run might use it.

```text
HOST-001
    Raspberry Pi 5 16 GB (TTP-ASSET-001) — already possessed.
    No purchase under this authorization.

MIC-001 / R0 USB acquisition device
    USB measurement microphone with integrated ADC (P-A class).
    Exact identity UNRESOLVED until D5.

other R0 physical items
    Not automatically authorized. Any additional item (cabling, mounting,
    storage, etc.) is added here only if the repository owner identifies an
    actual procurement need at authorization time.
```

The specimen and support are not procurement items under this record:
`TTP-R0-ADJ-001` authorized the existing real-wood specimen and a free-free foam
support **as a class**, and their concrete identity is recorded in the run sheet
at execution time, not purchased here.

---

## §5 Human authorization block

Hard gate. No inferred approval; every value below is filled by the authorizing
human, not by tooling or inference.

```text
PROCUREMENT AUTHORIZATION

status:
    PREPARED_NOT_AUTHORIZED        (current)
    -> AUTHORIZED                  (only when a human records the fields below)

authorized by:
    <actual human>

authorization date:
    <actual date>

authorized exact item(s):
    <actual item identities, from the completed §3 table>

maximum spend if owner elects to record one:
    <actual value, or omitted>

conditions:
    <actual conditions>

signature / explicit approval reference:
    <actual evidence>
```

While `status` is `PREPARED_NOT_AUTHORIZED`, nothing here authorizes a purchase.

---

## §6 Supersession semantics

Before authorization:

```text
TTP-AUTH-001 remains the governing physical procurement authority.
```

After explicit authorization (§5 completed):

```text
TTP-AUTH-002 supersedes TTP-AUTH-001 only for the R0 subset expressly
authorized here. All other deferred hardware remains deferred.
```

This is a narrow, R0-only supersession. It does **not** globally release
DO-104O / E1 hardware, and `TTP-AUTH-001` is not edited.

---

## What changes this record

D5 completion (§3 filled from verified current evidence) followed by an explicit
human authorization (§5 filled). Until both occur, this is a skeleton: prepared,
fail-closed, and truthful about the absence of the facts it will one day carry.
