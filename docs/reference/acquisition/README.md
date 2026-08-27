# Jitter-to-SNR Sensitivity Calculator — historical reference

**These files are reference visualizations. None of them is calculation
authority.** The canonical implementation is the Python Acquisition Budget
Authority in `tap_tone_pi/uncertainty/acquisition/`; see
[the authority document](../../ACQUISITION_BUDGET_AUTHORITY.md).

**No JavaScript reimplementation of these equations is authorized.** DO-107 §4.1
permits exactly one calculation implementation, and maintaining two is how they
drift apart without anyone noticing which one a number came from.

---

## Why three files, and why none is marked canonical

Four variants were supplied. Two were byte-identical, leaving **three materially
distinct** files:

| Archived as | Bytes | SHA-256 |
| --- | --- | --- |
| `jitter_to_snr_calculator_a.html` | 577,714 | `53c99999c3e167987f03680ebd2fb99fa58d862ee71683c7144411b9f45c9b0a` |
| `jitter_to_snr_calculator_b.html` | 583,984 | `052d1fb009f314c8cdee11e03efef6a56fdc7e993bd9c0184e62c0d19960ac05` |
| `jitter_to_snr_calculator_canvas.html` | 33,445 | `c08eb89fed424cbf3bea1aca9692e12a0a5a5cc2a77877d65152be45561ad721` |

`_b` was supplied twice under different names with identical bytes; the
duplicate is not archived.

DO-107 §5 asked for *the* variant the refined `acquisition_budget.py` was derived
from, with its digest recorded. **That relationship could not be established from
content, so none is designated canonical** — which is what the order prescribes
for exactly this case.

### What the comparison showed

**All three carry the same equations.** Each contains, character for character
in its JavaScript:

```js
Math.log10(2 * Math.PI * fMHz * 1e6 * jPs * 1e-12)   // jitter-limited SNR
6.02 * (bits || 0) + 1.76                            // ideal quantization SNR
(2 * Math.PI * fMHz * 1e6) * 1e12                    // inverse jitter budget
```

Those match `acquisition_budget.py`'s `jitter_snr_db()`, `quantization_snr_db()`
and `jitter_budget_s()` exactly. Since the mathematics is identical across all
three, **no variant is uniquely the formula source** — the derivation is equally
satisfied by any of them, and picking one would be a guess dressed as provenance.

They differ in packaging and presentation: `_a` and `_b` are bundled pages
differing by about 6 KB, and `_canvas` is the design-canvas source at a fraction
of the size.

### Circumstantial ordering, recorded as circumstantial

Supplied-file timestamps run `_canvas` (09:12) → `_a` (09:14) → `_b` (09:59,
re-saved 10:00) → `acquisition_budget.py` (12:24), all on 2026-08-27. That is
consistent with the Python being written after the last calculator revision, and
it is **not evidence**: these are download timestamps on loose files, not
repository history, and they cannot distinguish which variant was open when the
equations were transcribed.

Recorded here so a later reader does not have to re-derive it, and labelled so
nobody mistakes it for provenance.

## The parity target is the Python, not the HTML

DO-107's parity fixtures are built against `acquisition_budget.py`. Where a test
uses a value these calculators also produce, the agreement is a useful check on
transcription — but **an ambiguous HTML filename must not decide implementation
behavior.**

## Repository weight

These bundled pages total roughly 1.16 MB, most of it inlined framework rather
than the few lines of arithmetic that matter. They are kept whole rather than
excerpted so the reference is what was actually used, and each sits under the
1000 KB `check-added-large-files` limit individually.
