"""
Main window for the Tap Tone Analyzer application.
"""

from pathlib import Path
import numpy as np

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QMenuBar, QMenu, QToolBar, QStatusBar,
    QFileDialog, QMessageBox, QTabWidget
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QKeySequence

from analyzer.widgets.file_tree import FileTreeWidget
from analyzer.widgets.spectrum_chart import SpectrumChartWidget
from analyzer.widgets.peaks_table import PeaksTableWidget
from analyzer.widgets.stats_panel import StatsPanel
from analyzer.widgets.bode_plot import BodePlotWidget, WsiPlotWidget
from analyzer.widgets.plate_tuning import PlateTuningWidget
from analyzer.loaders.viewer_pack import ViewerPackLoader
from analyzer.loaders.transfer_function import parse_transfer_function
from analyzer.loaders.wsi_curve import parse_wsi_curve
from analyzer.analysis.coherence import analyze_coherence_quality
from analyzer.analysis.wood_properties import (
    estimate_wood_properties, WoodDimensions, identify_wood_species
)
from analyzer.reports.html_report import generate_html_report
from analyzer.reports.json_report import generate_json_report


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tap Tone Analyzer")
        self.setMinimumSize(1200, 800)

        self.current_pack = None
        self.current_spectrum = None
        self.current_peaks = []
        self.current_wood_props = None
        self.current_coherence_stats = None
        self.current_transfer_function = None
        self.current_wsi_data = None
        self.loader = ViewerPackLoader()

        self._setup_menu()
        self._setup_toolbar()
        self._setup_ui()
        self._setup_statusbar()

    def _setup_menu(self):
        """Create the menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        open_action = QAction("&Open Pack...", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self._open_pack)
        file_menu.addAction(open_action)

        open_folder_action = QAction("Open &Folder...", self)
        open_folder_action.setShortcut("Ctrl+Shift+O")
        open_folder_action.triggered.connect(self._open_folder)
        file_menu.addAction(open_folder_action)

        file_menu.addSeparator()

        # Sample data submenu
        sample_menu = file_menu.addMenu("Load &Sample")

        sample_sitka = QAction("Sitka Spruce Sample", self)
        sample_sitka.triggered.connect(lambda: self._load_sample("sample_sitka_spruce.zip"))
        sample_menu.addAction(sample_sitka)

        sample_cedar = QAction("Cedar Top Sample", self)
        sample_cedar.triggered.connect(lambda: self._load_sample("sample_cedar_top.zip"))
        sample_menu.addAction(sample_cedar)

        sample_menu.addSeparator()

        sample_tuning = QAction("Plate Tuning Demo", self)
        sample_tuning.triggered.connect(self._load_tuning_sample)
        sample_menu.addAction(sample_tuning)

        file_menu.addSeparator()

        # Export submenu
        export_menu = file_menu.addMenu("&Export Report")

        export_html = QAction("Export as &HTML...", self)
        export_html.triggered.connect(lambda: self._export_report("html"))
        export_menu.addAction(export_html)

        export_json = QAction("Export as &JSON...", self)
        export_json.triggered.connect(lambda: self._export_report("json"))
        export_menu.addAction(export_json)

        export_pdf = QAction("Export as &PDF...", self)
        export_pdf.triggered.connect(lambda: self._export_report("pdf"))
        export_menu.addAction(export_pdf)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # View menu
        view_menu = menubar.addMenu("&View")

        zoom_in_action = QAction("Zoom &In", self)
        zoom_in_action.setShortcut(QKeySequence.StandardKey.ZoomIn)
        zoom_in_action.triggered.connect(self._zoom_in)
        view_menu.addAction(zoom_in_action)

        zoom_out_action = QAction("Zoom &Out", self)
        zoom_out_action.setShortcut(QKeySequence.StandardKey.ZoomOut)
        zoom_out_action.triggered.connect(self._zoom_out)
        view_menu.addAction(zoom_out_action)

        reset_zoom_action = QAction("&Reset Zoom", self)
        reset_zoom_action.setShortcut("Ctrl+0")
        reset_zoom_action.triggered.connect(self._reset_zoom)
        view_menu.addAction(reset_zoom_action)

        # Analysis menu
        analysis_menu = menubar.addMenu("&Analysis")

        find_peaks_action = QAction("Find &Peaks", self)
        find_peaks_action.setShortcut("Ctrl+P")
        find_peaks_action.triggered.connect(self._find_peaks)
        analysis_menu.addAction(find_peaks_action)

        coherence_action = QAction("&Coherence Analysis", self)
        coherence_action.triggered.connect(self._analyze_coherence)
        analysis_menu.addAction(coherence_action)

        analysis_menu.addSeparator()

        wood_props_action = QAction("Estimate &Wood Properties", self)
        wood_props_action.setShortcut("Ctrl+W")
        wood_props_action.triggered.connect(self._estimate_wood_properties)
        analysis_menu.addAction(wood_props_action)

        identify_species_action = QAction("&Identify Species", self)
        identify_species_action.triggered.connect(self._identify_species)
        analysis_menu.addAction(identify_species_action)

        analysis_menu.addSeparator()

        full_analysis_action = QAction("Run &Full Analysis", self)
        full_analysis_action.setShortcut("Ctrl+Shift+A")
        full_analysis_action.triggered.connect(self._run_full_analysis)
        analysis_menu.addAction(full_analysis_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _setup_toolbar(self):
        """Create the toolbar."""
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        open_action = QAction("Open", self)
        open_action.triggered.connect(self._open_pack)
        toolbar.addAction(open_action)

        toolbar.addSeparator()

        self.zoom_in_action = QAction("Zoom In", self)
        self.zoom_in_action.triggered.connect(self._zoom_in)
        toolbar.addAction(self.zoom_in_action)

        self.zoom_out_action = QAction("Zoom Out", self)
        self.zoom_out_action.triggered.connect(self._zoom_out)
        toolbar.addAction(self.zoom_out_action)

        toolbar.addSeparator()

        self.peaks_action = QAction("Find Peaks", self)
        self.peaks_action.triggered.connect(self._find_peaks)
        toolbar.addAction(self.peaks_action)

        self.analyze_action = QAction("Full Analysis", self)
        self.analyze_action.triggered.connect(self._run_full_analysis)
        toolbar.addAction(self.analyze_action)

        toolbar.addSeparator()

        self.export_action = QAction("Export HTML", self)
        self.export_action.triggered.connect(lambda: self._export_report("html"))
        toolbar.addAction(self.export_action)

    def _setup_ui(self):
        """Set up the main UI layout."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Main splitter (left panel | right content)
        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left panel - file tree
        self.file_tree = FileTreeWidget()
        self.file_tree.file_selected.connect(self._on_file_selected)
        main_splitter.addWidget(self.file_tree)

        # Right panel - content area
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(4, 4, 4, 4)

        # Vertical splitter for chart and tables
        content_splitter = QSplitter(Qt.Orientation.Vertical)

        # Tab widget for different chart views (top)
        self.chart_tabs = QTabWidget()

        # Spectrum chart tab
        self.spectrum_chart = SpectrumChartWidget()
        self.chart_tabs.addTab(self.spectrum_chart, "Spectrum")

        # Bode plot tab (Transfer Function)
        self.bode_plot = BodePlotWidget()
        self.bode_plot.frequency_clicked.connect(self._on_frequency_clicked)
        self.chart_tabs.addTab(self.bode_plot, "Bode Plot")

        # WSI curve tab
        self.wsi_plot = WsiPlotWidget()
        self.wsi_plot.frequency_clicked.connect(self._on_frequency_clicked)
        self.chart_tabs.addTab(self.wsi_plot, "WSI Curve")

        # Plate tuning tab
        self.plate_tuning = PlateTuningWidget()
        self.chart_tabs.addTab(self.plate_tuning, "Plate Tuning")

        content_splitter.addWidget(self.chart_tabs)

        # Bottom panel with peaks and stats
        bottom_widget = QWidget()
        bottom_layout = QHBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(0, 0, 0, 0)

        # Peaks table
        self.peaks_table = PeaksTableWidget()
        bottom_layout.addWidget(self.peaks_table, stretch=2)

        # Stats panel
        self.stats_panel = StatsPanel()
        bottom_layout.addWidget(self.stats_panel, stretch=1)

        content_splitter.addWidget(bottom_widget)

        # Set splitter proportions
        content_splitter.setSizes([500, 200])

        right_layout.addWidget(content_splitter)
        main_splitter.addWidget(right_widget)

        # Set main splitter proportions
        main_splitter.setSizes([250, 950])

        main_layout.addWidget(main_splitter)

    def _setup_statusbar(self):
        """Create the status bar."""
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.statusbar.showMessage("Ready - Use File > Load Sample to try with test data")

    def _open_pack(self):
        """Open a viewer pack ZIP file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Viewer Pack",
            "",
            "Viewer Packs (*.zip);;All Files (*)"
        )
        if file_path:
            self._load_pack(file_path)

    def _open_folder(self):
        """Open a folder containing viewer pack data."""
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Open Folder"
        )
        if folder_path:
            self._load_folder(folder_path)

    def _load_sample(self, sample_name: str):
        """Load a sample viewer pack."""
        # Find sample data directory
        sample_dir = Path(__file__).parent / "sample_data"
        sample_path = sample_dir / sample_name

        if sample_path.exists():
            self._load_pack(str(sample_path))
        else:
            QMessageBox.warning(
                self,
                "Sample Not Found",
                f"Sample file not found: {sample_path}\n\n"
                "Run the sample generator first:\n"
                "python analyzer/sample_data/generate_sample_pack.py"
            )

    def _load_pack(self, path: str):
        """Load a viewer pack from a ZIP file."""
        try:
            self.current_pack = self.loader.load_zip(path)
            self.file_tree.set_pack(self.current_pack)
            self._auto_load_first_spectrum()
            self.statusbar.showMessage(f"Loaded: {path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load pack:\n{e}")

    def _load_folder(self, path: str):
        """Load viewer pack data from a folder."""
        try:
            self.current_pack = self.loader.load_folder(path)
            self.file_tree.set_pack(self.current_pack)
            self._auto_load_first_spectrum()
            self.statusbar.showMessage(f"Loaded: {path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load folder:\n{e}")

    def _auto_load_first_spectrum(self):
        """Automatically load the first spectrum from the pack."""
        if not self.current_pack:
            return

        spectra = self.current_pack.get("spectra", [])
        if spectra:
            first_spectrum = spectra[0]
            data = first_spectrum.get("data")
            if data:
                self.current_spectrum = data
                self.spectrum_chart.set_data(data)

                # Also load into Bode plot if it has transfer function data
                if "freq_hz" in data or "frequencies" in data:
                    try:
                        tf_data = parse_transfer_function(data)
                        self.current_transfer_function = tf_data
                        self.bode_plot.set_data(
                            frequencies=tf_data.frequencies,
                            magnitude_db=tf_data.magnitude_db,
                            phase=tf_data.phase,
                            coherence=tf_data.coherence
                        )
                    except Exception:
                        pass  # Not a valid transfer function format

                # Load session info
                session_meta = self.current_pack.get("metadata", {}).get("session", {})
                self.stats_panel.set_session_info(session_meta)

        # Check for WSI curve in derived data
        derived = self.current_pack.get("derived", {})
        for name, data in derived.items():
            if "wsi" in name.lower() and isinstance(data, dict):
                self._display_wsi(data, name)
                break

    def _on_file_selected(self, file_info: dict):
        """Handle file selection in the tree."""
        if file_info.get("type") == "spectrum":
            self._display_spectrum(file_info)
        elif file_info.get("type") == "peaks":
            self._display_peaks(file_info)
        elif file_info.get("type") == "derived":
            self._display_derived(file_info)

    def _display_spectrum(self, file_info: dict):
        """Display spectrum data in the chart."""
        data = file_info.get("data")
        if data:
            self.current_spectrum = data
            self.spectrum_chart.set_data(data)
            self.statusbar.showMessage(f"Displaying: {file_info.get('name', 'spectrum')}")

    def _display_peaks(self, file_info: dict):
        """Display peaks data in the table."""
        data = file_info.get("data")
        if data:
            # Handle both list and dict formats
            if isinstance(data, dict):
                data = data.get("peaks", [])
            self.current_peaks = data
            self.peaks_table.set_data(data)
            self.stats_panel.set_peaks_stats(data)

    def _display_derived(self, file_info: dict):
        """Display derived data (wood properties, WSI, etc.)."""
        data = file_info.get("data")
        name = file_info.get("name", "")

        if data and "wood_properties" in data:
            self.current_wood_props = data["wood_properties"]
            self.stats_panel.set_wood_properties(self.current_wood_props)
            self.statusbar.showMessage(f"Loaded wood properties from: {name}")

        # Check for WSI curve data
        elif data and "wsi" in data:
            self._display_wsi(data, name)

    def _display_wsi(self, data: dict, name: str = ""):
        """Display WSI curve data."""
        try:
            wsi_data = parse_wsi_curve(data)
            self.current_wsi_data = wsi_data
            self.wsi_plot.set_data(wsi_data)
            self.chart_tabs.setCurrentWidget(self.wsi_plot)
            self.statusbar.showMessage(f"Loaded WSI curve: {name}")
        except Exception as e:
            self.statusbar.showMessage(f"Error loading WSI: {e}")

    def _display_transfer_function(self, data: dict, name: str = ""):
        """Display transfer function data."""
        try:
            tf_data = parse_transfer_function(data)
            self.current_transfer_function = tf_data
            self.bode_plot.set_data(
                frequencies=tf_data.frequencies,
                magnitude_db=tf_data.magnitude_db,
                phase=tf_data.phase,
                coherence=tf_data.coherence,
                peaks=self.current_peaks
            )
            self.chart_tabs.setCurrentWidget(self.bode_plot)
            self.statusbar.showMessage(f"Loaded transfer function: {name}")
        except Exception as e:
            self.statusbar.showMessage(f"Error loading transfer function: {e}")

    def _on_frequency_clicked(self, freq_hz: float):
        """Handle frequency click from Bode/WSI plots."""
        self.statusbar.showMessage(f"Selected frequency: {freq_hz:.1f} Hz")

    def _export_report(self, format: str):
        """Export analysis report."""
        if not self.current_pack:
            QMessageBox.warning(self, "Warning", "No data loaded to export.")
            return

        # Get file path
        filters = {
            "html": "HTML Files (*.html)",
            "json": "JSON Files (*.json)",
            "pdf": "PDF Files (*.pdf)"
        }

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Report",
            f"tap_tone_report.{format}",
            filters.get(format, "All Files (*)")
        )

        if not file_path:
            return

        try:
            session_meta = self.current_pack.get("metadata", {}).get("session", {})
            spectrum_data = self.current_spectrum or {}
            peaks = self.current_peaks or []
            wood_props = self.current_wood_props
            coherence_stats = self.current_coherence_stats

            if format == "html":
                generate_html_report(
                    session_meta=session_meta,
                    spectrum_data=spectrum_data,
                    peaks=peaks,
                    wood_properties=wood_props,
                    coherence_stats=coherence_stats,
                    output_path=file_path
                )
            elif format == "json":
                generate_json_report(
                    session_meta=session_meta,
                    spectrum_data=spectrum_data,
                    peaks=peaks,
                    wood_properties=wood_props,
                    coherence_stats=coherence_stats,
                    output_path=file_path
                )
            elif format == "pdf":
                # PDF falls back to HTML
                html_path = file_path.replace(".pdf", ".html")
                generate_html_report(
                    session_meta=session_meta,
                    spectrum_data=spectrum_data,
                    peaks=peaks,
                    wood_properties=wood_props,
                    coherence_stats=coherence_stats,
                    output_path=html_path
                )
                QMessageBox.information(
                    self,
                    "PDF Export",
                    f"HTML report saved to:\n{html_path}\n\n"
                    "Open in browser and print to PDF."
                )
                file_path = html_path

            self.statusbar.showMessage(f"Exported to: {file_path}")

        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export:\n{e}")

    def _zoom_in(self):
        """Zoom in on the spectrum chart."""
        self.spectrum_chart.zoom_in()

    def _zoom_out(self):
        """Zoom out on the spectrum chart."""
        self.spectrum_chart.zoom_out()

    def _reset_zoom(self):
        """Reset zoom to default."""
        self.spectrum_chart.reset_zoom()

    def _find_peaks(self):
        """Run peak detection on current spectrum."""
        if self.spectrum_chart.has_data():
            peaks = self.spectrum_chart.find_peaks()
            self.current_peaks = peaks
            self.peaks_table.set_data(peaks)
            self.stats_panel.set_peaks_stats(peaks)
            self.spectrum_chart.highlight_peaks(peaks)
            self.statusbar.showMessage(f"Found {len(peaks)} peaks")
        else:
            QMessageBox.warning(self, "Warning", "No spectrum data loaded.")

    def _analyze_coherence(self):
        """Analyze coherence data."""
        if not self.spectrum_chart.has_data():
            QMessageBox.warning(self, "Warning", "No data loaded.")
            return

        stats = self.spectrum_chart.analyze_coherence()
        if stats:
            # Get full analysis
            coherence = np.array(self.current_spectrum.get("coherence", []))
            if len(coherence) > 0:
                full_stats = analyze_coherence_quality(coherence)
                self.current_coherence_stats = full_stats
                self.stats_panel.set_coherence_stats(full_stats)

                grade = full_stats.get("quality_grade", "?")
                self.statusbar.showMessage(
                    f"Coherence: {full_stats['mean']:.3f} mean, Grade {grade}"
                )

    def _estimate_wood_properties(self):
        """Estimate wood properties from peaks and metadata."""
        if not self.current_peaks:
            QMessageBox.warning(
                self,
                "Warning",
                "No peaks detected. Run 'Find Peaks' first."
            )
            return

        if not self.current_pack:
            QMessageBox.warning(self, "Warning", "No data loaded.")
            return

        try:
            session_meta = self.current_pack.get("metadata", {}).get("session", {})
            dimensions_mm = session_meta.get("dimensions_mm", {})
            weight_g = session_meta.get("weight_g")

            # Get fundamental frequency
            fundamental = self.current_peaks[0]["freq_hz"] if self.current_peaks else 180

            # Build dimensions
            dims = WoodDimensions(
                length=dimensions_mm.get("length", 500),
                width=dimensions_mm.get("width", 150),
                thickness=dimensions_mm.get("thickness", 3)
            )

            # Get coherence quality for confidence
            coherence_quality = 0.9
            if self.current_coherence_stats:
                coherence_quality = self.current_coherence_stats.get("mean", 0.9)

            # Estimate properties
            freq_hz = np.array(self.current_spectrum.get("freq_hz", []))
            magnitude = np.array(self.current_spectrum.get("H_mag", []))

            props = estimate_wood_properties(
                fundamental_hz=fundamental,
                dimensions=dims,
                weight_g=weight_g,
                peaks=self.current_peaks,
                freq_hz=freq_hz,
                magnitude=magnitude,
                coherence_quality=coherence_quality
            )

            self.current_wood_props = props.to_dict()
            self.stats_panel.set_wood_properties(self.current_wood_props)

            self.statusbar.showMessage(
                f"Wood: {props.radiation_coefficient:.1f} R-coeff, "
                f"Grade {props.quality_grade}, "
                f"{props.confidence*100:.0f}% confidence"
            )

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to estimate properties:\n{e}")

    def _identify_species(self):
        """Identify possible wood species from properties."""
        if not self.current_wood_props:
            QMessageBox.warning(
                self,
                "Warning",
                "No wood properties estimated. Run 'Estimate Wood Properties' first."
            )
            return

        try:
            # Reconstruct WoodProperties for identification
            from analyzer.analysis.wood_properties import WoodProperties

            props = WoodProperties(
                density_kg_m3=self.current_wood_props.get("density_kg_m3", 400),
                stiffness_along_gpa=self.current_wood_props.get("stiffness_along_gpa", 10),
                stiffness_cross_gpa=None,
                radiation_coefficient=self.current_wood_props.get("radiation_coefficient", 10),
                damping_factor=self.current_wood_props.get("damping_factor"),
                quality_grade=self.current_wood_props.get("quality_grade", "B"),
                fundamental_hz=self.current_wood_props.get("fundamental_hz", 180),
                confidence=self.current_wood_props.get("confidence", 0.7)
            )

            matches = identify_wood_species(props)

            # Format results
            results = "Possible Wood Species:\n\n"
            for species, score in matches[:5]:
                pct = score * 100
                species_display = species.replace("_", " ").title()
                results += f"  {species_display}: {pct:.0f}% match\n"

            QMessageBox.information(self, "Species Identification", results)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to identify species:\n{e}")

    def _run_full_analysis(self):
        """Run complete analysis pipeline."""
        if not self.spectrum_chart.has_data():
            QMessageBox.warning(self, "Warning", "No data loaded.")
            return

        self.statusbar.showMessage("Running full analysis...")

        # Step 1: Find peaks
        self._find_peaks()

        # Step 2: Analyze coherence
        self._analyze_coherence()

        # Step 3: Estimate wood properties
        if self.current_peaks:
            self._estimate_wood_properties()

        self.statusbar.showMessage("Full analysis complete")

    def _load_tuning_sample(self):
        """Load sample data for plate tuning demo."""
        self.plate_tuning.set_sample_data()
        self.chart_tabs.setCurrentWidget(self.plate_tuning)
        self.statusbar.showMessage("Loaded plate tuning demo data - target: 86 Hz")

    def _show_about(self):
        """Show about dialog."""
        QMessageBox.about(
            self,
            "About Tap Tone Analyzer",
            "Tap Tone Analyzer v0.3.0\n\n"
            "Desktop application for viewing and analyzing\n"
            "acoustic tap tone measurements.\n\n"
            "Features:\n"
            "• Spectrum visualization\n"
            "• Bode plot (Transfer Function)\n"
            "• WSI (Wolf Stress Index) analysis\n"
            "• Plate Tuning Regression\n"
            "• Peak detection\n"
            "• Coherence analysis\n"
            "• Wood property estimation\n"
            "• Species identification\n"
            "• HTML/JSON report export\n\n"
            "Part of the tap_tone_pi project."
        )
