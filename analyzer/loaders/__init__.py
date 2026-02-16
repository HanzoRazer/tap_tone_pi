"""
Data loaders for viewer packs and raw data files.
"""

from analyzer.loaders.viewer_pack import ViewerPackLoader, ViewerPack, EvidenceFile, PackSchema
from analyzer.loaders.csv_parser import SpectrumCSVParser, parse_spectrum_csv
from analyzer.loaders.evidence_types import (
    EvidenceFileKind,
    RendererCategory,
    classify_file,
    kind_to_category,
    get_display_name,
)
from analyzer.loaders.transfer_function import (
    parse_transfer_function,
    TransferFunctionData,
    linear_to_db,
    db_to_linear,
)
from analyzer.loaders.wsi_curve import (
    parse_wsi_curve,
    WsiCurveData,
)

__all__ = [
    # Viewer pack
    "ViewerPackLoader",
    "ViewerPack",
    "EvidenceFile",
    "PackSchema",
    # CSV parsing
    "SpectrumCSVParser",
    "parse_spectrum_csv",
    # Evidence types
    "EvidenceFileKind",
    "RendererCategory",
    "classify_file",
    "kind_to_category",
    "get_display_name",
    # Transfer function
    "parse_transfer_function",
    "TransferFunctionData",
    "linear_to_db",
    "db_to_linear",
    # WSI curve
    "parse_wsi_curve",
    "WsiCurveData",
]
