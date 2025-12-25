"""
Audio capture module for Tap Tone Pi.
Handles microphone input and recording.
"""
import sounddevice as sd
import soundfile as sf
import numpy as np
from typing import Tuple


class AudioCapture:
    """Handles audio recording from microphone."""
    
    def __init__(self, sample_rate: int = 44100, duration: float = 2.5, channels: int = 1, device=None):
        """
        Initialize audio capture.
        
        Args:
            sample_rate: Sample rate in Hz
            duration: Recording duration in seconds
            channels: Number of audio channels (1 for mono)
            device: Audio device index (None for default)
        """
        self.sample_rate = sample_rate
        self.duration = duration
        self.channels = channels
        self.device = device
    
    def record(self) -> np.ndarray:
        """
        Record audio from microphone.
        
        Returns:
            Numpy array containing audio data
        """
        print(f"Recording for {self.duration} seconds...")
        audio_data = sd.rec(
            int(self.duration * self.sample_rate),
            samplerate=self.sample_rate,
            channels=self.channels,
            device=self.device,
            dtype='float32'
        )
        sd.wait()  # Wait for recording to finish
        print("Recording complete!")
        return audio_data.flatten()
    
    def save_audio(self, audio_data: np.ndarray, filepath: str) -> None:
        """
        Save audio data to WAV file.
        
        Args:
            audio_data: Audio data to save
            filepath: Output file path
        """
        sf.write(filepath, audio_data, self.sample_rate)
        print(f"Audio saved to {filepath}")
    
    @staticmethod
    def get_available_devices():
        """List available audio devices."""
        return sd.query_devices()
