#!/usr/bin/env python3
"""
Example: Using Tap Tone Pi modules programmatically

This example shows how to use the individual modules
in your own Python scripts.
"""
import numpy as np
from analyzer import AudioAnalyzer
from output_handler import OutputHandler


def example_with_real_audio():
    """Example using real microphone input."""
    print("Example 1: Using real audio capture")
    print("-" * 40)
    
    # Import only when needed (requires audio hardware)
    from audio_capture import AudioCapture
    
    # Initialize audio capture
    capture = AudioCapture(
        sample_rate=44100,
        duration=2.5,
        channels=1
    )
    
    # Record audio
    print("Recording...")
    audio_data = capture.record()
    
    # Initialize analyzer
    analyzer = AudioAnalyzer(
        sample_rate=44100,
        min_freq=50,
        max_freq=5000,
        num_peaks=5
    )
    
    # Analyze
    results = analyzer.analyze(audio_data)
    
    # Display results
    print(f"Dominant Frequency: {results['dominant_frequency']:.2f} Hz")
    print(f"Confidence: {results['confidence']:.2%}")
    print(f"Quality: {results['quality_indicator']}")
    
    # Save files
    output = OutputHandler(output_dir="my_output")
    output.save_analysis_json(results)
    output.save_spectrum_csv(results)
    audio_path = output.get_audio_path()
    capture.save_audio(audio_data, audio_path)


def example_with_synthetic_audio():
    """Example using synthetic audio data."""
    print("\nExample 2: Using synthetic audio data")
    print("-" * 40)
    
    # Generate synthetic audio (e.g., from a simulation)
    sample_rate = 44100
    duration = 2.5
    t = np.linspace(0, duration, int(sample_rate * duration))
    
    # Create a simple sine wave at 250 Hz with decay
    frequency = 250
    audio_data = np.sin(2 * np.pi * frequency * t) * np.exp(-2 * t)
    audio_data = audio_data.astype(np.float32)
    
    # Analyze
    analyzer = AudioAnalyzer(sample_rate=sample_rate)
    results = analyzer.analyze(audio_data)
    
    # Display results
    print(f"Input frequency: {frequency} Hz")
    print(f"Detected frequency: {results['dominant_frequency']:.2f} Hz")
    print(f"Confidence: {results['confidence']:.2%}")


def example_batch_analysis():
    """Example: Analyzing multiple recordings."""
    print("\nExample 3: Batch analysis")
    print("-" * 40)
    
    # Simulate multiple recordings
    recordings = []
    for i, freq in enumerate([245, 280, 310]):
        print(f"\nRecording {i+1} (simulated at {freq} Hz)...")
        
        # Generate audio
        sample_rate = 44100
        duration = 2.5
        t = np.linspace(0, duration, int(sample_rate * duration))
        audio = np.sin(2 * np.pi * freq * t) * np.exp(-2 * t)
        audio = audio.astype(np.float32)
        
        # Analyze
        analyzer = AudioAnalyzer(sample_rate=sample_rate)
        results = analyzer.analyze(audio)
        
        recordings.append({
            'id': i + 1,
            'frequency': results['dominant_frequency'],
            'confidence': results['confidence'],
            'quality': results['quality_indicator']
        })
    
    # Summary
    print("\n" + "=" * 40)
    print("BATCH SUMMARY")
    print("=" * 40)
    for rec in recordings:
        print(f"Recording {rec['id']}: {rec['frequency']:.2f} Hz "
              f"({rec['quality']}, {rec['confidence']:.0%})")


def example_custom_peak_detection():
    """Example: Using custom analysis parameters."""
    print("\nExample 4: Custom peak detection parameters")
    print("-" * 40)
    
    # Generate test audio with multiple peaks
    sample_rate = 44100
    duration = 2.5
    t = np.linspace(0, duration, int(sample_rate * duration))
    
    # Multiple frequency components
    audio = (
        1.0 * np.sin(2 * np.pi * 200 * t) +
        0.5 * np.sin(2 * np.pi * 400 * t) +
        0.3 * np.sin(2 * np.pi * 600 * t)
    ) * np.exp(-2 * t)
    audio = audio.astype(np.float32)
    
    # Analyze with custom parameters
    analyzer = AudioAnalyzer(
        sample_rate=sample_rate,
        min_freq=100,           # Higher minimum
        max_freq=1000,          # Lower maximum
        num_peaks=3,            # Detect 3 peaks
        peak_threshold=0.05     # Lower threshold
    )
    
    results = analyzer.analyze(audio)
    
    print(f"Found {len(results['peaks'])} peaks:")
    for i, peak in enumerate(results['peaks'], 1):
        print(f"  {i}. {peak['frequency']:.2f} Hz (mag: {peak['magnitude']:.3f})")


if __name__ == "__main__":
    # Run synthetic examples (don't require hardware)
    example_with_synthetic_audio()
    example_batch_analysis()
    example_custom_peak_detection()
    
    # Uncomment to try with real audio (requires microphone)
    # example_with_real_audio()
    
    print("\n" + "=" * 40)
    print("Examples complete!")
    print("=" * 40)
