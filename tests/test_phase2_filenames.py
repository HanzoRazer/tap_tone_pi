from __future__ import annotations
import pathlib
import subprocess
import sys


def test_phase2_demo_creates_exact_filenames():
    """Ensure Phase-2 demo creates canonical filenames."""
    # Run demo script
    subprocess.check_call([sys.executable, "examples/phase2/make_demo.py"])

    root = pathlib.Path("runs_phase2/DEMO/session_0001")

    # Check all required files exist with exact names
    assert (root / "metadata.json").exists(), "metadata.json missing"
    assert (root / "grid.json").exists(), "grid.json missing"
    assert (root / "capture_meta.json").exists(), "capture_meta.json missing"
    assert (root / "ods_snapshot.json").exists(), "ods_snapshot.json missing"
    assert (root / "wolf_candidates.json").exists(), "wolf_candidates.json missing"


def test_phase2_demo_artifacts_are_valid_json():
    """Ensure demo artifacts parse as valid JSON."""
    import json

    root = pathlib.Path("runs_phase2/DEMO/session_0001")

    for name in [
        "metadata.json",
        "grid.json",
        "capture_meta.json",
        "ods_snapshot.json",
        "wolf_candidates.json",
    ]:
        path = root / name
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            assert isinstance(data, dict), f"{name} is not a JSON object"


def test_phase2_demo_schema_versions_present():
    """Ensure schema_version field is present in key artifacts."""
    import json

    root = pathlib.Path("runs_phase2/DEMO/session_0001")

    for name in ["metadata.json", "ods_snapshot.json", "wolf_candidates.json"]:
        path = root / name
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            assert "schema_version" in data, f"{name} missing schema_version"
