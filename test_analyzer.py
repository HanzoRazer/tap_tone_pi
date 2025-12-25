#!/usr/bin/env python3
"""
Test script for Tap Tone Pi
Tests the analysis functionality with simulated audio data.
"""
import numpy as np
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from analyzer import AudioAnalyzer
from output_handler import OutputHandler


def generate_test_audio(sample_rate=44100, duration=2.5, frequencies=[245, 492, 738], 
                        amplitudes=[1.0, 0.5, 0.3], noise_level=0.05):
    """
    Generate synthetic tap tone audio for testing.
    
    Args:
        sample_rate: Sample rate in Hz
        duration: Duration in seconds
        frequencies: List of frequency components
        amplitudes: List of amplitude for each frequency
        noise_level: Amount of random noise
        
    Returns:
        Numpy array with synthetic audio
    """
    t = np.linspace(0, duration, int(sample_rate * duration))
    
    # Generate composite signal
    signal = np.zeros_like(t)
    for freq, amp in zip(frequencies, amplitudes):
        signal += amp * np.sin(2 * np.pi * freq * t)
    
    # Apply exponential decay (like a tap impulse)
    decay = np.exp(-3 * t / duration)
    signal *= decay
    
    # Add noise
    noise = noise_level * np.random.randn(len(t))
    signal += noise
    
    # Normalize
    if np.max(np.abs(signal)) > 0:
        signal /= np.max(np.abs(signal))
    
    return signal.astype(np.float32)


def test_analyzer():
    """Test the AudioAnalyzer with synthetic data."""
    print("=" * 60)
    print("Testing Tap Tone Pi Analysis")
    print("=" * 60)
    print()
    
    # Generate test audio
    print("Generating synthetic tap tone audio...")
    test_frequencies = [245, 492, 738]
    audio_data = generate_test_audio(frequencies=test_frequencies)
    print(f"Generated {len(audio_data)} samples")
    print()
    
    # Initialize analyzer
    print("Initializing analyzer...")
    analyzer = AudioAnalyzer(
        sample_rate=44100,
        min_freq=50,
        max_freq=5000,
        num_peaks=5,
        peak_threshold=0.1
    )
    print()
    
    # Perform analysis
    print("Performing FFT analysis...")
    results = analyzer.analyze(audio_data)
    print("Analysis complete!")
    print()
    
    # Display results
    print("=" * 60)
    print("ANALYSIS RESULTS")
    print("=" * 60)
    print()
    
    print(f"Dominant Frequency: {results['dominant_frequency']:.2f} Hz")
    print(f"Expected: {test_frequencies[0]} Hz")
    print()
    
    print(f"Detected Peaks (top {len(results['peaks'])}):")
    for i, peak in enumerate(results['peaks'], 1):
        print(f"  {i}. {peak['frequency']:.2f} Hz (magnitude: {peak['magnitude']:.3f})")
    print()
    
    print(f"Confidence Score: {results['confidence']:.2%}")
    print(f"Quality Indicator: {results['quality_indicator']}")
    print()
    
    # Test output handler
    print("Testing output handler...")
    output_handler = OutputHandler(output_dir="test_output")
    
    # Save analysis
    filename_base = "test_run"
    output_handler.save_analysis_json(results, filename_base)
    output_handler.save_spectrum_csv(results, filename_base)
    
    print()
    print("=" * 60)
    print("Test Results:")
    
    # Validate results
    success = True
    
    # Check dominant frequency (should be close to 245 Hz)
    if abs(results['dominant_frequency'] - test_frequencies[0]) < 10:
        print("✓ Dominant frequency detection: PASS")
    else:
        print("✗ Dominant frequency detection: FAIL")
        success = False
    
    # Check number of peaks
    if len(results['peaks']) > 0:
        print("✓ Peak detection: PASS")
    else:
        print("✗ Peak detection: FAIL")
        success = False
    
    # Check confidence calculation
    if 0 <= results['confidence'] <= 1:
        print("✓ Confidence calculation: PASS")
    else:
        print("✗ Confidence calculation: FAIL")
        success = False
    
    # Check quality indicator
    if results['quality_indicator'] in ['EXCELLENT', 'GOOD', 'FAIR', 'POOR']:
        print("✓ Quality indicator: PASS")
    else:
        print("✗ Quality indicator: FAIL")
        success = False
    
    print("=" * 60)
    
    if success:
        print("\n✓ All tests passed!")
        return 0
    else:
        print("\n✗ Some tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(test_analyzer())
