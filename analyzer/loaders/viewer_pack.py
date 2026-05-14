"""
Viewer pack loader - loads ZIP or folder-based viewer packs.

Supports dual schema detection:
- viewer_pack_v1: Original tap_tone_pi export format
- toolbox_evidence_manifest_v1: ToolBox/luthiers-toolbox format
"""

import json
import zipfile
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum

from analyzer.loaders.csv_parser import SpectrumCSVParser
from analyzer.loaders.evidence_types import (
    classify_file,
    EvidenceFileKind,
    RendererCategory,
)


class PackSchema(Enum):
    """Detected pack schema type."""

    VIEWER_PACK_V1 = "viewer_pack_v1"
    TOOLBOX_MANIFEST_V1 = "toolbox_evidence_manifest_v1"
    UNKNOWN = "unknown"


@dataclass
class EvidenceFile:
    """Represents a single evidence file in the pack."""

    name: str
    path: str
    kind: EvidenceFileKind
    category: RendererCategory
    data: Optional[Any] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ViewerPack:
    """Unified viewer pack representation."""

    name: str
    source_path: str
    schema: PackSchema
    schema_version: str

    # Metadata
    session_meta: Dict[str, Any] = field(default_factory=dict)
    capture_meta: Dict[str, Any] = field(default_factory=dict)
    manifest: Dict[str, Any] = field(default_factory=dict)

    # Evidence files by category
    spectra: List[EvidenceFile] = field(default_factory=list)
    peaks: List[EvidenceFile] = field(default_factory=list)
    coherence: List[EvidenceFile] = field(default_factory=list)
    transfer_functions: List[EvidenceFile] = field(default_factory=list)
    wsi_curves: List[EvidenceFile] = field(default_factory=list)
    audio: List[EvidenceFile] = field(default_factory=list)
    images: List[EvidenceFile] = field(default_factory=list)
    derived: Dict[str, Any] = field(default_factory=dict)

    # All files for browsing
    all_files: List[EvidenceFile] = field(default_factory=list)

    def get_primary_spectrum(self) -> Optional[EvidenceFile]:
        """Get the primary spectrum file (first available)."""
        return self.spectra[0] if self.spectra else None

    def get_files_by_kind(self, kind: EvidenceFileKind) -> List[EvidenceFile]:
        """Get all files of a specific kind."""
        return [f for f in self.all_files if f.kind == kind]


class ViewerPackLoader:
    """
    Loader for viewer_pack format.

    Viewer packs can be:
    - ZIP files containing JSON metadata and CSV spectrum data
    - Folders with the same structure

    Standard structure:
        viewer_pack/
        ├── manifest.json           # Pack manifest
        ├── session_meta.json       # Session metadata
        ├── capture_meta.json       # Capture metadata
        ├── spectra/
        │   ├── transfer_function.csv
        │   └── ...
        ├── peaks/
        │   └── detected_peaks.json
        └── derived/
            ├── ods_snapshot.json
            └── wolf_candidates.json
    """

    def __init__(self):
        self._temp_dir: Optional[Path] = None
        self._csv_parser = SpectrumCSVParser()

    def load(self, path: str) -> ViewerPack:
        """
        Load a viewer pack from ZIP or folder.

        Auto-detects schema format and normalizes to ViewerPack.

        Args:
            path: Path to ZIP file or folder

        Returns:
            Normalized ViewerPack object
        """
        path = Path(path)
        if path.suffix.lower() == ".zip":
            return self.load_zip_as_pack(path)
        elif path.is_dir():
            return self.load_folder_as_pack(path)
        else:
            raise ValueError(f"Unsupported path type: {path}")

    def load_zip_as_pack(self, zip_path: Path) -> ViewerPack:
        """Load ZIP file and return ViewerPack."""
        raw = self.load_zip(str(zip_path))
        return self._normalize_to_pack(raw, str(zip_path))

    def load_folder_as_pack(self, folder_path: Path) -> ViewerPack:
        """Load folder and return ViewerPack."""
        raw = self.load_folder(str(folder_path))
        return self._normalize_to_pack(raw, str(folder_path))

    def _detect_schema(self, root: Path) -> tuple:
        """
        Detect pack schema from manifest or structure.

        Returns:
            (PackSchema, version_string)
        """
        # Check for ToolBox manifest
        toolbox_manifest = root / "manifest.json"
        if toolbox_manifest.exists():
            try:
                with open(toolbox_manifest, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                    schema_id = manifest.get("schema_id", "")
                    if schema_id == "toolbox_evidence_manifest_v1":
                        return (
                            PackSchema.TOOLBOX_MANIFEST_V1,
                            manifest.get("schema_version", "1.0"),
                        )
                    elif schema_id == "viewer_pack_v1":
                        return (
                            PackSchema.VIEWER_PACK_V1,
                            manifest.get("schema_version", "1.0"),
                        )
            except (json.JSONDecodeError, IOError):
                pass

        # Check for viewer_pack_v1 by structure
        if (root / "session_meta.json").exists():
            return (PackSchema.VIEWER_PACK_V1, "1.0")

        # Check for spectra directory (tap_tone_pi style)
        if (root / "spectra").is_dir():
            return (PackSchema.VIEWER_PACK_V1, "1.0")

        return (PackSchema.UNKNOWN, "unknown")

    def _normalize_to_pack(self, raw: Dict[str, Any], source_path: str) -> ViewerPack:
        """Normalize raw dict to ViewerPack object."""
        # Detect schema
        schema = PackSchema.VIEWER_PACK_V1  # Default
        schema_version = "1.0"

        manifest = raw.get("manifest", {})
        if manifest:
            schema_id = manifest.get("schema_id", "")
            if schema_id == "toolbox_evidence_manifest_v1":
                schema = PackSchema.TOOLBOX_MANIFEST_V1
            schema_version = manifest.get("schema_version", "1.0")

        pack = ViewerPack(
            name=raw.get("name", Path(source_path).stem),
            source_path=source_path,
            schema=schema,
            schema_version=schema_version,
            manifest=manifest,
            session_meta=raw.get("metadata", {}).get("session", {}),
            capture_meta=raw.get("metadata", {}).get("capture", {}),
            derived=raw.get("derived", {}),
        )

        # Process spectra
        for spec in raw.get("spectra", []):
            kind = classify_file(spec.get("name", "") + ".csv")
            ef = EvidenceFile(
                name=spec.get("name", ""),
                path=spec.get("name", ""),
                kind=kind,
                category=RendererCategory.SPECTRUM_CHART,
                data=spec.get("data"),
            )
            pack.spectra.append(ef)
            pack.all_files.append(ef)

        # Process peaks
        for peak in raw.get("peaks", []):
            ef = EvidenceFile(
                name=peak.get("name", ""),
                path=peak.get("name", ""),
                kind=EvidenceFileKind.PEAKS_JSON,
                category=RendererCategory.PEAKS_TABLE,
                data=peak.get("data"),
            )
            pack.peaks.append(ef)
            pack.all_files.append(ef)

        # Process audio
        for audio in raw.get("raw_audio", []):
            kind = classify_file(audio.get("path", ""))
            ef = EvidenceFile(
                name=audio.get("name", ""),
                path=audio.get("path", ""),
                kind=kind,
                category=RendererCategory.AUDIO,
            )
            pack.audio.append(ef)
            pack.all_files.append(ef)

        return pack

    def load_zip(self, zip_path: str) -> Dict[str, Any]:
        """
        Load a viewer pack from a ZIP file.

        Args:
            zip_path: Path to the ZIP file

        Returns:
            Parsed viewer pack dictionary
        """
        zip_path = Path(zip_path)
        if not zip_path.exists():
            raise FileNotFoundError(f"ZIP file not found: {zip_path}")

        # Extract to temp directory
        self._temp_dir = Path(tempfile.mkdtemp(prefix="tap_tone_viewer_"))

        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(self._temp_dir)

        # Find the root folder (might be nested)
        root = self._find_pack_root(self._temp_dir)

        pack = self._load_from_folder(root)
        pack["name"] = zip_path.stem
        pack["source_path"] = str(zip_path)

        return pack

    def load_folder(self, folder_path: str) -> Dict[str, Any]:
        """
        Load a viewer pack from a folder.

        Args:
            folder_path: Path to the folder

        Returns:
            Parsed viewer pack dictionary
        """
        folder = Path(folder_path)
        if not folder.is_dir():
            raise NotADirectoryError(f"Not a directory: {folder}")

        pack = self._load_from_folder(folder)
        pack["name"] = folder.name
        pack["source_path"] = str(folder)

        return pack

    def _find_pack_root(self, start: Path) -> Path:
        """Find the actual pack root (handles nested folders in ZIPs)."""
        # Check if start is already a valid pack root
        if self._is_pack_root(start):
            return start

        # Check immediate subdirectories
        for child in start.iterdir():
            if child.is_dir() and self._is_pack_root(child):
                return child

        # If no manifest found, just return start
        return start

    def _is_pack_root(self, folder: Path) -> bool:
        """Check if folder looks like a pack root."""
        return (
            (folder / "manifest.json").exists()
            or (folder / "session_meta.json").exists()
            or (folder / "spectra").is_dir()
        )

    def _load_from_folder(self, root: Path) -> Dict[str, Any]:
        """Load pack data from folder structure."""
        pack: Dict[str, Any] = {
            "metadata": {},
            "spectra": [],
            "peaks": [],
            "derived": {},
            "raw_audio": [],
        }

        # Load manifest
        manifest_path = root / "manifest.json"
        if manifest_path.exists():
            pack["manifest"] = self._load_json(manifest_path)

        # Load session metadata
        session_meta_path = root / "session_meta.json"
        if session_meta_path.exists():
            pack["metadata"]["session"] = self._load_json(session_meta_path)

        # Load capture metadata
        capture_meta_path = root / "capture_meta.json"
        if capture_meta_path.exists():
            pack["metadata"]["capture"] = self._load_json(capture_meta_path)

        # Load spectra
        spectra_dir = root / "spectra"
        if spectra_dir.is_dir():
            pack["spectra"] = self._load_spectra(spectra_dir)

        # Load peaks
        peaks_dir = root / "peaks"
        if peaks_dir.is_dir():
            pack["peaks"] = self._load_peaks(peaks_dir)

        # Also check for peaks.json at root
        peaks_json = root / "peaks.json"
        if peaks_json.exists():
            pack["peaks"].append({"name": "peaks", "data": self._load_json(peaks_json)})

        # Load derived data
        derived_dir = root / "derived"
        if derived_dir.is_dir():
            pack["derived"] = self._load_derived(derived_dir)

        # Look for raw audio files
        for audio_ext in [".wav", ".flac", ".mp3"]:
            for audio_file in root.rglob(f"*{audio_ext}"):
                pack["raw_audio"].append(
                    {"name": audio_file.stem, "path": str(audio_file)}
                )

        return pack

    def _load_json(self, path: Path) -> Dict[str, Any]:
        """Load and parse a JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _load_spectra(self, spectra_dir: Path) -> List[Dict[str, Any]]:
        """Load spectrum CSV files from directory."""
        spectra = []

        for csv_file in spectra_dir.glob("*.csv"):
            data = self._csv_parser.parse(csv_file)
            spectra.append({"name": csv_file.stem, "data": data})

        # Also load JSON spectrum files
        for json_file in spectra_dir.glob("*.json"):
            spectra.append({"name": json_file.stem, "data": self._load_json(json_file)})

        return spectra

    def _load_peaks(self, peaks_dir: Path) -> List[Dict[str, Any]]:
        """Load peaks JSON files from directory."""
        peaks = []

        for json_file in peaks_dir.glob("*.json"):
            data = self._load_json(json_file)
            # Normalize to list format
            if isinstance(data, dict) and "peaks" in data:
                data = data["peaks"]
            peaks.append({"name": json_file.stem, "data": data})

        return peaks

    def _load_derived(self, derived_dir: Path) -> Dict[str, Any]:
        """Load derived data files."""
        derived = {}

        for json_file in derived_dir.glob("*.json"):
            derived[json_file.stem] = self._load_json(json_file)

        return derived

    def cleanup(self):
        """Clean up temporary files."""
        if self._temp_dir and self._temp_dir.exists():
            shutil.rmtree(self._temp_dir, ignore_errors=True)
            self._temp_dir = None

    def __del__(self):
        """Destructor - clean up temp files."""
        self.cleanup()
