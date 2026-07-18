#!/usr/bin/env python3
# INSTRUMENT CLASS: MEASUREMENT
"""
Phase 2 Viewer Pack Exporter (viewer_pack_v1)

Input:
  runs_phase2/session_YYYYMMDDTHHMMSSZ/

Output (dir or zip):
  viewer_pack_v1/
    manifest.json
    README.txt
    audio/points/<PID>.wav
    spectra/points/<PID>/spectrum.csv
    spectra/points/<PID>/analysis.json
    provenance/points/<PID>/capture_meta.json
    meta/grid.json
    meta/metadata.json
    ods/ods_snapshot.json
    wolf/wolf_candidates.json
    wolf/wsi_curve.csv
    plots/*.png

Phase 2 assumptions:
  - points live in points/point_<PID>/
  - audio is 2-ch wav (ref=ch0, roving=ch1) kept as-is
"""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from zipfile import ZipFile, ZIP_DEFLATED

# Pre-export validation gate
from tap_tone_pi.validate.viewer_pack_v1 import validate_pack, write_validation_report

# Session metadata export
from tap_tone_pi.export_metadata import SessionMetaV1, write_session_meta

# Repeatability evidence (Dev Order 85)
from tap_tone_pi.core.repeatability import RepeatabilityEvidenceV1, MeasurementValidityEnvelopeV1

# Workflow provenance (Dev Order 86)
from tap_tone_pi.workflow.contracts import MeasurementWorkflowContractV1, WorkflowExecutionEvidenceV1

# Experiment provenance (Dev Order 87)
from tap_tone_pi.provenance import ExperimentCampaignV1, ExperimentRevisionV1, MeasurementLineageV1

# Build/environment/fixture provenance (Dev Order 88)
from tap_tone_pi.provenance import BuildSessionV1, EnvironmentRecordV1, FixtureRecordV1

# Campaign lifecycle and measurement sets (Dev Order 89)
from tap_tone_pi.provenance import (
    CampaignLifecycleExportV1,
    MeasurementSetV1,
    MeasurementSetSummaryV1,
)


def extract_session_metadata(session_dir: Path) -> Dict[str, Any]:
    """
    Extract metadata from existing session files.

    Reads from metadata.json, grid.json, and capture_meta.json to populate
    session-level metadata for ToolBox compare UI.
    """
    meta: Dict[str, Any] = {}

    # Try metadata.json (session-level config)
    metadata_file = session_dir / "metadata.json"
    if metadata_file.exists():
        try:
            with open(metadata_file) as f:
                data = json.load(f)
            meta["specimen_id"] = data.get("specimen_id", data.get("sample_id", ""))
            meta["device_id"] = data.get("device_id", "")
            meta["fixture_id"] = data.get("fixture_id", "")
            meta["mic_id"] = data.get("mic_id", "")
            meta["mic_gain_db"] = data.get("mic_gain_db")
            meta["preamp_model"] = data.get("preamp_model")
            meta["sample_rate_hz"] = data.get("sample_rate_hz")
            meta["tap_protocol"] = data.get("tap_protocol", data.get("protocol", ""))
            meta["ambient_notes"] = data.get("ambient_notes", data.get("notes", ""))
        except (json.JSONDecodeError, OSError):
            pass

    # Try grid.json for point count
    grid_file = session_dir / "grid.json"
    if grid_file.exists():
        try:
            with open(grid_file) as f:
                grid = json.load(f)
            points = grid.get("points", [])
            meta["tap_count"] = len(points)
        except (json.JSONDecodeError, OSError):
            pass

    # Count actual point folders if grid.json not available
    if "tap_count" not in meta or meta["tap_count"] is None:
        points_dir = session_dir / "points"
        if points_dir.exists():
            point_count = sum(
                1
                for p in points_dir.iterdir()
                if p.is_dir() and p.name.startswith("point_")
            )
            meta["tap_count"] = point_count

    # Try first capture_meta.json for sample rate if not in metadata.json
    if not meta.get("sample_rate_hz"):
        points_dir = session_dir / "points"
        if points_dir.exists():
            for point_folder in sorted(points_dir.iterdir()):
                cap_meta = point_folder / "capture_meta.json"
                if cap_meta.exists():
                    try:
                        with open(cap_meta) as f:
                            cap = json.load(f)
                        meta["sample_rate_hz"] = cap.get("sample_rate_hz")
                        break
                    except (json.JSONDecodeError, OSError):
                        pass

    # Use session folder name as run_id if not set
    meta["run_id"] = session_dir.name

    return meta


# Canonical kind vocabulary (single source of truth)
# ToolBox viewer dispatches on these exact strings
KIND_VOCAB = {
    "audio_raw",
    "spectrum_csv",
    "analysis_peaks",
    "coherence",
    "transfer_function",  # ODS data (ods_snapshot.json)
    "wolf_candidates",
    "wsi_curve",
    "provenance",
    "plot_png",
    "session_meta",
    "manifest",
    "unknown",
}

KIND_BY_RELPATH_RULES: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"^audio/points/.+\.wav$", re.I), "audio_raw"),
    (re.compile(r"^spectra/points/.+/spectrum\.csv$", re.I), "spectrum_csv"),
    (re.compile(r"^spectra/points/.+/analysis\.json$", re.I), "analysis_peaks"),
    (re.compile(r"^coherence/.+\.json$", re.I), "coherence"),
    (
        re.compile(r"^ods/.+\.json$", re.I),
        "transfer_function",
    ),  # ODS = transfer_function
    (re.compile(r"^wolf/.+candidates\.json$", re.I), "wolf_candidates"),
    (re.compile(r"^wolf/wsi_curve\.csv$", re.I), "wsi_curve"),
    (re.compile(r"^provenance/.+\.json$", re.I), "provenance"),
    (re.compile(r"^plots/.+\.png$", re.I), "plot_png"),
    (re.compile(r"^meta/.+\.json$", re.I), "session_meta"),
]


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def detect_kind(relpath: str) -> str:
    rp = relpath.replace("\\", "/")
    for pat, kind in KIND_BY_RELPATH_RULES:
        if pat.search(rp):
            return kind
    return "unknown"


def guess_mime(path: Path) -> str:
    mt, _ = mimetypes.guess_type(str(path))
    return mt or "application/octet-stream"


def point_id_from_folder(folder_name: str) -> Optional[str]:
    # point_A1 -> A1
    if folder_name.startswith("point_"):
        return folder_name.split("point_", 1)[1]
    return None


@dataclass
class FileEntry:
    relpath: str
    sha256: str
    bytes: int
    mime: str
    kind: str


def copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def write_text(dst: Path, text: str) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(text, encoding="utf-8")


def build_readme(session_dir: Path) -> str:
    return "\n".join(
        [
            "Tap Tone Viewer Pack v1",
            "",
            f"Source session: {session_dir.name}",
            "Contents:",
            "- audio/points/*.wav (2-ch: ch0 reference, ch1 roving)",
            "- spectra/points/*/spectrum.csv (freq_hz,H_mag,coherence,phase_deg)",
            "- spectra/points/*/analysis.json (summary/peaks metadata)",
            "- meta/grid.json + meta/metadata.json",
            "- ods/, wolf/, plots/ as available",
            "",
            "Viewer rule: dispatch by manifest.files[].kind",
            "",
        ]
    )


# -------------------------------------------------------------------------
# Export helpers
# -------------------------------------------------------------------------


def _add_readme(pack_root: Path, session_dir: Path, files: List[FileEntry]) -> None:
    """Add README.txt to pack."""
    readme_text = build_readme(session_dir)
    readme_path = pack_root / "README.txt"
    write_text(readme_path, readme_text)
    files.append(
        FileEntry(
            relpath="README.txt",
            sha256=sha256_file(readme_path),
            bytes=readme_path.stat().st_size,
            mime="text/plain",
            kind="provenance",
        )
    )


def _add_session_meta(
    pack_root: Path,
    session_dir: Path,
    files: List[FileEntry],
    add_file_fn,
) -> None:
    """Add session metadata files (grid.json, metadata.json, session_meta.json)."""
    grid = session_dir / "grid.json"
    metadata = session_dir / "metadata.json"
    if grid.exists():
        add_file_fn(grid, "meta/grid.json")
    if metadata.exists():
        add_file_fn(metadata, "meta/metadata.json")

    # session_meta.json (canonical metadata for ToolBox compare UI)
    extracted = extract_session_metadata(session_dir)
    session_meta = SessionMetaV1(
        specimen_id=extracted.get("specimen_id", ""),
        run_id=extracted.get("run_id", session_dir.name),
        device_id=extracted.get("device_id", ""),
        fixture_id=extracted.get("fixture_id", ""),
        mic_id=extracted.get("mic_id", ""),
        mic_gain_db=extracted.get("mic_gain_db"),
        preamp_model=extracted.get("preamp_model"),
        sample_rate_hz=extracted.get("sample_rate_hz"),
        tap_count=extracted.get("tap_count"),
        tap_protocol=extracted.get("tap_protocol"),
        ambient_notes=extracted.get("ambient_notes"),
    )
    session_meta_path = write_session_meta(pack_root, session_meta)
    files.append(
        FileEntry(
            relpath="meta/session_meta.json",
            sha256=sha256_file(session_meta_path),
            bytes=session_meta_path.stat().st_size,
            mime="application/json",
            kind="session_meta",
        )
    )


def _add_points(
    session_dir: Path,
    add_file_fn,
) -> List[str]:
    """Add point data (audio, spectra, analysis, provenance). Returns point IDs."""
    points_dir = session_dir / "points"
    if not points_dir.exists():
        raise FileNotFoundError(f"Phase2 points/ missing: {points_dir}")

    point_ids: List[str] = []

    for point_folder in sorted([p for p in points_dir.iterdir() if p.is_dir()]):
        pid = point_id_from_folder(point_folder.name)
        if not pid:
            continue
        point_ids.append(pid)

        wav = point_folder / "audio.wav"
        cap = point_folder / "capture_meta.json"
        spectrum = point_folder / "spectrum.csv"
        analysis = point_folder / "analysis.json"

        if wav.exists():
            add_file_fn(wav, f"audio/points/{pid}.wav")
        if spectrum.exists():
            add_file_fn(spectrum, f"spectra/points/{pid}/spectrum.csv")
        if analysis.exists():
            add_file_fn(analysis, f"spectra/points/{pid}/analysis.json")
        if cap.exists():
            add_file_fn(cap, f"provenance/points/{pid}/capture_meta.json")

    return point_ids


def _add_derived(session_dir: Path, add_file_fn) -> None:
    """Add derived artifacts (ods, wolf)."""
    derived_dir = session_dir / "derived"
    if not derived_dir.exists():
        return
    ods = derived_dir / "ods_snapshot.json"
    wc = derived_dir / "wolf_candidates.json"
    wsi = derived_dir / "wsi_curve.csv"
    if ods.exists():
        add_file_fn(ods, "ods/ods_snapshot.json")
    if wc.exists():
        _validate_wolf_candidates_clean(wc)
        add_file_fn(wc, "wolf/wolf_candidates.json")
    if wsi.exists():
        add_file_fn(wsi, "wolf/wsi_curve.csv")


def _add_coherence(session_dir: Path, add_file_fn) -> None:
    """Add coherence data (optional)."""
    coh_dir = session_dir / "coherence"
    if not coh_dir.exists():
        return
    coh = coh_dir / "coherence_summary.json"
    if coh.exists():
        add_file_fn(coh, "coherence/coherence_summary.json")


def _read_bending_moe(session_dir: Path) -> Optional[Dict[str, Any]]:
    """
    Locate and parse bending_moe.json from a session directory.

    Searches these locations in order (most to least specific):
      1. session_dir/bending/bending_moe.json
      2. session_dir/bending_moe.json
      3. session_dir/out/bending_moe.json

    Returns a dict with bending fields ready for the manifest, or None
    if no bending data is present for this session.
    """
    candidates = [
        session_dir / "bending" / "bending_moe.json",
        session_dir / "bending_moe.json",
        session_dir / "out" / "bending_moe.json",
    ]
    for path in candidates:
        if path.exists():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                # Extract fields that map to viewer_pack_v1 bending schema
                result: Dict[str, Any] = {}
                geom = raw.get("geometry", {})
                # Primary E value — use plate-corrected if available, else corrected
                e_gpa = raw.get("E_GPa")
                if e_gpa is not None:
                    # Determine orientation from geometry grain_orientation field
                    orientation = geom.get("grain_orientation", "unknown")
                    if orientation == "longitudinal":
                        result["E_L_GPa"] = round(e_gpa, 4)
                    elif orientation == "cross":
                        result["E_C_GPa"] = round(e_gpa, 4)
                    else:
                        # Unknown orientation — store as E_L by convention
                        result["E_L_GPa"] = round(e_gpa, 4)

                if "density_g_cm3" in raw:
                    result["density_g_cm3"] = round(raw["density_g_cm3"], 4)
                if "specific_modulus_GPa_per_gcm3" in raw:
                    result["specific_modulus_GPa_per_gcm3"] = round(
                        raw["specific_modulus_GPa_per_gcm3"], 4
                    )
                if "c_m_s" in raw:
                    result["c_m_s"] = round(raw["c_m_s"], 2)
                if "span_mm" in geom:
                    result["span_mm"] = geom["span_mm"]
                if "method" in raw:
                    method = raw["method"]
                    # Normalise bending_stiffness_mode.py naming conventions
                    if method in ("three_point_bending", "3point"):
                        result["method"] = "3point"
                    elif method in ("four_point_bending", "4point"):
                        result["method"] = "4point"

                # Orthotropic ratio if both directions present
                e_l = result.get("E_L_GPa")
                e_c = result.get("E_C_GPa")
                if e_l and e_c and e_c > 0:
                    result["orthotropic_ratio"] = round(e_l / e_c, 2)

                result["source_bundle"] = sha256_file(path)

                return result if result else None
            except (json.JSONDecodeError, OSError):
                continue
    return None


def _add_bending(session_dir: Path, add_file_fn) -> Optional[Dict[str, Any]]:
    """
    Add bending measurement files to the pack and return the bending
    manifest dict for embedding in manifest.json.

    Files added (if present):
      bending/bending_moe.json  → bending/bending_moe.json in pack

    Returns the bending dict for the manifest, or None if no bending
    data is available for this session.
    """
    candidates = [
        session_dir / "bending" / "bending_moe.json",
        session_dir / "bending_moe.json",
        session_dir / "out" / "bending_moe.json",
    ]
    for path in candidates:
        if path.exists():
            add_file_fn(path, "bending/bending_moe.json")
            break

    return _read_bending_moe(session_dir)


def _add_plots(session_dir: Path, add_file_fn) -> None:
    """Add plots."""
    plots_dir = session_dir / "plots"
    if not plots_dir.exists():
        return
    for png in sorted(plots_dir.glob("*.png")):
        add_file_fn(png, f"plots/{png.name}")


def _add_timeline(session_dir: Path, add_file_fn) -> None:
    """Add session timeline (PR #17, fail-closed)."""
    try:
        from tap_tone_pi.core.session_timeline import export_session_timeline

        tl_path = export_session_timeline(session_dir)
        if tl_path is not None and tl_path.is_file():
            add_file_fn(tl_path, "meta/session_timeline_v1.json")
    except (ImportError, OSError, ValueError, KeyError):
        pass  # Non-fatal: pack is valid without timeline


def _read_repeatability(session_dir: Path, add_file_fn) -> Optional[Dict[str, Any]]:
    """
    Read repeatability evidence from session (Dev Order 85).

    Searches for repeatability_evidence.json or measurement_validity_envelope.json
    in the session directory or derived folder.

    Returns dict for manifest embedding, or None if not present.
    """
    candidates = [
        session_dir / "derived" / "repeatability_evidence.json",
        session_dir / "repeatability_evidence.json",
        session_dir / "derived" / "measurement_validity_envelope.json",
        session_dir / "measurement_validity_envelope.json",
    ]

    for path in candidates:
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                # Add to pack
                if "repeatability" in path.name:
                    add_file_fn(path, "meta/repeatability_evidence.json")
                else:
                    add_file_fn(path, "meta/measurement_validity_envelope.json")
                return data
            except (json.JSONDecodeError, OSError):
                continue

    return None


def _read_workflow_provenance(
    session_dir: Path, add_file_fn
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Read workflow contract and execution evidence from session (Dev Order 86).

    Searches for workflow_contract.json and workflow_execution.json
    in the session directory or meta folder.

    Returns (contract_dict, execution_dict) tuple, either may be None.
    """
    contract_data = None
    execution_data = None

    # Look for workflow contract
    contract_candidates = [
        session_dir / "meta" / "workflow_contract.json",
        session_dir / "workflow_contract.json",
    ]
    for path in contract_candidates:
        if path.exists():
            try:
                contract_data = json.loads(path.read_text(encoding="utf-8"))
                add_file_fn(path, "meta/workflow_contract.json")
                break
            except (json.JSONDecodeError, OSError):
                continue

    # Look for workflow execution evidence
    execution_candidates = [
        session_dir / "meta" / "workflow_execution.json",
        session_dir / "workflow_execution.json",
        session_dir / "derived" / "workflow_execution.json",
    ]
    for path in execution_candidates:
        if path.exists():
            try:
                execution_data = json.loads(path.read_text(encoding="utf-8"))
                add_file_fn(path, "meta/workflow_execution.json")
                break
            except (json.JSONDecodeError, OSError):
                continue

    return contract_data, execution_data


def _read_experiment_provenance(
    session_dir: Path, add_file_fn
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Read experiment provenance from session (Dev Order 87).

    Searches for experiment_campaign.json, experiment_revision.json, and
    measurement_lineage.json in the session directory or meta folder.

    Returns (campaign_dict, revision_dict, lineage_dict) tuple, any may be None.
    """
    campaign_data = None
    revision_data = None
    lineage_data = None

    # Look for experiment campaign
    campaign_candidates = [
        session_dir / "meta" / "experiment_campaign.json",
        session_dir / "experiment_campaign.json",
    ]
    for path in campaign_candidates:
        if path.exists():
            try:
                campaign_data = json.loads(path.read_text(encoding="utf-8"))
                add_file_fn(path, "meta/experiment_campaign.json")
                break
            except (json.JSONDecodeError, OSError):
                continue

    # Look for experiment revision
    revision_candidates = [
        session_dir / "meta" / "experiment_revision.json",
        session_dir / "experiment_revision.json",
    ]
    for path in revision_candidates:
        if path.exists():
            try:
                revision_data = json.loads(path.read_text(encoding="utf-8"))
                add_file_fn(path, "meta/experiment_revision.json")
                break
            except (json.JSONDecodeError, OSError):
                continue

    # Look for measurement lineage
    lineage_candidates = [
        session_dir / "meta" / "measurement_lineage.json",
        session_dir / "measurement_lineage.json",
    ]
    for path in lineage_candidates:
        if path.exists():
            try:
                lineage_data = json.loads(path.read_text(encoding="utf-8"))
                add_file_fn(path, "meta/measurement_lineage.json")
                break
            except (json.JSONDecodeError, OSError):
                continue

    return campaign_data, revision_data, lineage_data


def _read_build_context_provenance(
    session_dir: Path, add_file_fn
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Read build context provenance from session (Dev Order 88).

    Searches for build_session.json, environment_record.json, and
    fixture_record.json in the session directory or meta folder.

    Returns (build_session_dict, environment_dict, fixture_dict) tuple, any may be None.
    """
    build_session_data = None
    environment_data = None
    fixture_data = None

    # Look for build session
    build_candidates = [
        session_dir / "meta" / "build_session.json",
        session_dir / "build_session.json",
    ]
    for path in build_candidates:
        if path.exists():
            try:
                build_session_data = json.loads(path.read_text(encoding="utf-8"))
                add_file_fn(path, "meta/build_session.json")
                break
            except (json.JSONDecodeError, OSError):
                continue

    # Look for environment record
    environment_candidates = [
        session_dir / "meta" / "environment_record.json",
        session_dir / "environment_record.json",
    ]
    for path in environment_candidates:
        if path.exists():
            try:
                environment_data = json.loads(path.read_text(encoding="utf-8"))
                add_file_fn(path, "meta/environment_record.json")
                break
            except (json.JSONDecodeError, OSError):
                continue

    # Look for fixture record
    fixture_candidates = [
        session_dir / "meta" / "fixture_record.json",
        session_dir / "fixture_record.json",
    ]
    for path in fixture_candidates:
        if path.exists():
            try:
                fixture_data = json.loads(path.read_text(encoding="utf-8"))
                add_file_fn(path, "meta/fixture_record.json")
                break
            except (json.JSONDecodeError, OSError):
                continue

    return build_session_data, environment_data, fixture_data


def _read_campaign_lifecycle_provenance(
    session_dir: Path, add_file_fn
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Read campaign lifecycle and measurement set provenance from session (Dev Order 89).

    Searches for campaign_lifecycle.json, measurement_set.json, and
    measurement_set_summary.json in the session directory or meta folder.

    Returns (lifecycle_dict, set_dict, summary_dict) tuple, any may be None.
    """
    lifecycle_data = None
    measurement_set_data = None
    measurement_set_summary_data = None

    # Look for campaign lifecycle
    lifecycle_candidates = [
        session_dir / "meta" / "campaign_lifecycle.json",
        session_dir / "campaign_lifecycle.json",
    ]
    for path in lifecycle_candidates:
        if path.exists():
            try:
                lifecycle_data = json.loads(path.read_text(encoding="utf-8"))
                add_file_fn(path, "meta/campaign_lifecycle.json")
                break
            except (json.JSONDecodeError, OSError):
                continue

    # Look for measurement set
    measurement_set_candidates = [
        session_dir / "meta" / "measurement_set.json",
        session_dir / "measurement_set.json",
    ]
    for path in measurement_set_candidates:
        if path.exists():
            try:
                measurement_set_data = json.loads(path.read_text(encoding="utf-8"))
                add_file_fn(path, "meta/measurement_set.json")
                break
            except (json.JSONDecodeError, OSError):
                continue

    # Look for measurement set summary
    summary_candidates = [
        session_dir / "meta" / "measurement_set_summary.json",
        session_dir / "measurement_set_summary.json",
    ]
    for path in summary_candidates:
        if path.exists():
            try:
                measurement_set_summary_data = json.loads(path.read_text(encoding="utf-8"))
                add_file_fn(path, "meta/measurement_set_summary.json")
                break
            except (json.JSONDecodeError, OSError):
                continue

    return lifecycle_data, measurement_set_data, measurement_set_summary_data


def _read_experiment_design_provenance(
    session_dir: Path, add_file_fn
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Read experiment design provenance from session (Dev Order 89A).

    Searches for experiment_design.json and design_validation.json
    in the session directory or meta folder.

    Returns (design_dict, validation_dict) tuple, either may be None.
    """
    design_data = None
    validation_data = None

    # Look for experiment design
    design_candidates = [
        session_dir / "meta" / "experiment_design.json",
        session_dir / "experiment_design.json",
    ]
    for path in design_candidates:
        if path.exists():
            try:
                design_data = json.loads(path.read_text(encoding="utf-8"))
                add_file_fn(path, "meta/experiment_design.json")
                break
            except (json.JSONDecodeError, OSError):
                continue

    # Look for design validation evidence
    validation_candidates = [
        session_dir / "meta" / "design_validation.json",
        session_dir / "design_validation.json",
    ]
    for path in validation_candidates:
        if path.exists():
            try:
                validation_data = json.loads(path.read_text(encoding="utf-8"))
                add_file_fn(path, "meta/design_validation.json")
                break
            except (json.JSONDecodeError, OSError):
                continue

    return design_data, validation_data


def _read_cohort_regression_provenance(
    session_dir: Path, add_file_fn
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Read cohort regression provenance from session (Dev Order 89C).

    Searches for cohort_regression_evidence.json and formula_candidate_evidence.json
    in the session directory or meta folder.

    Returns (regression_dict, formula_dict) tuple, either may be None.
    """
    regression_data = None
    formula_data = None

    # Look for cohort regression evidence
    regression_candidates = [
        session_dir / "meta" / "cohort_regression_evidence.json",
        session_dir / "cohort_regression_evidence.json",
    ]
    for path in regression_candidates:
        if path.exists():
            try:
                regression_data = json.loads(path.read_text(encoding="utf-8"))
                add_file_fn(path, "meta/cohort_regression_evidence.json")
                break
            except (json.JSONDecodeError, OSError):
                continue

    # Look for formula candidate evidence
    formula_candidates = [
        session_dir / "meta" / "formula_candidate_evidence.json",
        session_dir / "formula_candidate_evidence.json",
    ]
    for path in formula_candidates:
        if path.exists():
            try:
                formula_data = json.loads(path.read_text(encoding="utf-8"))
                add_file_fn(path, "meta/formula_candidate_evidence.json")
                break
            except (json.JSONDecodeError, OSError):
                continue

    return regression_data, formula_data


def _read_luthiery_formula_provenance(
    session_dir: Path, add_file_fn
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Read luthiery formula target provenance from session (Dev Order 94).

    Searches for luthiery_formula_target.json and
    luthiery_formula_evidence_link.json in the session directory or meta folder.

    These blocks are additive and optional — historical exports without them
    remain valid. They carry declarative luthiery domain meaning, never
    advisory or prescriptive content.

    Returns (target_dict, link_dict) tuple, either may be None.
    """
    target_data = None
    link_data = None

    target_candidates = [
        session_dir / "meta" / "luthiery_formula_target.json",
        session_dir / "luthiery_formula_target.json",
    ]
    for path in target_candidates:
        if path.exists():
            try:
                target_data = json.loads(path.read_text(encoding="utf-8"))
                add_file_fn(path, "meta/luthiery_formula_target.json")
                break
            except (json.JSONDecodeError, OSError):
                continue

    link_candidates = [
        session_dir / "meta" / "luthiery_formula_evidence_link.json",
        session_dir / "luthiery_formula_evidence_link.json",
    ]
    for path in link_candidates:
        if path.exists():
            try:
                link_data = json.loads(path.read_text(encoding="utf-8"))
                add_file_fn(path, "meta/luthiery_formula_evidence_link.json")
                break
            except (json.JSONDecodeError, OSError):
                continue

    return target_data, link_data


def _read_formula_validation_provenance(
    session_dir: Path, add_file_fn
) -> Optional[Dict[str, Any]]:
    """
    Read formula validation envelope from session (Dev Order 95).

    Searches for formula_validation_envelope.json in the session directory or
    meta folder.

    This block is additive and optional — historical exports without it remain
    valid. It records evidence sufficiency and detectable failure modes; it
    carries no advisory or pass/fail content.

    Returns the envelope dict, or None if not present.
    """
    candidates = [
        session_dir / "meta" / "formula_validation_envelope.json",
        session_dir / "formula_validation_envelope.json",
    ]
    for path in candidates:
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                add_file_fn(path, "meta/formula_validation_envelope.json")
                return data
            except (json.JSONDecodeError, OSError):
                continue
    return None


def _build_manifest(
    files: List[FileEntry],
    session_dir: Path,
    point_ids: List[str],
    bending_data: Optional[Dict[str, Any]] = None,
    repeatability_data: Optional[Dict[str, Any]] = None,
    workflow_contract: Optional[Dict[str, Any]] = None,
    workflow_execution: Optional[Dict[str, Any]] = None,
    experiment_campaign: Optional[Dict[str, Any]] = None,
    experiment_revision: Optional[Dict[str, Any]] = None,
    measurement_lineage: Optional[Dict[str, Any]] = None,
    build_session: Optional[Dict[str, Any]] = None,
    environment_record: Optional[Dict[str, Any]] = None,
    fixture_record: Optional[Dict[str, Any]] = None,
    campaign_lifecycle: Optional[Dict[str, Any]] = None,
    measurement_set: Optional[Dict[str, Any]] = None,
    measurement_set_summary: Optional[Dict[str, Any]] = None,
    experiment_design: Optional[Dict[str, Any]] = None,
    design_validation_evidence: Optional[Dict[str, Any]] = None,
    cohort_regression_evidence: Optional[Dict[str, Any]] = None,
    formula_candidate_evidence: Optional[Dict[str, Any]] = None,
    luthiery_formula_target: Optional[Dict[str, Any]] = None,
    luthiery_formula_evidence_link: Optional[Dict[str, Any]] = None,
    formula_validation_envelope: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build manifest dict and compute bundle_sha256."""
    manifest: Dict[str, Any] = {
        "schema_version": "v1",
        "schema_id": "viewer_pack_v1",
        "created_at_utc": utc_now_iso(),
        "source_capdir": session_dir.name,
        "detected_phase": "phase2",
        "measurement_only": True,
        "interpretation": "deferred",
        "points": point_ids,
        "contents": {
            "audio":      any(e.relpath.startswith("audio/")      for e in files),
            "spectra":    any(e.relpath.startswith("spectra/")    for e in files),
            "coherence":  any(e.relpath.startswith("coherence/")  for e in files),
            "ods":        any(e.relpath.startswith("ods/")        for e in files),
            "wolf":       any(e.relpath.startswith("wolf/")       for e in files),
            "plots":      any(e.relpath.startswith("plots/")      for e in files),
            "provenance": any(e.relpath.startswith("provenance/") for e in files),
            "bending":    any(e.relpath.startswith("bending/")    for e in files),
        },
        "files": [
            {
                "relpath": e.relpath,
                "sha256":  e.sha256,
                "bytes":   e.bytes,
                "mime":    e.mime,
                "kind":    e.kind,
            }
            for e in sorted(files, key=lambda x: x.relpath)
        ],
    }

    # Embed bending data when present — critical input for inverse brace engine
    if bending_data:
        manifest["bending"] = bending_data

    # Embed repeatability evidence when present (Dev Order 85)
    if repeatability_data:
        manifest["repeatability"] = repeatability_data

    # Embed workflow provenance when present (Dev Order 86)
    if workflow_contract:
        manifest["workflow_contract"] = workflow_contract
    if workflow_execution:
        manifest["workflow_execution"] = workflow_execution

    # Embed experiment provenance when present (Dev Order 87)
    if experiment_campaign:
        manifest["experiment_campaign"] = experiment_campaign
    if experiment_revision:
        manifest["experiment_revision"] = experiment_revision
    if measurement_lineage:
        manifest["measurement_lineage"] = measurement_lineage

    # Embed build context provenance when present (Dev Order 88)
    if build_session:
        manifest["build_session"] = build_session
    if environment_record:
        manifest["environment_record"] = environment_record
    if fixture_record:
        manifest["fixture_record"] = fixture_record

    # Embed campaign lifecycle and measurement sets when present (Dev Order 89)
    if campaign_lifecycle:
        manifest["campaign_lifecycle"] = campaign_lifecycle
    if measurement_set:
        manifest["measurement_set"] = measurement_set
    if measurement_set_summary:
        manifest["measurement_set_summary"] = measurement_set_summary

    # Experiment design provenance (DO-89A)
    if experiment_design:
        manifest["experiment_design"] = experiment_design
    if design_validation_evidence:
        manifest["design_validation_evidence"] = design_validation_evidence

    # Cohort regression provenance (DO-89C)
    if cohort_regression_evidence:
        manifest["cohort_regression_evidence"] = cohort_regression_evidence
    if formula_candidate_evidence:
        manifest["formula_candidate_evidence"] = formula_candidate_evidence

    # Luthiery formula target provenance (DO-94) — additive, declarative only
    if luthiery_formula_target:
        manifest["luthiery_formula_target"] = luthiery_formula_target
    if luthiery_formula_evidence_link:
        manifest["luthiery_formula_evidence_link"] = luthiery_formula_evidence_link

    # Formula validation envelope (DO-95) — additive, evidence-only, no pass/fail
    if formula_validation_envelope:
        manifest["formula_validation_envelope"] = formula_validation_envelope

    # bundle sha = sha256 of manifest JSON bytes (before adding bundle_sha256)
    manifest_bytes = json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8")
    bundle_sha = sha256_bytes(manifest_bytes)
    manifest["bundle_sha256"] = bundle_sha

    return manifest


def _validate_and_gate(pack_root: Path, manifest_path: Path) -> None:
    """Run validation and raise on failure."""
    viewer_pack_json = pack_root / "viewer_pack.json"
    if not viewer_pack_json.exists():
        shutil.copy2(manifest_path, viewer_pack_json)

    report = validate_pack(pack_root)
    report_path = write_validation_report(pack_root, report)

    if not report.passed:
        excerpt = []
        for e in (report.errors or [])[:3]:
            rule = e.get("rule", "?")
            msg = e.get("message", "")
            path = e.get("path")
            if path:
                excerpt.append(f"{rule}: {msg} ({path})")
            else:
                excerpt.append(f"{rule}: {msg}")

        excerpt_txt = "; ".join(excerpt) if excerpt else "No error details available."
        raise ValueError(
            f"viewer_pack_v1 validation failed: "
            f"errors={len(report.errors)} warnings={len(report.warnings)}. "
            f"{excerpt_txt}. "
            f"See {report_path}"
        )


def _zip_pack(pack_root: Path, out_dir: Path, session_dir: Path) -> Path:
    """Create zip archive of pack."""
    zip_path = out_dir / f"{session_dir.name}__viewer_pack_v1.zip"
    if zip_path.exists():
        zip_path.unlink()
    with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as z:
        for fp in pack_root.rglob("*"):
            if fp.is_file():
                arc = fp.relative_to(pack_root.parent).as_posix()
                z.write(fp, arcname=arc)
    return zip_path


# -------------------------------------------------------------------------
# Main export function
# -------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Wolf candidates purity gate (ADR-0009)
# ---------------------------------------------------------------------------

#: Fields that indicate WolfAdvisor output has leaked into wolf_candidates.json.
#: These are decision-support fields and must never appear in viewer_pack_v1.
_PROHIBITED_WOLF_ADVISORY_FIELDS = frozenset({
    "mitigation_suggestions",
    "recommendations",
    "advisor_output",
    "mitigations",
    "recommended_action",
    "confidence_level",   # WolfAdvisor.ConfidenceLevel
    "mitigation_type",    # WolfAdvisor.MitigationType
    "wolf_directive",
    "directive_id",
})


def _validate_wolf_candidates_clean(wc_path: Path) -> None:
    """
    Assert wolf_candidates.json contains no advisory fields.

    Raises ValueError if any WolfAdvisor-specific field is present.
    This is a hard stop — the export fails rather than silently
    contaminating the bundle with decision-support data.

    See docs/ADR-0009-advisory-boundary.md §3.
    """
    try:
        data = json.loads(wc_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return  # Parse errors are caught by other validators

    if not isinstance(data, dict):
        return

    # Check top-level keys
    found_top = _PROHIBITED_WOLF_ADVISORY_FIELDS & set(data.keys())

    # Also check inside a "wolf_candidates" or "candidates" list if present
    found_nested: set[str] = set()
    for candidate_key in ("wolf_candidates", "candidates", "results"):
        candidates = data.get(candidate_key, [])
        if isinstance(candidates, list):
            for item in candidates:
                if isinstance(item, dict):
                    found_nested |= _PROHIBITED_WOLF_ADVISORY_FIELDS & set(item.keys())

    found = found_top | found_nested
    if found:
        raise ValueError(
            f"wolf_candidates.json contains advisory fields: {sorted(found)}. "
            f"WolfAdvisor output (WolfAdvisor.get_recommendations(), "
            f"generate_wolf_directive()) must not appear in viewer_pack_v1. "
            f"Route advisory output to the agentic spine (AttentionDirectiveV1) "
            f"instead. See docs/ADR-0009-advisory-boundary.md"
        )


def export_viewer_pack(
    session_dir: Path,
    out_dir: Path,
    *,
    as_zip: bool,
) -> Path:
    if not session_dir.exists():
        raise FileNotFoundError(f"session_dir not found: {session_dir}")

    # Initialize pack root
    pack_root = out_dir / "viewer_pack_v1"
    if pack_root.exists():
        shutil.rmtree(pack_root)
    pack_root.mkdir(parents=True, exist_ok=True)

    files: List[FileEntry] = []

    def add_file(src: Path, relpath: str):
        dst = pack_root / relpath
        copy_file(src, dst)
        entry = FileEntry(
            relpath=relpath.replace("\\", "/"),
            sha256=sha256_file(dst),
            bytes=dst.stat().st_size,
            mime=guess_mime(dst),
            kind=detect_kind(relpath),
        )
        files.append(entry)

    # Add pack components
    _add_readme(pack_root, session_dir, files)
    _add_session_meta(pack_root, session_dir, files, add_file)
    point_ids = _add_points(session_dir, add_file)
    _add_derived(session_dir, add_file)
    _add_coherence(session_dir, add_file)
    bending_data = _add_bending(session_dir, add_file)
    repeatability_data = _read_repeatability(session_dir, add_file)
    workflow_contract, workflow_execution = _read_workflow_provenance(session_dir, add_file)
    experiment_campaign, experiment_revision, measurement_lineage = _read_experiment_provenance(session_dir, add_file)
    build_session, environment_record, fixture_record = _read_build_context_provenance(session_dir, add_file)
    campaign_lifecycle, measurement_set, measurement_set_summary = _read_campaign_lifecycle_provenance(session_dir, add_file)
    experiment_design, design_validation_evidence = _read_experiment_design_provenance(session_dir, add_file)
    cohort_regression_evidence, formula_candidate_evidence = _read_cohort_regression_provenance(session_dir, add_file)
    luthiery_formula_target, luthiery_formula_evidence_link = _read_luthiery_formula_provenance(session_dir, add_file)
    formula_validation_envelope = _read_formula_validation_provenance(session_dir, add_file)
    _add_plots(session_dir, add_file)
    _add_timeline(session_dir, add_file)

    # Build and write manifest
    manifest = _build_manifest(
        files, session_dir, point_ids, bending_data, repeatability_data,
        workflow_contract, workflow_execution,
        experiment_campaign, experiment_revision, measurement_lineage,
        build_session, environment_record, fixture_record,
        campaign_lifecycle, measurement_set, measurement_set_summary,
        experiment_design, design_validation_evidence,
        cohort_regression_evidence, formula_candidate_evidence,
        luthiery_formula_target, luthiery_formula_evidence_link,
        formula_validation_envelope
    )
    manifest_path = pack_root / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )

    # Validate
    _validate_and_gate(pack_root, manifest_path)

    # Zip if requested
    if as_zip:
        return _zip_pack(pack_root, out_dir, session_dir)

    return pack_root


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Export Phase 2 session to viewer_pack_v1 format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument(
        "--session-dir", required=True, help="runs_phase2/session_*/ directory"
    )
    ap.add_argument("--out", required=True, help="output directory for pack or zip")
    ap.add_argument("--zip", action="store_true", help="emit a .zip bundle")
    args = ap.parse_args()

    session_dir = Path(args.session_dir).resolve()
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    result = export_viewer_pack(session_dir, out_dir, as_zip=args.zip)
    print(f"[viewer-pack] wrote: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
