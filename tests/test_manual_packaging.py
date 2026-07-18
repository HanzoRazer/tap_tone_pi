# INSTRUMENT CLASS: MEASUREMENT
"""Isolated wheel-packaging verification for the Laboratory Manual (DO-97G).

A test that reads package data from the source checkout proves nothing about an
installed distribution. These tests build a real wheel, install it into an
isolated ``--target`` directory, and import ``tap_tone_pi`` from a subprocess
whose import resolution is confined to that directory (repository root removed
from ``sys.path``, ``PYTHONSAFEPATH`` set). They then assert the import origin is
the isolated install — not the checkout — and that the packaged manual manifest
and README ship and load through the public registry API.

Skips only when the packaging toolchain itself is unavailable, with a reason.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        **kw,
    )


@pytest.fixture(scope="module")
def built_wheel(tmp_path_factory) -> Path:
    """Build a wheel from the repository into an isolated wheelhouse (P-01)."""
    out = tmp_path_factory.mktemp("wheelhouse")

    # Prefer `python -m build`; fall back to `pip wheel`. Use no build isolation
    # so the build backend resolves from this interpreter (no network needed).
    attempts = [
        [
            sys.executable,
            "-m",
            "build",
            "--wheel",
            "--no-isolation",
            "--outdir",
            str(out),
            str(_REPO_ROOT),
        ],
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--no-build-isolation",
            "-w",
            str(out),
            str(_REPO_ROOT),
        ],
    ]

    errors: list[str] = []
    for cmd in attempts:
        proc = _run(cmd)
        if proc.returncode == 0:
            break
        errors.append(f"$ {' '.join(cmd[1:3])} ...\n{proc.stdout}\n{proc.stderr}")
    else:
        pytest.skip("wheel build toolchain unavailable:\n" + "\n---\n".join(errors))

    wheels = list(out.glob("tap_tone_pi-*.whl")) + list(out.glob("tap_tone*.whl"))
    if not wheels:
        pytest.skip(f"no tap_tone_pi wheel produced in {out}: {list(out.iterdir())}")
    return wheels[0]


@pytest.fixture(scope="module")
def installed_target(built_wheel, tmp_path_factory) -> Path:
    """Install the wheel into an isolated --target directory (P-02)."""
    target = tmp_path_factory.mktemp("isolated_site")
    proc = _run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-deps",
            "--target",
            str(target),
            str(built_wheel),
        ]
    )
    if proc.returncode != 0:
        pytest.skip(f"isolated install failed:\n{proc.stdout}\n{proc.stderr}")
    return target


def _run_isolated(target: Path, code: str, cwd: Path) -> subprocess.CompletedProcess:
    """Run Python with import resolution confined to ``target``.

    ``PYTHONSAFEPATH`` keeps cwd/script-dir off ``sys.path`` and ``PYTHONPATH``
    is set to only the isolated target, so the repository checkout cannot be
    imported by accident. cwd is outside the repository.
    """
    env = dict(os.environ)
    env["PYTHONPATH"] = str(target)
    env["PYTHONSAFEPATH"] = "1"
    env.pop("PYTHONHOME", None)
    return _run([sys.executable, "-P", "-c", code], cwd=str(cwd), env=env)


class TestIsolatedWheelPackaging:
    def test_wheel_is_built(self, built_wheel):  # P-01
        assert built_wheel.suffix == ".whl"
        assert built_wheel.is_file()

    def test_isolated_install_lands_package(self, installed_target):  # P-02
        assert (installed_target / "tap_tone_pi" / "__init__.py").is_file()

    def test_packaged_resources_present_on_disk(self, installed_target):  # P-05
        manual = installed_target / "tap_tone_pi" / "acoustic_lab" / "manual"
        assert (manual / "manual_manifest.json").is_file()
        assert (manual / "README.md").is_file()

    def test_import_origin_is_isolated_target(self, installed_target, tmp_path):  # P-03
        code = "import tap_tone_pi, json; print(json.dumps(tap_tone_pi.__file__))"
        proc = _run_isolated(installed_target, code, cwd=tmp_path)
        assert proc.returncode == 0, proc.stderr
        origin = Path(json.loads(proc.stdout.strip())).resolve()
        assert origin.is_relative_to(installed_target.resolve()), origin
        assert not origin.is_relative_to(_REPO_ROOT), origin

    def test_packaged_manifest_loads_via_public_api(
        self, installed_target, tmp_path
    ):  # P-04
        code = (
            "import json\n"
            "from importlib import resources\n"
            "import tap_tone_pi\n"
            "from tap_tone_pi.acoustic_lab import load_laboratory_manual_manifest\n"
            "root = resources.files('tap_tone_pi.acoustic_lab') / 'manual'\n"
            "m = load_laboratory_manual_manifest()\n"
            "print(json.dumps({\n"
            "    'origin': tap_tone_pi.__file__,\n"
            "    'manifest_file': (root / 'manual_manifest.json').is_file(),\n"
            "    'readme_file': (root / 'README.md').is_file(),\n"
            "    'schema': m.schema_version,\n"
            "    'entry_count': len(m.entries),\n"
            "}))\n"
        )
        proc = _run_isolated(installed_target, code, cwd=tmp_path)
        assert proc.returncode == 0, proc.stderr
        data = json.loads(proc.stdout.strip())
        assert Path(data["origin"]).resolve().is_relative_to(installed_target.resolve())
        assert data["manifest_file"] is True
        assert data["readme_file"] is True
        assert data["schema"] == "laboratory_manual_manifest_v1"
        # Ships empty by design; the empty manifest must load as valid.
        assert data["entry_count"] == 0
