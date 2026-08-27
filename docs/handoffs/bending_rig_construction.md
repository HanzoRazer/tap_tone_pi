# Bending Rig Construction — Build Guide for Future Self

**Path in repo:** `docs/handoffs/bending_rig_construction.md`
**Status:** **ENGINEERING INPUT — NOT AUTHORIZED FOR CONSTRUCTION.** Retained as
design input under the prototype hold; see
[`docs/dev_orders/CURRENT.md`](../dev_orders/CURRENT.md). No component in the
bill of materials below is authorized for procurement, and no fabrication step is
authorized. The build schedule in §5 describes what *would* be done once the
Prototype Analyzer + Displacement Jig authorization is given — it is not a
work order. Originally written as: Synthesized from chat `be335122` (2026-07-10), OPA1612 preamp thread (Rev 1.1 procedure, 2026-03-31), and the tap_tone_pi_management + resuming-session threads.
**Owner:** Ross Echols, P.E. — Texas Guitar Exchange LLC
**Total budget:** ~$1,500 DIY
**Timeline:** 4 weeks (weekends), starts when the Mitutoyo indicator ships

---

## 1. Why this rig exists

Produce **peer-reviewable E_L and E_C measurements** on plate stock so the σ_measurement leg of `σ²_total = σ²_measurement + σ²_build` is characterized. Feeds `tap_tone_pi/bending/merge_and_moe.py` → `bending_moe.json` → viewer_pack_v1 → luthiers-toolbox brace engine.

Rev 1.1 (`docs/Bending_Stiffness_Procedure_Rev1_1.md`) is the **shop-level** procedure. This rig is the **lab-level** upgrade — same math, tighter frame, calibrated masses, verified against known-modulus reference specimens.

---

## 2. What this rig produces

| Output | Route |
|---|---|
| Load series (N vs step) | `load_series.json` |
| Displacement series (mm vs step) | `displacement_series.json` |
| E_L, E_C, EI, ν-corrected E_plate | `bending_moe.json` via `merge_and_moe` |
| GUM-compliant uncertainty (k=2, 95% CI) | `qa_lab_spec.py` → `UncertaintyBudget` |

Existing CLI flags already accept this rig's output:

```
python -m tap_tone_pi.bending.merge_and_moe \
  --load load_series.json --disp displacement_series.json \
  --outdir out/<sample>/ \
  --method 4point \
  --specimen-type strip \
  --span 400 --width 20 --thickness <mm> \
  --grain-orientation longitudinal
```

For whole-plate measurements: `--specimen-type full_plate --poisson 0.35` applies the (1−ν²) = 0.878 correction automatically.

---

## 3. Fixture geometry (locked)

| Parameter | Value | Source |
|---|---|---|
| Outer span L | 400 mm | Rev 1.1 §2.2 |
| Inner span (4-point) | L/3 = 133 mm | Rev 1.1 §2.2 |
| Support block height | 40–50 mm | Rev 1.1 §2.2 |
| Support contact | 6 mm drill rod (hardened) in V-groove | this rig — upgrade from Rev 1.1 knife-edge |
| Loading point | 5 mm radius steel roller | Rev 1.1 §2.2 |
| Frame profile | 40 mm aluminum extrusion (T-slot) | this rig |
| Displacement pickup | Self-referencing yoke, indicator reads specimen-to-support | this rig |

**Why the yoke matters:** eliminates frame flex from the displacement reading. Indicator body rides a bridge that spans the two outer supports; probe tip contacts the specimen underside at midspan. Reading = pure specimen deflection relative to its own support line, not frame + specimen.

**Slenderness check before every session:** L/h ≥ 20. At L = 400 mm, minimum thickness is 20 mm — always satisfied for guitar plates (2.5–3.5 mm typical). At h < 2.0 mm, bump L to 500–600 mm.

---

## 4. Bill of Materials

### Week 1 — sensor path ($850)

| Item | Notes |
|---|---|
| Mitutoyo ID-C 543-861 | 25.4 mm range, 0.001 mm resolution, SPC output |
| Mitutoyo USB Input Tool Direct (06AFM380B or equivalent) | Direct-to-USB cable, no separate interface |
| Serial config file | `config/devices/dial_indicator_example.json` — port assigned by OS, baud 9600, rate 20 Hz, regex `(-?[0-9]+\.?[0-9]*)` |

Tier 2 fallback if Mitutoyo pricing shifts: LVDT + signal conditioning ($800–2,500). Tier 3: Keyence GT2 ($2,000–4,000). Tier 1 chosen for cost/precision/repeatability.

### Week 2 — mechanical path (~$600)

| Item | Qty | Notes |
|---|---|---|
| 40 mm T-slot aluminum extrusion, 1 m | 3 | Frame beams + uprights |
| 40 mm T-slot end/corner brackets | 8 | Squared assembly |
| M8 T-nuts + hardware | ~30 | Adjustable positioning |
| Ground steel plate stock, 6 mm × 100 × 100 | 2 | Support blocks |
| 6 mm drill rod, hardened, 100 mm | 3 | Knife-edges + rocker (spares) |
| 5 mm radius steel roller | 1 | Loading point (or ground from rod) |
| Rocker bar (self-centering, two knife edges at L/3) | 1 | Fabricate from steel bar stock + rod |
| Dead-weight load platform (aluminum) | 1 | Hangs from loading point |
| OIML class M1 calibrated masses | 100 g × 5, 500 g × 4, 1 kg × 2 | Total ~4.5 kg range covers 0–45 N |
| Displacement yoke (aluminum, bridges outer supports, holds indicator vertically) | 1 | Fabricate |

### Optional load-cell path (already in Rev 1.1 stack)

Skip if OIML masses are trusted. If load cell wanted for continuous logging:

| Item | Notes |
|---|---|
| Strain-gauge load cell, 0–50 N | Serial via HX711 24-bit ADC → Arduino Uno/Nano → USB (COM assigned by OS, 115200 baud, 50 Hz) |
| Config: `config/devices/loadcell_example.json` | Already in repo |

---

## 5. Four-week fabrication schedule

### Week 1 — order + prep
- [ ] Order Mitutoyo ID-C 543-861 + USB Input Tool Direct
- [ ] Order aluminum extrusion, brackets, hardware
- [ ] Order OIML M1 mass set
- [ ] Order 6 mm hardened drill rod, ground steel plate, 5 mm roller stock
- [ ] Clear a stable, level 1 m² bench area; confirm ambient temp control (target ±2 °C during a run)

### Weekend 1 — frame
- [ ] Cut extrusion: 2× 800 mm (base rails), 4× 200 mm (uprights + cross-braces)
- [ ] Assemble as a squared open box, base rails parallel at 400 mm center-to-center support spacing
- [ ] Verify frame diagonals equal (±0.5 mm) — this sets span accuracy
- [ ] Bolt frame to bench or heavy plate; frame must not walk under load

### Weekend 2 — supports + rocker
- [ ] Cut 2× support blocks from 6 mm ground steel plate, 40–50 mm tall
- [ ] Machine V-grooves for 6 mm drill rod, position rod flush with top of block → knife-edge line
- [ ] Mount support blocks on base rails at exactly 400 mm center-to-center
- [ ] Fabricate rocker bar: bar stock with two V-grooves 133 mm apart, drill rods installed, center pivot point on top for load application
- [ ] Verify rocker self-centers under symmetric load (no tilt bias)

### Weekend 3 — yoke + load path
- [ ] Fabricate displacement yoke: aluminum bridge that clamps to both outer supports (never to frame), holds Mitutoyo indicator vertically with probe centered at midspan
- [ ] Zero-check: with no specimen, yoke reading should be stable to ±0.001 mm across a full frame flex cycle (load applied to frame directly, not through supports)
- [ ] Hang dead-weight platform from rocker's center pivot
- [ ] Verify platform hangs freely, no rubbing, no tilt bias

### Weekend 4 — wiring + verification
- [ ] Connect Mitutoyo to Pi/PC via USB Input Tool Direct; confirm serial output parses with existing regex
- [ ] Confirm `python -m tap_tone_pi.bending.merge_and_moe --help` shows `--specimen-type`, `--poisson`, `--grain-orientation` flags
- [ ] Run verification sequence (§7)
- [ ] File first `bending_moe.json` for each reference specimen in `out/verify_<date>/`

---

## 6. Calibration procedure

Run before every measurement session, log to `docs/handoffs/bending_rig_calibration_log.md`:

1. **Ambient:** record temp (°C) and RH (%); refuse to run if temp shifts >2 °C during a session
2. **Frame flat check:** confirm outer supports' knife-edge tops are coplanar to ±0.05 mm (dial indicator across, no specimen)
3. **Yoke bias:** load frame via a corner (not the supports); indicator should not move. If it does, the yoke is picking up frame flex — rebuild
4. **Zero:** place specimen, load rocker with platform (no masses), zero indicator
5. **Mass sequence:** apply masses in ascending steps (e.g., 100 g increments), record indicator reading at each; hold 5 s per step for creep settle
6. **Reverse sweep:** unload in descending order; hysteresis at zero >0.003 mm → check for support slippage
7. **Linearity check:** slope of load vs deflection must be linear (R² > 0.999); nonlinearity indicates plastic deformation or fixture play

Mass values in `load_series.json`: multiply grams by 0.00981 to get Newtons. A 1 kg mass = 9.81 N.

---

## 7. Verification protocol (peer-review anchor)

**This is what makes the rig defensible.** Measure three known-modulus specimens; results within ±5 % of published values = rig verified.

| Material | E (GPa) | Specimen | Expected slope check |
|---|---|---|---|
| Aluminum 6061-T6 | 68.9 | 20 × 3 × 400 mm | Reference — very stiff |
| Steel 1018 | ≈200 | 20 × 3 × 400 mm | High-end range |
| Acrylic (cast) | ≈3.2 | 20 × 3 × 400 mm | Low-modulus range, closest to soft tonewoods |

Procedure per specimen:
1. Measure dimensions with caliper (thickness to 0.01 mm, width to 0.05 mm)
2. Run 3-point at 400 mm span, 5 load steps, 0.5–3 kg range
3. `merge_and_moe --method 3point --specimen-type strip`
4. Compare `E_corrected_Pa` to published value
5. Record deviation % in `docs/verification/bending_rig_verify_<date>.md`

**Pass criterion:** all three within ±5 %.
**Investigation trigger:** any specimen off by >8 %.
**Rebuild trigger:** two specimens off by >8 %.

Repeat verification every 3 months and after any physical modification to the rig.

---

## 8. Cross-validation option (peer-review upgrade)

For publication-grade certification, send 5 specimens (same materials + 2 tonewoods) to a certified lab (FPL, university mechanics lab). Cost: $1,000–$2,500. Compare their reported E to rig-measured E. This is the strongest external validation short of ASTM lab accreditation and turns the rig from "internally consistent" to "externally traceable."

Not required for the immediate ecosystem, but the verification specimen protocol was designed so this upgrade slots in without redesigning anything.

---

## 9. E_C measurement variants

**Two-strip method** (Rev 1.1 §3, preferred when wood permits): cut along-grain and cross-grain strips from the same billet, 20 × 400 mm × plate thickness. Run each through the rig separately. Report both E_L and E_C plus the orthotropic ratio.

**Cross-grain-only 170 mm strip** (Rev 1.1 §4.3): when a 400 mm cross-grain strip isn't possible, use 170 mm specimen suspended at 38 mm from each end (nodal-line support). Shorter span = smaller deflections; tighten dial indicator zeroing discipline.

**Species-ratio estimate** (Rev 1.1 §4.4, when no cross-grain wood available):

| Species | E_C estimate |
|---|---|
| Sitka spruce | E_L ÷ 12 |
| Engelmann spruce | E_L ÷ 15 |
| Western red cedar | E_L ÷ 13 |
| Adirondack spruce | E_L ÷ 15 |

Interpretation of orthotropic ratio E_L/E_C:
- < 8:1 → lower-quality wood (or grain direction misidentified — check first)
- 10:1–15:1 → typical acoustic tonewood
- \> 18:1 → exceptional

---

## 10. Whole-plate mode (Rev 1.1 §4)

Same fixture, wider specimen. `--specimen-type full_plate --poisson 0.35` applies the (1−ν²) = 0.878 plate-width correction automatically. Whole-plate measures **E_L only** — E_C requires either a second cross-grain strip or the species-ratio estimate above. This was the correction Rev 1.1 issued over Rev 1.0.

---

## 11. Data flow

```
Rig session
  → load_series.json + displacement_series.json (this rig writes)
  → merge_and_moe CLI
  → bending_moe.json (E_L, E_C, EI, ν-corrected E_plate, uncertainty)
  → viewer_pack_v1.json (already wired in Phase 4 Track A)
  → luthiers-toolbox brace engine (Phase 4 Track B via viewer_pack_bridge.py)
```

Every session bundle carries:
- SHA-256 of raw inputs
- Timestamp UTC
- Ambient temp + RH
- Schema version
- `qa_lab_spec.py` uncertainty budget (`coverage_factor=2.0`, `confidence_level_percent=95.0`)

Per `CLAUDE.md` anti-drift rules: provenance is mandatory. Don't skip the env fields — they're what makes the record defensible six months later.

---

## 12. Open items for future self

- [ ] **Rocker validation:** confirm rocker's self-centering does not introduce measurable bias vs a fixed-4-point config. Method: measure aluminum reference in both configs, compare E_corrected. Expected agreement: within measurement uncertainty.
- [ ] **Frame flex characterization:** with the yoke in place, verify that frame flex actually contributes zero to displacement reading across the full 0–45 N range. Load frame corners externally with a clamp, watch indicator.
- [ ] **Long-term drift:** after 30 days of ambient temperature swings, repeat verification. Note any drift trend.
- [ ] **Optional Rocker → 4-point switch:** if 3-point is producing higher variance on soft tonewoods, switch to 4-point with the rocker; 4-point puts uniform moment in the center zone and is less sensitive to grain irregularities.
- [ ] **Update Rev 1.1 → Rev 2.0:** once this rig is verified, publish `docs/Bending_Stiffness_Procedure_Rev2_0.md` incorporating the yoke, rocker, OIML masses, and verification protocol. Rev 1.1 stays available as the shop-level procedure.
- [ ] **Handoff to campaign:** the rig's completion unblocks the 20-plate characterization campaign — but do NOT stop revenue-generating builds during construction. Weekend fabrication runs in parallel with weekday production, per strategic reframing.

---

## 13. Related repo paths

| File | Purpose |
|---|---|
| `docs/Bending_Stiffness_Procedure_Rev1_1.md` | **NOT IN THE REPOSITORY** — see the reconciliation note below |
| `docs/hardware/TTP_HARDWARE_STACK.md` | Canonical hardware stack spec (absorbed `HARDWARE_STACK_SPEC.md` at Rev 1.3) |
| `docs/handoffs/no_soundhole_lab_protocol.md` | Adjacent measurement protocol |
| `docs/ADR-0009-advisory-boundary.md` | Rig outputs measurements only — no advisory logic |
| `docs/ADR-0011-measurement-authority.md` | Measurement authority chain |
| `docs/CHECKPOINT_2026-06-20_MEASUREMENT_LEGITIMACY.md` | Metrology framework this rig plugs into |
| `tap_tone_pi/bending/merge_and_moe.py` | CLI entry point; consumes rig output |
| `tap_tone_pi/bending/qa_lab_spec.py` | UncertaintyBudget dataclass |
| `contracts/schemas/bending_stiffness.schema.json` | Output contract |
| `contracts/schemas/load_series.schema.json`, `contracts/schemas/displacement_series.schema.json` | Input contracts |
| `config/devices/dial_indicator_example.json`, `loadcell_example.json` | Serial device configs |

---

---

## 14. Reconciliation against the repository (2026-08-27)

This guide instructs its reader to trust the repo over the document. That check
was run when the file was committed. Four things were found.

**`docs/Bending_Stiffness_Procedure_Rev1_1.md` does not exist in this repository,
and nothing references it.** It is cited throughout as the source for fixture
geometry (§2.2), the E_C measurement variants (§3, §4.3, §4.4), and whole-plate
mode (§4) — roughly a third of this document's dimensional authority. **Those
citations are orphaned.** No dimension has been altered: the geometry may be
entirely correct, and there is no basis in the repository to change a number. But
a reader must know that the cited source cannot be consulted here, and Rev 1.1
should be recovered or rewritten before any of these dimensions is cut into metal.

**Three contract paths were off by a directory.** They live under
`contracts/schemas/`, not `contracts/`. Corrected above; all three exist.

**`docs/HARDWARE_STACK_SPEC.md` was removed**, merged into
`docs/hardware/TTP_HARDWARE_STACK.md` at Rev 1.3. Corrected above.

**The CLI is exactly as described.** `--specimen-type`, `--poisson`,
`--grain-orientation`, `--method`, `--span`, `--width` and `--thickness` all
exist on `tap_tone_pi.bending.merge_and_moe`. The software half of this rig is
real and matches the guide.

### Ownership of the hardware in §4

**None of it is owned.** DO-104R census pass 2 records every item in the bill of
materials as `CONFIRMED_ABSENT` — no dial indicator, no USB interface, no
extrusion, no ground steel or drill rod, no OIML mass set, no load cell. The
"starts when the Mitutoyo indicator ships" timeline in §5 refers to an order that
has not been placed.

The displacement jig has **never had a hardware specification** in this
repository — no BOM row, no requirements document, no interface matrix. The
`TTP_E1_*` documents cover the acoustic and excitation chain only, and a serial
dial indicator appears in none of them. **This guide is currently the only
hardware description the jig has**, which is precisely why it is worth keeping
and precisely why it must not be mistaken for an authorized build.

---

*Written 2026-07-17 as pick-up-and-run guide. If any dimension, part number, or procedure below disagrees with the actual repo state when you return, trust the repo and update this document. Drift between handoff and reality breaks future sessions.*
