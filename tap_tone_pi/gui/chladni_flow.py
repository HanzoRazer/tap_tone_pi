"""
Chladni pattern analysis wizard for tap_tone_pi GUI.

Extracted from App class in app.py. Standalone function that
receives the App instance for outdir/run_id access.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
from tkinter import filedialog, messagebox, simpledialog


def do_chladni_wizard(app) -> None:
    """
    Chladni pattern analysis wizard:
    1) Ask for a sweep/stepped-tone WAV
    2) Run peaks_from_wav.py → peaks.json
    3) Multi-select Chladni images (F####.png/JPG filenames embed Hz)
    4) Ask Plate ID + (optional) Temp/RH
    5) Run index_patterns.py → chladni_run.json
    6) Emit manifest.json for the Chladni set
    """
    ROOT = pathlib.Path(__file__).resolve().parents[2]

    try:
        run_dir = app.outdir() / "chladni"
        run_dir.mkdir(parents=True, exist_ok=True)

        # 1) Pick WAV
        wav_path = filedialog.askopenfilename(
            title="Select Chladni sweep WAV",
            filetypes=[("WAV files", "*.wav"), ("All files", "*.*")],
        )
        if not wav_path:
            return

        peaks_json = run_dir / "peaks.json"

        # 2) Run peaks_from_wav.py
        cmd_peaks = [
            sys.executable,
            "-m",
            "tap_tone_pi.chladni.peaks_from_wav",
            "--wav",
            wav_path,
            "--out",
            peaks_json.as_posix(),
            "--min-hz",
            "50",
            "--max-hz",
            "2000",
            "--prominence",
            "0.02",
        ]
        subprocess.check_call(cmd_peaks, cwd=str(ROOT))

        # 3) Pick images (multi-select)
        img_paths = filedialog.askopenfilenames(
            title="Select Chladni pattern images (name like F0148.png)",
            filetypes=[
                ("Images", "*.png;*.jpg;*.jpeg;*.PNG;*.JPG;*.JPEG"),
                ("All files", "*.*"),
            ],
        )
        if not img_paths:
            messagebox.showwarning(
                "No images selected",
                "Peaks were extracted, but no images were chosen.",
            )
            return

        # 4) Plate ID + Env
        default_plate = f"{app.run_id.get()}_PLATE"
        plate_id = (
            simpledialog.askstring(
                "Plate ID", "Enter plate ID:", initialvalue=default_plate
            )
            or default_plate
        )

        try:
            temp_str = simpledialog.askstring(
                "Temperature (C)",
                "Enter temperature C (optional):",
                initialvalue="",
            )
            temp_c = float(temp_str) if temp_str else None
        except (TypeError, ValueError):
            temp_c = None

        try:
            rh_str = simpledialog.askstring(
                "RH (%)", "Enter relative humidity % (optional):", initialvalue=""
            )
            rh = float(rh_str) if rh_str else None
        except (TypeError, ValueError):
            rh = None

        chladni_run_json = run_dir / "chladni_run.json"

        # 5) Run index_patterns.py
        cmd_idx = [
            sys.executable,
            "-m",
            "tap_tone_pi.chladni.index_patterns",
            "--peaks-json",
            peaks_json.as_posix(),
            "--plate-id",
            plate_id,
            "--out",
            chladni_run_json.as_posix(),
            "--images",
        ]
        cmd_idx += [pathlib.Path(p).as_posix() for p in img_paths]
        if temp_c is not None:
            cmd_idx += ["--tempC", str(temp_c)]
        if rh is not None:
            cmd_idx += ["--rh", str(rh)]

        subprocess.check_call(cmd_idx, cwd=str(ROOT))

        # 6) Emit manifest
        manifest_json = run_dir / "manifest.json"
        art_args = [
            "--artifact",
            peaks_json.as_posix(),
            "--artifact",
            chladni_run_json.as_posix(),
            "--artifact",
            pathlib.Path(wav_path).as_posix(),
        ]
        for p in img_paths:
            art_args += ["--artifact", pathlib.Path(p).as_posix()]

        rig_kvs = ["--rig", f"plate_id={plate_id}"]
        notes = ["--notes", f"Chladni v1 wizard (run={app.outdir().name})"]

        cmd_manifest = [
            sys.executable,
            "modes/_shared/emit_manifest.py",
            "--out",
            manifest_json.as_posix(),
            *art_args,
            *rig_kvs,
            *notes,
        ]
        subprocess.check_call(cmd_manifest, cwd=str(ROOT))

        messagebox.showinfo(
            "Chladni v1",
            f"Peaks: {peaks_json}\nRun: {chladni_run_json}\nManifest: {manifest_json}",
        )

    except subprocess.CalledProcessError as e:
        messagebox.showerror(
            "Chladni wizard failed", f"Step failed with exit code {e.returncode}"
        )
    except Exception as ex:
        messagebox.showerror("Chladni wizard error", str(ex))
