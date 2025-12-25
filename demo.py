#!/usr/bin/env python3
"""
Demo script for Tap Tone Pi
Demonstrates the complete workflow using simulated audio data.
This can run without audio hardware.
"""
import numpy as np
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from analyzer import AudioAnalyzer
from output_handler import OutputHandler


def generate_demo_audio(sample_rate=44100, duration=2.5):
    """
    Generate realistic tap tone audio for demonstration.
    Simulates a guitar plate tap with multiple harmonics.
    
    Args:
        sample_rate: Sample rate in Hz
        duration: Duration in seconds
        
    Returns:
        Numpy array with synthetic audio
    """
    t = np.linspace(0, duration, int(sample_rate * duration))
    
    # Simulate a typical guitar tap tone
    # Fundamental frequency around 200-300 Hz
    fundamental = 245  # Hz
    
    # Create harmonic series with decay
    signal = np.zeros_like(t)
    
    # Add fundamental and harmonics
    harmonics = [
        (fundamental, 1.0),      # Fundamental
        (fundamental * 2, 0.6),  # 2nd harmonic
        (fundamental * 3, 0.4),  # 3rd harmonic
        (fundamental * 4, 0.2),  # 4th harmonic
        (180, 0.3),              # Additional resonance
        (520, 0.25),             # Another resonance
    ]
    
    for freq, amp in harmonics:
        signal += amp * np.sin(2 * np.pi * freq * t)
    
    # Apply exponential decay (characteristic of tap impulse)
    decay = np.exp(-4 * t / duration)
    signal *= decay
    
    # Add slight noise for realism
    noise = 0.03 * np.random.randn(len(t))
    signal += noise
    
    # Normalize
    if np.max(np.abs(signal)) > 0:
        signal /= np.max(np.abs(signal))
    
    return signal.astype(np.float32)


def main():
    """Run the demo."""
    print("=" * 60)
    print("TAP TONE PI - DEMO MODE")
    print("Guitar Plate Tap Tone Analyzer")
    print("=" * 60)
    print()
    print("This demo simulates the complete workflow:")
    print("1. Audio capture (simulated tap)")
    print("2. FFT analysis")
    print("3. Peak detection")
    print("4. Results display")
    print("5. File export")
    print()
    input("Press Enter to start the demo...")
    print()
    
    # Step 1: Generate simulated audio
    print("Step 1: Generating simulated tap impulse...")
    print("(In real usage, this would be recorded from microphone)")
    audio_data = generate_demo_audio()
    print(f"Generated {len(audio_data)} samples (2.5 seconds)")
    print()
    
    # Step 2: Initialize analyzer
    print("Step 2: Initializing analyzer...")
    analyzer = AudioAnalyzer(
        sample_rate=44100,
        min_freq=50,
        max_freq=5000,
        num_peaks=5,
        peak_threshold=0.1
    )
    print()
    
    # Step 3: Perform analysis
    print("Step 3: Performing FFT analysis...")
    results = analyzer.analyze(audio_data)
    print("Analysis complete!")
    print()
    
    # Step 4: Display results
    print("=" * 60)
    print("ANALYSIS RESULTS")
    print("=" * 60)
    print()
    
    # Dominant frequency
    dominant_freq = results['dominant_frequency']
    print(f"Dominant Frequency: {dominant_freq:.2f} Hz")
    print()
    
    # Peaks
    peaks = results['peaks']
    print(f"Detected Peaks (top {len(peaks)}):")
    for i, peak in enumerate(peaks, 1):
        print(f"  {i}. {peak['frequency']:.2f} Hz (magnitude: {peak['magnitude']:.3f})")
    print()
    
    # Confidence
    confidence = results['confidence']
    quality = results['quality_indicator']
    print(f"Confidence Score: {confidence:.2%}")
    print(f"Quality Indicator: {quality}")
    print()
    
    # Interpretation
    if quality in ["EXCELLENT", "GOOD"]:
        print("✓ Good take! The tap impulse was captured clearly.")
    elif quality == "FAIR":
        print("⚠ Fair take. Consider retapping for better results.")
    else:
        print("✗ Poor take. Please try again with a cleaner tap.")
    print()
    
    # Step 5: Save files
    print("=" * 60)
    print("Step 4: Saving output files...")
    output_handler = OutputHandler(output_dir="demo_output")
    
    filename_base = "demo_run"
    
    # Save analysis
    output_handler.save_analysis_json(results, filename_base)
    output_handler.save_spectrum_csv(results, filename_base)
    
    # Note about audio file
    print()
    print("Note: In real usage, the audio.wav file would also be saved.")
    print("(Skipped in demo mode as we're using simulated data)")
    
    print()
    print("=" * 60)
    print("DEMO COMPLETE!")
    print("=" * 60)
    print()
    print("Output files saved in 'demo_output/' directory:")
    print("  - demo_run_analysis.json")
    print("  - demo_run_spectrum.csv")
    print()
    print("On a real Raspberry Pi with microphone:")
    print("  python3 tap_tone_pi.py")
    print()
    print("To see available audio devices:")
    print("  python3 tap_tone_pi.py --list-devices")
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nDemo interrupted. Exiting...")
        sys.exit(0)
