# Acquisition — historical and deferred source material

**Nothing in this directory is calculation authority.** The canonical
implementation is the Python Acquisition Budget Authority in
`tap_tone_pi/uncertainty/acquisition/`; see
[the authority document](../../ACQUISITION_BUDGET_AUTHORITY.md).

---

## `JITTER_TO_SNR_CALCULATOR.html` — the original calculator

The interactive Jitter-to-SNR Sensitivity Calculator that `acquisition_budget.py`
was refined from. **Reference visualization only.**

| | |
| --- | --- |
| SHA-256 | `052d1fb009f314c8cdee11e03efef6a56fdc7e993bd9c0184e62c0d19960ac05` |
| Bytes | 583,984 |
| Supplied as | `Jitter-to-SNR Sensitivity Calculator (2).html` |

**No JavaScript reimplementation of these equations is authorized.** DO-107 §4.1
permits exactly one calculation implementation; maintaining two is how they drift
apart without anyone being able to say which one a number came from.

### Why the designation needed a ruling

Four files were supplied. Two were byte-identical, leaving three materially
distinct variants — and **all three carried character-identical mathematics**:

```js
Math.log10(2 * Math.PI * fMHz * 1e6 * jPs * 1e-12)   // jitter-limited SNR
6.02 * (bits || 0) + 1.76                            // ideal quantization SNR
(2 * Math.PI * fMHz * 1e6) * 1e12                    // inverse jitter budget
```

Those match `acquisition_budget.py`'s `jitter_snr_db()`, `quantization_snr_db()`
and `jitter_budget_s()` exactly. Since the mathematics was identical across all
three, **content could not identify which one the Python was derived from** — the
variants differ only in packaging and presentation. The file above was designated
by ruling as the version supplied with the refined Python work, not inferred from
a filename.

The two variants not retained are recorded here so the ambiguity stays visible
without carrying 611 KB of duplicate framework:

| Not retained | Bytes | SHA-256 |
| --- | --- | --- |
| bundled page, earlier revision | 577,714 | `53c99999c3e167987f03680ebd2fb99fa58d862ee71683c7144411b9f45c9b0a` |
| design-canvas source | 33,445 | `c08eb89fed424cbf3bea1aca9692e12a0a5a5cc2a77877d65152be45561ad721` |

**The parity target for DO-107 is the Python, not the HTML.** Where a test uses a
value these calculators also produce, the agreement checks transcription — but an
ambiguous filename must not decide implementation behavior.

---

## `deferred/` — arrived after the order was written, deliberately not incorporated

Both files below arrived while DO-107A was stopped at its grounding questions.
They are archived as source material and **none of their content is implemented
by DO-107A.**

| File | Bytes | SHA-256 |
| --- | --- | --- |
| `deferred/TTP_ACQUISITION_MATHEMATICS.md` | 22,903 | `c9a77a862913206a…` |
| `deferred/patch-02-acquisition.patch` | 54,578 | `9e964a8e6408ba97…` |

### Why they are deferred rather than applied

They postdate the dev order, and the mathematics document marks itself **"Not yet
source-verified."** It carries pending Patch #2 functions and unresolved
publication items — including an acknowledged CRLB discrepancy, a force-correction
question, and coverage-factor work.

**Folding unverified equations into the order that publishes the first
`acquisition_budget_v1` contract would be the worst possible sequencing.** A
published contract is the point after which downstream code is written against
it; a contract shaped by propositions their own author flagged as unverified is
one we would be migrating away from immediately.

Specifically **not** incorporated into DO-107A: the new equations, the T4
retargeting, the jitter regression, and the Smart Guitar conclusions.

They deserve a successor reconciliation order once the initial authority lands
and the source verification is done.

**The patch file is archived, not applied.** It is present so the proposal
survives; `git apply` has not been run against it and it is not expected to apply
cleanly to the post-DO-107A tree.
