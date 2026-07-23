# tap_tone_pi — Instrumentation (Measurement-Only)

This repo is a **measurement instrument toolchain** for luthier lab work:
- Phase 1: single-mic tap tone capture + FFT peaks
- Phase 2: roving-grid 2-channel capture + ODS (transfer functions) + coherence + wolf metrics (WSI)
- Bending rig: bending stiffness measurements (EI / k) with defensible metadata

> **Boundary:** This project measures and summarizes signals. It does **not** interpret "tone quality"
> or prescribe structural modifications. See `docs/MEASUREMENT_BOUNDARY.md`.

---

## What this repo is (and is not)

### ✅ IS
- evidence capture (WAV + capture metadata)
- deterministic DSP summaries (FFT peaks, transfer function H(f), coherence γ²(f))
- robust bundle persistence (session folders, derived artifacts)
- schemas and validation contracts for outputs

### ❌ IS NOT
- "design optimizer"
- "tone grader"
- structural modification advisor
- ToolBox/RMOS backend (interop is export-only)

---

## Quickstart

### Install (Pi or desktop)
```bash
sudo apt-get update
sudo apt-get install -y portaudio19-dev python3-dev
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\Activate.ps1 on Windows
pip install -U pip
pip install -e .
```

---

## Phase 1 — Single-mic tap tone

List audio devices:
```bash
python -m tap_tone.main devices
```

Record + analyze:
```bash
python -m tap_tone.main record \
  --device 1 \
  --seconds 2.5 \
  --out ./captures/session_001 \
  --label "OM_top_bridge_tap"
```

Live mode (simple loop):
```bash
python -m tap_tone.main live --device 1 --out ./captures/live
```

### Outputs

Each capture produces:

* `audio.wav`
* `analysis.json` (peaks, dominant frequency, confidence)
* `spectrum.csv` (freq_hz, magnitude)
* `session.jsonl` (append-only log)

---

## Phase 2 — Roving-grid ODS + coherence + wolf metrics

### Canonical Phase 2 CLI

**Main executable:** `scripts/phase2_slice.py`
**Canonical package:** `scripts/phase2/`
**Canonical grid:** `config/grids/guitar_top_35pt.json`

```bash
python scripts/phase2_slice.py --help
```

### Typical run directory

```
runs_phase2/
  session_YYYYMMDDTHHMMSSZ/
    grid.json
    metadata.json
    points/
      point_A1/
        audio.wav
        capture_meta.json
        analysis.json
        spectrum.csv
    derived/
      ods_snapshot.json
      wolf_candidates.json
      wsi_curve.csv
    plots/
      *.png
```

### Common workflow

```bash
# Synthetic validation (no hardware)
python scripts/phase2_slice.py run \
  --grid examples/phase2_grid_mm.json \
  --out ./runs_phase2 \
  --synthetic

# Hardware capture
python scripts/phase2_slice.py devices
python scripts/phase2_slice.py run \
  --grid config/grids/guitar_top_35pt.json \
  --out ./runs_phase2 \
  --device 1
```

See `docs/phase2/README.md` for full documentation.

---

## Bending rig workflow

Bending stiffness measurements are documented in `docs/MEASUREMENT_README.md`.

### Simulated demo (no hardware)

```bash
make sim-load OUT=out/DEMO/load_series.json SIM_AMP_F=12 SIM_BASE_F=0.5 SEED=1337
make sim-dial OUT=out/DEMO/displacement_series.json SIM_AMP_D=0.8 SEED=1337

make bend-merge-moe LOAD=out/DEMO/load_series.json DISP=out/DEMO/displacement_series.json \
  OUTDIR=out/DEMO/rig METHOD=3point SPAN=400 WIDTH=20 THICKNESS=3.0

make plot-fvd PAIRS=out/DEMO/rig/pairs.csv OUT=out/DEMO/rig/f_vs_d.png
```

---

## Validation & Contracts

Machine-readable output contracts live in `contracts/`.

Key Phase 2 schemas:
* `contracts/phase2_grid.schema.json`
* `contracts/phase2_session_meta.schema.json`
* `contracts/phase2_point_capture_meta.schema.json`
* `contracts/phase2_ods_snapshot.schema.json`
* `contracts/phase2_wolf_candidates.schema.json`

---

## Policies / governance

* Measurement boundary: `docs/MEASUREMENT_BOUNDARY.md`
* Agent guidance: `.github/copilot-instructions.md`
* ADR trail: `docs/ADR-0001-measurement-scope.md` … `docs/ADR-0007_PHASE2_ODS_COHERENCE.md`

---

## Failure playbook (Analyzer)

1. **Schema validation fails**
   - Run: `make validate-schemas` (or `python scripts/validate_schemas.py --out-root out`)
   - Read the error paths/messages and fix the offending JSON producer.

2. **Chladni tolerance exceeded**
   - The run fails if worst `delta_hz` > `CHLADNI_FREQ_TOLERANCE_HZ` (default 5 Hz).
   - Re-check your excitation, mounting, or set a stricter/looser env value explicitly.

3. **WAV guard trips in CI**
   - Direct `scipy.io.wavfile` usage is blocked outside `modes/_shared/wav_io.py`.
   - Import `read_wav_mono/2ch` or `write_wav_mono/2ch` from that module instead.

4. **Viewer pack export fails**
   - Check `validation_report.json` for specific rule violations.
   - Common issues: missing manifest, frequency grid mismatch, peak off-grid.

---

## Laboratory Manual (desktop)

Laboratory Manual resources are packaged in the `tap_tone_pi` distribution: a
versioned, read-only, offline registry of laboratory procedure documents (no
network access required). The desktop viewer currently runs from the existing
desktop application environment, opened via **Help → Laboratory Manual**; full
`analyzer/` installer packaging is a separate task.

Each registered procedure carries a maturity label
(`approved` / `provisional` / `deferred` / `superseded`) so validated methods
are never confused with exploratory ones. The manifest currently ships **empty**
by design — no consolidated manual document exists yet — so the viewer shows a
controlled empty state. Invalid or unavailable manual resources likewise produce
distinct, controlled states rather than crashing the viewer. The manual documents
procedures; it does not execute or interpret measurements.

---

## HTTP API server

An optional FastAPI server exposes read-only listing/detail endpoints (`/grids`,
`/sessions`, `/sessions/{id}`, `/export/{id}`) plus health/info.

### Starting the server

The `--data-root` flag lives on the `ttp server` wrapper. If you launch uvicorn
directly, the flag does **not** apply — configure the root via the
`TTP_SERVER_DATA_ROOT` environment variable instead:

```bash
# ttp wrapper (recommended): --data-root is honored
ttp server --host 0.0.0.0 --port 8000                      # root defaults to cwd
ttp server --data-root /srv/tap-tone-data                  # authorize a specific root

# direct uvicorn: --data-root does NOT exist here; set the env var explicitly
TTP_SERVER_DATA_ROOT=/srv/tap-tone-data uvicorn tap_tone_pi.server.app:app
uvicorn tap_tone_pi.server.app:app                         # root = cwd (no confinement to a mounted dir)
```

Under the `ttp server` wrapper, `--data-root` is bridged to the launched app via
`TTP_SERVER_DATA_ROOT` (required so `--reload`'s re-imported process sees it).

### Data-root authorization

The file-backed endpoints accept a `directory` query parameter, and every
supplied path — **relative or absolute** — must resolve **beneath the configured
data root**. Resolution precedence:

1. `create_app(data_root=...)` (programmatic / tests);
2. `--data-root` → `TTP_SERVER_DATA_ROOT` environment variable;
3. `Path.cwd()` (default when nothing is configured).

Containment is a true path-component check applied **after** resolving the path,
so the following are rejected with **HTTP 400**:

- relative `..` traversal that escapes the root (`../../etc`);
- an absolute path outside the root (`/etc`, `/home/other`);
- a sibling directory that merely shares the root's name prefix
  (`/srv/app` vs `/srv/app_evil`);
- a symlink beneath the root whose target resolves outside it.

Paths that resolve beneath the root — including absolute paths under it and
`..` segments that normalize back inside — are accepted. A configured root that
does not exist fails at server startup rather than silently falling back to the
working directory. Relative request paths are interpreted **relative to the
configured data root**, not the process launch directory. A leading `~` in a
request path is **not** expanded (only the server-configured root expands `~`).

For example, with `--data-root /srv/tap-tone-data`:

```text
/srv/tap-tone-data/runs/session-001   ALLOWED
runs/session-001                      ALLOWED  (relative to the data root)
/etc                                  REJECTED (HTTP 400)
../private                            REJECTED (HTTP 400)
```

**Compatibility note:** before this boundary existed, absolute `directory` values
were accepted as-is. They are now rejected unless they resolve beneath the
configured root — point clients at directories under `--data-root` (or widen the
root) if they previously passed absolute paths elsewhere.

**Scope.** This boundary confines filesystem *reads* of the `directory` parameter
across `/grids`, `/sessions`, `/sessions/{id}`, and `/export/{id}`; it is not an
authentication or per-user permission system. The export endpoints' `output_dir`
is a *write* target and is deliberately **not** confined to the data root (write
authorization is a separate concern) — treat it as trusted-operator input.

### Authorization diagnostics

The authorization layer is observable without exposing any host path.

`GET /server/status` returns policy metadata only:

```json
{
  "policy_version": "filesystem-auth-v2",
  "configured": true,
  "root_digest": "3f9a1c0b7e42",
  "started_at": "2026-07-22T18:20:29.123456+00:00"
}
```

- `configured` — `true` when the root came from `--data-root`/`TTP_SERVER_DATA_ROOT`,
  `false` when it defaulted to cwd (it does not reveal which source). Captured
  once at app creation; `/server/status` reflects that startup state, not the
  current environment.
- `root_digest` — a one-way `sha256(canonical_root)[:12]` digest, **never** the
  path. It is derived from the *canonical resolved* root, so differently-spelled
  equivalents (`.`, `./data`, `foo/../data`) share one digest. It fingerprints a
  path, not a logical environment: the same service on a different mount produces
  a different digest — use it to correlate events with a running instance, not as
  a durable cross-deploy environment id.

Both request-time authorization decisions **and** the startup root validation
emit a structured event on the `tap_tone_pi.server.authz` logger (configure a
handler to collect them):

- **allowed** → `DEBUG`; **rejected** (`OUTSIDE_ROOT`, `SYMLINK_ESCAPE`) →
  `WARNING`; **startup invalid root** (`INVALID_ROOT`, emitted by `create_app`
  before the `ValueError`, not a per-request decision) and **resolution failure**
  (`PATH_RESOLUTION_FAILURE`) → `ERROR`.
- Reason codes are stable: `OUTSIDE_ROOT` (absolute/`..` escape), `SYMLINK_ESCAPE`
  (lexically in-root but resolves out), `INVALID_ROOT`, `PATH_RESOLUTION_FAILURE`.
- Events carry only: endpoint, input role, path type (relative/absolute), result,
  reason code, policy version, and the root digest — **no** requested/resolved/root
  paths and no exception text (only an exception *class* name when relevant).

Diagnostics are observability only; they do not change any authorization decision.
`PATH_RESOLUTION_FAILURE` deliberately preserves the original exception (it does
not convert it to a sanitized 4xx), so a filesystem/permission error surfaces as
a 500 — the event records it without leaking the path.

---

## Run IDs & retention

- Use `from modes._shared.run_id import new_run_dir` to create timestamped run folders,
  e.g., `out/2026-01-20T17-22-31Z_ab12cd/`.
- Add a brief retention/backup policy as needed (e.g., sync `out/**` to S3 with SHA256).

---

## Contributing

See `CONTRIBUTING.md`.
