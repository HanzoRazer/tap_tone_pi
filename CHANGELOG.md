# Changelog

All notable changes to this project are documented here. This file follows [Keep a Changelog](https://keepachangelog.com/) style and [Semantic Versioning](https://semver.org/).

## [1.0.0-rc1] — 2026-01-18

### Added
- **Schema Registry** at `contracts/schema_registry.json` and **contracts** for:
  - `tap_peaks`, `moe_result`, `measurement_manifest`, `chladni_run`
  - Phase-2: `phase2_ods_snapshot`, `phase2_wolf_candidates`
- **Registry-driven validator**: `scripts/validate_schemas.py` (consumes registry; no hardcoded maps).
- **Hardware-free demos**:
  - **Chladni v1**: `examples/chladni/` (WAV → peaks → image index → `chladni_run.json`) + manifest append.
  - **Phase-2 mini**: `examples/phase2/` with canonical filenames under `runs_phase2/DEMO/session_0001/`.
  - **MOE**: `examples/moe/` producing a valid `moe_result.json`.
- **Canonical WAV I/O**: `modes/_shared/wav_io.py` (float32 in ±1, PCM16 out).
- **Chladni mismatch policy**: warn+keep with `delta_hz`; **fail** if worst `delta_hz` exceeds `CHLADNI_FREQ_TOLERANCE_HZ` (default 5 Hz).
- **Run-level manifest append** for Chladni: `modes/chladni/manifest_utils.py` (idempotent).
- **Local CI dry run**: `make ci-dry-run` (tests → coverage → demos → schema validation).
- **Pre-export validator**: `tap_tone/validate/viewer_pack_v1.py` for staged directory validation.

### Changed
- All readers/writers route through canonical WAV I/O; removed ad-hoc `/32767` scaling.
- Docs: Governance and Measurement README updated with policy, demos, and local CI instructions.

### CI / Quality Gates
- **pytest** + **coverage ≥ 80%** (merge-blocking).
- **WAV I/O guard**: disallow `scipy.io.wavfile` outside `modes/_shared/wav_io.py`.
- **Schema-bump guard**: changes to `contracts/schemas/*.schema.json` must bump versions in the registry.
- **PR title linter** for schema edits (`schema: …` prefix).
- **Schema validation** in CI for `out/**` and Phase-2 demo.
- **CODEOWNERS** for `contracts/**` and `modes/_shared/**`.

### Tests
- Chladni policy unit tests (warn vs fail).
- Manifest test asserts expected entries + SHA-256 hashes and idempotency.
- Pre-export validator tests (15 rules across M/S/P/W/A/O categories).

### Notes
- This release is **Analyzer-only** ("facts, not opinions"). Design/CAM interpretation remains out-of-scope.

[1.0.0-rc1]: https://github.com/HanzoRazer/tap_tone_pi/releases/tag/analyzer-v1.0.0-rc1
