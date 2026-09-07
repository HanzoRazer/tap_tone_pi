# DO-108H — Capability Matrix / Commercial Excitation Reconciliation

## Status

**COMPLETE — adjudication performed, no capability-state conflict found.**

This is an evidence-closure order, not an implementation project. It changed no
capability state, no hardware state, no vocabulary, and no code.

## The question

DO-108P recorded three capability statements locally, because the repository-wide
capability matrix was unmerged at the time and importing a fragment of it would
have forked an authority that did not yet exist on that branch. The architecture
document promised that when the matrix landed, those three lines were what it
must reconcile with.

**The matrix landed** as `6c5366f`. Nothing owned the promised reconciliation —
[DO-108G](backlog/DO-108G_GAP_INVENTORY_EXCITATION_RECONCILIATION.md) explicitly
scopes the matrix out. This order performs it.

The question is narrow, and it is deliberately not *"how should the matrix
change?"*:

> Now that [the capability matrix](../ANALYZER_CAPABILITY_MATRIX.md) is
> authoritative on `main`, does it reconcile with the three capability states
> [DO-108P](DO-108P_COMMERCIAL_EXCITATION_OUTPUT_STAGE.md) deliberately recorded
> locally while the matrix was unavailable?

## Adjudication vocabulary

Local to this order. It is **not** a new repository provenance vocabulary and
nothing outside DO-108H should adopt it — the standing rule against inventing
competing vocabularies applies here as everywhere else.

| Disposition | Means |
| --- | --- |
| `RECONCILED_AS_WRITTEN` | Both documents say the same thing in the same terms |
| `RECONCILED_DIFFERENT_VOCABULARY` | Same substance, different words or different axis |
| `RECONCILED_DIFFERENT_SCOPE` | Both true, over different populations |
| `MATRIX_UPDATE_REQUIRED` | The matrix must change |
| `ARCHITECTURE_UPDATE_REQUIRED` | The architecture document must change |
| `CONFLICT` | The documents cannot both be true |

## Evidence read

Read-only, all on `main` at `27e92bd`:

- [`docs/ANALYZER_CAPABILITY_MATRIX.md`](../ANALYZER_CAPABILITY_MATRIX.md) — owned by `TTP-TECH-MANUAL-001`, Commit 1
- [`docs/hardware/TTP_COMMERCIAL_EXCITATION_ARCHITECTURE.md`](../hardware/TTP_COMMERCIAL_EXCITATION_ARCHITECTURE.md) — DO-108P
- commit `49c5997`, historical and unlanded
- the E1 [BOM](../hardware/TTP_E1_HARDWARE_BOM.md) and [ownership census](../hardware/TTP_E1_OWNERSHIP_CENSUS.md)

## Adjudication

### Proposition 1 — `controlled waveform emission = implemented`

**`RECONCILED_DIFFERENT_VOCABULARY`**

The matrix carries the capability with `IMPLEMENTED` maturity:

> `| Controlled excitation — stepped sweep | excitation/stepped_sweep.py | IMPLEMENTED | LIB | Observed | none |`

Substance agrees. The wording does not: the implemented capability is **waveform
emission**, and the matrix row calls it *controlled excitation*. Read in
isolation that row is imprecise. See the referred finding below.

### Proposition 2 — `controlled physical excitation = external physical transducer required`

**`RECONCILED_DIFFERENT_VOCABULARY`**

The matrix supplies this distinction on its **executability** axis rather than in
the maturity column:

> `| Controlled contact modal analysis | IMPLEMENTED | E1 shaker, stinger, force transducer, conditioner — all CONFIRMED_ABSENT, procurement HOLD | NO | Gap record only. No chapter. |`

and in the gap record:

> `required hardware:   absent (E1 chain, procurement on HOLD)`
> `executable workflow: NO`

Read as a whole the matrix does not claim the Analyzer can drive a plate on its
own. **The operational distinction is preserved; only its location differs.**
The matrix expresses it as *hardware disposition plus executability*; DO-108P
expresses it as a capability state. Neither is wrong, and the matrix's own
opening insists its four axes are independent — which is precisely why the
distinction can live on an axis other than maturity without being lost.

### Proposition 3 — `measured dynamic input force = absent from the commercial path`

**`RECONCILED_DIFFERENT_SCOPE`**

The matrix states the repository-wide position:

> **Absolute mobility is not claimed anywhere.** Transfer-function mathematics
> existing does not establish a calibrated force measurement chain, and no
> force measurement chain exists to calibrate.

DO-108P states a narrower one: force is absent **from the commercial path**,
which is a property of that architecture rather than of the repository. Both are
true at once, and the difference is population, not substance:

```text
repository-wide      no calibrated force measurement chain exists today
commercial path      no force channel exists by design, ever
reference E1 path    a force channel is specified, and is CONFIRMED_ABSENT
```

The commercial statement is the stronger of the two and survives even if the E1
reference chain is one day built and measures force. Recording this as plain
agreement would lose that, which is why the scope disposition exists.

## Disposition of `49c5997`

**`STILL_APPLICABLE — REFERRED, NOT CHERRY-PICKED`**

The commit renames the matrix's maturity rows from *"Controlled excitation"* to
*"Excitation waveform **emission**"* and adds a three-row table separating
emission, physical specimen excitation, and measured input force. That table maps
almost one-to-one onto DO-108P's three propositions, which is unsurprising —
both were written to prevent the same collapse.

Three separate judgments, and they do not travel together:

```text
the distinction it identified   STILL_APPLICABLE
the historical patch itself     NOT AUTHORIZED FOR CHERRY-PICK
the owner of its disposition    TTP-TECH-MANUAL-001
```

That a refinement remains semantically applicable does not establish that a
months-old diff should be applied to today's document. The matrix has changed
since; the patch was written against an earlier state; and the matrix is not this
order's to edit. **Reconciliation does not transfer ownership.**

## Findings referred to `TTP-TECH-MANUAL-001`

DO-108H makes no change to the matrix. It records one finding for its owner:

> **Matrix-side terminology finding.** The excitation maturity rows use
> *"Controlled excitation"* for a capability that is strictly waveform emission.
> Read with the executability axis the matrix is correct; read row-by-row the
> naming overstates. Commit `49c5997` proposes wording for exactly this and is
> available as historical evidence of an attempted refinement. Adopting it,
> rewriting it, or declining it is `TTP-TECH-MANUAL-001`'s decision.

This is a referral, not a defect report. Nothing on `main` currently asserts a
capability TTP does not have.

## Conclusion

> **No substantive capability-state conflict was found.** The merged matrix and
> the commercial-excitation architecture reconcile, with terminology and scope
> differences recorded. Historical commit `49c5997` identifies a still-applicable
> matrix-side terminology refinement and is referred to the matrix's owning work
> without modification or cherry-pick by DO-108H.

The architecture document's future-action promise is closed, with the historical
fact preserved: the matrix genuinely was unmerged when DO-108P was written, and
DO-108P's decision to record capability states locally was correct at the time
and remains correct now.

## Scope

**Changed:** this order record (created), and the promise paragraph in
[the commercial excitation architecture](../hardware/TTP_COMMERCIAL_EXCITATION_ARCHITECTURE.md)
(closed, chronology preserved).

**Deliberately not changed:** the capability matrix; commit `49c5997`; any
capability, hardware, ownership or selection state; DO-108P's three capability
lines, which the adjudication found correct as written; DO-108G; any runtime
code, checker, CI workflow, or schema.

**No new persistent invariant was created.** The reconciliation is a one-time
comparison against a document that has now landed. A permanent test asserting
that two prose documents agree would be a semantic judgment of exactly the kind
[the PR admission protocol](../TTP_PR_ADMISSION_PROTOCOL.md) forbids automating.

## Acceptance

| Criterion | State |
| --- | --- |
| All three propositions adjudicated with dispositions | met |
| `49c5997` dispositioned separately from its patch | met |
| Terminology finding recorded rather than suppressed | met |
| Matrix unmodified | met |
| Architecture promise closed with chronology preserved | met |
| No capability, hardware or ownership state changed | met |
| No new vocabulary escaping this order | met |
