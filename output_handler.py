"""
Output module for Tap Tone Pi.
Handles saving analysis results to various formats.
"""
import json
import csv
import os
from typing import Dict
from datetime import datetime


class OutputHandler:
    """Handles saving analysis results to files."""
    
    def __init__(self, output_dir: str = "output"):
        """
        Initialize output handler.
        
        Args:
            output_dir: Directory to save output files
        """
        self.output_dir = output_dir
        self._ensure_output_dir()
    
    def _ensure_output_dir(self) -> None:
        """Create output directory if it doesn't exist."""
        os.makedirs(self.output_dir, exist_ok=True)
    
    def generate_filename_base(self) -> str:
        """
        Generate base filename with timestamp.
        
        Returns:
            Base filename string
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"tap_tone_{timestamp}"
    
    def save_analysis_json(self, results: Dict, filename: str = None) -> str:
        """
        Save analysis results to JSON file.
        
        Args:
            results: Analysis results dictionary
            filename: Output filename (without extension)
            
        Returns:
            Path to saved file
        """
        if filename is None:
            filename = self.generate_filename_base()
        
        filepath = os.path.join(self.output_dir, f"{filename}_analysis.json")
        
        # Create a clean copy for JSON (without full spectrum data)
        json_results = {
            'timestamp': datetime.now().isoformat(),
            'dominant_frequency': results['dominant_frequency'],
            'peaks': results['peaks'],
            'confidence': results['confidence'],
            'quality_indicator': results['quality_indicator']
        }
        
        with open(filepath, 'w') as f:
            json.dump(json_results, f, indent=2)
        
        print(f"Analysis saved to {filepath}")
        return filepath
    
    def save_spectrum_csv(self, results: Dict, filename: str = None) -> str:
        """
        Save frequency spectrum to CSV file.
        
        Args:
            results: Analysis results dictionary
            filename: Output filename (without extension)
            
        Returns:
            Path to saved file
        """
        if filename is None:
            filename = self.generate_filename_base()
        
        filepath = os.path.join(self.output_dir, f"{filename}_spectrum.csv")
        
        spectrum = results.get('spectrum', {})
        frequencies = spectrum.get('frequencies', [])
        magnitudes = spectrum.get('magnitudes', [])
        
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Frequency (Hz)', 'Magnitude'])
            for freq, mag in zip(frequencies, magnitudes):
                writer.writerow([freq, mag])
        
        print(f"Spectrum saved to {filepath}")
        return filepath
    
    def get_audio_path(self, filename: str = None) -> str:
        """
        Get path for audio file.
        
        Args:
            filename: Output filename (without extension)
            
        Returns:
            Path for audio file
        """
        if filename is None:
            filename = self.generate_filename_base()
        
        return os.path.join(self.output_dir, f"{filename}_audio.wav")
