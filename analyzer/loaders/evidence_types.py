"""
Evidence file type system for tap tone analysis.

Migrated from luthiers-toolbox TypeScript implementation.
Provides classification of evidence files by kind and renderer category.
"""

from enum import Enum
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


# Extension-based classification (simple lookups)
_EXT_MAP = {
    ".wav": EvidenceFileKind.AUDIO_WAV,
    ".flac": EvidenceFileKind.AUDIO_FLAC,
    ".mp3": EvidenceFileKind.AUDIO_MP3,
    ".png": EvidenceFileKind.IMAGE_PNG,
    ".jpg": EvidenceFileKind.IMAGE_JPG,
    ".jpeg": EvidenceFileKind.IMAGE_JPG,
    ".md": EvidenceFileKind.MARKDOWN,
    ".txt": EvidenceFileKind.TEXT,
}

# CSV stem patterns: (patterns, result) - any pattern match wins
_CSV_PATTERNS = [
    (("spectrum", "transfer", "frf"), EvidenceFileKind.SPECTRUM_CSV),
    (("peak",), EvidenceFileKind.PEAKS_CSV),
    (("coherence", "coh"), EvidenceFileKind.COHERENCE_CSV),
    (("wsi", "wolf"), EvidenceFileKind.WSI_CURVE),
]

# JSON stem patterns: (patterns, result, require_all)
# require_all=True means ALL patterns must match, False means ANY
_JSON_PATTERNS = [
    (("manifest",), EvidenceFileKind.MANIFEST, False),
    (("session", "meta"), EvidenceFileKind.SESSION_META, True),
    (("capture", "meta"), EvidenceFileKind.CAPTURE_META, True),
    (("meta",), EvidenceFileKind.SESSION_META, False),
    (("peak",), EvidenceFileKind.PEAKS_JSON, False),
    (("spectrum",), EvidenceFileKind.SPECTRUM_JSON, False),
    (("coherence", "coh"), EvidenceFileKind.COHERENCE_JSON, False),
    (("transfer", "frf", "bode"), EvidenceFileKind.TRANSFER_FUNCTION, False),
    (("wsi",), EvidenceFileKind.WSI_CURVE, False),
    (("wolf",), EvidenceFileKind.WOLF_CANDIDATES, False),
]


def _match_patterns(stem: str, patterns: tuple, require_all: bool = False) -> bool:
    """Check if stem matches patterns (any or all based on require_all)."""
    if require_all:
        return all(p in stem for p in patterns)
    return any(p in stem for p in patterns)


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
    stem = path.stem.lower()
    ext = path.suffix.lower()

    # Direct extension lookup
    if ext in _EXT_MAP:
        return _EXT_MAP[ext]

    # CSV pattern matching
    if ext == ".csv":
        for patterns, result in _CSV_PATTERNS:
            if _match_patterns(stem, patterns):
                return result
        return EvidenceFileKind.SPECTRUM_CSV  # Default CSV

    # JSON pattern matching
    if ext == ".json":
        for patterns, result, require_all in _JSON_PATTERNS:
            if _match_patterns(stem, patterns, require_all):
                return result
        return EvidenceFileKind.UNKNOWN  # Default JSON

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
