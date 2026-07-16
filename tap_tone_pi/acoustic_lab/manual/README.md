# Laboratory Manual — canonical content

This directory is the **single authoritative home** of the Luthier Acoustics
Laboratory Manual. It is packaged with the TTP Analyzer and read at runtime
through `importlib.resources`, so it must remain importable package data — not
a documentation afterthought.

`docs/laboratory_manual/README.md` is a pointer to this directory. It is not a
second copy. Do not create one.

## Current state

The manifest registers **no entries**. A consolidated Laboratory Manual does
not yet exist as a canonical document, and DO-97 explicitly prohibits
fabricating one to populate the registry. The desktop viewer therefore shows a
controlled empty state.

This is the intended state, not an incomplete migration.

## Content authority

A document belongs here only when it is a laboratory *procedure, apparatus
description, limit specification, or measurement-context reference*.

The manual documents how measurements are performed. It does not execute them,
alter engineering results, or interpret tone quality. Content that interprets
results or prescribes design changes belongs downstream (see
`docs/MEASUREMENT_BOUNDARY.md`), not in this directory.

## Status vocabulary

Every registered entry declares exactly one status:

| Status | Meaning |
|---|---|
| `approved` | Validated procedure suitable for normal instrument use |
| `provisional` | Laboratory method under controlled evaluation |
| `deferred` | Documented concept not authorized for execution |
| `superseded` | Retained for lineage; not presented as a current procedure |

**Only `approved` entries may be presented as standard TTP measurement
methods.** Placing speculative, exploratory, or unvalidated procedures under
`approved` is prohibited. Promotion between statuses is a separate governed
action — no code path in this package promotes an entry automatically.

Avoid the words `best`, `optimal`, `proven`, and `recommended design` in manual
content. They assert a judgment the instrument does not make.

## Naming conventions

- Documents are Markdown (`.md`); Markdown is the canonical source format.
- Filenames are lowercase `snake_case`, ending in `.md`.
- Paths in the manifest are relative to this directory, use forward slashes,
  and may not contain `..` or a leading `/`.
- `doc_id` is a stable lowercase identifier that **must not change** when a
  document is retitled or moved. It is the handle callers store.
- `section` groups documents in the viewer's navigation.

## Revision requirements

- Every entry carries a `revision` string; bump it whenever the document's
  substance changes.
- Bump `manual_revision` on the manifest whenever entries are added, removed,
  or re-statused.
- When a document is replaced, set the old entry's status to `superseded` and
  point `superseded_by` at the replacement's `doc_id`. The manifest rejects a
  `superseded_by` that names an unregistered document.

## Registering a document

1. Add the Markdown file under this directory.
2. Add an entry to `manual_manifest.json` with a unique `doc_id`, its relative
   `path`, a `section`, an honest `status`, and a `revision`.
3. Bump `manual_revision`.
4. Run `pytest tests/test_laboratory_manual_registry.py`.

The registry validates identity, status, path safety, and file existence at
load time. A registered file that does not exist is a hard error, not a
warning — the manifest may not promise content the package does not ship.
