#!/usr/bin/env python3
"""
two_channel_coherence.py  (MERGED: includes --write-plots)

Phase 2 starter: 2-channel synchronous capture + coherence + delay + phase.
Optionally writes inspection plots (PNG) into the bundle.

Outputs (in a capture_<ts>/ folder under --out):
- audio.wav                (2-channel PCM WAV)
- analysis.json            (includes cross_channel: delay/coherence/phase)
- spectrum.csv             (freq_hz,ch0_mag,ch1_mag)
- channels.json            (optional minimal channel mapping)
- geometry.json            (optional simple geometry stub)
- coherence.png            (optional if --write-plots)
- phase_deg.png            (optional if --write-plots)
- spectrum.png             (optional if --write-plots)
- waveform.png             (optional if --write-plots)
- session.jsonl            (append-only log at --out root)

Notes:
- Requires a *single* 2-input audio interface / device with shared clock.
- Two separate USB mics will not remain phase-stable.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import sounddevice as sd
from scipy.fft import rfft, rfftfreq
from scipy.io import wavfile
from scipy.signal import butter, filtfilt, coherence, csd, correlate

# plotting is optional; import unconditionally for simplicity
import matplotlib.pyplot as plt


# ----------------------------
# Utility
# ----------------------------
def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")


def _append_jsonl(path: Path, obj: Any) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, sort_keys=True))
        f.write("\n")


def list_devices() -> list[dict[str, Any]]:
    devs = sd.query_devices()
    out: list[dict[str, Any]] = []
    for i, d in enumerate(devs):
        out.append(
            {
                "index": i,
                "name": d.get("name"),
                "max_input_channels": int(d.get("max_input_channels") or 0),
                "default_samplerate": d.get("default_samplerate"),
            }
        )
    return out


def _highpass(x: np.ndarray, fs: int, hz: float) -> np.ndarray:
    if hz <= 0:
        return x
    nyq = 0.5 * fs
    w = hz / nyq
    b, a = butter(2, w, btype="highpass")
    return filtfilt(b, a, x).astype(np.float32)


def _rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(x * x)))


def _is_clipped(x: np.ndarray) -> bool:
    return bool(np.any(np.abs(x) >= 0.999))


def _normalize_spec(spec: np.ndarray) -> np.ndarray:
    m = float(np.max(spec)) if spec.size else 0.0
    return (spec / m).astype(np.float32) if m > 0 else spec.astype(np.float32)


def _dominant_peak(freqs: np.ndarray, mag: np.ndarray, fmin: float, fmax: float) -> float | None:
    if freqs.size == 0:
        return None
    mask = (freqs >= fmin) & (freqs <= fmax)
    if not np.any(mask):
        return None
    idx = int(np.argmax(mag[mask]))
    freqs_m = freqs[mask]
    return float(freqs_m[idx])


def _downsample_series(f: np.ndarray, y: np.ndarray, max_points: int) -> list[dict[str, float]]:
    if f.size == 0:
        return []
    if f.size <= max_points:
        idxs = np.arange(f.size)
    else:
        idxs = np.linspace(0, f.size - 1, num=max_points).astype(int)
    return [{"freq_hz": float(f[i]), "value": float(y[i])} for i in idxs]


# ----------------------------
# Plot helpers
# ----------------------------
def _save_line_plot(
    *,
    out_path: Path,
    x: np.ndarray,
    y: np.ndarray,
    title: str,
    xlabel: str,
    ylabel: str,
    xlim: tuple[float, float] | None = None,
    ylim: tuple[float, float] | None = None,
) -> None:
    fig = plt.figure(figsize=(10, 4))
    ax = fig.add_subplot(111)
    ax.plot(x, y)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    if xlim is not None:
        ax.set_xlim(*xlim)
    if ylim is not None:
        ax.set_ylim(*ylim)
    fig.tight_layout()
    fig.savefig(out_path, dpi=160)
    # copy raw for waveform plotting later (pre-filter)
    raw0 = audio_2ch[:, 0].astype(np.float32)
    raw1 = audio_2ch[:, 1].astype(np.float32)

    x0 = raw0 - float(np.mean(raw0))
    x1 = raw1 - float(np.mean(raw1))

    x: np.ndarray,
    y0: np.ndarray,
    y1: np.ndarray,
    title: str,
    xlabel: str,raw0), _is_clipped(raw
    ylabel: str,
    labels: tuple[str, str] = ("ch0", "ch1"),
    xlim: tuple[float, float] | None = None,
    ylim: tuple[float, float] | None = None,
) -> None:
    fig = plt.figure(figsize=(10, 4))
    ax = fig.add_subplot(111)
    ax.plot(x, y0, label=labels[0])
    ax.plot(x, y1, label=labels[1])
    ax.legend()
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    if xlim is not None:
        ax.set_xlim(*xlim)
    if ylim is not None:
        ax.set_ylim(*ylim)
    fig.tight_layout()
    fig.savefig(out_path, dpi=160)
    plt.close(fig)


def write_plots_from_arrays(
    *,
    cap_dir: Path,
    max_hz: float,
    freqs_fft: np.ndarray,
    ch0_mag: np.ndarray,
    ch1_mag: np.ndarray,
    x_time_s: np.ndarray,
    ch0_time: np.ndarray,
    ch1_time: np.ndarray,
    coh_f: np.ndarray,
    coh: np.ndarray,
    ph_f: np.ndarray,
    ph_deg: np.ndarray,
) -> None:
    # coherence.png
    _save_line_plot(
        out_path=cap_dir / "coherence.png",
        x=coh_f,
        y=coh,
        title="Magnitude-Squared Coherence (ch0 vs ch1)",
        xlabel="Frequency (Hz)",
        ylabel="Coherence",
        if (rms0 > 0.005 and rms1 > 0.005):
            conf = min(1.0, 0.4 + 0.6 * max(0.0, min(1.0, coh_mean_focus)))
        elif (rms0 > 0.01 or rms1 > 0.01):
            conf = 0.25

    # Downsample coherence/phase series for JSON size
    coh_series = _downsample_series(f_coh, coh, coherence_max_points)
    ph_series = _fft,
        y0=ch0_mag,
        y1=ch1_mag,
        title="Spectrum (normalized)",
        xlabel="Frequency (Hz)",
        ylabel="Magnitude",
        xlim=(0.0, float(max_hz)),
        labels=("ch0", "ch1"),
    )

    # waveform.png
    _save_two_line_plot(
        out_path=cap_dir / "waveform.png",
        x=x_time_s,
        y0=ch0_time,
        y1=ch1_time,
        title="Waveform (ch0, ch1)",
        xlabel="Time (s)",
        ylabel="Amplitude",
        labels=("ch0", "ch1"),
    )


# ----------------------------
# Capture
# ----------------------------
@dataclass(frozen=True)
class Capture2Ch:
    sample_rate: int
    audio: np.ndarray  # shape (n,2) float32 [-1,1]


def record_2ch(*, device: int, sample_rate: int, seconds: float) -> Capture2Ch:
    sd.default.samplerate = sample_rate
    sd.default.device = (device, None)

    n_samples = int(sample_rate * seconds)
    audio = sd.rec(frames=n_samples, channels=2, dtype="float32", blocking=True)
    audio = np.nan_to_num(audio, nan=0.0)
    return Capture2Ch(sample_rate=sample_rate, audio=audio)


# ----------------------------
# Analysis
# ----------------------------
def analyze_2ch(
    audio_2ch: np.ndarray,
    fs: int,
    *,
    highpass_hz: float = 20.0,
    peak_min_hz: float = 40.0,
    peak_max_hz: float = 2000.0,
    coherence_nperseg: int = 4096,
    coherence_max_points: int = 300,  # downsample for json size
    band_focus: tuple[float, float] = (60.0, 600.0),  # typical low-mode band
) -> dict[str, Any]:
    if audio_2ch.ndim != 2 or audio_2ch.shape[1] != 2:
        raise ValueError("Expected audio shape (n,2)")

    x0 = audio_2ch[:, 0].astype(np.float32)
    x1 = audio_2ch[:, 1].astype(np.float32)

    # DC removal + highpass (same filter both channels)
    x0 = x0 - float(np.mean(x0))
    x1 = x1 - float(np.mean(x1))
    x0 = _highpass(x0, fs, highpass_hz)
    x1 = _highpass(x1, fs, highpass_hz)

    # Health metrics
    rms0, rms1 = _rms(x0), _rms(x1)
    clip0, clip1 = _is_clipped(x0), _is_clipped(x1)

    # FFT (for spectra output + dominant freq)
    w = np.hanning(x0.size).astype(np.float32)
    X0 = np.abs(rfft(x0 * w)).astype(np.float32)
    X1 = np.abs(rfft(x1 * w)).astype(np.float32)
    freqs = rfftfreq(x0.size, d=1.0 / fs).astype(np.float32)

    X0n = _normalize_spec(X0)
    X1n = _normalize_spec(X1)

    dom0 = _dominant_peak(freqs, X0n, peak_min_hz, peak_max_hz)
    dom1 = _dominant_peak(freqs, X1n, peak_min_hz, peak_max_hz)

    # Coherence (magnitude-squared)
    nperseg = int(min(coherence_nperseg, x0.size))
    if nperseg < 256:
        nperseg = max(128, nperseg)

    f_coh, coh = coherence(x0, x1, fs=fs, nperseg=nperseg)
    f_coh = f_coh.astype(np.float32)
    coh = coh.astype(np.float32)

    # Phase difference using cross spectral density
    f_csd, Pxy = csd(x0, x1, fs=fs, nperseg=nperseg)
    f_csd = f_csd.astype(np.float32)
    phase = np.angle(Pxy).astype(np.float32)  # radians
    phase_deg = (phase * (180.0 / math.pi)).astype(np.float32)

    # Time delay estimate via cross-correlation (broadband)
    # Positive delay means x1 lags x0 by delay_samples.
    corr = correlate(x1, x0, mode="full", method="auto")
    lag = int(np.argmax(corr) - (x0.size - 1))
    delay_samples = lag
    delay_seconds = float(delay_samples / fs)

    # Focus-band coherence summary
    f_lo, f_hi = band_focus
    mask_focus = (f_coh >= f_lo) & (f_coh <= f_hi)
    coh_mean_focus = float(np.mean(coh[mask_focus])) if np.any(mask_focus) else float(np.mean(coh)) if coh.size else 0.0

    # Confidence heuristic (conservative)
    conf = 0.0
    if clip0 or clip1:
        conf = 0.0
    else:
        # require signal above floor + coherence in focus band
        if (rms0 > 0.005 and rms1 > 0.005):
            conf = min(1.0, 0.4 + 0.6 * max(0.0, min(1.0, coh_mean_focus)))
        elif (rms0 > 0.01 or rms1 > 0.01):
            conf = 0.25

    # Downsample coherence/phase series for JSON size (keep shape)
    def downsample_series(f: np.ndarray, y: np.ndarray, max_points: int) -> list[dict[str, float]]:
        if f.size == 0:
            return []
        if f.size <= max_points:
            idxs = np.arange(f.size)
        else:
            idxs = np.linspace(0, f.size - 1, num=max_points).astype(int)
        out = [{"freq_hz": float(f[i]), "value": float(y[i])} for i in idxs]
        return out

    coh_series = downsample_series(f_coh, coh, coherence_max_points)
    ph_series = downsample_series(f_csd, phase_deg, coherence_max_points)

    analysis: dict[str, Any] = {
        "sample_rate": int(fs),
        "channels": 2,
        "dominant_hz": dom0 if dom0 is not None else dom1,
        "rms": [rms0, rms1],
        "clipped": [clip0, clip1],
        "confidence": float(conf),
        "peaks": {
            "ch0": [{"freq_hz": dom0, "magnitude": None}] if dom0 is not None else [],
            "ch1": [{"freq_hz": dom1, "magnitude": None}] if dom1 is not None else [],
        },
        "cross_channel": {
            "pair": [0, 1],
            "delay_samples": int(delay_samples),
            "delay_seconds": float(delay_seconds),
            "coherence_focus_band_hz": [float(f_lo), float(f_hi)],
            "coherence_focus_mean": float(coh_mean_focus),
            "coherence": coh_series,
            "phase_deg": ph_series,
        },
        "algo": {
            "version": "0.2.0-phase2",
            "window": "hann",
            "highpass_hz": float(highpass_hz),
            "peak_min_hz": float(peak_min_hz),
            "peak_max_hz": float(peak_max_hz),
            "coherence_nperseg": int(nperseg),
        },
    }

    spectra = {
        "freqs": freqs,1-phase2-plots",
            "window": "hann",
            "highpass_hz": float(highpass_hz),
            "peak_min_hz": float(peak_min_hz),
            "peak_max_hz": float(peak_max_hz),
            "coherence_nperseg": int(nperseg),
        },
    }

    return {
        "analysis": analysis,
        "spectra": {"freqs": freqs, "ch0_mag": X0n, "ch1_mag": X1n},
        "series": {
            "coh_f": f_coh,
            "coh": coh,
            "ph_f": f_csd,
            "ph_deg": phase_deg,
        },
        "waveform": {
            "raw
# ----------------------------
def persist_bundle(
    *,
    out_root: Path,
    label: str | None,
    cap: Capture2Ch,
    analysis: dict[str, Any],
    freqs: np.ndarray,
    ch0_mag: np.ndarray,
    ch1_mag: np.ndarray,
    write_channels: bool,
    write_geometry: bool,
    mic_distance_mm: float | None,
    write_plots: bool,
    plot_max_hz: float,
    plot_payload: dict[str, Any]
    ts = dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    cap_dir = out_root / f"capture_{ts}"
    _ensure_dir(cap_dir)

    # audio.wav
    wav_path = cap_dir / "audio.wav"
    x = np.clip(cap.audio, -1.0, 1.0)
    x_i16 = (x * 32767.0).astype(np.int16)
    wavfile.write(str(wav_path), cap.sample_rate, x_i16)

    # analysis.json
    analysis_path = cap_dir / "analysis.json"
    analysis_out = dict(analysis)
    analysis_out["ts_utc"] = dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    analysis_out["label"] = label
    _write_json(analysis_path, analysis_out)

    lines = ["freq_hz,ch0_mag,ch1_mag\n"]
    for i in range(freqs.size):
        lines.append(f"{float(freqs[i]):.6f},{float(ch0_mag[i]):.8f},{float(ch1_mag
    for i in range(f.size):
        lines.append(f"{float(f[i]):.6f},{float(m0[i]):.8f},{float(m1[i]):.8f}\n")
    spec_path.write_text("".join(lines), encoding="utf-8")

    # optional channels.json
    if write_channels:
        channels_path = cap_dir / "channels.json"
        _write_json(
            channels_path,
            {
                "channels": [
                    {"index": 0, "id": "mic_0", "type": "microphone", "role": "reference"},
                    {"index": 1, "id": "mic_1", "type": "microphone", "role": "secondary"},
                ]
            },
        )

    # optional geometry.json (simple stub)
    if write_geometry:
        geom_path = cap_dir / "geometry.json"
        z = float(mic_distance_mm) if mic_distance_mm is not None else 300.0
        _write_json(
            geom_path,
            {
                "coordinate_system": "instrument_body",
                "units": "mm",
                "origin": "bridge_center",
                "microphones": [
                    {"id": "mic_0", "position": [0.0, 0.0, z], "estimated": True},
                    {"id": "mic_1", "position": [120.0, 40.0, z], "estimated": True},
                ],
            },
        )

    # session.jsonl (append-only at out_root)
    session_log = out_root / "session.jsonl"
    _append_jsonl(
        session_log,
        {
            "ts_utc": ts,
            "label": label,
            "capture_dir": str(cap_dir),
            "dominant_hz": analysis_out.get("dominant_hz"),
            "confidence": analysis_out.get("confidence"),
            "clipped": analysis_out.get("clipped"),
            "rms": analysis_out.get("rms"),
            "cross_delay_s": analysis_out.get("cross_channel", {}).get("delay_seconds"),
            "coherence_focus_mean": analysis_out.get("cross_channel", {}).get("coherence_focus_mean"),
        },(analysis_out.get("cross_channel") or {}).get("delay_seconds"),
            "coherence_focus_mean": (analysis_out.get("cross_channel") or {}).get("coherence_focus_mean"),
        },
    )

    # Optional plots (computed from arrays, not by re-reading files)
    if write_plots:
        if plot_payload is None:
            raise RuntimeError("write_plots=True requires plot_payload.")
        n = plot_payload["raw0"].size
        t = (np.arange(n, dtype=np.float32) / float(cap.sample_rate)).astype(np.float32)

        write_plots_from_arrays().")

    sub = ap.add_subparsers(dest="cmd", required=True)

    p_dev = sub.add_parser("devices", help="List audio input devices")
    p_dev.add_argument("--all", action="store_true", help="Show devices even if no input channels")

    p_run = sub.add_parser("run", help="Capture 2ch audio and compute coherence/delay/phase")
    p_run.add_argument("--device", type=int, required=True, help="Input device index with >=2 inputs")
    p_run.add_argument("--sample-rate", type=int, default=48000)
    p_run.add_argument("--seconds", type=float, default=2.5)
    p_run.add_argument("--label", type=str, default=None)
    p_run.add_argument("--out", type=str, required=True, help="Output root directory")
    p_run.add_argument("--highpass-hz", type=float, default=20.0)
    p_run.add_argument("--peak-min-hz", type=float, default=40.0)
    p_run.add_argument("--peak-max-hz", type=float, default=2000.0)
    p_run.add_argument("--nperseg", type=int, default=4096)
    p_run.add_argument("--coh-max-points", type=int, default=300)
    p_run.add_argument("--focus-band", type=str, default="60,600", help="e.g. '60,600' Hz")
    p_run.add_argument("--write-channels", action="store_true", help="Write channels.json stub")
    p_run.add_argument("--write-geometry", action="store_true", help="Write geometry.json stub")
    p_run.add_argument("--mic-distance-mm", type=float, default=None, help="If writing geometry, set z distance")

    # NEW: plots
    p_run.add_argument("--write-plots", action="store_true", help="Write coherence/phase/spectrum/waveform PNGs")
    p_run.add_argument("--plot-max-hz", type=float, default=1500.0, help="Max frequency to show in plots")

    args = ap.parse_args()

    if args.cmd == "devices":
        devs = list_devices()
        for d in devs:
            if (not args.all) and (d["max_input_channels"] <= 0):
                continue
            print(f'[{d["index"]}] {d["name"]} (in={d["max_input_channels"]}, default_sr={d["default_samplerate"]})')
        return

    if args.cmd == "run":
        f0, f1 = [float(x.strip()) for x in args.focus_band.split(",")]
        if f0 <= 0 or f1 <= 0 or f1 <= f0:
            raise SystemExit("Invalid --focus-band. Use like '60,600' with 0 < f0 < f1.")
        if args.plot_max_hz <= 0:
            raise SystemExit("--plot-max-hz must be > 0")

        # quick device sanity
        dev = sd.query_devices(args.device)
        if int(dev.get("max_input_channels") or 0) < 2:
            raise SystemExit(f"Device {args.device} has <2 input channels: {dev.get('name')}
    p_run.add_argument("--coh-max-points", type=int, default=300)
    p_run.add_argument("--focus-band", type=str, default="60,600", help="e.g. '60,600' Hz")
    p_run.add_argument("--write-channels", action="store_true", help="Write channels.json stub")
    p_run.add_argument("--write-geometry", action="store_true", help="Write geometry.json stub")
    p_run.add_argument("--mic-distance-mm", type=float, default=None, help="If writing geometry, set z distance")

    argsfreqs = out["spectra"]["freqs"]
        ch0_mag = out["spectra"]["ch0_mag"]
        ch1_mag = out["spectra"]["ch1_mag"]

        # Human summary
        dom = analysis.get("dominant_hz")
        rms = analysis.get("rms")
        clipped = analysis.get("clipped")
        conf = analysis.get("confidence")
        cc = analysis.get("cross_channel", {})
        print("")
        print(f"Dominant: {dom} Hz")
        print(f"RMS: ch0={rms[0]:.6f} ch1={rms[1]:.6f}  Clipped: {clipped}  Conf: {conf:.2f}")
        print(f"Delay: {cc.get('delay_seconds')} s  (samples={cc.get('delay_samples')})")
        print(f"Coherence mean [{f0:.0f},{f1:.0f}] Hz: {cc.get('coherence_focus_mean'):.3f}")
        print("")

        out_root = Path(args.out).expanduser().resolve()
        plot_payload = None
        if args.write_plots:
            plot_payload = {
                "raw0": out["waveform"]["raw0"],
                "raw1": out["waveform"]["raw1"],
                "coh_f": out["series"]["coh_f"],
                "coh": out["series"]["coh"],
                "ph_f": out["series"]["ph_f"],
                "ph_deg": out["series"]["ph_deg"],
            }

        cap_dir = persist_bundle(
            out_root=out_root,
            label=args.label,
            cap=cap,
            analysis=analysis,
            freqs=freqs,
            ch0_mag=ch0_mag,
            ch1_mag=ch1_mag,
            write_channels=args.write_channels,
            write_geometry=args.write_geometry,
            mic_distance_mm=args.mic_distance_mm,
            write_plots=args.write_plots,
            plot_max_hz=args.plot_max_hz,
            plot_payload=plot_payload,
        )
        print(f"[OK] Wrote bundle: {cap_dir}")
        if args.write_plots:
            print("      + coherence.png, phase_deg.png, spectrum.png, waveform.pngx_points,
            band_focus=(f0, f1),
        )

        analysis = out["analysis"]
        spectra = out["spectra"]

        # Human summary
        dom = analysis.get("dominant_hz")
        rms = analysis.get("rms")
        clipped = analysis.get("clipped")
        conf = analysis.get("confidence")
        cc = analysis.get("cross_channel", {})
        print("")
        print(f"Dominant: {dom} Hz")
        print(f"RMS: ch0={rms[0]:.6f} ch1={rms[1]:.6f}  Clipped: {clipped}  Conf: {conf:.2f}")
        print(f"Delay: {cc.get('delay_seconds')} s  (samples={cc.get('delay_samples')})")
        print(f"Coherence mean [{f0:.0f},{f1:.0f}] Hz: {cc.get('coherence_focus_mean'):.3f}")
        print("")

        out_root = Path(args.out).expanduser().resolve()
        cap_dir = persist_bundle(
            out_root=out_root,
            label=args.label,
            cap=cap,
            analysis=analysis,
            spectra=spectra,
            write_channels=args.write_channels,
            write_geometry=args.write_geometry,
            mic_distance_mm=args.mic_distance_mm,
        )
        print(f"[OK] Wrote bundle: {cap_dir}")
        return

    raise SystemExit("Unknown command")


if __name__ == "__main__":
    main()
