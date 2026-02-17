"""
Chladni pattern eigenfunction computation and visualization.

Implements analytical solutions for vibrating plate eigenmodes:

1. Simply Supported Square Plate:
   φₘₙ(x,y) = sin(mπx/L) · sin(nπy/L)

   Eigenfrequencies: fₘₙ = (π/2L²)√(D/ρh) · (m² + n²)

2. Center-Constrained Plate (free edges, clamped center):
   Nodal pattern from interference:
   cos(nπx/L)cos(mπy/L) - cos(mπx/L)cos(nπy/L) = 0

Usage:
    python -m modes.chladni.eigenfunctions --mode 2,3 --size 512 --out mode_2_3.png
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Literal

import numpy as np

# Optional imports for visualization
try:
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False


@dataclass
class PlateParams:
    """Physical parameters for plate eigenfrequency calculation."""
    length_m: float = 0.3          # Plate side length (square)
    thickness_m: float = 0.003     # Plate thickness
    density_kg_m3: float = 2700.0  # Material density (aluminum default)
    youngs_modulus_pa: float = 70e9  # Young's modulus
    poissons_ratio: float = 0.33   # Poisson's ratio

    @property
    def flexural_rigidity(self) -> float:
        """Compute flexural rigidity D = Eh³/12(1-ν²)."""
        E = self.youngs_modulus_pa
        h = self.thickness_m
        nu = self.poissons_ratio
        return (E * h**3) / (12 * (1 - nu**2))

    def eigenfrequency_hz(self, m: int, n: int) -> float:
        """
        Compute eigenfrequency for mode (m,n) of simply supported plate.

        fₘₙ = (π/2L²) · √(D/ρh) · (m² + n²)
        """
        L = self.length_m
        D = self.flexural_rigidity
        rho = self.density_kg_m3
        h = self.thickness_m

        coeff = (np.pi / (2 * L**2)) * np.sqrt(D / (rho * h))
        return coeff * (m**2 + n**2)


def compute_simply_supported_mode(
    m: int,
    n: int,
    grid_size: int = 256,
    normalize: bool = True
) -> np.ndarray:
    """
    Compute eigenfunction for simply supported square plate.

    φₘₙ(x,y) = sin(mπx/L) · sin(nπy/L)

    Normalized to unit plate (L=1).

    Args:
        m: Mode number in x direction (m >= 1)
        n: Mode number in y direction (n >= 1)
        grid_size: Resolution of output array
        normalize: If True, scale to [-1, 1] range

    Returns:
        2D array of displacement values
    """
    if m < 1 or n < 1:
        raise ValueError(f"Mode numbers must be >= 1, got m={m}, n={n}")

    x = np.linspace(0, 1, grid_size)
    y = np.linspace(0, 1, grid_size)
    X, Y = np.meshgrid(x, y)

    phi = np.sin(m * np.pi * X) * np.sin(n * np.pi * Y)

    if normalize:
        phi = phi / np.abs(phi).max()

    return phi


def compute_center_constrained_nodal(
    m: int,
    n: int,
    grid_size: int = 256
) -> np.ndarray:
    """
    Compute nodal pattern for center-constrained plate.

    Interference pattern:
    cos(nπx/L)cos(mπy/L) - cos(mπx/L)cos(nπy/L) = 0

    Returns array where values near zero represent nodal lines.

    Args:
        m: Mode number (m >= 1)
        n: Mode number (n >= 1, n != m for non-trivial pattern)
        grid_size: Resolution of output array

    Returns:
        2D array of interference values
    """
    if m < 1 or n < 1:
        raise ValueError(f"Mode numbers must be >= 1, got m={m}, n={n}")

    # Center at origin for symmetric interference
    x = np.linspace(-0.5, 0.5, grid_size)
    y = np.linspace(-0.5, 0.5, grid_size)
    X, Y = np.meshgrid(x, y)

    # Interference: cos(nπx)cos(mπy) - cos(mπx)cos(nπy)
    term1 = np.cos(n * np.pi * X) * np.cos(m * np.pi * Y)
    term2 = np.cos(m * np.pi * X) * np.cos(n * np.pi * Y)

    return term1 - term2


def extract_nodal_contour(
    displacement: np.ndarray,
    threshold: float = 0.01
) -> np.ndarray:
    """
    Extract binary nodal line mask from displacement field.

    Args:
        displacement: 2D array of displacement values
        threshold: Values with |φ| < threshold are nodal

    Returns:
        Binary mask where True = nodal line region
    """
    normalized = displacement / (np.abs(displacement).max() + 1e-12)
    return np.abs(normalized) < threshold


def render_chladni_pattern(
    displacement: np.ndarray,
    output_path: Path | None = None,
    title: str | None = None,
    colormap: str = "seismic",
    show_nodal: bool = True,
    dpi: int = 150
) -> np.ndarray | None:
    """
    Render Chladni pattern visualization.

    Args:
        displacement: 2D array of displacement values
        output_path: If provided, save PNG to this path
        title: Plot title
        colormap: Matplotlib colormap name
        show_nodal: Overlay nodal lines in black
        dpi: Output resolution

    Returns:
        RGBA array if no output_path, else None (saves to file)
    """
    if not HAS_MATPLOTLIB:
        raise ImportError("matplotlib required for visualization")

    fig, ax = plt.subplots(figsize=(6, 6), dpi=dpi)

    # Normalize to [-1, 1]
    vmax = np.abs(displacement).max()
    normalized = displacement / vmax if vmax > 0 else displacement

    # Main displacement heatmap
    im = ax.imshow(
        normalized,
        cmap=colormap,
        vmin=-1,
        vmax=1,
        origin='lower',
        extent=[0, 1, 0, 1]
    )

    if show_nodal:
        # Overlay nodal contour at zero
        ax.contour(
            normalized,
            levels=[0],
            colors='black',
            linewidths=1.5,
            extent=[0, 1, 0, 1]
        )

    ax.set_xlabel('x / L')
    ax.set_ylabel('y / L')
    if title:
        ax.set_title(title)

    plt.colorbar(im, ax=ax, label='Displacement (normalized)')

    if output_path:
        fig.savefig(output_path, bbox_inches='tight', dpi=dpi)
        plt.close(fig)
        return None
    else:
        # Return as RGBA array
        fig.canvas.draw()
        rgba = np.asarray(fig.canvas.buffer_rgba())
        plt.close(fig)
        return rgba


def render_sand_pattern(
    displacement: np.ndarray,
    output_path: Path | None = None,
    title: str | None = None,
    dpi: int = 150
) -> np.ndarray | None:
    """
    Render realistic sand Chladni pattern (sand accumulates at nodal lines).

    Uses grayscale where white = nodal (sand), dark = antinodal (no sand).

    Args:
        displacement: 2D array of displacement values
        output_path: If provided, save PNG to this path
        title: Plot title
        dpi: Output resolution

    Returns:
        RGBA array if no output_path, else None (saves to file)
    """
    if not HAS_MATPLOTLIB:
        raise ImportError("matplotlib required for visualization")

    fig, ax = plt.subplots(figsize=(6, 6), dpi=dpi)

    # Sand accumulates where displacement is near zero
    # High displacement = sand blown away (dark)
    # Zero displacement = sand stays (light)
    vmax = np.abs(displacement).max()
    normalized = np.abs(displacement) / vmax if vmax > 0 else np.abs(displacement)

    # Invert: 1 = nodal (white sand), 0 = antinode (dark plate)
    sand_density = 1 - normalized

    # Apply slight nonlinearity to emphasize nodal lines
    sand_density = sand_density ** 0.7

    ax.imshow(
        sand_density,
        cmap='gray',
        vmin=0,
        vmax=1,
        origin='lower',
        extent=[0, 1, 0, 1]
    )

    ax.set_xlabel('x / L')
    ax.set_ylabel('y / L')
    if title:
        ax.set_title(title)
    ax.set_aspect('equal')

    if output_path:
        fig.savefig(output_path, bbox_inches='tight', dpi=dpi)
        plt.close(fig)
        return None
    else:
        fig.canvas.draw()
        rgba = np.asarray(fig.canvas.buffer_rgba())
        plt.close(fig)
        return rgba


@dataclass
class ChladniModeResult:
    """Result container for computed Chladni mode."""
    m: int
    n: int
    boundary_condition: Literal["simply_supported", "center_constrained"]
    frequency_hz: float | None  # Only computed for simply_supported with params
    grid_size: int
    displacement: np.ndarray  # Not serialized to JSON

    def to_json_dict(self) -> dict:
        """Return JSON-serializable dict (excludes displacement array)."""
        d = asdict(self)
        d.pop('displacement')
        d['shape'] = list(self.displacement.shape)
        return d


def compute_mode(
    m: int,
    n: int,
    boundary: Literal["simply_supported", "center_constrained"] = "simply_supported",
    grid_size: int = 256,
    plate_params: PlateParams | None = None
) -> ChladniModeResult:
    """
    Compute Chladni mode for given parameters.

    Args:
        m: Mode number in x direction
        n: Mode number in y direction
        boundary: Boundary condition type
        grid_size: Resolution of output grid
        plate_params: Physical parameters for frequency calculation

    Returns:
        ChladniModeResult with displacement field and metadata
    """
    if boundary == "simply_supported":
        displacement = compute_simply_supported_mode(m, n, grid_size)
    elif boundary == "center_constrained":
        displacement = compute_center_constrained_nodal(m, n, grid_size)
    else:
        raise ValueError(f"Unknown boundary condition: {boundary}")

    freq_hz = None
    if plate_params and boundary == "simply_supported":
        freq_hz = plate_params.eigenfrequency_hz(m, n)

    return ChladniModeResult(
        m=m,
        n=n,
        boundary_condition=boundary,
        frequency_hz=freq_hz,
        grid_size=grid_size,
        displacement=displacement
    )


def main() -> None:
    """CLI entry point for eigenfunction computation."""
    parser = argparse.ArgumentParser(
        description="Compute and visualize Chladni plate eigenmodes"
    )
    parser.add_argument(
        "--mode", "-m",
        required=True,
        help="Mode numbers as 'm,n' (e.g., '2,3')"
    )
    parser.add_argument(
        "--boundary", "-b",
        choices=["simply_supported", "center_constrained"],
        default="simply_supported",
        help="Boundary condition type"
    )
    parser.add_argument(
        "--size", "-s",
        type=int,
        default=256,
        help="Grid resolution (default: 256)"
    )
    parser.add_argument(
        "--out", "-o",
        help="Output PNG path (omit for terminal summary only)"
    )
    parser.add_argument(
        "--sand",
        action="store_true",
        help="Render realistic sand pattern instead of displacement field"
    )
    parser.add_argument(
        "--json",
        help="Output metadata to JSON file"
    )
    parser.add_argument(
        "--plate-length",
        type=float,
        default=0.3,
        help="Plate side length in meters (default: 0.3)"
    )
    parser.add_argument(
        "--plate-thickness",
        type=float,
        default=0.003,
        help="Plate thickness in meters (default: 0.003)"
    )

    args = parser.parse_args()

    # Parse mode numbers
    try:
        m_str, n_str = args.mode.split(",")
        m, n = int(m_str.strip()), int(n_str.strip())
    except ValueError:
        print(f"Error: --mode must be 'm,n' format, got '{args.mode}'", file=sys.stderr)
        sys.exit(1)

    # Build plate parameters
    plate_params = PlateParams(
        length_m=args.plate_length,
        thickness_m=args.plate_thickness
    )

    # Compute mode
    result = compute_mode(
        m=m,
        n=n,
        boundary=args.boundary,
        grid_size=args.size,
        plate_params=plate_params
    )

    # Output summary
    print(f"Mode: ({m}, {n})")
    print(f"Boundary: {args.boundary}")
    print(f"Grid size: {args.size}x{args.size}")
    if result.frequency_hz:
        print(f"Eigenfrequency: {result.frequency_hz:.2f} Hz")

    # Save visualization
    if args.out:
        if not HAS_MATPLOTLIB:
            print("Error: matplotlib required for visualization", file=sys.stderr)
            sys.exit(1)

        out_path = Path(args.out)
        title = f"Mode ({m}, {n}) — {args.boundary.replace('_', ' ').title()}"

        if args.sand:
            render_sand_pattern(result.displacement, out_path, title)
        else:
            render_chladni_pattern(result.displacement, out_path, title)

        print(f"Saved: {out_path}")

    # Save metadata
    if args.json:
        json_path = Path(args.json)
        meta = result.to_json_dict()
        meta['plate_params'] = asdict(plate_params)
        json_path.write_text(json.dumps(meta, indent=2))
        print(f"Metadata: {json_path}")


if __name__ == "__main__":
    main()
