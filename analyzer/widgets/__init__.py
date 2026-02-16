"""
UI widgets for the Tap Tone Analyzer.
"""

from analyzer.widgets.spectrum_chart import SpectrumChartWidget
from analyzer.widgets.peaks_table import PeaksTableWidget
from analyzer.widgets.file_tree import FileTreeWidget
from analyzer.widgets.stats_panel import StatsPanel
from analyzer.widgets.bode_plot import BodePlotWidget, WsiPlotWidget
from analyzer.widgets.plate_tuning import PlateTuningWidget

__all__ = [
    "SpectrumChartWidget",
    "PeaksTableWidget",
    "FileTreeWidget",
    "StatsPanel",
    "BodePlotWidget",
    "WsiPlotWidget",
    "PlateTuningWidget",
]
