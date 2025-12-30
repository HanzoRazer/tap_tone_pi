# tap_tone_pi — Measurement Quick Guide

## Modes

- **Tap-tone (live)**: `modes/tap_tone/tap_fft_logger.py`
- **Tap-tone (offline WAV)**: `modes/tap_tone/offline_from_wav.py`
- **Bending stiffness → MOE**: `modes/bending_stiffness/deflection_to_moe.py`
- **Provenance import (hash only)**: `modes/provenance_import/attach_grain_provenance.py`
- **Manifest writer**: `modes/_shared/emit_manifest.py`

## Typical Flow

1. Capture tap-tone live **or** run offline analysis from WAV.
2. Run a 3-point (or 4-point) deflection test → MOE fact(s).
3. Emit a `manifest.json` that hashes artifacts and records rig metadata.
4. Validate JSONs against schemas (locally or in CI).

## One-liners

Live tap + spectrum:

```bash
python modes/tap_tone/tap_fft_logger.py --outfile out/tap_tone.json --plot out/spectrum.png
```

Offline analysis from a WAV file (44.1 kHz recommended):

```bash
python modes/tap_tone/offline_from_wav.py --wav data/sample_tap.wav --outfile out/tap_tone_offline.json --labels A0 T11 B11
```

MOE (single):

```bash
python modes/bending_stiffness/deflection_to_moe.py --method 3point --span 400 --width 20 --thickness 3.0 --force 5.0 --deflection 0.62 --density 0.41 --out out/bending_test.json
```

MOE (batch):

```bash
python modes/bending_stiffness/deflection_to_moe.py --csv data/deflection_runs.csv --out out/moe_results.csv
```

Provenance hashing (no computation):

```bash
python modes/provenance_import/attach_grain_provenance.py --file data/grain_field.png --out out/provenance.json
```

Manifest:

```bash
python modes/_shared/emit_manifest.py --out out/manifest.json \
  --artifact out/tap_tone.json --artifact out/bending_test.json \
  --rig fixture=3-point span_mm=400 operator=Ross \
  --notes "Tap + bending run (J45-0001)"
```
