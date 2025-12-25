"""
FFT analysis module for Tap Tone Pi.
Performs frequency analysis and peak detection.
"""
import numpy as np
from scipy import signal
from scipy.fft import rfft, rfftfreq
from typing import List, Tuple, Dict


class AudioAnalyzer:
    """Performs FFT and peak analysis on audio data."""
    
    def __init__(self, sample_rate: int = 44100, min_freq: float = 50, 
                 max_freq: float = 5000, num_peaks: int = 5, peak_threshold: float = 0.1):
        """
        Initialize audio analyzer.
        
        Args:
            sample_rate: Sample rate in Hz
            min_freq: Minimum frequency to analyze (Hz)
            max_freq: Maximum frequency to analyze (Hz)
            num_peaks: Number of peaks to detect
            peak_threshold: Relative threshold for peak detection (0-1)
        """
        self.sample_rate = sample_rate
        self.min_freq = min_freq
        self.max_freq = max_freq
        self.num_peaks = num_peaks
        self.peak_threshold = peak_threshold
    
    def analyze(self, audio_data: np.ndarray) -> Dict:
        """
        Perform complete analysis on audio data.
        
        Args:
            audio_data: Audio samples
            
        Returns:
            Dictionary containing analysis results
        """
        # Compute FFT
        fft_values, frequencies = self._compute_fft(audio_data)
        
        # Filter to frequency range of interest
        freq_mask = (frequencies >= self.min_freq) & (frequencies <= self.max_freq)
        filtered_freqs = frequencies[freq_mask]
        filtered_fft = fft_values[freq_mask]
        
        # Find peaks
        peaks = self._find_peaks(filtered_fft, filtered_freqs)
        
        # Determine dominant frequency
        dominant_freq = peaks[0]['frequency'] if peaks else 0.0
        
        # Calculate confidence
        confidence = self._calculate_confidence(audio_data, filtered_fft, peaks)
        
        # Prepare results
        results = {
            'dominant_frequency': float(dominant_freq),
            'peaks': peaks[:self.num_peaks],
            'confidence': float(confidence),
            'quality_indicator': self._quality_label(confidence),
            'spectrum': {
                'frequencies': filtered_freqs.tolist(),
                'magnitudes': filtered_fft.tolist()
            }
        }
        
        return results
    
    def _compute_fft(self, audio_data: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compute FFT of audio data.
        
        Args:
            audio_data: Audio samples
            
        Returns:
            Tuple of (magnitudes, frequencies)
        """
        # Apply window to reduce spectral leakage
        window = signal.windows.hann(len(audio_data))
        windowed_data = audio_data * window
        
        # Compute FFT
        fft_complex = rfft(windowed_data)
        fft_magnitude = np.abs(fft_complex)
        frequencies = rfftfreq(len(audio_data), 1.0 / self.sample_rate)
        
        return fft_magnitude, frequencies
    
    def _find_peaks(self, fft_magnitude: np.ndarray, frequencies: np.ndarray) -> List[Dict]:
        """
        Find peaks in FFT spectrum.
        
        Args:
            fft_magnitude: FFT magnitude values
            frequencies: Corresponding frequencies
            
        Returns:
            List of peak dictionaries sorted by magnitude
        """
        # Normalize magnitude
        if len(fft_magnitude) == 0 or np.max(fft_magnitude) == 0:
            return []
        
        normalized_mag = fft_magnitude / np.max(fft_magnitude)
        
        # Find peaks using scipy
        peak_indices, properties = signal.find_peaks(
            normalized_mag,
            height=self.peak_threshold,
            distance=10  # Minimum distance between peaks
        )
        
        # Sort by magnitude
        if len(peak_indices) > 0:
            peak_mags = normalized_mag[peak_indices]
            sorted_indices = np.argsort(peak_mags)[::-1]  # Descending order
            
            peaks = []
            for idx in sorted_indices:
                peak_idx = peak_indices[idx]
                peaks.append({
                    'frequency': float(frequencies[peak_idx]),
                    'magnitude': float(normalized_mag[peak_idx])
                })
            return peaks
        
        return []
    
    def _calculate_confidence(self, audio_data: np.ndarray, fft_magnitude: np.ndarray, 
                             peaks: List[Dict]) -> float:
        """
        Calculate confidence score for the recording.
        
        Args:
            audio_data: Original audio samples
            fft_magnitude: FFT magnitude values
            peaks: Detected peaks
            
        Returns:
            Confidence score (0-1)
        """
        confidence_factors = []
        
        # Factor 1: Signal strength (RMS)
        rms = np.sqrt(np.mean(audio_data ** 2))
        signal_strength = min(rms * 10, 1.0)  # Scale and cap at 1.0
        confidence_factors.append(signal_strength)
        
        # Factor 2: Number of clear peaks
        if peaks:
            peak_clarity = min(len(peaks) / self.num_peaks, 1.0)
            confidence_factors.append(peak_clarity)
        else:
            confidence_factors.append(0.0)
        
        # Factor 3: Dominant peak strength
        if peaks and len(fft_magnitude) > 0:
            dominant_strength = peaks[0]['magnitude']
            confidence_factors.append(dominant_strength)
        else:
            confidence_factors.append(0.0)
        
        # Factor 4: SNR-like metric (peak to average ratio)
        if len(fft_magnitude) > 0:
            avg_magnitude = np.mean(fft_magnitude)
            max_magnitude = np.max(fft_magnitude)
            if avg_magnitude > 0:
                snr_factor = min(max_magnitude / (avg_magnitude * 10), 1.0)
                confidence_factors.append(snr_factor)
            else:
                confidence_factors.append(0.0)
        else:
            confidence_factors.append(0.0)
        
        # Average all factors
        confidence = np.mean(confidence_factors)
        return confidence
    
    def _quality_label(self, confidence: float) -> str:
        """
        Convert confidence score to quality label.
        
        Args:
            confidence: Confidence score (0-1)
            
        Returns:
            Quality label string
        """
        if confidence >= 0.75:
            return "EXCELLENT"
        elif confidence >= 0.6:
            return "GOOD"
        elif confidence >= 0.4:
            return "FAIR"
        else:
            return "POOR"
