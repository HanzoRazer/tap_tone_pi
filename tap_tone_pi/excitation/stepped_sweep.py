# INSTRUMENT CLASS: MEASUREMENT
"""Stepped and sweep excitation emission (DO-93).

emit_stepped() and emit_sweep() generate and play excitation signals,
returning provenance records.

No advisory semantics. No tone quality judgments.
"""

import hashlib
from datetime import datetime, timezone
from typing import Optional
import uuid

import numpy as np

from tap_tone_pi.excitation.amplitude import (
    AmplitudeGuardrail,
    validate_amplitude,
    DEFAULT_AMPLITUDE,
)
from tap_tone_pi.excitation.contracts import (
    SteppedExcitationRecordV1,
    SweepExcitationRecordV1,
)
from tap_tone_pi.signal_gen.generators import generate_sweep


def generate_stepped_signal(
    frequencies_hz: list[float] | tuple[float, ...],
    dwell_time_s: float,
    transition_time_s: float,
    amplitude: float,
    sample_rate_hz: int,
) -> np.ndarray:
    """Generate a stepped frequency signal.

    Each frequency step has a dwell period followed by a transition ramp
    to the next frequency.

    Args:
        frequencies_hz: List of frequencies for each step
        dwell_time_s: Time at each frequency
        transition_time_s: Ramp time between steps
        amplitude: Peak amplitude
        sample_rate_hz: Sample rate

    Returns:
        Numpy array with stepped signal
    """
    segments = []
    freqs = list(frequencies_hz)

    for i, freq in enumerate(freqs):
        # Generate dwell segment at this frequency
        dwell_samples = int(dwell_time_s * sample_rate_hz)
        t = np.arange(dwell_samples) / sample_rate_hz
        dwell_signal = amplitude * np.sin(2 * np.pi * freq * t)
        segments.append(dwell_signal)

        # Generate transition to next frequency (if not last)
        if i < len(freqs) - 1:
            next_freq = freqs[i + 1]
            trans_samples = int(transition_time_s * sample_rate_hz)
            if trans_samples > 0:
                t = np.arange(trans_samples) / sample_rate_hz
                # Linear frequency interpolation during transition
                freq_interp = freq + (next_freq - freq) * t / transition_time_s
                # Instantaneous phase from frequency integral
                phase = 2 * np.pi * np.cumsum(freq_interp) / sample_rate_hz
                trans_signal = amplitude * np.sin(phase)
                segments.append(trans_signal)

    return np.concatenate(segments) if segments else np.array([])


def emit_stepped(
    frequencies_hz: list[float] | tuple[float, ...],
    dwell_time_s: float = 1.0,
    transition_time_s: float = 0.1,
    amplitude: float = DEFAULT_AMPLITUDE,
    sample_rate_hz: int = 48000,
    *,
    output_device_id: Optional[str] = None,
    excitation_id: Optional[str] = None,
    source_characterization_id: Optional[str] = None,
    record_id: Optional[str] = None,
    blocking: bool = True,
) -> SteppedExcitationRecordV1:
    """Generate and emit a stepped frequency excitation.

    Args:
        frequencies_hz: List of frequencies for each step
        dwell_time_s: Time at each frequency
        transition_time_s: Ramp time between steps
        amplitude: Peak amplitude (0.0 to 1.0)
        sample_rate_hz: Sample rate
        output_device_id: Output device identifier (None = default)
        excitation_id: Link to excitation contract
        source_characterization_id: Link to source characterization
        record_id: Unique identifier for the record (auto-generated if None)
        blocking: If True, wait for playback to complete

    Returns:
        SteppedExcitationRecordV1 with emission provenance

    Raises:
        ValueError: If amplitude exceeds guardrail limits
    """
    import sounddevice as sd

    # Validate amplitude
    validation = validate_amplitude(amplitude)
    if validation.guardrail == AmplitudeGuardrail.REJECTED:
        raise ValueError(validation.message)

    # Generate record ID if not provided
    if record_id is None:
        record_id = f"stepped_{uuid.uuid4().hex[:8]}"

    # Get device ID string
    if output_device_id is None:
        device_info = sd.query_devices(sd.default.device[1], "output")
        output_device_id = str(device_info.get("name", "default"))

    # Generate the stepped signal
    signal = generate_stepped_signal(
        frequencies_hz=frequencies_hz,
        dwell_time_s=dwell_time_s,
        transition_time_s=transition_time_s,
        amplitude=amplitude,
        sample_rate_hz=sample_rate_hz,
    )

    # Compute waveform hash
    waveform_sha256 = hashlib.sha256(signal.tobytes()).hexdigest()

    # Record emission timestamp
    emitted_at_utc = datetime.now(timezone.utc).isoformat()

    # Play the signal
    sd.play(signal.astype(np.float32), samplerate=sample_rate_hz)

    if blocking:
        sd.wait()

    # Compute total duration
    freqs = tuple(frequencies_hz)
    step_count = len(freqs)
    total_duration_s = (
        step_count * dwell_time_s + max(0, step_count - 1) * transition_time_s
    )

    # Create and return provenance record
    return SteppedExcitationRecordV1(
        record_id=record_id,
        excitation_id=excitation_id,
        frequencies_hz=freqs,
        step_count=step_count,
        dwell_time_s=dwell_time_s,
        transition_time_s=transition_time_s,
        amplitude=amplitude,
        total_duration_s=total_duration_s,
        sample_rate_hz=sample_rate_hz,
        output_device_id=output_device_id,
        emitted_at_utc=emitted_at_utc,
        source_characterization_id=source_characterization_id,
        waveform_sha256=waveform_sha256,
    )


def emit_sweep(
    start_frequency_hz: float,
    stop_frequency_hz: float,
    duration_s: float = 5.0,
    amplitude: float = DEFAULT_AMPLITUDE,
    sample_rate_hz: int = 48000,
    *,
    sweep_type: str = "logarithmic",
    output_device_id: Optional[str] = None,
    excitation_id: Optional[str] = None,
    source_characterization_id: Optional[str] = None,
    record_id: Optional[str] = None,
    blocking: bool = True,
) -> SweepExcitationRecordV1:
    """Generate and emit a frequency sweep excitation.

    Args:
        start_frequency_hz: Starting frequency
        stop_frequency_hz: Ending frequency
        duration_s: Duration of sweep
        amplitude: Peak amplitude (0.0 to 1.0)
        sample_rate_hz: Sample rate
        sweep_type: Type of sweep ("linear" or "logarithmic")
        output_device_id: Output device identifier (None = default)
        excitation_id: Link to excitation contract
        source_characterization_id: Link to source characterization
        record_id: Unique identifier for the record (auto-generated if None)
        blocking: If True, wait for playback to complete

    Returns:
        SweepExcitationRecordV1 with emission provenance

    Raises:
        ValueError: If amplitude exceeds guardrail limits
    """
    import sounddevice as sd

    # Validate amplitude
    validation = validate_amplitude(amplitude)
    if validation.guardrail == AmplitudeGuardrail.REJECTED:
        raise ValueError(validation.message)

    # Generate record ID if not provided
    if record_id is None:
        record_id = f"sweep_{uuid.uuid4().hex[:8]}"

    # Get device ID string
    if output_device_id is None:
        device_info = sd.query_devices(sd.default.device[1], "output")
        output_device_id = str(device_info.get("name", "default"))

    # Generate the sweep signal using existing signal_gen
    signal = generate_sweep(
        start_freq_hz=start_frequency_hz,
        end_freq_hz=stop_frequency_hz,
        duration_s=duration_s,
        sample_rate=sample_rate_hz,
        amplitude=amplitude,
        sweep_type=sweep_type,
        fade_in_ms=10.0,
        fade_out_ms=10.0,
        pre_silence_ms=0.0,
        post_silence_ms=0.0,
    )

    # Compute waveform hash
    waveform_sha256 = hashlib.sha256(signal.tobytes()).hexdigest()

    # Record emission timestamp
    emitted_at_utc = datetime.now(timezone.utc).isoformat()

    # Play the signal
    sd.play(signal.astype(np.float32), samplerate=sample_rate_hz)

    if blocking:
        sd.wait()

    # Create and return provenance record
    return SweepExcitationRecordV1(
        record_id=record_id,
        excitation_id=excitation_id,
        start_frequency_hz=start_frequency_hz,
        stop_frequency_hz=stop_frequency_hz,
        sweep_type=sweep_type,
        duration_s=duration_s,
        amplitude=amplitude,
        sample_rate_hz=sample_rate_hz,
        output_device_id=output_device_id,
        emitted_at_utc=emitted_at_utc,
        source_characterization_id=source_characterization_id,
        waveform_sha256=waveform_sha256,
    )
