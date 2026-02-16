"""
Evidence file type system for tap tone analysis.

Migrated from luthiers-toolbox TypeScript implementation.
Provides classification of evidence files by kind and renderer category.
"""

from enum import Enum
from typing import Optional
from pathlib import Path


class EvidenceFileKind(Enum):
    """
    Classification of evidence file types.

    Maps to renderer categories for display decisions.
    """
    # Audio files
    AUDIO_WAV = "audio_wav"
    AUDIO_FLAC = "audio_flac"
    AUDIO_MP3 = "audio_mp3"

    # Spectrum data
    SPECTRUM_CSV = "spectrum_csv"
    SPECTRUM_JSON = "spectrum_json"

    # Analysis results
    PEAKS_CSV = "peaks_csv"
    PEAKS_JSON = "peaks_json"
    COHERENCE_CSV = "coherence_csv"
    COHERENCE_JSON = "coherence_json"

    # Transfer function / Bode plot
    TRANSFER_FUNCTION = "transfer_function"
    FRF_JSON = "frf_json"

    # WSI (Wolf Stress Index)
    WSI_CURVE = "wsi_curve"
    WOLF_CANDIDATES = "wolf_candidates"

    # Metadata
    SESSION_META = "session_meta"
    CAPTURE_META = "capture_meta"
    MANIFEST = "manifest"

    # Images
    IMAGE_PNG = "image_png"
    IMAGE_JPG = "image_jpg"

    # Documents
    MARKDOWN = "markdown"
    TEXT = "text"

    # Unknown
    UNKNOWN = "unknown"


class RendererCategory(Enum):
    """
    Categories of renderers for displaying evidence.

    Each category corresponds to a specific visualization approach.
    """
    AUDIO = "audio"
    IMAGE = "image"
    CSV = "csv"
    JSON = "json"
    MARKDOWN = "markdown"
    SPECTRUM_CHART = "spectrum_chart"
    WSI_CHART = "wsi_chart"
    BODE_PLOT = "bode_plot"
    PEAKS_TABLE = "peaks_table"
    METADATA = "metadata"
    UNKNOWN = "unknown"


def kind_to_category(kind: EvidenceFileKind) -> RendererCategory:
    """
    Map evidence file kind to renderer category.

    Args:
        kind: The evidence file kind

    Returns:
        The appropriate renderer category
    """
    mapping = {
        # Audio -> audio player
        EvidenceFileKind.AUDIO_WAV: RendererCategory.AUDIO,
        EvidenceFileKind.AUDIO_FLAC: RendererCategory.AUDIO,
        EvidenceFileKind.AUDIO_MP3: RendererCategory.AUDIO,

        # Spectrum data -> spectrum chart
        EvidenceFileKind.SPECTRUM_CSV: RendererCategory.SPECTRUM_CHART,
        EvidenceFileKind.SPECTRUM_JSON: RendererCategory.SPECTRUM_CHART,

        # Peaks -> peaks table
        EvidenceFileKind.PEAKS_CSV: RendererCategory.PEAKS_TABLE,
        EvidenceFileKind.PEAKS_JSON: RendererCategory.PEAKS_TABLE,

        # Coherence -> spectrum chart (overlay)
        EvidenceFileKind.COHERENCE_CSV: RendererCategory.SPECTRUM_CHART,
        EvidenceFileKind.COHERENCE_JSON: RendererCategory.SPECTRUM_CHART,

        # Transfer function -> Bode plot
        EvidenceFileKind.TRANSFER_FUNCTION: RendererCategory.BODE_PLOT,
        EvidenceFileKind.FRF_JSON: RendererCategory.BODE_PLOT,

        # WSI -> WSI chart
        EvidenceFileKind.WSI_CURVE: RendererCategory.WSI_CHART,
        EvidenceFileKind.WOLF_CANDIDATES: RendererCategory.WSI_CHART,

        # Metadata -> metadata viewer
        EvidenceFileKind.SESSION_META: RendererCategory.METADATA,
        EvidenceFileKind.CAPTURE_META: RendererCategory.METADATA,
        EvidenceFileKind.MANIFEST: RendererCategory.METADATA,

        # Images
        EvidenceFileKind.IMAGE_PNG: RendererCategory.IMAGE,
        EvidenceFileKind.IMAGE_JPG: RendererCategory.IMAGE,

        # Documents
        EvidenceFileKind.MARKDOWN: RendererCategory.MARKDOWN,
        EvidenceFileKind.TEXT: RendererCategory.CSV,  # Plain text as CSV-like

        EvidenceFileKind.UNKNOWN: RendererCategory.UNKNOWN,
    }
    return mapping.get(kind, RendererCategory.UNKNOWN)


def classify_file(filepath: str) -> EvidenceFileKind:
    """
    Classify a file by its path/name.

    Uses filename patterns and extensions to determine file kind.

    Args:
        filepath: Path to the file (relative or absolute)

    Returns:
        The classified file kind
    """
    path = Path(filepath)
    name = path.name.lower()
    stem = path.stem.lower()
    ext = path.suffix.lower()

    # Audio files by extension
    if ext == ".wav":
        return EvidenceFileKind.AUDIO_WAV
    if ext == ".flac":
        return EvidenceFileKind.AUDIO_FLAC
    if ext == ".mp3":
        return EvidenceFileKind.AUDIO_MP3

    # Images
    if ext == ".png":
        return EvidenceFileKind.IMAGE_PNG
    if ext in (".jpg", ".jpeg"):
        return EvidenceFileKind.IMAGE_JPG

    # Markdown
    if ext == ".md":
        return EvidenceFileKind.MARKDOWN

    # CSV files - classify by name pattern
    if ext == ".csv":
        if "spectrum" in stem or "transfer" in stem or "frf" in stem:
            return EvidenceFileKind.SPECTRUM_CSV
        if "peak" in stem:
            return EvidenceFileKind.PEAKS_CSV
        if "coherence" in stem or "coh" in stem:
            return EvidenceFileKind.COHERENCE_CSV
        if "wsi" in stem or "wolf" in stem:
            return EvidenceFileKind.WSI_CURVE
        # Default CSV
        return EvidenceFileKind.SPECTRUM_CSV

    # JSON files - classify by name pattern
    if ext == ".json":
        if "manifest" in stem:
            return EvidenceFileKind.MANIFEST
        if "session" in stem and "meta" in stem:
            return EvidenceFileKind.SESSION_META
        if "capture" in stem and "meta" in stem:
            return EvidenceFileKind.CAPTURE_META
        if "meta" in stem:
            return EvidenceFileKind.SESSION_META
        if "peak" in stem:
            return EvidenceFileKind.PEAKS_JSON
        if "spectrum" in stem:
            return EvidenceFileKind.SPECTRUM_JSON
        if "coherence" in stem or "coh" in stem:
            return EvidenceFileKind.COHERENCE_JSON
        if "transfer" in stem or "frf" in stem or "bode" in stem:
            return EvidenceFileKind.TRANSFER_FUNCTION
        if "wsi" in stem:
            return EvidenceFileKind.WSI_CURVE
        if "wolf" in stem:
            return EvidenceFileKind.WOLF_CANDIDATES
        # Default JSON
        return EvidenceFileKind.UNKNOWN

    # Text files
    if ext == ".txt":
        return EvidenceFileKind.TEXT

    return EvidenceFileKind.UNKNOWN


def get_display_name(kind: EvidenceFileKind) -> str:
    """Get human-readable display name for file kind."""
    names = {
        EvidenceFileKind.AUDIO_WAV: "Audio (WAV)",
        EvidenceFileKind.AUDIO_FLAC: "Audio (FLAC)",
        EvidenceFileKind.AUDIO_MP3: "Audio (MP3)",
        EvidenceFileKind.SPECTRUM_CSV: "Spectrum Data",
        EvidenceFileKind.SPECTRUM_JSON: "Spectrum Data",
        EvidenceFileKind.PEAKS_CSV: "Peak Detection",
        EvidenceFileKind.PEAKS_JSON: "Peak Detection",
        EvidenceFileKind.COHERENCE_CSV: "Coherence Analysis",
        EvidenceFileKind.COHERENCE_JSON: "Coherence Analysis",
        EvidenceFileKind.TRANSFER_FUNCTION: "Transfer Function",
        EvidenceFileKind.FRF_JSON: "FRF Data",
        EvidenceFileKind.WSI_CURVE: "WSI Curve",
        EvidenceFileKind.WOLF_CANDIDATES: "Wolf Note Candidates",
        EvidenceFileKind.SESSION_META: "Session Metadata",
        EvidenceFileKind.CAPTURE_META: "Capture Metadata",
        EvidenceFileKind.MANIFEST: "Pack Manifest",
        EvidenceFileKind.IMAGE_PNG: "Image (PNG)",
        EvidenceFileKind.IMAGE_JPG: "Image (JPEG)",
        EvidenceFileKind.MARKDOWN: "Documentation",
        EvidenceFileKind.TEXT: "Text File",
        EvidenceFileKind.UNKNOWN: "Unknown",
    }
    return names.get(kind, "Unknown")
