# Namespace Policy (Scripts & Phases)

This repo is an **instrumentation toolchain**. We enforce phase isolation to preserve the integrity of the frozen v1.0 baseline.

## Core rule

**Experimental scripts must self-identify by filename prefix, not by folder layout.**

This keeps intent obvious in code review and makes CI enforcement stable over time.

## Approved experimental prefixes

Any script under `scripts/` starting with one of these prefixes is considered **Phase 2 Experimental**:

- `wolf_` — wolf-note / instability / localization metrics
- `ir_` — impulse response, deconvolution, time-gating, frequency response extraction
- `ods_` — operational deflection shapes (roving-grid, coherence/phase mapping)
- `exp_` — exploratory probes / research scratch (must remain measurement-only)

## Label requirements (CI enforced)

If a PR changes any file matching:

- `scripts/wolf_*`
- `scripts/ir_*`
- `scripts/ods_*`
- `scripts/exp_*`

then the PR **must** carry **both** labels:

- `phase2`
- `experimental`

Additionally, if a PR is labeled `experimental`, it **must** touch one of the paths above (prevents label drift).

## What is NOT experimental by default

Scripts that do not use the prefixes above are not automatically considered experimental. However:

- If the work is exploratory or not yet validated, it should use `exp_` (or a more specific experimental prefix).
- Phase 1 baseline code remains protected by the Phase Gate policy.

## Naming examples

Good:
- `scripts/ir_time_gated.py`
- `scripts/ods_roving_grid.py`
- `scripts/wolf_silver_metrics.py`
- `scripts/exp_modal_density_probe.py`

Avoid:
- `scripts/new_feature.py` (ambiguous intent)
- `scripts/test2.py` (no domain signal)

## Rationale

Prefix-based identification:
- survives folder refactors
- is easy to review in diffs
- is easy to enforce in CI
- prevents Phase 2 research work from silently contaminating the baseline
