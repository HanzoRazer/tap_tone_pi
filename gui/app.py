#!/usr/bin/env python3
"""
tap_tone_pi — Minimal GUI (Tkinter), measurement-only.

Runs:
- Tap-tone (live / offline WAV)
- Bending stiffness → MOE (single / batch)
- Provenance hash
- Load cell capture (serial) → load_series.json
- Dial indicator capture (serial) → displacement_series.json
- Emit manifest.json

No advisory or design logic. Facts only.
"""
from __future__ import annotations
import tkinter as tk
from tkinter import filedialog, messagebox
import subprocess, shlex, pathlib, datetime, os

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
DATA = ROOT / "data"

def run(cmd: str):
    try:
        print("> " + cmd)
        subprocess.check_call(shlex.split(cmd))
        messagebox.showinfo("Done", f"Ran:\n{cmd}")
    except subprocess.CalledProcessError as e:
        messagebox.showerror("Error", f"Command failed ({e.returncode}):\n{cmd}")

def default_run_id():
    return datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("tap_tone_pi — Measurement GUI")
        self.geometry("640x520")
        self.run_id = tk.StringVar(value=default_run_id())

        frm = tk.Frame(self); frm.pack(fill="both", expand=True, padx=10, pady=10)

        # Run ID
        rrow = tk.Frame(frm); rrow.pack(fill="x", pady=4)
        tk.Label(rrow, text="Run ID (folder under out/)").pack(side="left")
        tk.Entry(rrow, textvariable=self.run_id, width=20).pack(side="left", padx=6)

        # --- Tap-tone live
        group(frm, "Tap-tone (live)", [
            ("Duration (s)", "4"), ("Sample rate", "44100")
        ], self.do_tap_live)

        # --- Tap-tone offline
        self.wav_path = tk.StringVar(value=str((DATA/"sample_tap.wav").as_posix()))
        group_file(frm, "Tap-tone (offline WAV)", self.wav_path, self.do_tap_offline)

        # --- MOE single
        self.single_vals = {
            "method":"3point", "span":"400", "width":"20",
            "thickness":"3.0", "force":"5.0", "deflection":"0.62", "density":""
        }
        group(frm, "Bending → MOE (single)", [
            ("Method (3point/4point)", self.single_vals["method"]),
            ("Span mm", self.single_vals["span"]),
            ("Width mm", self.single_vals["width"]),
            ("Thickness mm", self.single_vals["thickness"]),
            ("Force N", self.single_vals["force"]),
            ("Deflection mm", self.single_vals["deflection"]),
            ("Density g/cm^3 (optional)", self.single_vals["density"]),
        ], self.do_moe_single, binds=self.single_vals)

        # --- MOE batch
        self.csv_path = tk.StringVar(value=str((ROOT/"data/deflection_runs.csv").as_posix()))
        group_file(frm, "Bending → MOE (batch CSV)", self.csv_path, self.do_moe_batch)

        # --- Provenance hash
        self.prov_path = tk.StringVar(value=str((ROOT/"data/grain_field.png").as_posix()))
        group_file(frm, "Provenance import (hash only)", self.prov_path, self.do_provenance)

        # --- Load cell capture
        self.load_cfg = tk.StringVar(value=str((ROOT/"config/devices/loadcell_example.json").as_posix()))
        group_file(frm, "Load cell capture (serial) → load_series.json", self.load_cfg, self.do_loadcell)

        # --- Dial indicator capture
        self.dial_port = tk.StringVar(value="COM3" if os.name=="nt" else "/dev/ttyUSB0")
        group_entry(frm, "Dial indicator serial port", self.dial_port, self.do_dial)

        # --- Manifest
        tk.Button(frm, text="Emit manifest.json (hash everything in out/<RunID>)", command=self.do_manifest, width=50).pack(pady=6)

    def outdir(self) -> pathlib.Path:
        p = OUT / self.run_id.get().strip()
        p.mkdir(parents=True, exist_ok=True)
        return p

    # callbacks
    def do_tap_live(self, vals):
        outdir = self.outdir()
        dur, sr = vals[0].get(), vals[1].get()
        cmd = f"python modes/tap_tone/tap_fft_logger.py --outfile {outdir/'tap_tone.json'} --plot {outdir/'spectrum.png'} --duration {dur} --sr {sr} --labels A0 T11 B11"
        run(cmd)

    def do_tap_offline(self, path_var):
        outdir = self.outdir()
        cmd = f"python modes/tap_tone/offline_from_wav.py --wav {path_var.get()} --outfile {outdir/'tap_tone_offline.json'} --labels A0 T11 B11"
        run(cmd)

    def do_moe_single(self, binds):
        outdir = self.outdir()
        b = binds
        cmd = f"python modes/bending_stiffness/deflection_to_moe.py --method {b['method']} --span {b['span']} --width {b['width']} --thickness {b['thickness']} --force {b['force']} --deflection {b['deflection']} --out {outdir/'bending_test.json'}"
        if b['density'].strip():
            cmd += f" --density {b['density']}"
        run(cmd)

    def do_moe_batch(self, path_var):
        outdir = self.outdir()
        cmd = f"python modes/bending_stiffness/deflection_to_moe.py --csv {path_var.get()} --out {outdir/'moe_results.csv'}"
        run(cmd)

    def do_provenance(self, path_var):
        outdir = self.outdir()
        cmd = f"python modes/provenance_import/attach_grain_provenance.py --file {path_var.get()} --out {outdir/'provenance.json'}"
        run(cmd)

    def do_loadcell(self, cfg_var):
        outdir = self.outdir()
        cmd = f"python modes/acquisition/loadcell_serial.py --config {cfg_var.get()} --out {outdir/'load_series.json'}"
        run(cmd)

    def do_dial(self, port_var):
        outdir = self.outdir()
        cmd = f"python modes/acquisition/dial_indicator_serial.py --port {port_var.get()} --out {outdir/'displacement_series.json'}"
        run(cmd)

    def do_manifest(self):
        outdir = self.outdir()
        # include all JSON/CSV/PNG/WAV in the run folder
        artifacts = []
        for p in sorted(outdir.glob("*")):
            if p.suffix.lower() in {".json",".csv",".png",".wav"}:
                artifacts += ["--artifact", p.as_posix()]
        rig = ["--rig", "operator=Shop"]
        cmd = ["python","modes/_shared/emit_manifest.py","--out", (outdir/"manifest.json").as_posix(), *artifacts, *rig]
        run(" ".join(shlex.quote(c) for c in cmd))

def group(parent, title, fields, callback, binds=None):
    f = tk.LabelFrame(parent, text=title); f.pack(fill="x", pady=4)
    entries = []
    for label, default in fields:
        row = tk.Frame(f); row.pack(fill="x")
        tk.Label(row, text=label, width=28, anchor="w").pack(side="left")
        var = None
        if isinstance(default, str):
            var = tk.StringVar(value=default)
            tk.Entry(row, textvariable=var, width=16).pack(side="left")
        else:
            var = tk.StringVar(value=str(default))
            tk.Entry(row, textvariable=var, width=16).pack(side="left")
        entries.append(var)
        if binds and isinstance(binds, dict):
            # map by normalized key name if present
            key = label.split()[0].lower()
            for k in list(binds.keys()):
                if k.startswith(key):
                    binds[k] = var.get()
    tk.Button(f, text="Run", command=lambda: callback(entries if not binds else binds)).pack(pady=3)

def group_file(parent, title, path_var, callback):
    f = tk.LabelFrame(parent, text=title); f.pack(fill="x", pady=4)
    row = tk.Frame(f); row.pack(fill="x")
    tk.Entry(row, textvariable=path_var, width=48).pack(side="left")
    tk.Button(row, text="Browse", command=lambda: path_var.set(filedialog.askopenfilename() or path_var.get())).pack(side="left", padx=6)
    tk.Button(f, text="Run", command=lambda: callback(path_var)).pack(pady=3)

def group_entry(parent, title, var, callback):
    f = tk.LabelFrame(parent, text=title); f.pack(fill="x", pady=4)
    row = tk.Frame(f); row.pack(fill="x")
    tk.Entry(row, textvariable=var, width=32).pack(side="left")
    tk.Button(f, text="Run", command=lambda: callback(var)).pack(pady=3)

if __name__ == "__main__":
    App().mainloop()
