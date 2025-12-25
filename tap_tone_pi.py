#!/usr/bin/env python3
"""
Tap Tone Pi - Main Application
A bench unit for capturing and analyzing tap tone from guitar plates.
"""
import json
import sys
import argparse
from pathlib import Path


def import_modules():
    """Import required modules with better error handling."""
    try:
        from audio_capture import AudioCapture
        from analyzer import AudioAnalyzer
        from output_handler import OutputHandler
        return AudioCapture, AudioAnalyzer, OutputHandler
    except ImportError as e:
        print(f"Error importing modules: {e}")
        print("\nNote: If running on a system without audio hardware,")
        print("some dependencies may not be available.")
        print("On Raspberry Pi, install with:")
        print("  sudo apt-get install portaudio19-dev libsndfile1")
        print("  pip3 install -r requirements.txt")
        sys.exit(1)


class TapTonePi:
    """Main application class for Tap Tone Pi."""
    
    def __init__(self, config_path: str = "config.json"):
        """
        Initialize Tap Tone Pi application.
        
        Args:
            config_path: Path to configuration file
        """
        AudioCapture, AudioAnalyzer, OutputHandler = import_modules()
        
        self.config = self._load_config(config_path)
        
        # Initialize components
        audio_config = self.config['audio']
        self.audio_capture = AudioCapture(
            sample_rate=audio_config['sample_rate'],
            duration=audio_config['duration'],
            channels=audio_config['channels'],
            device=audio_config['device']
        )
        
        analysis_config = self.config['analysis']
        self.analyzer = AudioAnalyzer(
            sample_rate=audio_config['sample_rate'],
            min_freq=analysis_config['min_frequency'],
            max_freq=analysis_config['max_frequency'],
            num_peaks=analysis_config['num_peaks'],
            peak_threshold=analysis_config['peak_threshold']
        )
        
        output_config = self.config['output']
        self.output_handler = OutputHandler(
            output_dir=output_config['directory']
        )
    
    def _load_config(self, config_path: str) -> dict:
        """Load configuration from JSON file."""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Warning: Config file '{config_path}' not found. Using defaults.")
            return self._default_config()
    
    def _default_config(self) -> dict:
        """Return default configuration."""
        return {
            'audio': {
                'sample_rate': 44100,
                'duration': 2.5,
                'channels': 1,
                'device': None
            },
            'analysis': {
                'min_frequency': 50,
                'max_frequency': 5000,
                'num_peaks': 5,
                'peak_threshold': 0.1
            },
            'output': {
                'directory': 'output',
                'save_audio': True,
                'save_analysis': True,
                'save_spectrum': True
            }
        }
    
    def run(self) -> None:
        """Run the main tap tone capture and analysis workflow."""
        print("=" * 60)
        print("TAP TONE PI - Guitar Plate Tap Tone Analyzer")
        print("=" * 60)
        print()
        
        # Step 1: Record audio
        print("Step 1: Recording tap impulse...")
        print("Please tap the guitar plate now!")
        audio_data = self.audio_capture.record()
        print()
        
        # Step 2: Analyze audio
        print("Step 2: Analyzing audio...")
        results = self.analyzer.analyze(audio_data)
        print("Analysis complete!")
        print()
        
        # Step 3: Display results
        self._display_results(results)
        print()
        
        # Step 4: Save artifacts
        print("Step 4: Saving artifacts...")
        filename_base = self.output_handler.generate_filename_base()
        
        output_config = self.config['output']
        
        if output_config['save_audio']:
            audio_path = self.output_handler.get_audio_path(filename_base)
            self.audio_capture.save_audio(audio_data, audio_path)
        
        if output_config['save_analysis']:
            self.output_handler.save_analysis_json(results, filename_base)
        
        if output_config['save_spectrum']:
            self.output_handler.save_spectrum_csv(results, filename_base)
        
        print()
        print("=" * 60)
        print("Analysis complete! All artifacts saved.")
        print("=" * 60)
    
    def _display_results(self, results: dict) -> None:
        """
        Display analysis results to console.
        
        Args:
            results: Analysis results dictionary
        """
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
        
        # Interpretation
        print()
        if quality in ["EXCELLENT", "GOOD"]:
            print("✓ Good take! The tap impulse was captured clearly.")
        elif quality == "FAIR":
            print("⚠ Fair take. Consider retapping for better results.")
        else:
            print("✗ Poor take. Please try again with a cleaner tap.")
        print()
    
    def list_devices(self) -> None:
        """List available audio devices."""
        print("Available Audio Devices:")
        print("=" * 60)
        AudioCapture, _, _ = import_modules()
        devices = AudioCapture.get_available_devices()
        print(devices)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Tap Tone Pi - Guitar Plate Tap Tone Analyzer"
    )
    parser.add_argument(
        '--config',
        default='config.json',
        help='Path to configuration file (default: config.json)'
    )
    parser.add_argument(
        '--list-devices',
        action='store_true',
        help='List available audio devices and exit'
    )
    
    args = parser.parse_args()
    
    try:
        app = TapTonePi(config_path=args.config)
        
        if args.list_devices:
            app.list_devices()
        else:
            app.run()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Exiting...")
        sys.exit(0)
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
