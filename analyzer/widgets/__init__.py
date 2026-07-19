"""
UI widgets for the Tap Tone Analyzer.
PyQt6 imports are guarded — module is importable in headless/CI mode.
"""

try:
    from analyzer.widgets.spectrum_chart import SpectrumChartWidget
    from analyzer.widgets.peaks_table import PeaksTableWidget
    from analyzer.widgets.file_tree import FileTreeWidget
    from analyzer.widgets.stats_panel import StatsPanel
    from analyzer.widgets.bode_plot import BodePlotWidget, WsiPlotWidget
    from analyzer.widgets.plate_tuning import PlateTuningWidget
    from analyzer.widgets.limit_overlay import LimitOverlay
    from analyzer.widgets.limit_editor_panel import LimitEditorPanel
    from analyzer.widgets._heatmap import HeatmapWidget
    from analyzer.widgets.phase2_results import Phase2ResultsWidget

    __all__ = [
        "SpectrumChartWidget",
        "PeaksTableWidget",
        "FileTreeWidget",
        "StatsPanel",
        "BodePlotWidget",
        "WsiPlotWidget",
        "PlateTuningWidget",
        "LimitOverlay",
        "LimitEditorPanel",
        "HeatmapWidget",
        "Phase2ResultsWidget",
    ]
except ImportError:
    # PyQt6 not installed — headless/CI mode
    __all__ = []
