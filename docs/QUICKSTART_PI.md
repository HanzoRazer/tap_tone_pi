# Quick Start Guide for Raspberry Pi

## First Time Setup

### 1. Install on Raspberry Pi

```bash
# Update system
sudo apt-get update

# Install system dependencies
sudo apt-get install -y python3-pip python3-venv portaudio19-dev libsndfile1

# Clone repository
git clone https://github.com/HanzoRazer/tap_tone_pi.git
cd tap_tone_pi

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install Python dependencies
pip install -e .
```

### 2. Verify Installation (No Hardware Needed)

Test that everything works without connecting a microphone:

```bash
ttp demo
```

You should see synthetic audio being analyzed with results like:
```
Dominant Frequency: 245.20 Hz
Confidence: 97.43%
[PASS] Measurement quality OK
```

### 3. Connect Your Microphone

- Connect a USB microphone to your Raspberry Pi
- Or use a 3.5mm microphone via USB audio adapter

List available audio devices:
```bash
ttp devices
```

### 4. Run the Setup Wizard

Configure your preferred audio device:
```bash
ttp setup
```

### 5. Your First Real Measurement

Quick capture (auto-detect device):
```bash
ttp quick
```

Or quality-gated measurement session:
```bash
ttp measure --out ./my_session
```

## Commands Reference

| Command | Purpose |
|---------|---------|
| `ttp demo` | Test without hardware (synthetic audio) |
| `ttp devices` | List audio devices |
| `ttp setup` | Configure preferred device |
| `ttp quick` | Zero-config quick capture |
| `ttp measure --out ./dir` | Quality-gated measurement session |
| `ttp record --out ./dir` | Single recording (QC recorded, not gated) |

## Understanding Results

### Dominant Frequency
- **200-250 Hz**: Typical for guitar tops
- **250-350 Hz**: Common for backs
- Values depend on wood type, thickness, bracing

### Quality Verdicts
- **PASS**: Clean capture, reliable measurement
- **WARN**: Usable but has minor issues (quiet signal, few peaks)
- **FAIL**: Retry needed (clipping, no signal, too noisy)

### Confidence Score
Physics-based confidence combining:
- Signal-to-noise ratio
- Spectral flatness (tonal vs noise)
- Q-factor (resonance sharpness)

## Tips for Good Measurements

1. Tap in the center of the plate
2. Use consistent tap force
3. Minimize background noise
4. Hold plate at edges/nodal points
5. Let plate ring freely
6. Position mic 6-12 inches from plate

## Troubleshooting

### "No audio signal detected"
- Check microphone connection
- Run `ttp devices` and verify input channels > 0
- Run `ttp setup` to select correct device

### Low confidence scores
- Ensure clean, sharp tap
- Check microphone placement
- Reduce background noise

### "Device not found"
```bash
# List all devices
ttp devices

# Re-run setup wizard
ttp setup --reset
```

## Autostart on Boot (Optional)

Create a systemd service for headless operation:

```bash
sudo nano /etc/systemd/system/tap-tone-pi.service
```

Add:
```ini
[Unit]
Description=Tap Tone Pi
After=sound.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/tap_tone_pi
ExecStart=/home/pi/tap_tone_pi/.venv/bin/ttp measure --out /home/pi/sessions
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Enable:
```bash
sudo systemctl enable tap-tone-pi.service
```

## Next Steps

- Run `ttp --help` for all commands
- See `docs/` for architecture details
- Phase 2 ODS scanning: `ttp phase2 --help`
