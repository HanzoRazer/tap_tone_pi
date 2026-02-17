# Tap Tone Pi — Quick Start Guide

Get up and running with acoustic measurements in 5 minutes.

## Prerequisites

- Python 3.11+
- A USB microphone or audio interface
- A specimen to measure (guitar top, wood blank, etc.)

## Installation

```bash
# Clone the repository
git clone https://github.com/HanzoRazer/tap_tone_pi.git
cd tap_tone_pi

# Install dependencies
pip install -e .
```

## First Steps

### 1. Run the Setup Wizard

```bash
ttp setup
```

The wizard will:
- List your audio devices
- Help you select the right one
- Test the audio levels
- Save your configuration

### 2. Test Your Hardware

```bash
ttp preflight
```

This verifies:
- Device is connected
- Audio levels are detectable
- No clipping or silence issues

### 3. Quick Capture

```bash
ttp quick
```

This is a zero-config capture that:
- Auto-detects your device
- Records for 2.5 seconds
- Analyzes the frequency spectrum
- Shows dominant frequency and peaks

### 4. Quality-Gated Measurement

```bash
ttp measure --out ./my_session
```

For serious measurements with quality control:
- Pre-flight hardware check
- Captures audio
- Runs quality gate checks
- Prompts to retry if quality is poor

## Common Workflows

### Single Point Measurement

```bash
# Record a single tap point
ttp record --out ./session1 --label "bridge_A1"
```

### Continuous Recording

```bash
# Loop mode: tap, analyze, repeat
ttp live --out ./session1
```

Press Ctrl+C to stop.

### Gold Standard Run

```bash
# Multi-point capture with auto-ingest
ttp gold-run --specimen-id "SG-001" --device 2 --out-dir ./runs --ingest
```

### View Your Sessions

```bash
# List all sessions
ttp sessions

# Show most recent session
ttp last

# Open session in file manager
ttp last --open
```

## Troubleshooting

### "No audio devices found"

- Connect your USB microphone
- Check system audio permissions
- Run `ttp devices` to see what's detected

### "Audio is clipping"

- Reduce microphone gain
- Move mic further from specimen
- Use a quieter tap

### "No audio detected"

- Check microphone connection
- Increase microphone gain
- Verify correct device with `ttp setup`

### "Device not found"

```bash
# List available devices
ttp devices

# Use specific device
ttp measure --out ./test --device 2
```

## Next Steps

- Read the [Phase 2 ODS workflow](docs/ADR-0007_PHASE2_ODS_COHERENCE.md) for grid-based measurements
- Explore the [quality policy](docs/AGENT_DECISION_POLICY_V1.md) for understanding QC gates
- Run `ttp --help` for all available commands

## Getting Help

```bash
# Show all commands
ttp --help

# Show help for specific command
ttp measure --help
```
