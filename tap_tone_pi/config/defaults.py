"""
Centralized Configuration Defaults.

m1 Audit Fix: Scattered Configuration Constants.
All magic numbers and default values should be defined here for:
- Easy discovery
- Consistent defaults across modules
- Single source of truth

Usage:
    from tap_tone_pi.config.defaults import (
        SAMPLE_RATE_DEFAULT,
        CAPTURE_DURATION_S,
        ...
    )

Categories:
- Audio capture
- FFT/DSP analysis
- Peak detection
- Calibration
- Quality thresholds
- Physical constants
- UI/UX defaults
"""

from __future__ import annotations

# =============================================================================
# Audio Capture
# =============================================================================

SAMPLE_RATE_DEFAULT = 48000  # Hz (DVD quality, divisible by many frame sizes)
SAMPLE_RATE_CD = 44100  # Hz (CD quality)
SAMPLE_RATE_HIGH = 96000  # Hz (high-res audio)

CAPTURE_CHANNELS_DEFAULT = 1  # Mono for Phase 1
CAPTURE_CHANNELS_STEREO = 2  # Stereo for Phase 2 ODS

CAPTURE_DURATION_S = 2.5  # Default capture duration in seconds
CAPTURE_DURATION_MIN_S = 0.5  # Minimum sensible capture
CAPTURE_DURATION_MAX_S = 60.0  # Maximum before memory concerns

# =============================================================================
# FFT / DSP Analysis
# =============================================================================

HIGHPASS_HZ = 20.0  # Remove DC and subsonic noise
LOWPASS_HZ = 20000.0  # Nyquist-safe for 48 kHz

WINDOW_TYPE = "hanning"  # Good compromise for frequency vs amplitude accuracy
# Alternatives: "blackman" (better sidelobe suppression), "hamming" (narrower main lobe)

FFT_ZERO_PAD_FACTOR = 1  # No zero-padding by default (1x = no padding)

# Butterworth filter defaults
BUTTERWORTH_ORDER = 4  # 24 dB/octave rolloff, minimal phase distortion
# Justification: Order 4 provides sufficient attenuation for modal analysis
# while maintaining acceptable group delay characteristics. Higher orders
# would improve stopband rejection but increase phase distortion.

# =============================================================================
# Peak Detection
# =============================================================================

PEAK_MIN_HZ = 40.0  # Below this is typically noise/rumble
PEAK_MAX_HZ = 2000.0  # Most wood resonances below this
PEAK_MIN_PROMINENCE = 0.05  # Relative to max (0-1 scale)
PEAK_MIN_SPACING_HZ = 10.0  # Minimum frequency separation between peaks
MAX_PEAKS = 12  # Maximum peaks to return

# Clipping detection
CLIPPING_THRESHOLD = 0.995  # Industry standard for float audio
# Note: 0.999 is too conservative; many ADCs show nonlinearity by 0.995

# =============================================================================
# Signal Health
# =============================================================================

RMS_MIN_THRESHOLD = 0.005  # Below this = too quiet
RMS_MAX_THRESHOLD = 0.9  # Above this = likely clipping
SNR_MIN_DB = 15.0  # Minimum acceptable SNR for reliable peak detection

# =============================================================================
# Calibration
# =============================================================================

CALIBRATION_EXPIRY_DAYS = 30  # Recalibrate after this many days
LOOPBACK_LATENCY_MAX_MS = 50.0  # Maximum expected loopback latency
REFERENCE_TONE_HZ = 440.0  # A4 for calibration tones
REFERENCE_TONE_DURATION_S = 1.0  # Duration of calibration tone

# =============================================================================
# Quality Thresholds
# =============================================================================

CONFIDENCE_HIGH = 0.8  # High confidence threshold
CONFIDENCE_MEDIUM = 0.5  # Medium confidence threshold
CONFIDENCE_LOW = 0.3  # Below this = unreliable

Q_FACTOR_MIN = 5.0  # Below this = probably not a resonance
Q_FACTOR_TYPICAL = 20.0  # Typical wood resonance Q
Q_FACTOR_HIGH = 50.0  # Very sharp resonance

# =============================================================================
# Physical Constants
# =============================================================================

GRAVITY_M_S2 = 9.80665  # Standard gravity (m/s²)
SPEED_OF_SOUND_M_S = 343.0  # Speed of sound in air at 20°C

# Typical tonewood properties (for validation/sanity checks)
WOOD_DENSITY_MIN_KG_M3 = 300.0  # Very light wood (balsa-ish)
WOOD_DENSITY_MAX_KG_M3 = 800.0  # Very dense wood (ebony)
WOOD_DENSITY_TYPICAL_KG_M3 = 420.0  # Sitka spruce

WOOD_MOE_MIN_GPA = 5.0  # Very soft wood
WOOD_MOE_MAX_GPA = 20.0  # Very stiff wood
WOOD_MOE_TYPICAL_GPA = 12.0  # Sitka spruce longitudinal

# =============================================================================
# Cross-Validation
# =============================================================================

CROSSVAL_THRESHOLD_PCT = 10.0  # Static vs dynamic E divergence threshold
CROSSVAL_GOOD_PCT = 5.0  # Good agreement threshold
CROSSVAL_MARGINAL_PCT = 10.0  # Marginal agreement threshold

# =============================================================================
# Session/Measurement
# =============================================================================

SESSION_ID_LENGTH = 8  # Characters in session ID
GRID_MAX_ROWS = 26  # A-Z (see m4 fix for extended grid)
GRID_MAX_COLS = 26  # Same as rows

# Frequency tolerance for matching
FREQ_TOLERANCE_PCT = 2.0  # Default relative tolerance (%)
FREQ_TOLERANCE_HZ_MIN = 1.0  # Minimum absolute tolerance (Hz)

# =============================================================================
# Uncertainty / Statistics
# =============================================================================

COVERAGE_FACTOR_95 = 2.0  # k=2 for ~95% confidence interval
COVERAGE_FACTOR_99 = 3.0  # k=3 for ~99% confidence interval
FALLBACK_THRESHOLD_PCT = 0.5  # When no uncertainty available

# =============================================================================
# Agentic / UWSM
# =============================================================================

UWSM_CONFIDENCE_FLOOR = 0.20  # Minimum confidence (never goes below)
UWSM_DELTA_EXPLICIT = 0.20  # Confidence change for explicit feedback
UWSM_DELTA_BEHAVIORAL = 0.05  # Confidence change for behavioral signal
UWSM_CAP_EXPLICIT = 0.90  # Max confidence from explicit feedback
UWSM_CAP_BEHAVIORAL = 0.80  # Max confidence from behavioral signals

# Half-life for confidence decay (days)
UWSM_HALF_LIFE_DAYS = {
    "temperature": 30,
    "humidity": 30,
    "material": 90,
    "technique": 60,
    "equipment": 180,
}

# =============================================================================
# Ingest / External
# =============================================================================

DEFAULT_INGEST_URL = "http://localhost:8000"
INGEST_TIMEOUT_S = 30.0  # HTTP timeout for ingest requests

# =============================================================================
# Retry Logic
# =============================================================================

RETRY_MAX_ATTEMPTS = 3
RETRY_DELAY_S = 0.5  # Initial delay (exponential backoff)
RETRY_BACKOFF_FACTOR = 2.0  # Multiply delay by this each retry

# =============================================================================
# File I/O
# =============================================================================

JSON_INDENT = 2  # Pretty-print JSON with this indent
WAV_PCM_BITS = 16  # Default PCM bit depth for WAV files
