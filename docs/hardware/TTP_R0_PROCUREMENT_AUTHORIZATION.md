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

D5 was performed on **2026-09-27**. Full candidate detail, per-fact evidence, and
the source ledger are in
[`TTP_R0_D5_MICROPHONE_VERIFICATION.md`](TTP_R0_D5_MICROPHONE_VERIFICATION.md)
(`TTP-R0-D5-001`). This section is the compact summary. Prices/stock are
observations dated 2026-09-27 and must be re-checked at purchase time. No single
model is written into `exact_microphone`: selection is a separate human step.

| Candidate | Disposition | Linux | Pi/ARM | UAC | Sample rate | Cal file | Availability / price (2026-09-27) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| miniDSP UMIK-1 | `VERIFIED_ELIGIBLE` | VERIFIED (mfr) | UNRESOLVED | UAC1 | 24-bit @ 48 kHz | per-serial `.txt` | In stock; $79 (miniDSP) / $139.98 (Parts Express) |
| miniDSP UMIK-2 | `VERIFIED_ELIGIBLE` | VERIFIED (mfr) | UNRESOLVED | UAC2 | 32-bit @ 44.1–192 kHz | per-serial | In stock; $195 (miniDSP) / ~$280–$325 retail |
| Dayton Audio UMM-6 | `UNRESOLVED` | works, mono/stereo caveat | Pi-4 detected, enum caveat | UAC1 | **UNRESOLVED (not stated)** | per-serial `.txt` | Parts Express $79.99; SoundImports out of stock |

Two candidates are `VERIFIED_ELIGIBLE` (miniDSP UMIK-1, miniDSP UMIK-2); the
Dayton UMM-6 is `UNRESOLVED` because its official sample-rate/bit-depth are not
stated and its Linux/Pi handling is only community-documented. A material
compatibility point that remains unresolved for a chosen model keeps procurement
`BLOCKED` for that model; uncertainty is not filled with a "probably compatible"
value.

`exact_microphone` remains `UNRESOLVED`, `procurement_authorized` `NO`, and
`measurement_authorized` `NO`, pending the repository owner's selection from the
`VERIFIED_ELIGIBLE` candidates and a separate `TTP-AUTH-002` grant.

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

The specimen, support condition, tap implement, physical dimensions, and
placement values are not procurement facts established by this record. They are
recorded only from the actual bench configuration when R0 is later executed.

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
