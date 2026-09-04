# DO-108G — Gap Inventory Reconciliation: Commercial Excitation

## Status

**QUEUED — NOT STARTED.** Raised by DO-108P review; deliberately not folded into
DO-108P's commits.

## Why this is its own order

[`docs/01_GAP_INVENTORY.md`](../../01_GAP_INVENTORY.md) is the repository
authority for shipped-versus-missing capability — CLAUDE.md says to trust it over
memory or training data. DO-108P made one of its entries stale, and editing a
repository-wide authority as a side effect of a hardware-architecture order is
exactly the kind of quiet scope expansion that makes such an authority
untrustworthy. So the change is recorded here and made deliberately, by someone
who has looked at the whole document rather than at one row of it.

## The stale entry

`§7 — Hardware (DESIGN-ONLY)`, row 7.3, written 2026-05-01:

```text
| 7.3 | TTP Analyzer (driven excitation hardware) | DESIGN-ONLY |
      Signal-gen software ready; transducer/amp/mic hardware not built |
```

That was accurate when written and is now imprecise in both directions. It
understates what exists — the excitation contracts, provenance records and
amplitude guardrails in `tap_tone_pi/excitation/` go well beyond "signal-gen
software ready", and there is now a defined commercial architecture with
registered, datasheet-backed candidate hardware. And it flattens what is
missing, since "hardware not built" does not distinguish a chain nobody has
specified from one specified and awaiting a bench.

## The gap statement to record

> **Commercial controlled physical excitation is architecturally defined and
> candidate hardware is registered, but no commercial excitation chain has been
> assembled or bench-qualified.**

That is the useful form. It tells a reader what not to rebuild, and it names the
one thing that would change the status: a bench.

## Scope

1. Update `§7` row 7.3 to the gap statement above, pointing at
   [the commercial excitation architecture](../../hardware/TTP_COMMERCIAL_EXCITATION_ARCHITECTURE.md),
   the `COMMERCIAL_PROTOTYPE` tier in
   [the E1 BOM](../../hardware/TTP_E1_HARDWARE_BOM.md), and
   [the characterization protocol](../../hardware/TTP_EXCITER_POWER_CHARACTERIZATION_PROTOCOL.md).
2. Decide whether `DESIGN-ONLY` still fits, or whether §7 needs a state for
   "specified and candidate-registered, awaiting bench qualification". Prefer
   adding a state over stretching an existing one — the repository's standing
   rule is that a new distinction gets an axis or a value, not a re-used rung.
3. Check the rest of the document for entries DO-103 through DO-108P have made
   stale. Row 7.3 is the one review caught; it is unlikely to be the only one in
   a file dated 2026-05-01. **Report what is stale; do not fix beyond §7 in this
   order** without a further ruling.
4. Leave every other status alone. This order records a gap more precisely; it
   promotes nothing.

## Out of scope

Editing capability status anywhere else; touching the E1 hardware documents;
`ANALYZER_CAPABILITY_MATRIX.md`, which belongs to unmerged technical-manual work;
any claim that the commercial chain works.

## Acceptance

- Row 7.3 states the gap in terms of what exists and what is missing, and names
  the bench as the thing that would change it.
- No capability is promoted, and no status elsewhere in the document moves.
- A list of any other stale entries found, reported rather than silently
  corrected.
