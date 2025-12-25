# Tap Tone Pi

A bench unit for capturing and analyzing tap tone from guitar plates. This Raspberry Pi-based appliance provides luthiers with a dedicated tool for analyzing the acoustic properties of guitar tops, backs, and plates through tap tone testing.

## Features

- **Audio Capture**: Record 2-3 second tap impulse from microphone
- **FFT Analysis**: Perform frequency analysis on recorded audio
- **Peak Detection**: Identify dominant frequency and key resonant peaks
- **Quality Indicator**: Automatic confidence scoring for "good take?" validation
- **Multiple Output Formats**:
  - `audio.wav` - Raw audio recording
  - `analysis.json` - Analysis results with peaks and confidence
  - `spectrum.csv` - Full frequency spectrum data
- **Offline Operation**: No internet required, runs standalone
- **Simple CLI**: Easy to use command-line interface

## Hardware Requirements

- Raspberry Pi (3/4/Zero 2 recommended)
- USB or 3.5mm microphone
- Optional: 7" touchscreen display
- Audio interface (built-in or USB)

## Installation

1. Clone this repository:
```bash
git clone https://github.com/HanzoRazer/tap_tone_pi.git
cd tap_tone_pi
```

2. Install system dependencies (on Raspberry Pi OS):
```bash
sudo apt-get update
sudo apt-get install -y python3-pip portaudio19-dev libsndfile1
```

3. Install Python dependencies:
```bash
pip3 install -r requirements.txt
```

## Configuration

Edit `config.json` to customize settings:

```json
{
  "audio": {
    "sample_rate": 44100,
    "duration": 2.5,
    "channels": 1,
    "device": null
  },
  "analysis": {
    "min_frequency": 50,
    "max_frequency": 5000,
    "num_peaks": 5,
    "peak_threshold": 0.1
  },
  "output": {
    "directory": "output",
    "save_audio": true,
    "save_analysis": true,
    "save_spectrum": true
  }
}
```

### Configuration Options

- **audio.sample_rate**: Audio sample rate in Hz (default: 44100)
- **audio.duration**: Recording duration in seconds (default: 2.5)
- **audio.channels**: Number of audio channels (1 for mono)
- **audio.device**: Audio device index (null for default, use `--list-devices` to see options)
- **analysis.min_frequency**: Minimum frequency to analyze in Hz
- **analysis.max_frequency**: Maximum frequency to analyze in Hz
- **analysis.num_peaks**: Number of peaks to detect and display
- **analysis.peak_threshold**: Relative threshold for peak detection (0-1)
- **output.directory**: Directory to save output files
- **output.save_audio**: Enable/disable audio file saving
- **output.save_analysis**: Enable/disable JSON analysis file saving
- **output.save_spectrum**: Enable/disable CSV spectrum file saving

## Usage

### Basic Usage

Run the tap tone analyzer:

```bash
python3 tap_tone_pi.py
```

The program will:
1. Prompt you to tap the guitar plate
2. Record audio for the configured duration
3. Analyze the frequency content
4. Display results on screen
5. Save all artifacts to the output directory

### List Audio Devices

To see available audio devices:

```bash
python3 tap_tone_pi.py --list-devices
```

### Custom Configuration

Use a different configuration file:

```bash
python3 tap_tone_pi.py --config custom_config.json
```

## Output Files

All output files are saved to the `output/` directory with timestamps:

- **tap_tone_YYYYMMDD_HHMMSS_audio.wav** - Recorded audio
- **tap_tone_YYYYMMDD_HHMMSS_analysis.json** - Analysis results
- **tap_tone_YYYYMMDD_HHMMSS_spectrum.csv** - Frequency spectrum

### Example Analysis Output

```json
{
  "timestamp": "2025-12-25T05:23:00.000000",
  "dominant_frequency": 245.67,
  "peaks": [
    {"frequency": 245.67, "magnitude": 0.987},
    {"frequency": 492.34, "magnitude": 0.654},
    {"frequency": 738.01, "magnitude": 0.432}
  ],
  "confidence": 0.82,
  "quality_indicator": "GOOD"
}
```

## Quality Indicators

- **EXCELLENT** (≥75%): Very clean tap, strong signal
- **GOOD** (≥60%): Clear tap with good frequency response
- **FAIR** (≥40%): Usable but may want to retry
- **POOR** (<40%): Noisy or weak signal, should retry

## Autostart on Raspberry Pi

To make the application start automatically on boot:

1. Create a systemd service file:
```bash
sudo nano /etc/systemd/system/tap-tone-pi.service
```

2. Add the following content:
```ini
[Unit]
Description=Tap Tone Pi
After=sound.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/tap_tone_pi
ExecStart=/usr/bin/python3 /home/pi/tap_tone_pi/tap_tone_pi.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

3. Enable and start the service:
```bash
sudo systemctl enable tap-tone-pi.service
sudo systemctl start tap-tone-pi.service
```

## Troubleshooting

### No Audio Input Detected

- Check microphone connection
- List devices with `--list-devices`
- Set correct device in `config.json`

### Permission Issues

On some systems, you may need to add your user to the audio group:
```bash
sudo usermod -a -G audio $USER
```

### Low Confidence Scores

- Ensure clean, sharp tap on the plate
- Check microphone placement (6-12 inches from plate)
- Reduce background noise
- Verify proper microphone sensitivity

## License

MIT License - see LICENSE file for details

## Contributing

Contributions welcome! Please open an issue or submit a pull request.

## Bench Appliance Integration

This software is designed for integration into a "Bench Appliance" setup:
- Raspberry Pi + 7" display + controls + audio interface
- Goal: A dedicated, luthier-friendly tool that feels like an instrument, not a dev rig
- Offline operation, lives on a shelf, plug in when needed
