# SPRINTS.md — Backlog & Deferred Maintenance

A durable, lightweight backlog for **deferred work and maintenance** surfaced
during other tasks — the things that would otherwise evaporate as "noted as a
follow-up" in a review thread or chat. If it should be revisited but isn't being
done now, it goes here so it survives past the PR that surfaced it.

This is intentionally low-ceremony. When an item grows into real scoped work it
graduates to a dev order (`docs/dev_orders/`); until then it lives here.

---

## What belongs here (and what doesn't)

| Kind of thing | Where it goes | Why |
|---|---|---|
| Deferred **work** — a test gap, a maintenance chore, a conditional feature | **This file** | Real to-dos that aren't scheduled yet |
| A scoped, active development effort | `docs/dev_orders/` (+ `CURRENT.md`) | Has acceptance criteria and a sprint |
| An architectural **decision or property** ("this is how/why it works") | `docs/ADR-NNNN-*.md` or code/README | Not a to-do; documenting it as one is false backlog noise |
| An accepted **tradeoff** already documented in code/README | Leave it documented | Same — not open work |

Rule of thumb: if the honest description is *"someone should do X later,"* it
belongs here. If it's *"X works this way on purpose,"* it belongs in an ADR or a
docstring, **not** here.

---

## How to use

- **Add** an item with the next `B-NNN` id, a one-line summary, its origin, a
  category, a rough priority, and enough context to action it later (including
  any **trigger** that would make it worth doing).
- **Update** status as it moves: `open` → `in-progress` (link the dev order/PR)
  → `done` (link the merge) or `wontfix` (say why).
- **Graduate** anything substantial into a dev order and link it here rather than
  implementing straight from a backlog line.
- Keep design *decisions/properties* out — link the ADR/doc instead.

**Status:** `open` · `in-progress` · `done` · `wontfix`
**Priority:** `P1` (do soon) · `P2` (opportunistic) · `P3` (only if triggered)

---

## Backlog

### B-001 — Windows-specific server path-containment tests
- **Status:** open · **Priority:** P3 (triggered) · **Area:** `tap_tone_pi/server`
- **Origin:** PR #11 review (DO-98 data-root authorization).
- **Context:** `_safe_directory` containment relies on `Path.resolve()` +
  `is_relative_to`, which is platform-sound (different drives → not relative →
  HTTP 400), and CI runs on Ubuntu. There is no explicit coverage for
  Windows-only path shapes: drive-letter differences, UNC paths
  (`\\server\share`), case-insensitive comparisons, and junctions/reparse points.
- **Trigger:** promote to P1 and add tests if Windows becomes a **supported
  server deployment target** (not merely a dev environment).
- **Acceptance:** parametrized tests asserting containment/rejection for
  cross-drive, UNC, mixed-case, and junction-escape cases, guarded so they skip
  cleanly on non-Windows runners.

### B-002 — Export `output_dir` write-target authorization
- **Status:** open · **Priority:** P2 · **Area:** `tap_tone_pi/server`
- **Origin:** PR #11 review (DO-98). DO-98 governs **read** authorization only;
  filesystem-write authorization was explicitly out of scope
  (see the DO-98 note in `docs/dev_orders/CURRENT.md`).
- **Context:** `/export/{id}` takes an `output_dir` write target that is
  intentionally **not** confined to the data root (documented in README under
  "HTTP API server"). For untrusted callers this is a write-traversal surface;
  it is currently treated as trusted-operator input.
- **Decision needed:** whether writes should be confined to the data root, to a
  separate configurable **export root**, or remain unconstrained-by-design.
- **Acceptance:** an explicit, documented write-authorization policy plus tests
  for the chosen behavior — or a recorded decision to leave it unconstrained.

---

## Not backlog — recorded here only so they aren't mistaken for open items

These are **design properties / accepted tradeoffs**, documented in code/README;
they are not to-dos.

- **`resolve()`-based containment is filesystem-dependent.** Checking containment
  *after* resolving is exactly what defeats symlink escapes; the consequence
  (outcomes depend on live filesystem layout) is inherent and intended.
  Documented in `_safe_directory` and README.
- **CLI `--data-root` bridges through a process-global env var
  (`TTP_SERVER_DATA_ROOT`).** Required so `uvicorn --reload`'s re-imported app
  sees the configured root; mutation is scoped to the run and restored after, and
  bounded by CLI env-restore tests. Accepted design (DO-98).
