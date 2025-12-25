# Quick Start Guide for Tap Tone Pi

## For First Time Users

### 1. Setup on Raspberry Pi

```bash
# Update system
sudo apt-get update

# Install system dependencies
sudo apt-get install -y python3-pip portaudio19-dev libsndfile1

# Clone repository
git clone https://github.com/HanzoRazer/tap_tone_pi.git
cd tap_tone_pi

# Install Python dependencies
pip3 install -r requirements.txt
```

### 2. Connect Your Microphone

- Connect a USB microphone to your Raspberry Pi
- Or use a 3.5mm microphone if you have one
- Check available devices: `python3 tap_tone_pi.py --list-devices`

### 3. Run Your First Analysis

```bash
# Basic usage
python3 tap_tone_pi.py
```

When prompted:
1. Hold the guitar plate/top/back firmly
2. Tap it sharply with a knuckle or small hammer
3. Wait for recording to complete
4. Review the results on screen

### 4. Check Your Results

Output files are saved in the `output/` directory:
- `tap_tone_YYYYMMDD_HHMMSS_audio.wav` - Audio recording
- `tap_tone_YYYYMMDD_HHMMSS_analysis.json` - Analysis results
- `tap_tone_YYYYMMDD_HHMMSS_spectrum.csv` - Full spectrum data

## Try the Demo

Test without hardware:

```bash
python3 demo.py
```

## Run Tests

Verify installation:

```bash
python3 test_analyzer.py
```

## Understanding Results

### Dominant Frequency
- **200-250 Hz**: Typical for guitar tops
- **250-350 Hz**: Common for backs
- Values depend on wood type, thickness, bracing

### Quality Indicators
- **EXCELLENT** (≥75%): Perfect tap, use this measurement
- **GOOD** (≥60%): Reliable measurement
- **FAIR** (≥40%): Consider retapping
- **POOR** (<40%): Retry with cleaner tap

### Tips for Good Measurements
1. Tap in the center of the plate
2. Use consistent tap force
3. Minimize background noise
4. Hold plate at edges/nodal points
5. Let plate ring freely

## Configuration

Edit `config.json` to customize:

```json
{
  "audio": {
    "duration": 2.5,        // Recording length in seconds
    "sample_rate": 44100,   // Audio quality
    "device": null          // Set device index or null for default
  },
  "analysis": {
    "min_frequency": 50,    // Lower frequency bound
    "max_frequency": 5000,  // Upper frequency bound
    "num_peaks": 5          // Number of peaks to detect
  }
}
```

## Troubleshooting

### "No module named 'sounddevice'"
```bash
pip3 install -r requirements.txt
```

### "PortAudio library not found"
```bash
sudo apt-get install portaudio19-dev
```

### Low confidence scores
- Check microphone is working
- Reduce background noise
- Ensure clean, sharp tap
- Check microphone placement (6-12 inches)

### No audio input detected
```bash
# List devices
python3 tap_tone_pi.py --list-devices

# Set device in config.json
# "device": 2  // Use the index from list-devices
```

## Next Steps

- Compare multiple taps of the same plate
- Track changes during construction
- Build a database of your work
- Experiment with different wood types

## Need Help?

- Check the full README.md
- Review test_analyzer.py for examples
- Run demo.py to see expected behavior
- Open an issue on GitHub
