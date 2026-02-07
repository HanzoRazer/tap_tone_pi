"""I/O utilities: WAV read/write, manifest generation, capture storage.

This is the canonical location for WAV I/O. All other modules should
import from here, never directly from scipy.io.wavfile.

Usage:
    from tap_tone_pi.io.wav import read_wav_mono, write_wav_mono
    from tap_tone_pi.io.manifest import write_manifest
    from tap_tone_pi.io.storage import persist_capture, PersistedCapture
"""

from .wav import read_wav_mono, write_wav_mono
from .storage import persist_capture, PersistedCapture, analysis_to_json_dict

__all__ = [
    "read_wav_mono",
    "write_wav_mono",
    "persist_capture",
    "PersistedCapture",
    "analysis_to_json_dict",
]
