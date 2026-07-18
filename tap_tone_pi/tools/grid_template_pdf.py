# INSTRUMENT CLASS: MEASUREMENT
"""
PDF Grid Template Generator.

Generates printable PDF templates for ODS measurement grids.
Users can print these and position them on their workpiece to guide
tap locations during Phase 2 capture.

Usage:
    from tap_tone_pi.tools.grid_template_pdf import generate_grid_pdf

    generate_grid_pdf(
        grid_path="config/grids/guitar_top_35pt.json",
        output_path="grid_template.pdf",
        scale=1.0,  # 1:1 scale for direct placement
    )

CLI:
    ttp grid-template --grid config/grids/guitar_top_35pt.json --out template.pdf
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Literal

# Use reportlab for PDF generation (optional dependency)
try:
    from reportlab.lib.pagesizes import letter, A4, A3
    from reportlab.lib.units import mm, inch
    from reportlab.pdfgen import canvas
    from reportlab.lib.colors import black, gray, lightgrey, red

    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False


@dataclass
class GridPoint:
    """Point in the measurement grid."""

    id: str
    x: float  # mm from origin
    y: float  # mm from origin


@dataclass
class Grid:
    """Measurement grid definition."""

    units: str  # "mm" or "inch"
    origin: str  # "center", "corner", etc.
    points: list[GridPoint]
    name: str = ""

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        """Return (min_x, min_y, max_x, max_y) in grid units."""
        if not self.points:
            return (0, 0, 0, 0)

        xs = [p.x for p in self.points]
        ys = [p.y for p in self.points]
        return (min(xs), min(ys), max(xs), max(ys))

    @property
    def width(self) -> float:
        """Grid width in units."""
        min_x, _, max_x, _ = self.bounds
        return max_x - min_x

    @property
    def height(self) -> float:
        """Grid height in units."""
        _, min_y, _, max_y = self.bounds
        return max_y - min_y


@dataclass
class TemplateConfig:
    """Configuration for PDF template generation."""

    # Page settings
    page_size: Literal["letter", "A4", "A3"] = "letter"
    orientation: Literal["portrait", "landscape"] = "landscape"

    # Margins (in mm)
    margin_mm: float = 15.0

    # Scale
    scale: float = 1.0  # 1.0 = actual size, 0.5 = half size

    # Visual options
    show_grid_lines: bool = True
    show_point_labels: bool = True
    show_crosshairs: bool = True
    show_origin_marker: bool = True

    # Point appearance
    point_radius_mm: float = 3.0
    crosshair_size_mm: float = 8.0
    label_font_size: int = 8

    # Title and metadata
    show_title: bool = True
    show_scale_bar: bool = True
    show_point_count: bool = True

    # Registration marks for alignment
    show_registration_marks: bool = True


def load_grid(path: Path) -> Grid:
    """Load grid definition from JSON file."""
    with open(path) as f:
        data = json.load(f)

    points = [GridPoint(id=p["id"], x=p["x"], y=p["y"]) for p in data.get("points", [])]

    return Grid(
        units=data.get("units", "mm"),
        origin=data.get("origin", "center"),
        points=points,
        name=data.get("name", path.stem),
    )


def _get_page_size(config: TemplateConfig) -> tuple[float, float]:
    """Get page dimensions in points."""
    sizes = {
        "letter": letter,
        "A4": A4,
        "A3": A3,
    }
    width, height = sizes.get(config.page_size, letter)

    if config.orientation == "landscape":
        return (height, width)
    return (width, height)


def _mm_to_points(mm_val: float) -> float:
    """Convert millimeters to PDF points."""
    return mm_val * mm


def generate_grid_pdf(
    grid_path: str | Path,
    output_path: str | Path,
    config: Optional[TemplateConfig] = None,
) -> Path:
    """
    Generate printable PDF template for measurement grid.

    Args:
        grid_path: Path to grid JSON file
        output_path: Output PDF path
        config: Template configuration (uses defaults if None)

    Returns:
        Path to generated PDF

    Raises:
        ImportError: If reportlab is not installed
        FileNotFoundError: If grid file doesn't exist
    """
    if not HAS_REPORTLAB:
        raise ImportError(
            "reportlab is required for PDF generation. "
            "Install with: pip install reportlab"
        )

    grid_path = Path(grid_path)
    output_path = Path(output_path)

    if not grid_path.exists():
        raise FileNotFoundError(f"Grid file not found: {grid_path}")

    config = config or TemplateConfig()
    grid = load_grid(grid_path)

    # Create PDF
    page_width, page_height = _get_page_size(config)
    c = canvas.Canvas(str(output_path), pagesize=(page_width, page_height))

    # Calculate drawable area
    margin = _mm_to_points(config.margin_mm)
    draw_width = page_width - 2 * margin
    draw_height = page_height - 2 * margin - 50  # Reserve space for title

    # Calculate scale to fit
    grid_width_pts = _mm_to_points(grid.width * config.scale)
    grid_height_pts = _mm_to_points(grid.height * config.scale)

    fit_scale_x = draw_width / grid_width_pts if grid_width_pts > 0 else 1
    fit_scale_y = draw_height / grid_height_pts if grid_height_pts > 0 else 1
    fit_scale = min(fit_scale_x, fit_scale_y, 1.0)  # Don't scale up

    actual_scale = config.scale * fit_scale

    # Calculate grid center on page
    min_x, min_y, max_x, max_y = grid.bounds
    grid_center_x = (min_x + max_x) / 2
    grid_center_y = (min_y + max_y) / 2

    page_center_x = page_width / 2
    page_center_y = page_height / 2 - 20  # Offset for title

    def grid_to_page(gx: float, gy: float) -> tuple[float, float]:
        """Convert grid coordinates to page coordinates."""
        # Offset from grid center, scale, then offset to page center
        dx = (gx - grid_center_x) * actual_scale
        dy = (gy - grid_center_y) * actual_scale
        return (
            page_center_x + _mm_to_points(dx),
            page_center_y + _mm_to_points(dy),
        )

    # Draw title
    if config.show_title:
        c.setFont("Helvetica-Bold", 14)
        title = f"ODS Grid Template: {grid.name}"
        c.drawCentredString(page_center_x, page_height - margin, title)

        c.setFont("Helvetica", 10)
        subtitle = f"{len(grid.points)} points | Scale: {actual_scale:.2f}:1 | Units: {grid.units}"
        c.drawCentredString(page_center_x, page_height - margin - 15, subtitle)

    # Draw registration marks (corners)
    if config.show_registration_marks:
        mark_size = 10
        c.setStrokeColor(black)
        c.setLineWidth(0.5)

        for corner_x, corner_y in [
            (margin, margin),
            (margin, page_height - margin),
            (page_width - margin, margin),
            (page_width - margin, page_height - margin),
        ]:
            # L-shaped registration mark
            c.line(corner_x, corner_y, corner_x + mark_size, corner_y)
            c.line(corner_x, corner_y, corner_x, corner_y + mark_size)

    # Draw origin marker
    if config.show_origin_marker and grid.origin == "center":
        ox, oy = grid_to_page(0, 0)
        c.setStrokeColor(red)
        c.setLineWidth(1)
        size = 15
        c.line(ox - size, oy, ox + size, oy)
        c.line(ox, oy - size, ox, oy + size)
        c.circle(ox, oy, 5, stroke=1, fill=0)

    # Draw grid boundary
    if config.show_grid_lines:
        c.setStrokeColor(lightgrey)
        c.setLineWidth(0.5)
        c.setDash(3, 3)

        # Bounding rectangle
        p1 = grid_to_page(min_x, min_y)
        p2 = grid_to_page(max_x, min_y)
        p3 = grid_to_page(max_x, max_y)
        p4 = grid_to_page(min_x, max_y)

        c.line(p1[0], p1[1], p2[0], p2[1])
        c.line(p2[0], p2[1], p3[0], p3[1])
        c.line(p3[0], p3[1], p4[0], p4[1])
        c.line(p4[0], p4[1], p1[0], p1[1])

        c.setDash()  # Reset dash

    # Draw measurement points
    point_radius = _mm_to_points(config.point_radius_mm * actual_scale)
    crosshair_size = _mm_to_points(config.crosshair_size_mm * actual_scale)

    for point in grid.points:
        px, py = grid_to_page(point.x, point.y)

        # Draw crosshair
        if config.show_crosshairs:
            c.setStrokeColor(gray)
            c.setLineWidth(0.5)
            c.line(px - crosshair_size, py, px + crosshair_size, py)
            c.line(px, py - crosshair_size, px, py + crosshair_size)

        # Draw point circle
        c.setStrokeColor(black)
        c.setLineWidth(1)
        c.circle(px, py, point_radius, stroke=1, fill=0)

        # Draw label
        if config.show_point_labels:
            c.setFont("Helvetica", config.label_font_size)
            c.setFillColor(black)
            label_offset = point_radius + 3
            c.drawString(px + label_offset, py + label_offset, point.id)

    # Draw scale bar
    if config.show_scale_bar:
        bar_y = margin + 20
        bar_x = margin + 20

        # 50mm reference bar
        bar_length_mm = 50
        bar_length_pts = _mm_to_points(bar_length_mm * actual_scale)

        c.setStrokeColor(black)
        c.setLineWidth(1)
        c.line(bar_x, bar_y, bar_x + bar_length_pts, bar_y)
        c.line(bar_x, bar_y - 3, bar_x, bar_y + 3)
        c.line(bar_x + bar_length_pts, bar_y - 3, bar_x + bar_length_pts, bar_y + 3)

        c.setFont("Helvetica", 8)
        c.drawString(bar_x, bar_y + 8, f"{bar_length_mm} {grid.units}")

    # Draw footer
    c.setFont("Helvetica", 8)
    c.setFillColor(gray)
    footer = f"Generated by tap_tone_pi | Grid: {grid_path.name}"
    c.drawString(margin, 15, footer)

    c.save()

    return output_path


def add_grid_template_subcommand(subparsers) -> None:
    """Add grid-template subcommand to CLI."""

    parser = subparsers.add_parser(
        "grid-template",
        help="Generate printable PDF grid template",
        description="Generate a printable PDF template for ODS measurement grid positioning.",
    )

    parser.add_argument(
        "--grid",
        "-g",
        type=str,
        required=True,
        help="Path to grid JSON file",
    )

    parser.add_argument(
        "--out",
        "-o",
        type=str,
        default="grid_template.pdf",
        help="Output PDF path (default: grid_template.pdf)",
    )

    parser.add_argument(
        "--scale",
        "-s",
        type=float,
        default=1.0,
        help="Scale factor (1.0 = actual size, 0.5 = half size)",
    )

    parser.add_argument(
        "--page",
        choices=["letter", "A4", "A3"],
        default="letter",
        help="Page size (default: letter)",
    )

    parser.add_argument(
        "--orientation",
        choices=["portrait", "landscape"],
        default="landscape",
        help="Page orientation (default: landscape)",
    )

    parser.add_argument(
        "--no-labels",
        action="store_true",
        help="Omit point labels",
    )

    parser.add_argument(
        "--no-crosshairs",
        action="store_true",
        help="Omit crosshair markers",
    )

    parser.set_defaults(fn=cmd_grid_template)


def cmd_grid_template(args) -> int:
    """CLI handler for grid-template command."""

    config = TemplateConfig(
        page_size=args.page,
        orientation=args.orientation,
        scale=args.scale,
        show_point_labels=not args.no_labels,
        show_crosshairs=not args.no_crosshairs,
    )

    try:
        output = generate_grid_pdf(
            grid_path=args.grid,
            output_path=args.out,
            config=config,
        )
        print(f"Generated: {output}")
        return 0

    except ImportError as e:
        print(f"Error: {e}")
        print("Install reportlab: pip install reportlab")
        return 1

    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1

    except Exception as e:
        print(f"Error generating PDF: {e}")
        return 1
