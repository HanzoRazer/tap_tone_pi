# INSTRUMENT CLASS: MEASUREMENT
"""
Phase 2 Grid Progress Display — ASCII terminal visualization.

Renders a 2D grid showing capture status for each point:
- Green (✓): captured successfully
- Yellow (!): captured with warnings (low coherence)
- Red (✗): failed capture
- Gray (○): pending
- Current point highlighted with [ ]

Usage:
    from tap_tone_pi.phase2.grid_display import GridDisplay, PointStatus

    display = GridDisplay(grid)
    display.update("A1", PointStatus.CAPTURED)
    display.set_current("A2")
    print(display.render())
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

from tap_tone_pi.core.grid import Grid, GridPoint


class PointStatus(Enum):
    """Status of a grid point capture."""

    PENDING = "pending"
    CAPTURED = "captured"
    WARNING = "warning"  # Captured but low coherence
    FAILED = "failed"
    SKIPPED = "skipped"


# ANSI color codes
class Colors:
    """ANSI escape codes for terminal colors."""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # Foreground
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    GRAY = "\033[90m"
    CYAN = "\033[36m"
    WHITE = "\033[97m"

    # Background
    BG_BLUE = "\033[44m"

    @classmethod
    def supports_color(cls) -> bool:
        """Check if terminal supports ANSI colors."""
        if os.getenv("NO_COLOR"):
            return False
        if os.getenv("FORCE_COLOR"):
            return True
        if not hasattr(sys.stdout, "isatty"):
            return False
        return sys.stdout.isatty()


@dataclass
class GridDisplay:
    """
    ASCII grid display for Phase 2 measurement progress.

    Attributes:
        grid: The Grid object with point definitions
        statuses: Dict mapping point_id to PointStatus
        current_point: The point currently being measured (highlighted)
        use_color: Whether to use ANSI colors (auto-detected)
    """

    grid: Grid
    statuses: Dict[str, PointStatus] = field(default_factory=dict)
    current_point: Optional[str] = None
    use_color: bool = field(default_factory=Colors.supports_color)

    # Display settings
    cell_width: int = 4
    show_legend: bool = True
    show_stats: bool = True

    def __post_init__(self):
        """Initialize all points as pending."""
        for point in self.grid.points:
            if point.id not in self.statuses:
                self.statuses[point.id] = PointStatus.PENDING

    def update(self, point_id: str, status: PointStatus) -> None:
        """Update the status of a point."""
        self.statuses[point_id] = status

    def set_current(self, point_id: Optional[str]) -> None:
        """Set the current point being measured."""
        self.current_point = point_id

    def get_stats(self) -> Dict[str, int]:
        """Get counts of each status."""
        stats = {s.value: 0 for s in PointStatus}
        for status in self.statuses.values():
            stats[status.value] += 1
        return stats

    def _color(self, text: str, *codes: str) -> str:
        """Apply color codes to text if colors enabled."""
        if not self.use_color:
            return text
        return "".join(codes) + text + Colors.RESET

    def _status_char(self, status: PointStatus, is_current: bool) -> str:
        """Get the display character for a status."""
        chars = {
            PointStatus.PENDING: "○",
            PointStatus.CAPTURED: "✓",
            PointStatus.WARNING: "!",
            PointStatus.FAILED: "✗",
            PointStatus.SKIPPED: "-",
        }
        char = chars.get(status, "?")

        # Apply colors
        if status == PointStatus.CAPTURED:
            char = self._color(char, Colors.GREEN, Colors.BOLD)
        elif status == PointStatus.WARNING:
            char = self._color(char, Colors.YELLOW, Colors.BOLD)
        elif status == PointStatus.FAILED:
            char = self._color(char, Colors.RED, Colors.BOLD)
        elif status == PointStatus.PENDING:
            char = self._color(char, Colors.GRAY)
        elif status == PointStatus.SKIPPED:
            char = self._color(char, Colors.DIM)

        # Highlight current point
        if is_current:
            char = (
                self._color("[", Colors.CYAN, Colors.BOLD)
                + char
                + self._color("]", Colors.CYAN, Colors.BOLD)
            )
        else:
            char = " " + char + " "

        return char

    def _build_grid_matrix(
        self,
    ) -> Tuple[List[List[Optional[str]]], List[float], List[float]]:
        """
        Build a 2D matrix of point IDs based on their coordinates.

        Returns:
            (matrix, unique_x_coords, unique_y_coords)
        """
        # Get unique coordinates
        x_coords = sorted(set(p.x for p in self.grid.points))
        y_coords = sorted(
            set(p.y for p in self.grid.points), reverse=True
        )  # Top to bottom

        # Build coordinate to point mapping
        coord_to_point: Dict[Tuple[float, float], str] = {}
        for p in self.grid.points:
            coord_to_point[(p.x, p.y)] = p.id

        # Build matrix
        matrix: List[List[Optional[str]]] = []
        for y in y_coords:
            row: List[Optional[str]] = []
            for x in x_coords:
                row.append(coord_to_point.get((x, y)))
            matrix.append(row)

        return matrix, x_coords, y_coords

    def render(self) -> str:
        """Render the grid as an ASCII string."""
        lines: List[str] = []

        # Title
        title = f"Phase 2 Grid Progress — {len(self.grid.points)} points"
        lines.append(self._color(title, Colors.BOLD, Colors.WHITE))
        lines.append("")

        # Build grid matrix
        matrix, x_coords, y_coords = self._build_grid_matrix()

        # Render grid
        for row_idx, row in enumerate(matrix):
            row_str = ""
            for point_id in row:
                if point_id is None:
                    row_str += "   "  # Empty cell
                else:
                    status = self.statuses.get(point_id, PointStatus.PENDING)
                    is_current = point_id == self.current_point
                    row_str += self._status_char(status, is_current)
            lines.append(row_str)

        lines.append("")

        # Legend
        if self.show_legend:
            legend_items = [
                (self._color("✓", Colors.GREEN, Colors.BOLD), "captured"),
                (self._color("!", Colors.YELLOW, Colors.BOLD), "warning"),
                (self._color("✗", Colors.RED, Colors.BOLD), "failed"),
                (self._color("○", Colors.GRAY), "pending"),
            ]
            legend_str = "  ".join(f"{char} {label}" for char, label in legend_items)
            lines.append(legend_str)

        # Stats
        if self.show_stats:
            stats = self.get_stats()
            total = len(self.grid.points)
            captured = stats["captured"]
            warnings = stats["warning"]
            failed = stats["failed"]
            _pending = stats["pending"]

            pct = (captured + warnings) / total * 100 if total > 0 else 0

            stats_line = f"Progress: {captured + warnings}/{total} ({pct:.0f}%)"
            if warnings > 0:
                stats_line += f" | {warnings} warnings"
            if failed > 0:
                stats_line += f" | {failed} failed"

            lines.append("")
            lines.append(self._color(stats_line, Colors.CYAN))

        # Current point info
        if self.current_point:
            lines.append("")
            lines.append(
                self._color(
                    f"→ Current: {self.current_point}", Colors.CYAN, Colors.BOLD
                )
            )

        return "\n".join(lines)

    def render_compact(self) -> str:
        """Render a single-line compact status."""
        stats = self.get_stats()
        total = len(self.grid.points)
        done = stats["captured"] + stats["warning"]

        bar_width = 20
        filled = int(bar_width * done / total) if total > 0 else 0
        bar = "█" * filled + "░" * (bar_width - filled)

        current = f" → {self.current_point}" if self.current_point else ""

        return f"[{bar}] {done}/{total}{current}"

    def clear_and_render(self) -> str:
        """Return ANSI codes to clear screen and render grid."""
        clear = "\033[2J\033[H"  # Clear screen and move cursor to top-left
        return clear + self.render()


def demo():
    """Demo the grid display with synthetic data."""
    from tap_tone_pi.core.grid import Grid

    # Create a 5x7 grid (35 points)
    points = []
    for row, y in enumerate([0, 50, 100, 150, 200]):
        for col, x in enumerate([0, 40, 80, 120, 160, 200, 240]):
            point_id = f"{chr(65 + row)}{col + 1}"  # A1, A2, ... E7
            points.append(GridPoint(id=point_id, x=float(x), y=float(y)))

    grid = Grid(units="mm", origin="center", points=points)
    display = GridDisplay(grid)

    # Simulate some progress
    display.update("A1", PointStatus.CAPTURED)
    display.update("A2", PointStatus.CAPTURED)
    display.update("A3", PointStatus.WARNING)
    display.update("A4", PointStatus.CAPTURED)
    display.update("B1", PointStatus.CAPTURED)
    display.update("B2", PointStatus.FAILED)
    display.set_current("B3")

    print(display.render())
    print()
    print("Compact:", display.render_compact())


if __name__ == "__main__":
    demo()
