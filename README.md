# Tap Tone PI (Desktop)

A small Raspberry Pi desktop utility to record a tap impulse with a USB mic, analyze resonant peaks, and save artifacts.

## Install (Pi)

```bash
sudo apt-get update
sudo apt-get install -y portaudio19-dev python3-dev
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
```

## Run

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

## Outputs

Each capture produces:

* `audio.wav`
* `analysis.json` (peaks, dominant frequency, confidence)
* `spectrum.csv` (freq_hz, magnitude)
* `session.jsonl` (append-only log)
