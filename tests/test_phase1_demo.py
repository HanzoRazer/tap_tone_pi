"""Tests for Phase 1 demo mode (synthetic tap tone generation)."""

import json
import tempfile
from pathlib import Path

import numpy as np

from tap_tone_pi.phase1.demo import (
    TapImpulseConfig,
    DEFAULT_HARMONICS,
    generate_tap_impulse,
    run_demo,
)


class TestGenerateTapImpulse:
    """Tests for synthetic tap impulse generation."""

    def test_returns_float32_array(self):
        audio = generate_tap_impulse()
        assert audio.dtype == np.float32

    def test_correct_length(self):
        audio = generate_tap_impulse(sample_rate=48000, duration_s=2.5)
        expected_samples = int(48000 * 2.5)
        assert len(audio) == expected_samples

    def test_normalized_range(self):
        audio = generate_tap_impulse()
        assert np.max(np.abs(audio)) <= 1.0
        assert np.max(np.abs(audio)) > 0.5  # Should have reasonable amplitude

    def test_reproducible_with_seed(self):
        audio1 = generate_tap_impulse(seed=42)
        audio2 = generate_tap_impulse(seed=42)
        np.testing.assert_array_equal(audio1, audio2)

    def test_different_without_seed(self):
        audio1 = generate_tap_impulse(seed=None)
        audio2 = generate_tap_impulse(seed=None)
        # Very unlikely to be equal without seed
        assert not np.array_equal(audio1, audio2)

    def test_custom_fundamental(self):
        # Just verify it doesn't crash with different fundamentals
        for fundamental in [100.0, 245.0, 400.0, 800.0]:
            audio = generate_tap_impulse(fundamental_hz=fundamental)
            assert len(audio) > 0

    def test_config_override(self):
        config = TapImpulseConfig(
            fundamental_hz=300.0,
            sample_rate=44100,
            duration_s=1.0,
            seed=123,
        )
        audio = generate_tap_impulse(config)
        expected_samples = int(44100 * 1.0)
        assert len(audio) == expected_samples

    def test_exponential_decay_envelope(self):
        audio = generate_tap_impulse(seed=42, noise_level=0.0)
        # First quarter should have higher RMS than last quarter
        quarter = len(audio) // 4
        rms_first = np.sqrt(np.mean(audio[:quarter] ** 2))
        rms_last = np.sqrt(np.mean(audio[-quarter:] ** 2))
        assert rms_first > rms_last * 2  # At least 2x louder at start


class TestRunDemo:
    """Tests for the complete demo workflow."""

    def test_returns_dict_with_expected_keys(self):
        result = run_demo(save_artifacts=False, show_results=False)
        assert isinstance(result, dict)
        assert "demo" in result
        assert "analysis" in result
        assert "quality" in result
        assert "timestamp_utc" in result
        assert result["demo"] is True

    def test_detects_correct_fundamental(self):
        result = run_demo(
            fundamental_hz=245.0,
            save_artifacts=False,
            show_results=False,
            seed=42,
        )
        detected = result["analysis"]["dominant_hz"]
        # Should be within 5% of expected
        assert abs(detected - 245.0) / 245.0 < 0.05

    def test_different_fundamentals(self):
        for expected_hz in [200.0, 280.0, 350.0]:
            result = run_demo(
                fundamental_hz=expected_hz,
                save_artifacts=False,
                show_results=False,
                seed=42,
            )
            detected = result["analysis"]["dominant_hz"]
            error_pct = abs(detected - expected_hz) / expected_hz
            assert error_pct < 0.05, f"Expected ~{expected_hz} Hz, got {detected} Hz"

    def test_quality_pass_for_clean_synthetic(self):
        result = run_demo(save_artifacts=False, show_results=False, seed=42)
        # Synthetic audio should pass quality gate
        assert result["quality"]["verdict"] in ("pass", "warn")

    def test_saves_artifacts_when_requested(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_demo(
                save_artifacts=True,
                output_dir=tmpdir,
                show_results=False,
                seed=42,
            )
            assert "artifacts" in result

            # Check files exist
            audio_path = Path(result["artifacts"]["audio"])
            json_path = Path(result["artifacts"]["analysis"])
            csv_path = Path(result["artifacts"]["spectrum"])

            assert audio_path.exists()
            assert json_path.exists()
            assert csv_path.exists()

            # Verify JSON is valid
            with open(json_path, encoding="utf-8") as f:
                data = json.load(f)
            assert data["demo"] is True
            assert "analysis" in data

            # Verify CSV has content
            csv_content = csv_path.read_text()
            assert "frequency_hz,magnitude" in csv_content
            lines = csv_content.strip().split("\n")
            assert len(lines) > 100  # Should have many frequency bins

    def test_no_artifacts_when_disabled(self):
        result = run_demo(save_artifacts=False, show_results=False)
        assert "artifacts" not in result

    def test_reproducible_with_seed(self):
        result1 = run_demo(save_artifacts=False, show_results=False, seed=42)
        result2 = run_demo(save_artifacts=False, show_results=False, seed=42)
        assert result1["analysis"]["dominant_hz"] == result2["analysis"]["dominant_hz"]
        assert result1["analysis"]["peaks"] == result2["analysis"]["peaks"]


class TestDefaultHarmonics:
    """Tests for the default harmonic structure."""

    def test_has_fundamental(self):
        assert any(ratio == 1.0 for ratio, _ in DEFAULT_HARMONICS)

    def test_fundamental_is_loudest(self):
        fundamental_amp = next(amp for ratio, amp in DEFAULT_HARMONICS if ratio == 1.0)
        for ratio, amp in DEFAULT_HARMONICS:
            if ratio != 1.0:
                assert amp <= fundamental_amp

    def test_has_multiple_harmonics(self):
        assert len(DEFAULT_HARMONICS) >= 4
