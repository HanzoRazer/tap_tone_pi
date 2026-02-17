"""
Tests for tap_tone_pi.gui.widgets module (Phase 8 UI Polish).

These tests verify that the widget classes are properly defined
and can be instantiated without a display (where possible).
"""


class TestWidgetsImport:
    """Test that widgets module imports correctly."""

    def test_import_status_level(self):
        """StatusLevel enum should be importable."""
        from tap_tone_pi.gui.widgets import StatusLevel

        assert StatusLevel.INFO.value == "info"
        assert StatusLevel.SUCCESS.value == "success"
        assert StatusLevel.WARNING.value == "warning"
        assert StatusLevel.ERROR.value == "error"
        assert StatusLevel.PROGRESS.value == "progress"

    def test_import_status_message(self):
        """StatusMessage dataclass should be importable."""
        from tap_tone_pi.gui.widgets import StatusMessage, StatusLevel

        msg = StatusMessage(text="Test message")
        assert msg.text == "Test message"
        assert msg.level == StatusLevel.INFO
        assert msg.progress is None

        msg_with_progress = StatusMessage(
            text="Loading...", level=StatusLevel.PROGRESS, progress=0.5
        )
        assert msg_with_progress.progress == 0.5

    def test_import_all_exports(self):
        """All __all__ exports should be importable."""
        from tap_tone_pi.gui.widgets import (
            StatusBar,
            AudioLevelMeter,
            DeviceSelector,
            SetupWizardDialog,
            CaptureProgressDialog,
        )

        # Verify they are classes (except enums/dataclasses)
        assert hasattr(StatusBar, "__init__")
        assert hasattr(AudioLevelMeter, "__init__")
        assert hasattr(DeviceSelector, "__init__")
        assert hasattr(SetupWizardDialog, "__init__")
        assert hasattr(CaptureProgressDialog, "__init__")


class TestAudioLevelMeterLogic:
    """Test AudioLevelMeter color logic without GUI."""

    def test_color_thresholds(self):
        """Verify color threshold definitions."""
        from tap_tone_pi.gui.widgets import AudioLevelMeter

        # Check that COLORS is defined correctly
        assert len(AudioLevelMeter.COLORS) == 5

        # First color should be green (low levels)
        assert AudioLevelMeter.COLORS[0][1] == "#2ecc71"

        # Last color should be red (high levels)
        assert AudioLevelMeter.COLORS[-1][1] == "#e74c3c"


class TestStatusBarColors:
    """Test StatusBar color definitions."""

    def test_color_definitions(self):
        """Verify status bar colors are defined."""
        from tap_tone_pi.gui.widgets import StatusBar, StatusLevel

        # All status levels should have colors defined
        for level in StatusLevel:
            assert level in StatusBar.COLORS
            fg, bg = StatusBar.COLORS[level]
            assert fg.startswith("#")
            assert bg.startswith("#")


class TestSetupWizardSampleRates:
    """Test SetupWizardDialog sample rate options."""

    def test_sample_rates(self):
        """Verify standard sample rates are available."""
        from tap_tone_pi.gui.widgets import SetupWizardDialog

        rates = SetupWizardDialog.SAMPLE_RATES
        assert 44100 in rates
        assert 48000 in rates
        assert 96000 in rates


class TestCaptureProgressDialogStages:
    """Test CaptureProgressDialog stage definitions."""

    def test_stages(self):
        """Verify capture stages are defined."""
        from tap_tone_pi.gui.widgets import CaptureProgressDialog

        stages = CaptureProgressDialog.STAGES
        assert len(stages) == 4
        assert "Preflight" in stages
        assert "Capturing" in stages
        assert "Analyzing" in stages
        assert "Quality Check" in stages


class TestSessionInfo:
    """Test SessionInfo dataclass."""

    def test_import(self):
        """SessionInfo should be importable."""
        from tap_tone_pi.gui.widgets import SessionInfo

        assert hasattr(SessionInfo, "from_path")

    def test_size_display_bytes(self):
        """Test size display for small files."""
        from tap_tone_pi.gui.widgets import SessionInfo
        from pathlib import Path
        from datetime import datetime

        info = SessionInfo(
            path=Path("."),
            name="test",
            modified=datetime.now(),
            size_bytes=500,
        )
        assert info.size_display == "500 B"

    def test_size_display_kb(self):
        """Test size display for KB range."""
        from tap_tone_pi.gui.widgets import SessionInfo
        from pathlib import Path
        from datetime import datetime

        info = SessionInfo(
            path=Path("."),
            name="test",
            modified=datetime.now(),
            size_bytes=2048,
        )
        assert info.size_display == "2.0 KB"

    def test_size_display_mb(self):
        """Test size display for MB range."""
        from tap_tone_pi.gui.widgets import SessionInfo
        from pathlib import Path
        from datetime import datetime

        info = SessionInfo(
            path=Path("."),
            name="test",
            modified=datetime.now(),
            size_bytes=1024 * 1024 * 5,
        )
        assert info.size_display == "5.0 MB"

    def test_type_icons(self):
        """Test type icons for different session types."""
        from tap_tone_pi.gui.widgets import SessionInfo
        from pathlib import Path
        from datetime import datetime

        for session_type, expected_icon in [
            ("quality_gated", "🎯"),
            ("chladni", "🔊"),
            ("bending", "📏"),
            ("moe", "📊"),
            ("tap_tone", "🎵"),
            ("unknown", "📁"),
        ]:
            info = SessionInfo(
                path=Path("."),
                name="test",
                modified=datetime.now(),
                session_type=session_type,
            )
            assert info.type_icon == expected_icon


class TestSessionBrowserDialog:
    """Test SessionBrowserDialog."""

    def test_import(self):
        """SessionBrowserDialog should be importable."""
        from tap_tone_pi.gui.widgets import SessionBrowserDialog

        assert hasattr(SessionBrowserDialog, "__init__")


class TestPackDiffDialog:
    """Test PackDiffDialog."""

    def test_import(self):
        """PackDiffDialog should be importable."""
        from tap_tone_pi.gui.widgets import PackDiffDialog

        assert hasattr(PackDiffDialog, "__init__")
