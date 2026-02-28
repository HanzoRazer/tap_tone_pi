"""Tests for CLI limits integration (Phase 3.5)."""

import argparse
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from tap_tone_pi.cli.limits_integration import (
    add_limits_args,
    load_limits_config,
    run_limit_test,
    format_limit_test_cli,
    handle_limit_test_result,
)


class TestAddLimitsArgs:
    """Tests for add_limits_args function."""

    def test_adds_limits_group(self):
        """Should add limit testing argument group."""
        parser = argparse.ArgumentParser()
        add_limits_args(parser)

        # Parse with no args
        args = parser.parse_args([])

        assert hasattr(args, "limits")
        assert hasattr(args, "limits_preset")
        assert hasattr(args, "limits_fail")
        assert hasattr(args, "limits_json")

    def test_default_values(self):
        """Default values should be None/False."""
        parser = argparse.ArgumentParser()
        add_limits_args(parser)
        args = parser.parse_args([])

        assert args.limits is None
        assert args.limits_preset is None
        assert args.limits_fail is False
        assert args.limits_json is False

    def test_preset_choices(self):
        """Should accept valid preset names."""
        parser = argparse.ArgumentParser()
        add_limits_args(parser)

        for preset in ["tonewood_tap", "speaker_response", "noise_floor"]:
            args = parser.parse_args(["--limits-preset", preset])
            assert args.limits_preset == preset

    def test_invalid_preset_rejected(self):
        """Should reject invalid preset names."""
        parser = argparse.ArgumentParser()
        add_limits_args(parser)

        with pytest.raises(SystemExit):
            parser.parse_args(["--limits-preset", "invalid_preset"])

    def test_limits_file_arg(self):
        """Should accept --limits file path."""
        parser = argparse.ArgumentParser()
        add_limits_args(parser)

        args = parser.parse_args(["--limits", "my_limits.json"])
        assert args.limits == "my_limits.json"

    def test_limits_fail_flag(self):
        """Should set limits_fail to True."""
        parser = argparse.ArgumentParser()
        add_limits_args(parser)

        args = parser.parse_args(["--limits-fail"])
        assert args.limits_fail is True

    def test_limits_json_flag(self):
        """Should set limits_json to True."""
        parser = argparse.ArgumentParser()
        add_limits_args(parser)

        args = parser.parse_args(["--limits-json"])
        assert args.limits_json is True


class TestLoadLimitsConfig:
    """Tests for load_limits_config function."""

    def test_no_limits_returns_none(self):
        """Should return None when no limits specified."""
        args = argparse.Namespace(limits=None, limits_preset=None)
        result = load_limits_config(args)
        assert result is None

    def test_load_preset(self):
        """Should load built-in preset."""
        args = argparse.Namespace(limits=None, limits_preset="tonewood_tap")
        result = load_limits_config(args)

        assert result is not None
        assert "limits" in result or "name" in result

    def test_load_custom_file(self):
        """Should load custom limits file."""
        limits_data = {
            "name": "test_limits",
            "limits": [
                {
                    "name": "test_upper",
                    "limit_type": "upper",
                    "points": [
                        {"frequency_hz": 100, "value_db": 0},
                        {"frequency_hz": 1000, "value_db": -10},
                    ],
                }
            ],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(limits_data, f)
            f.flush()

            args = argparse.Namespace(limits=f.name, limits_preset=None)
            result = load_limits_config(args)

            assert result is not None
            assert result["name"] == "test_limits"
            assert len(result["limits"]) == 1

        Path(f.name).unlink()

    def test_missing_file_raises(self):
        """Should raise FileNotFoundError for missing file."""
        args = argparse.Namespace(limits="/nonexistent/path.json", limits_preset=None)

        with pytest.raises(FileNotFoundError):
            load_limits_config(args)

    def test_invalid_preset_raises(self):
        """Should raise ValueError for invalid preset."""
        args = argparse.Namespace(limits=None, limits_preset="invalid")

        with pytest.raises(ValueError):
            load_limits_config(args)

    def test_preset_takes_precedence(self):
        """Preset should take precedence over custom file."""
        args = argparse.Namespace(limits="some_file.json", limits_preset="tonewood_tap")
        result = load_limits_config(args)

        # Should load preset, not file (preset checked first)
        assert result is not None


class TestRunLimitTest:
    """Tests for run_limit_test function."""

    def test_no_spectrum_data(self):
        """Should handle analysis without spectrum data."""
        analysis = MagicMock()
        analysis.spectrum_freq_hz = None
        analysis.spectrum_mag = None

        limits_config = {"limits": []}

        passed, output = run_limit_test(analysis, limits_config)

        assert passed is True
        assert "No spectrum data" in output

    def test_with_spectrum_data_pass(self):
        """Should pass when within limits."""
        import numpy as np

        analysis = MagicMock()
        analysis.spectrum_freq_hz = list(np.linspace(100, 1000, 100))
        analysis.spectrum_mag = list(np.ones(100) * 0.1)  # Low magnitude

        limits_config = {
            "name": "test_limits",
            "limits": [
                {
                    "name": "upper",
                    "limit_type": "upper",
                    "points": [
                        {"frequency_hz": 100, "value_db": 10},
                        {"frequency_hz": 1000, "value_db": 10},
                    ],
                }
            ],
        }

        passed, output = run_limit_test(analysis, limits_config)

        assert passed is True

    def test_json_output(self):
        """Should return JSON when as_json=True."""
        import numpy as np

        analysis = MagicMock()
        analysis.spectrum_freq_hz = list(np.linspace(100, 1000, 100))
        analysis.spectrum_mag = list(np.ones(100) * 0.1)

        limits_config = {
            "name": "test",
            "limits": [],
        }

        passed, output = run_limit_test(analysis, limits_config, as_json=True)

        # Should be valid JSON
        data = json.loads(output)
        assert "passed" in data


class TestHandleLimitTestResult:
    """Tests for handle_limit_test_result function."""

    def test_pass_returns_zero(self, capsys):
        """Should return 0 when test passes."""
        exit_code = handle_limit_test_result(
            passed=True,
            output="Test passed",
            fail_on_violation=True,
        )

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Test passed" in captured.out

    def test_fail_warn_only(self, capsys):
        """Should return 0 when fail but warn_only mode."""
        exit_code = handle_limit_test_result(
            passed=False,
            output="Test failed",
            fail_on_violation=False,
        )

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Test failed" in captured.out

    def test_fail_with_fail_flag(self, capsys):
        """Should return 1 when fail and fail_on_violation=True."""
        exit_code = handle_limit_test_result(
            passed=False,
            output="Test failed",
            fail_on_violation=True,
        )

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "Test failed" in captured.out


class TestFormatLimitTestCli:
    """Tests for format_limit_test_cli function."""

    def test_format_pass(self):
        """Should format passing result."""
        from tap_tone_pi.limits.testing import TestVerdict

        result = MagicMock()
        result.passed = True
        result.verdict = TestVerdict.PASS
        result.points_tested = 100
        result.points_masked = 0
        result.worst_margin_db = 5.0
        result.violations = []

        output = format_limit_test_cli(
            result,
            {"name": "Test Limits"},
            verbose=True,
        )

        assert "PASS" in output
        assert "Test Limits" in output
        assert "Points tested: 100" in output

    def test_format_fail_with_violations(self):
        """Should show violations when verbose."""
        from tap_tone_pi.limits.testing import TestVerdict, LimitType

        violation = MagicMock()
        violation.frequency_hz = 500.0
        violation.measured_db = 5.0
        violation.limit_db = 0.0
        violation.limit_type = LimitType.UPPER

        result = MagicMock()
        result.passed = False
        result.verdict = TestVerdict.FAIL
        result.points_tested = 100
        result.points_masked = 0
        result.worst_margin_db = -5.0
        result.violations = [violation]

        output = format_limit_test_cli(
            result,
            {"name": "Test Limits"},
            verbose=True,
        )

        assert "FAIL" in output
        assert "Violations: 1" in output
        assert "500.0 Hz" in output


class TestCLIIntegration:
    """Integration tests for CLI limits."""

    def test_parser_has_limits_on_record(self):
        """Record command should have limits args."""
        from tap_tone_pi.cli.main import build_parser

        parser = build_parser()
        args = parser.parse_args(
            ["record", "--out", "./test", "--limits-preset", "tonewood_tap"]
        )

        assert args.limits_preset == "tonewood_tap"

    def test_parser_has_limits_on_quick(self):
        """Quick command should have limits args."""
        from tap_tone_pi.cli.main import build_parser

        parser = build_parser()
        args = parser.parse_args(["quick", "--limits-preset", "speaker_response"])

        assert args.limits_preset == "speaker_response"

    def test_parser_has_limits_on_measure(self):
        """Measure command should have limits args."""
        from tap_tone_pi.cli.main import build_parser

        parser = build_parser()
        args = parser.parse_args(
            [
                "measure",
                "--out",
                "./test",
                "--limits-preset",
                "noise_floor",
                "--limits-fail",
            ]
        )

        assert args.limits_preset == "noise_floor"
        assert args.limits_fail is True
