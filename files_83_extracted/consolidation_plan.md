# tap-tone-pi Consolidation Plan: Untangling the Spaghetti

**Date:** 2026-02-05
**Scope:** Resolve duplicate packages, unclear boundaries, and missing UX shortcuts
**Risk if ignored:** Bugs from WAV I/O divergence; contributor confusion; user friction

---

## 1. The Forensic Findings

### 1.1 Four code locations do overlapping work

```
tap_tone/               634 LOC   Phase 1 installable package (pip install -e .)
tap-tone-lab/tap_tone/  982 LOC   Evolved fork of above (v0.3.2, ahead of root)
modes/                 1812 LOC   Measurement entry points (hardware + capture)
scripts/phase2/        1461 LOC   Phase 2 pipeline (DSP, metrics, viz)
```

### 1.2 Three places that capture/analyze tap tones

| Location | What it does | WAV I/O method |
|----------|-------------|----------------|
| `tap_tone/main.py` | CLI record + analyze | `modes._shared.wav_io.write_wav_mono` ✅ |
| `tap-tone-lab/tap_tone/_cli_core.py` | Nearly identical CLI | `scipy.io.wavfile` directly ❌ |
| `modes/tap_tone/tap_fft_logger.py` | Standalone FFT logger | `modes._shared.wav_io.read_wav_mono` ✅ |

**The WAV I/O divergence is a ticking time bomb.** The `tap-tone-lab` storage.py
bypasses the canonical WAV I/O layer, violating the project's own policy declared in
`modes/_shared/wav_io.py` line 12:

> *"Any direct usage of scipy.io.wavfile.read/write outside this module should be treated as a bug."*

### 1.3 Two competing pyproject.toml files

| File | Package name | Version | Entrypoint |
|------|-------------|---------|------------|
| `/pyproject.toml` | `tap-tone-pi` | 0.1.0 | `tap-tone = tap_tone.main:main` |
| `/tap-tone-lab/pyproject.toml` | `tap-tone-lab` | 0.3.2 | `tap-tone = tap_tone.cli:main` |

Both register the **same CLI command** (`tap-tone`) but from different packages.
Installing both is a silent conflict.

### 1.4 The GUI bypasses both packages

`gui/app.py` imports **nothing** from `tap_tone/` or `tap-tone-lab/`. It shells out
to `modes/` scripts via `subprocess.check_call()`:

```python
cmd = f"python modes/tap_tone/offline_from_wav.py --wav ..."   # modes/, not tap_tone/
cmd = f"python modes/chladni/peaks_from_wav.py --wav ..."       # modes/
cmd = f"python modes/bending_stiffness/deflection_to_moe.py ..." # modes/
```

So there are effectively **three parallel entry paths** into the same functionality:
the installable CLI, the GUI, and direct script invocation — each wired to a different
code location.

### 1.5 The modes/ vs scripts/phase2/ distinction

This is governed by GOVERNANCE.md and is architecturally sound:

```
modes/          → capture entry points (hardware I/O, single-point)
scripts/phase2/ → pipelines (multi-point aggregation, DSP, metrics)
```

**The problem isn't the architecture — it's that users don't know it.** There's no
discoverable way to understand which to run without reading governance docs.

---

## 2. Root Cause

The duplication happened organically:

1. `tap_tone/` was created as the original Phase 1 skeleton
2. `modes/` was added for the measurement boundary (hardware entry points)
3. `tap-tone-lab/` was born as a "clean rewrite" of `tap_tone/` with extras
   (exporter.py, cli.py, RMOS integration) — but the root was never deleted
4. Nobody merged back, so both diverged with cosmetic + real differences

---

## 3. The Consolidation Plan

### 3.1 Target layout (one canonical package)

```
tap_tone_pi/                      ← single installable package
├── __init__.py                   ← version = "1.1.0"
├── core/                         ← pure analysis (no I/O, no hardware)
│   ├── __init__.py
│   ├── analysis.py               ← from tap-tone-lab (has better type hints)
│   ├── config.py
│   └── dsp.py                    ← promoted from scripts/phase2/dsp.py
├── capture/                      ← hardware I/O (wraps sounddevice, serial)
│   ├── __init__.py
│   ├── audio.py                  ← from tap_tone/capture.py
│   ├── loadcell.py               ← from modes/acquisition/loadcell_serial.py
│   ├── dial_indicator.py         ← from modes/acquisition/dial_indicator_serial.py
│   └── simulators.py             ← merged from modes/acquisition/*_sim.py
├── io/                           ← all file I/O (the ONE place for WAV/JSON/CSV)
│   ├── __init__.py
│   ├── wav.py                    ← from modes/_shared/wav_io.py (canonical)
│   ├── storage.py                ← from tap-tone-lab/storage.py (fixed to use wav.py)
│   └── manifest.py               ← from modes/_shared/manifest.py
├── phase1/                       ← Phase 1 workflow
│   ├── __init__.py
│   └── tap_fft.py                ← merged: tap_fft_logger.py + offline_from_wav.py
├── phase2/                       ← Phase 2 workflow (promoted from scripts/phase2/)
│   ├── __init__.py
│   ├── grid.py
│   ├── metrics.py
│   ├── pipeline.py               ← from phase2_slice.py (the vertical slice)
│   └── viz.py
├── bending/                      ← Bending rig workflow
│   ├── __init__.py
│   ├── deflection_to_moe.py
│   └── merge_and_moe.py
├── chladni/                      ← Chladni workflow
│   ├── __init__.py
│   ├── peaks_from_wav.py
│   └── index_patterns.py
├── export/                       ← Bundle export + RMOS integration
│   ├── __init__.py
│   ├── viewer_pack.py            ← from scripts/export/
│   └── exporter.py               ← from tap-tone-lab/exporter.py
├── cli/                          ← ALL CLI entrypoints
│   ├── __init__.py
│   ├── main.py                   ← unified dispatcher
│   ├── phase1_cmds.py
│   ├── phase2_cmds.py
│   └── bending_cmds.py
└── gui/                          ← GUI (imports from package, no subprocess)
    ├── __init__.py
    └── app.py
```

### 3.2 What gets deleted

| Path | Action | Reason |
|------|--------|--------|
| `tap_tone/` (root) | **DELETE** | Superseded by `tap_tone_pi/` |
| `tap-tone-lab/` | **DELETE** | Merged into `tap_tone_pi/`; exporter.py promoted |
| `modes/tap_tone/` | **DELETE** | Merged into `tap_tone_pi/phase1/` |
| `modes/acquisition/` | **DELETE** | Merged into `tap_tone_pi/capture/` |
| `modes/bending_stiffness/` | **DELETE** | Merged into `tap_tone_pi/bending/` |
| `modes/bending_rig/` | **DELETE** | Merged into `tap_tone_pi/bending/` |
| `modes/chladni/` | **DELETE** | Merged into `tap_tone_pi/chladni/` |
| `modes/_shared/` | **DELETE** | `wav_io.py` → `tap_tone_pi/io/wav.py` |
| `modes/provenance_import/` | **DELETE** | Merged into `tap_tone_pi/io/manifest.py` |

### 3.3 What gets kept (unchanged)

| Path | Reason |
|------|--------|
| `contracts/` | Schema contracts are stable and correct |
| `schemas/` | Measurement schemas are referenced by tests |
| `config/` | Device and grid configs are data, not code |
| `docs/` | ADRs and governance docs remain valid |
| `tests/` | Migrated to import from `tap_tone_pi.*` |
| `scripts/` | Becomes thin wrappers calling `tap_tone_pi.cli` |

---

## 4. Migration Steps (ordered)

### Step 1: Create package skeleton (30 min)

```bash
mkdir -p tap_tone_pi/{core,capture,io,phase1,phase2,bending,chladni,export,cli,gui}
touch tap_tone_pi/__init__.py
touch tap_tone_pi/{core,capture,io,phase1,phase2,bending,chladni,export,cli,gui}/__init__.py
```

### Step 2: Move canonical WAV I/O first (15 min)

```bash
cp modes/_shared/wav_io.py tap_tone_pi/io/wav.py
```

This is the **foundation** — everything else imports from here. Zero logic changes needed.

### Step 3: Move core analysis (30 min)

Take `tap-tone-lab/tap_tone/analysis.py` (the better version) and fix its import:

```python
# tap_tone_pi/core/analysis.py
# Identical to tap-tone-lab version — it has better type hints and docstrings
```

Take `tap-tone-lab/tap_tone/config.py` as-is.

### Step 4: Move Phase 2 DSP into core (15 min)

```bash
cp scripts/phase2/dsp.py tap_tone_pi/core/dsp.py
cp scripts/phase2/metrics.py tap_tone_pi/phase2/metrics.py
cp scripts/phase2/grid.py tap_tone_pi/phase2/grid.py
cp scripts/phase2/viz.py tap_tone_pi/phase2/viz.py
```

Update imports: `from scripts.phase2.dsp import ...` → `from tap_tone_pi.core.dsp import ...`

### Step 5: Fix storage.py to use canonical WAV I/O (15 min)

In the migrated storage.py, replace:

```python
# BEFORE (tap-tone-lab version — policy violation)
from scipy.io import wavfile
wavfile.write(str(audio_path), sample_rate, x_i16)

# AFTER
from tap_tone_pi.io.wav import write_wav_mono
write_wav_mono(audio_path, audio, sample_rate)
```

### Step 6: Move hardware capture modules (30 min)

```bash
cp modes/acquisition/loadcell_serial.py tap_tone_pi/capture/loadcell.py
cp modes/acquisition/dial_indicator_serial.py tap_tone_pi/capture/dial_indicator.py
# merge *_sim.py into simulators.py
```

### Step 7: Rewrite GUI to import instead of subprocess (1-2 hours)

Replace:
```python
# BEFORE
cmd = f"python modes/tap_tone/offline_from_wav.py --wav {path} ..."
subprocess.check_call(shlex.split(cmd))

# AFTER
from tap_tone_pi.phase1.tap_fft import analyze_wav_file
result = analyze_wav_file(path, labels=["A0", "T11", "B11"])
```

This eliminates the PYTHONPATH fragility and gives proper error handling.

### Step 8: Build unified CLI dispatcher (1 hour)

```python
# tap_tone_pi/cli/main.py
import argparse

def build_parser():
    p = argparse.ArgumentParser(prog="ttp", description="Tap Tone Pi — Luthier Measurement Toolkit")
    sub = p.add_subparsers(dest="cmd")

    # Phase 1
    sub.add_parser("devices", help="List audio devices")
    sub.add_parser("record", help="Single tap capture + analysis")
    sub.add_parser("live", help="Continuous capture loop")
    sub.add_parser("analyze-wav", help="Offline WAV analysis")

    # Phase 2
    sub.add_parser("phase2", help="Roving grid ODS capture")

    # Bending
    sub.add_parser("bend", help="Bending stiffness measurement")

    # Utilities
    sub.add_parser("last", help="Open most recent session")        # NEW
    sub.add_parser("sessions", help="List all sessions")           # NEW
    sub.add_parser("export", help="Export bundle for ToolBox")
    sub.add_parser("gui", help="Launch GUI")

    return p
```

### Step 9: Update pyproject.toml (15 min)

```toml
[project]
name = "tap-tone-pi"
version = "1.1.0"

[project.scripts]
ttp = "tap_tone_pi.cli.main:main"           # short command
tap-tone = "tap_tone_pi.cli.main:main"      # backward compat
tap-tone-export = "tap_tone_pi.export.exporter:main"
```

### Step 10: Delete old locations + add deprecation stubs (30 min)

Replace `tap_tone/__init__.py` with:

```python
import warnings
warnings.warn(
    "tap_tone is deprecated. Use tap_tone_pi instead. "
    "See docs/MIGRATION.md for details.",
    DeprecationWarning, stacklevel=2
)
from tap_tone_pi.core.analysis import *  # noqa: temporary shim
```

Remove after one release cycle.

### Step 11: Update CI boundary guards (15 min)

Update `ci/check_boundary_imports.py` and `no_logic_creep.yml` to reference
`tap_tone_pi` namespace. Update `wav-io-guard.yml` to enforce the new canonical
path.

### Step 12: Run full test suite against new layout (30 min)

```bash
pytest tests/ -v
make phase2-full GRID=examples/phase2_grid_mm.json --synthetic
```

---

## 5. Solving the UX Shortcuts

### 5.1 "Last session" command

```python
# tap_tone_pi/cli/main.py

def cmd_last(args):
    """Open / print the most recent session directory."""
    from pathlib import Path
    import os

    roots = [Path("out"), Path("runs_phase2")]
    sessions = []
    for root in roots:
        if root.exists():
            for d in root.iterdir():
                if d.is_dir() and d.name.startswith(("session_", "bend_", "capture_")):
                    sessions.append(d)

    if not sessions:
        print("No sessions found.")
        return 1

    latest = max(sessions, key=lambda p: p.stat().st_mtime)
    print(f"Latest session: {latest}")
    print(f"  Modified: {datetime.fromtimestamp(latest.stat().st_mtime)}")

    # List contents
    for f in sorted(latest.rglob("*")):
        if f.is_file():
            rel = f.relative_to(latest)
            size = f.stat().st_size
            print(f"  {rel}  ({size:,} bytes)")

    if args.open:
        if sys.platform == "darwin":
            os.system(f"open '{latest}'")
        elif sys.platform == "win32":
            os.startfile(str(latest))
        else:
            os.system(f"xdg-open '{latest}'")

    return 0
```

Usage:
```bash
ttp last           # print latest session path + contents
ttp last --open    # open in file manager
```

### 5.2 Session listing with human-readable output

```bash
$ ttp sessions

   #  Type      Date                 Points  Coherence   Path
   1  phase2    2026-01-15 14:22     35/35   γ²=0.89     runs_phase2/session_20260115T142200Z/
   2  bend      2026-01-14 09:15     —       —           out/bend_20260114T091500Z/
   3  tap       2026-01-13 16:40     —       —           out/20260113_164000/
```

### 5.3 Tab completion

```bash
# tap_tone_pi/cli/completion.py

def generate_bash_completion():
    return '''
_ttp_completions() {
    local commands="devices record live analyze-wav phase2 bend last sessions export gui"
    COMPREPLY=($(compgen -W "$commands" -- "${COMP_WORDS[COMP_CWORD]}"))
}
complete -F _ttp_completions ttp
'''
```

Install with: `eval "$(ttp --completion bash)"`

---

## 6. Verification Checklist

After consolidation, every one of these must pass:

- [ ] `pip install -e .` works from repo root
- [ ] `ttp devices` lists audio devices
- [ ] `ttp record --device 0 --out /tmp/test --seconds 1` captures
- [ ] `ttp last` finds the capture just made
- [ ] `ttp phase2 run --synthetic --grid examples/phase2_grid_mm.json --out /tmp/p2` works
- [ ] `ttp sessions` lists all sessions
- [ ] `ttp gui` launches Tkinter GUI
- [ ] `ttp export --bundle /tmp/test --out /tmp/export` creates manifest
- [ ] `pytest tests/ -v` — all 23+ tests pass
- [ ] `grep -r "scipy.io.wavfile" tap_tone_pi/` returns ONLY `io/wav.py`
- [ ] `grep -r "from modes\." tap_tone_pi/` returns nothing
- [ ] `grep -r "from tap_tone\." tap_tone_pi/` returns nothing (no self-referencing old name)

---

## 7. Estimated Effort

| Step | Time | Risk |
|------|------|------|
| 1-2. Skeleton + WAV I/O | 45 min | Low |
| 3-4. Core + Phase 2 | 45 min | Low |
| 5-6. Storage fix + hardware | 45 min | Medium (test serial) |
| 7. GUI rewrite | 1.5 hrs | Medium (test all buttons) |
| 8-9. CLI + pyproject | 1.25 hrs | Low |
| 10-11. Deprecation + CI | 45 min | Low |
| 12. Verification | 30 min | Low |
| **Total** | **~6 hours** | |

This is a single-day effort. The WAV I/O fix alone (Step 5) eliminates the most
dangerous divergence in the codebase.

---

## 8. What NOT to Change

- **contracts/** — schemas are stable, downstream depends on them
- **docs/ADR-\*** — historical decisions remain valid
- **docs/GOVERNANCE.md** — the modes-vs-pipeline distinction stays, just under new namespaces
- **Makefile** — update target paths but keep the target names
- **boundary_spec.json** — update after migration, not during
