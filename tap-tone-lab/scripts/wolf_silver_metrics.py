#!/usr/bin/env python3
"""
wolf_silver_metrics.py

Compute "silver idea" boundary-stress metrics from a roving-grid bundle:
  - E∇(f): amplitude gradient energy (on log|H|)
  - Eφ(f): phase gradient energy (wrapped phase)
  - L(f): localization index
  - WSI(f): wolf susceptibility index = L * sqrt(E∇) * sqrt(Eφ)

Inputs (bundle directory):
  - grid.json (required)
      {
        "units": "mm",
        "points": [
          {"label":"P01","x_mm":0.0,"y_mm":0.0, ...}, ...
        ]
      }

  - per-point frequency response data (required):
    The script supports either NPZ or JSON per point:

    Preferred NPZ:
      analysis/point_<LABEL>.npz with arrays:
        - freq_hz: float array (N,)
        - H_re: float array (N,)
        - H_im: float array (N,)
        - coh: float array (N,)   (optional; if missing -> all 1.0)

    Alternate JSON:
      analysis/point_<LABEL>.json with keys:
        - freq_hz: [..]
        - H_re: [..]
        - H_im: [..]
        - coh: [..] (optional)

Outputs:
  - derived/wsi_curve.csv
  - derived/wolf_candidates.json
  - plots/wsi_curve.png
  - plots/stress_map_amp_fXXXX.png
  - plots/stress_map_phase_fXXXX.png

Usage:
  python scripts/wolf_silver_metrics.py --bundle ./captures/run_001 \
    --radius-mm 60 --coh-min 0.8 --top-n 5 --freq-min 40 --freq-max 600

Notes:
- Coherence gating: points with coh < coh_min at a frequency are down-weighted (or excluded).
- Adjacency: either radius graph or k-nearest neighbors (choose one).
- Designed for N ~ 20–500 points. O(N^2) neighbor build is acceptable at this scale.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional

import numpy as np

# matplotlib is used only to write PNGs (headless OK)
import matplotlib.pyplot as plt

try:
    from scipy.signal import find_peaks
except Exception:
    find_peaks = None  # optional


EPS = 1e-12


# ----------------------------
# Utilities
# ----------------------------

def read_json(p: Path) -> dict[str, Any]:
    return json.loads(p.read_text(encoding="utf-8"))

def write_json(p: Path, obj: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")

def wrap_pi(x: np.ndarray) -> np.ndarray:
    """Wrap to [-pi, pi]."""
    return (x + np.pi) % (2 * np.pi) - np.pi

def safe_label(label: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in label)

def ensure_dirs(bundle: Path) -> tuple[Path, Path]:
    derived = bundle / "derived"
    plots = bundle / "plots"
    derived.mkdir(parents=True, exist_ok=True)
    plots.mkdir(parents=True, exist_ok=True)
    return derived, plots


# ----------------------------
# Bundle loading
# ----------------------------

def load_grid(bundle: Path) -> list[dict[str, Any]]:
    grid_path = bundle / "grid.json"
    if not grid_path.exists():
        raise FileNotFoundError(f"Missing required {grid_path}")
    grid = read_json(grid_path)
    pts = grid.get("points")
    if not isinstance(pts, list) or not pts:
        raise ValueError("grid.json missing non-empty points[]")
    # normalize x_mm/y_mm if present else fall back to x/y
    out = []
    for p in pts:
        if not isinstance(p, dict) or "label" not in p:
            continue
        label = str(p["label"])
        x = p.get("x_mm", p.get("x"))
        y = p.get("y_mm", p.get("y"))
        if x is None or y is None:
            raise ValueError(f"grid point {label} missing coordinates")
        out.append({"label": label, "x_mm": float(x), "y_mm": float(y)})
    if not out:
        raise ValueError("grid.json produced zero usable points")
    return out

def load_point_response(bundle: Path, label: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Returns (freq_hz, H_complex, coh).
    """
    analysis_dir = bundle / "analysis"
    if not analysis_dir.exists():
        raise FileNotFoundError(f"Missing required directory {analysis_dir}")

    base = analysis_dir / f"point_{safe_label(label)}"
    npz_path = base.with_suffix(".npz")
    json_path = base.with_suffix(".json")

    if npz_path.exists():
        d = np.load(npz_path)
        freq = np.asarray(d["freq_hz"], dtype=np.float64)
        H = np.asarray(d["H_re"], dtype=np.float64) + 1j * np.asarray(d["H_im"], dtype=np.float64)
        coh = np.asarray(d["coh"], dtype=np.float64) if "coh" in d.files else np.ones_like(freq)
        return freq, H, coh

    if json_path.exists():
        d = read_json(json_path)
        freq = np.asarray(d["freq_hz"], dtype=np.float64)
        H = np.asarray(d["H_re"], dtype=np.float64) + 1j * np.asarray(d["H_im"], dtype=np.float64)
        coh = np.asarray(d.get("coh", [1.0] * len(freq)), dtype=np.float64)
        return freq, H, coh

    raise FileNotFoundError(f"Missing point response for {label}: expected {npz_path} or {json_path}")

def align_frequency_axes(freqs: list[np.ndarray], *, tol_hz: float = 1e-6) -> np.ndarray:
    """
    Enforce identical frequency axis across points.
    If minor float noise exists, we snap to the first axis when within tol.
    """
    ref = freqs[0].astype(np.float64)
    for i, f in enumerate(freqs[1:], start=1):
        if f.shape != ref.shape:
            raise ValueError(f"Frequency axis mismatch: point 0 has {ref.shape}, point {i} has {f.shape}")
        if np.max(np.abs(f - ref)) > tol_hz:
            raise ValueError("Frequency axes differ beyond tolerance. Ensure all point files share the same freq_hz.")
    return ref


# ----------------------------
# Adjacency building
# ----------------------------

def build_edges_radius(xy: np.ndarray, radius_mm: float) -> list[tuple[int, int, float]]:
    """
    Returns edges as (i, j, dist_mm), i<j, within radius.
    """
    n = xy.shape[0]
    edges: list[tuple[int, int, float]] = []
    r2 = radius_mm * radius_mm
    for i in range(n):
        dx = xy[i, 0] - xy[i+1:, 0]
        dy = xy[i, 1] - xy[i+1:, 1]
        d2 = dx*dx + dy*dy
        js = np.where(d2 <= r2)[0]
        for jj in js:
            j = i + 1 + int(jj)
            dist = float(math.sqrt(float(d2[jj])))
            edges.append((i, j, dist))
    if not edges:
        raise ValueError("Radius adjacency produced zero edges. Increase --radius-mm or verify grid spacing.")
    return edges

def build_edges_knn(xy: np.ndarray, k: int) -> list[tuple[int, int, float]]:
    """
    Symmetric kNN graph (approx) computed by O(N^2) distances.
    Returns unique undirected edges (i<j).
    """
    n = xy.shape[0]
    if k <= 0:
        raise ValueError("k must be > 0")
    # distances matrix
    d = np.sqrt(((xy[:, None, :] - xy[None, :, :]) ** 2).sum(axis=2))
    edges_set = set()
    for i in range(n):
        idx = np.argsort(d[i, :])
        # skip self at idx[0]
        nbrs = [int(j) for j in idx[1:k+1]]
        for j in nbrs:
            a, b = (i, j) if i < j else (j, i)
            edges_set.add((a, b))
    edges: list[tuple[int, int, float]] = []
    for a, b in sorted(edges_set):
        edges.append((a, b, float(d[a, b])))
    if not edges:
        raise ValueError("kNN adjacency produced zero edges.")
    return edges


# ----------------------------
# Silver metrics computation
# ----------------------------

def compute_metrics(
    H: np.ndarray,            # shape (P, F) complex
    coh: np.ndarray,          # shape (P, F) float in [0,1]
    edges: list[tuple[int, int, float]],
    *,
    coh_min: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Returns Egrad(F), Ephi(F), L(F), WSI(F).
    Coherence gating weights points and edges per frequency.
    """
    P, F = H.shape
    mag = np.abs(H).astype(np.float64)
    phase = np.angle(H).astype(np.float64)

    # log amplitude for stability
    a = np.log(mag + EPS)

    # point weights: 0..1
    w = (coh - coh_min) / max(EPS, (1.0 - coh_min))
    w = np.clip(w, 0.0, 1.0)

    Egrad = np.zeros(F, dtype=np.float64)
    Ephi = np.zeros(F, dtype=np.float64)

    # Edge-based energies
    for (i, j, _dist) in edges:
        wi = w[i, :]
        wj = w[j, :]
        wij = wi * wj
        if np.all(wij <= 0):
            continue

        da = (a[i, :] - a[j, :])
        dphi = wrap_pi(phase[i, :] - phase[j, :])

        Egrad += wij * (da * da)
        Ephi += wij * (dphi * dphi)

    # Normalize by effective edge weight per frequency
    Wedge = np.zeros(F, dtype=np.float64)
    for (i, j, _dist) in edges:
        Wedge += w[i, :] * w[j, :]

    Egrad = np.where(Wedge > 0, Egrad / (Wedge + EPS), 0.0)
    Ephi = np.where(Wedge > 0, Ephi / (Wedge + EPS), 0.0)

    # Localization index (coherence-weighted)
    # Use only points with w>0 as "valid" at that freq.
    valid = w > 0
    L = np.zeros(F, dtype=np.float64)
    for f in range(F):
        idx = np.where(valid[:, f])[0]
        if idx.size < 2:
            L[f] = 0.0
            continue
        vals = mag[idx, f]
        L[f] = float(np.max(vals) / (np.mean(vals) + EPS))

    WSI = L * np.sqrt(np.maximum(Egrad, 0.0)) * np.sqrt(np.maximum(Ephi, 0.0))
    return Egrad, Ephi, L, WSI


def compute_local_stress_maps(
    H: np.ndarray, coh: np.ndarray, edges: list[tuple[int, int, float]], f_idx: int, *, coh_min: float
) -> tuple[np.ndarray, np.ndarray]:
    """
    For a selected frequency bin index, compute per-point stress contributions:
      - amp_stress[p] = sum over edges incident to p of (Δlog|H|)^2 weighted by coherence
      - phi_stress[p] = sum over edges incident to p of (wrapped Δphase)^2 weighted by coherence
    """
    P, F = H.shape
    mag = np.abs(H).astype(np.float64)
    phase = np.angle(H).astype(np.float64)

    a = np.log(mag + EPS)

    # weights at this freq
    w = (coh[:, f_idx] - coh_min) / max(EPS, (1.0 - coh_min))
    w = np.clip(w, 0.0, 1.0)

    amp_stress = np.zeros(P, dtype=np.float64)
    phi_stress = np.zeros(P, dtype=np.float64)

    for (i, j, _dist) in edges:
        wij = w[i] * w[j]
        if wij <= 0:
            continue
        da = a[i, f_idx] - a[j, f_idx]
        dphi = float(wrap_pi(np.array([phase[i, f_idx] - phase[j, f_idx]]))[0])
        sA = wij * (da * da)
        sP = wij * (dphi * dphi)
        amp_stress[i] += sA
        amp_stress[j] += sA
        phi_stress[i] += sP
        phi_stress[j] += sP

    # normalize to 0..1 for plotting
    if amp_stress.max() > 0:
        amp_stress = amp_stress / amp_stress.max()
    if phi_stress.max() > 0:
        phi_stress = phi_stress / phi_stress.max()

    return amp_stress, phi_stress


# ----------------------------
# Output helpers
# ----------------------------

def save_curve_csv(path: Path, freq: np.ndarray, Egrad: np.ndarray, Ephi: np.ndarray, L: np.ndarray, WSI: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        f.write("freq_hz,Egrad,Ephi,L,WSI\n")
        for i in range(freq.size):
            f.write(f"{freq[i]:.6f},{Egrad[i]:.12g},{Ephi[i]:.12g},{L[i]:.12g},{WSI[i]:.12g}\n")

def plot_wsi_curve(out_png: Path, freq: np.ndarray, WSI: np.ndarray, *, freq_min: float, freq_max: float) -> None:
    plt.figure()
    plt.plot(freq, WSI)
    plt.title("Wolf Susceptibility Index (WSI) vs Frequency")
    plt.xlabel("Frequency (Hz)")
    plt.ylabel("WSI (arb)")
    plt.xlim(freq_min, freq_max)
    plt.grid(True, alpha=0.3)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_png, dpi=200)
    plt.close()

def plot_scatter_map(
    out_png: Path, xy: np.ndarray, values: np.ndarray, *, title: str, xlabel: str = "x (mm)", ylabel: str = "y (mm)"
) -> None:
    plt.figure()
    plt.scatter(xy[:, 0], xy[:, 1], c=values, s=140, cmap="inferno")
    plt.colorbar(label="normalized stress")
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.gca().set_aspect("equal", adjustable="box")
    plt.grid(True, alpha=0.25)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_png, dpi=200)
    plt.close()


# ----------------------------
# Candidate selection
# ----------------------------

def pick_candidates(freq: np.ndarray, WSI: np.ndarray, *, top_n: int, min_prominence: float) -> list[int]:
    """
    Return indices of candidate frequencies.
    Uses scipy.signal.find_peaks if available; otherwise falls back to top-N by value.
    """
    if freq.size == 0:
        return []
    if find_peaks is not None:
        peaks, props = find_peaks(WSI, prominence=min_prominence)
        if peaks.size == 0:
            # fallback to top values
            return list(np.argsort(WSI)[::-1][:top_n])
        # sort by peak height
        peaks_sorted = sorted(peaks.tolist(), key=lambda i: float(WSI[i]), reverse=True)
        return peaks_sorted[:top_n]
    # fallback: top values
    return list(np.argsort(WSI)[::-1][:top_n])


# ----------------------------
# Main
# ----------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="Compute silver wolf metrics from a roving-grid bundle.")
    ap.add_argument("--bundle", required=True, help="Bundle directory containing grid.json and analysis/point_* files")
    ap.add_argument("--radius-mm", type=float, default=60.0, help="Neighbor radius in mm (used if --knn not set)")
    ap.add_argument("--knn", type=int, default=0, help="Use kNN adjacency (k); if >0 overrides radius graph")
    ap.add_argument("--coh-min", type=float, default=0.8, help="Coherence minimum threshold for weighting")
    ap.add_argument("--freq-min", type=float, default=40.0, help="Min frequency to analyze (Hz)")
    ap.add_argument("--freq-max", type=float, default=600.0, help="Max frequency to analyze (Hz)")
    ap.add_argument("--top-n", type=int, default=5, help="Number of candidate frequencies to map")
    ap.add_argument("--min-prominence", type=float, default=0.05, help="WSI peak prominence (scipy find_peaks)")
    args = ap.parse_args()

    bundle = Path(args.bundle).expanduser().resolve()
    derived_dir, plots_dir = ensure_dirs(bundle)

    pts = load_grid(bundle)
    labels = [p["label"] for p in pts]
    xy = np.array([[p["x_mm"], p["y_mm"]] for p in pts], dtype=np.float64)

    # Load per-point responses
    freqs_list: list[np.ndarray] = []
    H_list: list[np.ndarray] = []
    coh_list: list[np.ndarray] = []

    for lab in labels:
        f, H, c = load_point_response(bundle, lab)
        freqs_list.append(f)
        H_list.append(H)
        coh_list.append(c)

    freq = align_frequency_axes(freqs_list)

    # Stack into arrays: (P, F)
    H = np.vstack([h.reshape(1, -1) for h in H_list]).astype(np.complex128)
    coh = np.vstack([c.reshape(1, -1) for c in coh_list]).astype(np.float64)

    # Restrict frequency band
    mask = (freq >= args.freq_min) & (freq <= args.freq_max)
    if not np.any(mask):
        raise ValueError("No frequency bins within requested freq-min/freq-max.")
    freq_b = freq[mask]
    H_b = H[:, mask]
    coh_b = coh[:, mask]

    # Build adjacency
    if args.knn and args.knn > 0:
        edges = build_edges_knn(xy, args.knn)
        adj_desc = {"type": "knn", "k": args.knn}
    else:
        edges = build_edges_radius(xy, args.radius_mm)
        adj_desc = {"type": "radius", "radius_mm": args.radius_mm}

    # Compute silver metrics
    Egrad, Ephi, L, WSI = compute_metrics(H_b, coh_b, edges, coh_min=args.coh_min)

    # Write curve CSV
    curve_csv = derived_dir / "wsi_curve.csv"
    save_curve_csv(curve_csv, freq_b, Egrad, Ephi, L, WSI)

    # Plot WSI curve
    wsi_png = plots_dir / "wsi_curve.png"
    plot_wsi_curve(wsi_png, freq_b, WSI, freq_min=args.freq_min, freq_max=args.freq_max)

    # Pick candidate frequencies
    cand_idx = pick_candidates(freq_b, WSI, top_n=args.top_n, min_prominence=args.min_prominence)

    candidates: list[dict[str, Any]] = []
    for idx in cand_idx:
        f0 = float(freq_b[idx])

        amp_stress, phi_stress = compute_local_stress_maps(H_b, coh_b, edges, idx, coh_min=args.coh_min)

        amp_png = plots_dir / f"stress_map_amp_f{int(round(f0))}.png"
        phi_png = plots_dir / f"stress_map_phase_f{int(round(f0))}.png"

        plot_scatter_map(
            amp_png, xy, amp_stress,
            title=f"Amplitude Stress Map (log|H| gradient) @ {f0:.1f} Hz"
        )
        plot_scatter_map(
            phi_png, xy, phi_stress,
            title=f"Phase Stress Map (wrapped gradient) @ {f0:.1f} Hz"
        )

        # summarize coherence at f0
        coh_col = coh_b[:, idx]
        valid = coh_col >= args.coh_min
        coh_mean_valid = float(np.mean(coh_col[valid])) if np.any(valid) else 0.0
        pct_valid = float(100.0 * np.mean(valid))

        candidates.append({
            "freq_hz": f0,
            "WSI": float(WSI[idx]),
            "L": float(L[idx]),
            "Egrad": float(Egrad[idx]),
            "Ephi": float(Ephi[idx]),
            "coh_min": float(args.coh_min),
            "coh_mean_valid": coh_mean_valid,
            "pct_points_valid": pct_valid,
            "adjacency": adj_desc,
            "plots": {
                "amp_stress_png": str(amp_png.relative_to(bundle)),
                "phase_stress_png": str(phi_png.relative_to(bundle)),
            },
        })

    out_json = derived_dir / "wolf_candidates.json"
    write_json(out_json, {
        "bundle": str(bundle),
        "generated_utc": __import__("datetime").datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "freq_band_hz": [float(args.freq_min), float(args.freq_max)],
        "adjacency": adj_desc,
        "metrics": {
            "Egrad": "mean weighted edge (Δlog|H|)^2",
            "Ephi": "mean weighted edge (wrapped Δphase)^2",
            "L": "max(|H|)/mean(|H|) over coherence-valid points",
            "WSI": "L * sqrt(Egrad) * sqrt(Ephi)",
        },
        "outputs": {
            "wsi_curve_csv": str(curve_csv.relative_to(bundle)),
            "wsi_curve_png": str(wsi_png.relative_to(bundle)),
        },
        "candidates": candidates,
    })

    print(f"[OK] wrote: {curve_csv}")
    print(f"[OK] wrote: {out_json}")
    print(f"[OK] wrote: {wsi_png}")
    if candidates:
        print("[OK] candidate maps:")
        for c in candidates:
            print(f"  - {c['freq_hz']:.1f} Hz -> {c['plots']['amp_stress_png']}, {c['plots']['phase_stress_png']}")
    else:
        print("[WARN] no candidates found (WSI flat or below prominence). Try lowering --min-prominence or widening band.")


if __name__ == "__main__":
    main()
