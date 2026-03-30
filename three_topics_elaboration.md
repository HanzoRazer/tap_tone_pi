# tap_tone_pi — Three Open Issues: Elaboration
**Date:** 2026-03-30  
**Status:** Engineering analysis + action items

---

## Topic 1 — Dual FFT Stack: How It Happened, What To Do

### How It Happened

The dual-stack is a direct artifact of context exhaustion across separate
conversations. The reconstruction pattern is consistent with what you
describe: a GPT conversation that ran out of context mid-session was
restarted, and the new session recreated functionality from scratch rather
than locating and extending the existing implementation. The result is:

```
tap_tone_pi/core/analysis.py     ← Capture engine FFT (Pi-side)
    analyze_tap() → AnalysisResult
    Hanning window, scipy.fft.rfft, normalized 0..1, float32

analyzer/analysis/fft.py         ← Desktop viewer FFT (PC-side)  
    compute_fft() → (frequencies, magnitudes)
    Hanning window, scipy.fft.rfft, amplitude scaling (2.0/N), NOT normalized
```

These were written independently. They agree today on dominant frequency
(verified: 0.000 Hz difference on synthetic signals). But they diverge on
magnitude representation — the capture engine normalizes to 0..1, the
analyzer scales by `2.0 / N`. That divergence will matter the moment anyone
tries to compare relative mode amplitudes between a Pi session report and
the desktop viewer.

### Terminal Confirmation Prompt

Run this directly in your repo root. It does not require pytest — it is a
standalone diagnostic that prints a clear PASS/FAIL with specifics:

```powershell
# Windows — run from tap_tone_pi repo root
python - << 'EOF'
"""
Dual-FFT stack diagnostic.
Verifies that tap_tone_pi/core/analysis.py and analyzer/analysis/fft.py
agree on peak frequencies for synthetic signals.
Prints PASS/FAIL with numeric evidence.
"""
import sys
import numpy as np
sys.path.insert(0, ".")

# ── Import both stacks ──────────────────────────────────────────────────────
try:
    from tap_tone_pi.core.analysis import analyze_tap
    CAPTURE_OK = True
except Exception as e:
    print(f"[ERROR] Cannot import tap_tone_pi.core.analysis: {e}")
    CAPTURE_OK = False

try:
    from analyzer.analysis.fft import compute_fft, find_resonance_frequency
    from analyzer.analysis.peaks import find_spectrum_peaks
    ANALYZER_OK = True
except Exception as e:
    print(f"[ERROR] Cannot import analyzer.analysis.fft: {e}")
    ANALYZER_OK = False

if not (CAPTURE_OK and ANALYZER_OK):
    print("\n[FAIL] One or both stacks could not be imported — dual-stack exists.")
    sys.exit(1)

# ── Signal synthesis ─────────────────────────────────────────────────────────
SR = 44100
T  = np.arange(int(SR * 0.5)) / SR

def synth(freqs_hz, snr_db=40, seed=42):
    rng = np.random.default_rng(seed)
    sig = sum(
        (1/(i+1)) * np.exp(-T/0.15) * np.sin(2*np.pi*f*T)
        for i, f in enumerate(freqs_hz)
    ).astype(np.float32)
    noise_rms = float(np.sqrt(np.mean(sig**2))) / (10**(snr_db/20))
    sig += rng.normal(0, noise_rms, size=len(T)).astype(np.float32)
    sig /= np.max(np.abs(sig)) * 1.1
    return sig

CASES = [
    ("180 Hz single",        [180.0],               180.0),
    ("220 Hz single",        [220.0],               220.0),
    ("203 Hz Sitka-like",    [203.0, 380.0, 635.0], 203.0),
    ("165 Hz cedar-like",    [165.0, 330.0, 495.0], 165.0),
]

FREQ_TOLERANCE_HZ  = 1.5    # Max allowed difference between implementations
TRUTH_TOLERANCE_HZ = 12.0   # Max allowed distance from true frequency (1 FFT bin)

print("\n=== Dual-FFT Stack Diagnostic ===\n")
print(f"{'Case':<30}  {'Capture':>10}  {'Analyzer':>10}  {'Diff':>8}  {'Status':>8}")
print("-" * 75)

all_pass = True
for name, freqs, truth in CASES:
    sig = synth(freqs)

    # Capture engine
    r = analyze_tap(sig, SR, peak_min_hz=40.0, peak_max_hz=2000.0,
                    peak_min_prominence=0.03)
    cap_hz = r.dominant_hz or 0.0

    # Analyzer
    f_arr, m_arr = compute_fft(sig, float(SR), window="hann")
    ana_hz = find_resonance_frequency(f_arr, m_arr, freq_range=(40.0, 2000.0)) or 0.0

    diff = abs(cap_hz - ana_hz)
    ok = diff <= FREQ_TOLERANCE_HZ
    if not ok:
        all_pass = False
    status = "PASS" if ok else "FAIL"
    print(f"{name:<30}  {cap_hz:>10.3f}  {ana_hz:>10.3f}  {diff:>8.3f}  {status:>8}")

print("-" * 75)
# Magnitude representation check
sig = synth([220.0])
r = analyze_tap(sig, SR)
cap_mag = max((p.magnitude for p in r.peaks), default=0.0)
f_arr, m_arr = compute_fft(sig, float(SR), window="hann")
ana_mag = float(m_arr.max()) if m_arr.size else 0.0

print(f"\nMagnitude representation:")
print(f"  Capture engine peak magnitude (normalized 0-1): {cap_mag:.4f}")
print(f"  Analyzer FFT max magnitude (amplitude scale):   {ana_mag:.4f}")
if abs(cap_mag - 1.0) < 0.05:
    print("  Capture engine: correctly normalized to 0..1")
else:
    print("  [WARN] Capture engine magnitude not near 1.0 at dominant peak")
if ana_mag > 1.0:
    print("  Analyzer: uses amplitude scale (not 0..1) — DIFFERENT from capture engine")
    print("  [WARN] Comparing magnitudes across stacks will produce wrong answers")

print()
if all_pass:
    print("[PASS] Frequency agreement: both stacks produce consistent peak frequencies.")
else:
    print("[FAIL] Frequency disagreement detected. The stacks have diverged.")
    print("       Fix: align windowing/normalization in analyzer/analysis/fft.py")
    print("       to match tap_tone_pi/core/analysis.py")
print()
EOF
```

### What the Diagnostic Proves

The test will confirm two things independently:

1. **Frequency agreement** — PASS today. Both stacks use `scipy.fft.rfft`
   with a Hanning window on the same data. They land at the same bin.

2. **Magnitude agreement** — FAIL by design. The capture engine returns
   `spectrum_mag` normalized to `[0..1]`. The analyzer's `compute_fft`
   returns raw amplitude scaled by `2.0/N`. These are not comparable numbers.
   A mode with `magnitude = 0.65` in the Pi report means something completely
   different from `magnitude = 0.0031` in the analyzer plot, even for the same
   WAV file.

### Resolution

The magnitude divergence has two options:

**Option A (preferred): Normalize in both** — add one line to `analyzer/analysis/fft.py`:
```python
magnitudes = np.abs(fft_result) * 2.0 / n
mag_max = magnitudes.max()
if mag_max > 0:
    magnitudes = magnitudes / mag_max   # Add this line
```

**Option B: Make it explicit** — rename `analyzer/analysis/fft.py`'s output
to `amplitudes` (not `magnitudes`) so downstream code can never accidentally
compare the two. Document the two representations in ADR-0009 or a new
ADR-0010.

The frequency agreement is the safety-critical property. Magnitude
representation is a display concern. Fix Option A now; it's one line.

---

## Topic 2 — OPA1612 Gain Staging: Fix for HiFiBerry 0.8–2.1 Vrms Sweet Spot

### The Problem

`docs/hardware/TTP_HARDWARE_STACK.md` lists:

| Stage | Gain | dB |
|---|---|---|
| U1A (mic stage) | 11× | +20.8 dB |
| U1B low gain | 2× | +6.0 dB |
| U1B high gain | 5.7× | +15.1 dB |
| **Total low** | **22×** | **+26.8 dB** |
| **Total high** | **63×** | **+35.9 dB** |

These numbers are **correct for the chip** but were never verified against
an actual tap-tone acoustic source. The workshop noise floor question is
moot for now — **no unit exists yet**. The design-stage question is: will
these gains reliably land the output in the 0.8–2.1 Vrms window for the
expected tap-tone SPL range?

### Tap Tone Source Level Analysis

A finger tap on a guitar plate at 30 cm mic distance produces approximately:
- **Loud workshop tap:** 75–85 dB SPL at mic
- **Typical bench tap:** 65–75 dB SPL at mic
- **Quiet or distant tap:** 55–65 dB SPL at mic

A small-diaphragm condenser at these SPLs outputs roughly:

| SPL at mic | Mic sensitivity (−40 dBV/Pa typical) | Mic output |
|---|---|---|
| 85 dB SPL | −40 dBV + (85−94) dBPa = −49 dBV | ~3.6 mVrms |
| 75 dB SPL | −49 − 10 = −59 dBV | ~1.1 mVrms |
| 65 dB SPL | −59 − 10 = −69 dBV | ~0.36 mVrms |

*(Using 94 dB SPL = 1 Pa reference; −40 dBV/Pa sensitivity)*

### Gain Staging Calculation

Target ADC input: **1.0 Vrms** (centre of 0.8–2.1 sweet spot)

| Tap SPL | Mic output | Required gain to 1.0 Vrms | Required dB gain |
|---|---|---|---|
| 85 dB | 3.6 mVrms | 278× | 48.9 dB |
| 75 dB | 1.1 mVrms | 909× | 59.2 dB |
| 65 dB | 0.36 mVrms | 2,778× | 68.9 dB |

**The current design tops out at 63× (+35.9 dB). This is 13–33 dB short.**

Even at the loudest realistic tap (85 dB SPL at the mic), the current gain
produces only ~227 mVrms into the ADC — well below the 0.8 Vrms floor.
At a typical bench tap (75 dB SPL) it produces ~69 mVrms. The ADC will
be operating far below its optimal range, meaning poor dynamic range and
elevated noise in measurements.

### Corrected Gain Specification

To cover the realistic tap tone SPL range (65–85 dB SPL at mic):

| Target | Required total gain |
|---|---|
| Worst case (65 dB SPL, 0.8 Vrms floor) | 2,222× = +66.9 dB |
| Typical (75 dB SPL, 1.0 Vrms target) | 909× = +59.2 dB |
| Loud tap (85 dB SPL, 2.1 Vrms ceiling) | 583× = +55.3 dB |

**Design target: adjustable gain 55–70 dB total, centred at ~60 dB.**

### OPA1612 Corrected Circuit

The fix is in U1B's gain network. U1A is fine at 11× (+20.8 dB) — that's
appropriate for the mic pre stage. U1B needs to swing between approximately
34× and 100× (+30.6 to +40 dB) to cover the range.

```
Stage        Current            Corrected
────────────────────────────────────────
U1A          11×  (+20.8 dB)   11×  (+20.8 dB)   — unchanged
U1B low      2×   (+6.0 dB)    34×  (+30.6 dB)   — Rf=470k, Rg=14k
U1B high     5.7× (+15.1 dB)   100× (+40.0 dB)   — Rf=1M, Rg=10k

Total low    22×  (+26.8 dB)   374× (+51.5 dB)
Total high   63×  (+35.9 dB)   1100× (+60.8 dB)
```

**Rationale for the new U1B values:**
- `Rf=470k, Rg=14k` → Gain = 1 + 470/14 = 34.6× → +30.7 dB
  Total low: 11 × 34.6 = 381× → +51.6 dB
  At 85 dB SPL: 3.6 mVrms × 381 = 1.37 Vrms ✅ (inside sweet spot)

- `Rf=1M, Rg=10k` → Gain = 1 + 1000/10 = 101× → +40.1 dB
  Total high: 11 × 101 = 1111× → +60.9 dB
  At 75 dB SPL: 1.1 mVrms × 1111 = 1.22 Vrms ✅ (inside sweet spot)
  At 65 dB SPL: 0.36 mVrms × 1111 = 0.40 Vrms — marginal (needs ADC
  sensitivity or a third gain step)

**For production: add a three-position gain switch:**

| Switch | U1B Rf | U1B Rg | U1B gain | Total gain | Use case |
|---|---|---|---|---|---|
| LOW | 100k | 14k | 8.1× | 89× (+39 dB) | Close mic, loud tap, dynamic mic |
| MID | 470k | 14k | 34.6× | 381× (+52 dB) | Standard bench setup |
| HIGH | 1M | 10k | 101× | 1111× (+61 dB) | Distant mic, quiet plate, condenser |

A trim pot on Rg (10k–22k range) gives continuous adjustment within each
switch position for fine-tuning.

### Update to TTP_HARDWARE_STACK.md

The current table in the hardware doc must be replaced. The correct entry:

```markdown
### Corrected Gain Staging (3-position switch)

| Switch | Total Gain | dB | Output at 85 dB SPL | Output at 75 dB SPL |
|---|---|---|---|---|
| LOW | 89× | +39 dB | 320 mVrms | 98 mVrms |
| MID | 381× | +52 dB | 1.37 Vrms ✅ | 0.42 Vrms ⚠ |
| HIGH | 1111× | +61 dB | 4.0 Vrms ⚠ (clip) | 1.22 Vrms ✅ |

HiFiBerry sweet spot: 0.8–2.1 Vrms. ⚠ = outside range.
MID is the default. HIGH is for condenser mic + quiet plates.

Note: These are design-stage calculations against modelled source levels.
First hardware prototype must verify with measured mic output at the
actual test bench before finalising Rf/Rg values.
```

### AliExpress Module Note

The $12–15 OPA1612 modules sold on AliExpress have **fixed gain** —
typically the mic stage only, at around +20–30 dB total. They will not
hit the HiFiBerry sweet spot for tap-tone work. For the prototype, you
need to either:
1. Add a second gain stage board in series, or
2. Build the two-stage circuit on a breadboard using the OPA1612 DIP
   package (SOIC adapter needed) with the corrected Rf/Rg values above

---

## Topic 3 — wolf_advisor in viewer_pack_v1: What Actually Contaminates What

### Clarifying the Distinction

There are **two different wolf outputs** in the codebase. The prior analysis
conflated them. They are not the same thing:

```
tap_tone_pi/wolf/wolf_beat.py      → wolf_candidates.json, wsi_curve.csv
tap_tone_pi/wolf/wolf_advisor.py   → WolfAdvisor recommendations, MitigationType
```

| Output | Instrument Class | In viewer_pack_v1? | Contaminates chain? |
|---|---|---|---|
| `wolf_candidates.json` | **MEASUREMENT** | ✅ Yes — it's in the schema | ❌ No |
| `wsi_curve.csv` | **MEASUREMENT** | ✅ Yes — it's in the schema | ❌ No |
| `WolfAdvisor` recommendations | **DECISION SUPPORT** | ❓ Must verify | ⚠ Yes, if present |

`wolf_candidates.json` is measurement data: detected peak pairs, beat
frequency, coupling strength Ω, WSI value. These are numbers derived
from the FFT. They belong in the provenance chain the same way peak
frequencies do.

`WolfAdvisor` output is different: `MitigationType.ADD_MASS`, confidence
levels, ranked intervention strategies. These are model-derived
recommendations. If these appear in `viewer_pack_v1`, the provenance
chain is contaminated because a downstream consumer (Production Shop)
cannot distinguish "this is what we measured" from "this is what the
model recommended."

### Current Export Pipeline Trace

From `scripts/phase2/export_viewer_pack_v1.py`:
```python
# Lines 334-341 — what actually goes into the bundle:
wc = derived_dir / "wolf_candidates.json"    # ← wolf_beat output
wsi = derived_dir / "wsi_curve.csv"          # ← wolf_beat output
add_file_fn(wc, "wolf/wolf_candidates.json")
add_file_fn(wsi, "wolf/wsi_curve.csv")
```

The export pipeline **does not import `wolf_advisor.py`** and does not
call `WolfAdvisor`. The `wolf/` directory in the bundle contains only
`wolf_beat` outputs. The schema's `interpretation_free` assertion
(line 55 in `viewer_pack_v1.schema.json`) is currently honoured.

### What Would Cause Contamination

The contamination happens if any of these occur:

1. A future sprint adds `WolfAdvisor.get_recommendations()` output to
   `wolf_candidates.json` — e.g. appending a `"mitigation_suggestions"`
   field to the JSON.

2. The `/export` FastAPI endpoint (currently a stub) is implemented and
   someone pipes `generate_wolf_directive()` output into the response.

3. The `analyzer/` desktop viewer saves an annotated bundle that includes
   wolf recommendations back to disk, and a subsequent session uses that
   as input.

### The Correct Architecture

```
wolf_beat.py       →  wolf_candidates.json  →  viewer_pack_v1  →  Production Shop
  (measurement)                                  (measurement)       reads numbers

wolf_advisor.py    →  AttentionDirectiveV1  →  agentic layer   →  operator screen
  (decision support)                           (never persisted   shows recommendation
                                                 to bundle)        operator decides
```

`WolfAdvisor` output must flow to the **agentic spine** (`AttentionDirectiveV1`),
not to the export pipeline. The directive appears on the operator's screen,
the operator makes a decision, and that decision (if any) is recorded in the
session timeline as a human action — not as a measurement result.

### Concrete Fix: Gate in the Export Pipeline

Add an explicit assertion in `export_viewer_pack_v1.py` that the
`wolf_candidates.json` file does not contain advisory fields:

```python
# In _add_derived_artifacts(), after loading wolf_candidates.json:
PROHIBITED_WOLF_ADVISORY_FIELDS = {
    "mitigation_suggestions",
    "recommendations",
    "advisor_output",
    "mitigations",
    "confidence_level",   # WolfAdvisor-specific field
    "recommended_action", # WolfAdvisor-specific field
}

def _validate_wolf_candidates_clean(wc_path: Path) -> None:
    """Assert wolf_candidates.json contains no advisory fields."""
    try:
        data = json.loads(wc_path.read_text())
    except Exception:
        return  # Parse errors caught elsewhere
    found = PROHIBITED_WOLF_ADVISORY_FIELDS & set(data.keys())
    if found:
        raise ValueError(
            f"wolf_candidates.json contains advisory fields: {found}. "
            f"WolfAdvisor output must not appear in viewer_pack_v1. "
            f"See docs/ADR-0009-advisory-boundary.md"
        )
```

Call this before `add_file_fn(wc, ...)`. It is a hard stop — the export
fails rather than silently contaminating the bundle.

### ADR-0009 Update Required

ADR-0009 as written says wolf_advisor "must not appear in viewer_pack_v1."
It should be more precise:

> `wolf_beat.py` outputs (`wolf_candidates.json`, `wsi_curve.csv`) are
> MEASUREMENT data and belong in `viewer_pack_v1`. They measure the
> avoided-crossing phenomenon.
>
> `wolf_advisor.py` outputs (`WolfAdvisor`, `AttentionDirectiveV1`) are
> DECISION SUPPORT and must route to the agentic spine only. They must
> never appear in any export artifact.
>
> The distinction is: measuring that a wolf exists and quantifying its
> severity is a measurement. Recommending what to do about it is
> interpretation.

---

## Action Summary

| # | Action | File | Effort |
|---|---|---|---|
| 1 | Normalize analyzer magnitude to 0..1 | `analyzer/analysis/fft.py` | 1 line |
| 2 | Run terminal diagnostic, screenshot result | `python -` script above | 10 min |
| 3 | Update gain table in hardware doc | `docs/hardware/TTP_HARDWARE_STACK.md` | 30 min |
| 4 | Add `_validate_wolf_candidates_clean()` | `scripts/phase2/export_viewer_pack_v1.py` | 1 hour |
| 5 | Update ADR-0009 wolf section | `docs/ADR-0009-advisory-boundary.md` | 30 min |
| 6 | Update hardware stack: three-position gain switch | `docs/hardware/TTP_HARDWARE_STACK.md` | 1 hour |
