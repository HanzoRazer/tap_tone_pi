# Laboratory Manual — pointer

**The Laboratory Manual is not stored here.** Its canonical, authoritative
location is:

```text
tap_tone_pi/acoustic_lab/manual/
```

This file is a pointer and a governance note. It is deliberately not a second
copy of the manual, and one must not be created here — two authoritative copies
would drift, and the packaged copy is the one the instrument actually reads.

## Why the manual lives inside the package

The Laboratory Manual is an operational component of the TTP Analyzer desktop
instrument, not external documentation. It must be readable offline from an
installed build, which means it has to ship as package data resolvable through
`importlib.resources`. Content under `docs/` sits outside every packaged root
and cannot satisfy that requirement.

Keeping the authored source inside the package gives one copy that is
simultaneously the thing authors edit and the thing the installed application
reads. There is no build-time sync step and no source-tree fallback.

## Where to go

| You want to... | Go to |
|---|---|
| Read the authoring and status rules | `tap_tone_pi/acoustic_lab/manual/README.md` |
| See registered documents | `tap_tone_pi/acoustic_lab/manual/manual_manifest.json` |
| Add or revise a procedure | `tap_tone_pi/acoustic_lab/manual/` |
| Read the manual as an operator | TTP Analyzer → **Help → Laboratory Manual** |
| Understand the measurement boundary | `docs/MEASUREMENT_BOUNDARY.md` |

## Contribution rules in brief

The full rules live in the canonical README. The three that matter most:

1. **Only `approved` entries may be presented as standard TTP measurement
   methods.** Speculative or exploratory procedures are `provisional` or
   `deferred` — never `approved`.
2. **Promotion is a separate governed action.** No code path promotes an entry
   automatically, and status is visible in the desktop viewer so an operator can
   always see what they are reading.
3. **The manual documents procedures; it does not execute or interpret them.**
   Interpretation and design guidance belong downstream of this repository.

## Current state

No procedures are registered yet. A consolidated Laboratory Manual does not
exist as a canonical document, and DO-97 prohibited fabricating one to populate
the registry. The desktop viewer shows a controlled empty state until real
content is authored and classified.
