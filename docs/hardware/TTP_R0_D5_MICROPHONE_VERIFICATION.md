# TTP R0 D5 — USB Measurement Microphone Verification

| Field | Value |
| --- | --- |
| `verification_id` | `TTP-R0-D5-001` |
| `verification_date` | 2026-09-27 |
| `scope` | current market + Linux/Pi/UAC compatibility for the P-A R0 acquisition device |
| `source_decision` | `TTP-R0-ADJ-001` (P-A) |
| `authorization_state` | `TTP-AUTH-002` = `PREPARED_NOT_AUTHORIZED`; `exact_microphone` = `UNRESOLVED` |
| `procurement_authorized` | NO |
| `measurement_authorized` | NO |
| `ownership_changed` | NO |

**This is evidence input, not authorization or selection.** `VERIFIED_ELIGIBLE`
means only that current evidence supports a model as a technically plausible R0
P-A input device. It does not mean selected, authorized, purchased, received, or
validated. The repository owner selects one exact model (§Human selection); a
purchase requires a separate `TTP-AUTH-002` grant.

Prices, stock, and lifecycle are observations dated **2026-09-27** and must be
re-checked at purchase time.

---

## Candidate table

| Candidate | Disposition | Linux | Pi/ARM | UAC | Sample rate | Calibration | Availability (2026-09-27) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| miniDSP UMIK-1 | `VERIFIED_ELIGIBLE` | VERIFIED (mfr: driverless) | UNRESOLVED (no direct Pi source this pass) | UAC1 (mfr) | 24-bit @ 48 kHz (mfr) | per-serial `.txt` (mfr) | In stock ($79 miniDSP / $139.98 Parts Express) |
| miniDSP UMIK-2 | `VERIFIED_ELIGIBLE` | VERIFIED (mfr: driverless) | UNRESOLVED (no direct Pi source this pass) | UAC2 (mfr) | 32-bit @ 44.1–192 kHz (mfr) | per-serial file (mfr) | In stock ($195 miniDSP / $279.95–$324.99 retail) |
| Dayton Audio UMM-6 | `UNRESOLVED` | works via `snd-usb-audio`, with a documented mono/stereo caveat (community) | detected on Pi 4 (community), with a USB-enumeration caveat | UAC1 (distributor) | **UNRESOLVED** — official page does not state bit depth / sample rate | per-serial `.txt` (mfr) | Parts Express $79.99; SoundImports out of stock |

---

## Candidate detail

### C1 — miniDSP UMIK-1 · `VERIFIED_ELIGIBLE`

```text
manufacturer        miniDSP
exact model         UMIK-1 (Parts Express part 230-332)
product status      current; actively listed by manufacturer and distributor
interface           USB (miniUSB on v1 pre-Jan-2021; USB-C on v2 post-Jan-2021)
driver requirement  none on Linux (manufacturer: "Driverless interface for
                    Windows, Mac & Linux")
Linux evidence      VERIFIED — manufacturer product page states Linux driverless;
                    distributor corroborates "Windows, Mac, Linux ... without
                    extra drivers"
Pi/ARM evidence     UNRESOLVED — no direct UMIK-1-on-Raspberry-Pi source retrieved
                    this pass. It is a UAC1 class-compliant device, which is the
                    class the Pi handles via snd-usb-audio, but that inference is
                    not recorded as Pi-verified.
USB Audio Class     UAC1 (manufacturer)
sample rate         24-bit ADC @ 48 kHz (manufacturer); one distributor lists
                    "44.1 or 48 kHz"
channel count       single measurement capsule; exact ALSA channel enumeration on
                    Linux not directly observed this pass
bit depth           24-bit (manufacturer)
calibration         unique per-serial calibration .txt file (plain text),
                    downloadable by serial number (manufacturer)
availability        In stock — miniDSP direct 79 USD; Parts Express $139.98
                    (MSRP $164.99), "ships next business day"
price               79 USD (miniDSP) to $139.98 (Parts Express), 2026-09-27
sources             S01, S05, S06
disposition         VERIFIED_ELIGIBLE
reason              UAC1 driverless on Linux (manufacturer-stated), plain-text
                    per-serial calibration, 48 kHz/24-bit, currently obtainable.
                    Pi-specific evidence is UNRESOLVED but generic Linux/UAC1
                    behavior is sufficient for the human decision (R0 is
                    uncalibrated and single-channel-capable).
```

### C2 — miniDSP UMIK-2 · `VERIFIED_ELIGIBLE`

```text
manufacturer        miniDSP
exact model         UMIK-2 (Parts Express part 230-3420)
product status      current; actively listed by manufacturer and distributors
interface           USB-C
driver requirement  none on Linux/macOS/Android/iOS (manufacturer: driverless);
                    Windows requires a supplied ASIO driver (not relevant to Pi)
Linux evidence      VERIFIED — manufacturer: "Driverless operation with macOS,
                    Linux, Android and iOS"
Pi/ARM evidence     UNRESOLVED — no direct UMIK-2-on-Pi source this pass (UAC2
                    class-compliant)
USB Audio Class     UAC2 (manufacturer; XMOS controller)
sample rate         32-bit @ 44.1–192 kHz (manufacturer)
channel count       single measurement capsule; ALSA enumeration not directly
                    observed this pass
bit depth           32-bit (manufacturer)
calibration         unique per-serial calibration file (manufacturer); a 90-degree
                    file is also generated. Plain-text format is consistent with
                    miniDSP practice but was not explicitly confirmed this pass.
availability        In stock — miniDSP direct 195 USD; Deer Creek $279.95;
                    Parts Express $324.99; Amazon $318.95
price               195 USD (miniDSP) to ~$325 (retail), 2026-09-27
sources             S02, S07, S08, S09
disposition         VERIFIED_ELIGIBLE
reason              UAC2 driverless on Linux (manufacturer-stated), per-serial
                    calibration, currently obtainable. Over-specified for R0
                    (R0 needs no >48 kHz). Nuance: gain control is exposed only via
                    a Mac/Windows application, so on Linux the device runs at its
                    default gain — acceptable for uncalibrated R0. Pi-specific
                    evidence UNRESOLVED.
```

### C3 — Dayton Audio UMM-6 · `UNRESOLVED`

```text
manufacturer        Dayton Audio (Parts Express)
exact model         UMM-6
product status      current on manufacturer site; stock varies by seller
interface           USB-B; USB powered; C-Media controller (lsusb 0d8c:0147)
driver requirement  none (registers on Linux via snd-usb-audio)
Linux evidence      works via snd-usb-audio, BUT community reports a material
                    caveat: on Linux the device requires STEREO capture and may
                    reject mono/direct hw access; REW does not always recognize the
                    device name ("UMM-6"/"UMM_6"/"UMM6"), so its Sens Factor cal
                    entry is not auto-applied. (community sources)
Pi/ARM evidence     detected on Raspberry Pi 4 via snd-usb-audio (community, Pi
                    kernel issue), BUT with a documented USB-enumeration quirk on
                    some setups (not detected at boot unless another USB device is
                    present; VL805-firmware related)
USB Audio Class     UAC1 (distributor spec)
sample rate         UNRESOLVED — the official Dayton page/quick-reference does NOT
                    state ADC bit depth or sample rate. (The 24-bit/48 kHz figure
                    seen online belongs to the UMIK-1, not the UMM-6.)
channel count       Linux capture reported as stereo-required (community)
bit depth           UNRESOLVED (not stated by manufacturer)
calibration         unique per-serial calibration .txt file (plain text),
                    downloadable from Dayton by serial number (manufacturer)
availability        Parts Express $79.99; SoundImports €99.13 but OUT OF STOCK;
                    HardwareX ~$119.99 (2026-09-27)
price               ~$80–$120 depending on seller, 2026-09-27
sources             S03, S04, S10, S11
disposition         UNRESOLVED
reason              A real, obtainable UAC1 class-compliant device with direct
                    Pi-detection evidence, but two material facts are not resolved
                    from credible sources: (1) official sample-rate / bit-depth are
                    not stated, and (2) Linux mono-vs-stereo capture handling and
                    the Pi enumeration quirk are only community-documented. Per the
                    D5 acceptance criteria (sample-rate behavior must be
                    established), it does not reach VERIFIED_ELIGIBLE this pass. It
                    is not rejected — the unresolved facts are answerable with a
                    manufacturer datasheet or a direct bench observation.
```

---

## Source ledger

```text
S01  minidsp.com/products/acoustic-measurement/umik-1/           manufacturer   2026-09-27
     supports: UMIK-1 UAC1 driverless Win/Mac/Linux; 24-bit@48kHz; per-serial .txt cal; 79 USD

S02  minidsp.com/products/acoustic-measurement/umik-2            manufacturer   2026-09-27
     supports: UMIK-2 UAC2 driverless macOS/Linux/Android/iOS; 32-bit 44.1-192kHz; 195 USD; per-serial cal

S03  daytonaudio.com/product/1116/umm-6-usb-measurement-microphone  manufacturer 2026-09-27
     supports: UMM-6 6mm electret, 18-20kHz calibrated, USB-B, USB powered; bit depth / sample rate NOT stated

S04  daytonaudio.com/images/resources/390-808-...umm-6-quick-reference-guide-2.pdf  manufacturer 2026-09-27
     supports: UMM-6 quick-reference; per-serial .txt cal downloadable by serial; sensitivity via Windows volume; no sample rate stated

S05  parts-express.com/miniDSP-UMIK-1-...-230-332                 distributor    2026-09-27
     supports: UMIK-1 "Windows, Mac, Linux, iOS without extra drivers"; $139.98, In Stock

S06  opentip.com/miniDSP-UMIK-1-...                               distributor    2026-09-27
     supports: UMIK-1 UAC1 recognized by Windows/Mac/Linux; 24-bit @ 44.1 or 48 kHz

S07  parts-express.com/MiniDSP-UMIK-2-...-230-3420               distributor    2026-09-27
     supports: UMIK-2 32-bit ADC 44.1-192 kHz; $324.99, In Stock

S08  deercreekaudio.com/products/minidsp-umik-2                  distributor    2026-09-27
     supports: UMIK-2 $279.95, in stock, ships same business day

S09  amazon.com/.../dp/B094KX8ZZN                                 marketplace    2026-09-27
     supports (secondary): UMIK-2 driverless macOS/Linux/Android/iOS; $318.95

S10  soundimports.eu/en/dayton-audio-umm-6.html                  distributor    2026-09-27
     supports: UMM-6 USB Audio class 1.0; USB-B; per-serial cal; €99.13 OUT OF STOCK

S11  github.com/raspberrypi/linux issue #4010 + forums.raspberrypi.com t=295841  community 2026-09-27
     supports: UMM-6 detected on Raspberry Pi 4 via snd-usb-audio; USB-enumeration quirk on some setups

S12  avnirvana.com/threads/...umm-6...ubuntu-linux...             community      2026-09-27
     supports: UMM-6 on Ubuntu requires stereo capture; REW device-name recognition issue affecting auto cal
```

---

## Remaining uncertainties

- **Pi-specific evidence for the miniDSP mics** is UNRESOLVED this pass. Both are
  UAC-class-compliant and manufacturer-stated Linux-driverless; a direct
  Raspberry-Pi observation would upgrade Pi/ARM from UNRESOLVED to VERIFIED but is
  not required for the human decision (generic Linux/UAC behavior suffices for an
  uncalibrated R0).
- **UMM-6 sample-rate / bit-depth** is not stated by the manufacturer and is the
  main reason it is UNRESOLVED rather than eligible.
- **Calibration-file usability on Linux/TTP** was not exercised. R0 makes no
  calibrated claim, so a loaded calibration is not required for R0; the presence
  of a plain-text per-serial file is recorded as a fact, not as a working
  Linux/TTP calibration.

---

## Human selection block

To be completed by the repository owner (not by tooling):

```text
exact_microphone selected:
    <manufacturer + exact model>   (choose from VERIFIED_ELIGIBLE candidates)

selection_date:
selected_by:            repository owner
rationale:

D5:                     COMPLETE (on selection)
procurement_authorized: still NO  (requires a separate TTP-AUTH-002 grant)
```

Until the owner records a selection, `exact_microphone` remains `UNRESOLVED` in
`TTP_R0_PROCUREMENT_AUTHORIZATION.md`, and no purchase is authorized.
