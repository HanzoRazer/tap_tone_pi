#!/usr/bin/env python3
"""Tests for extended grid ID generation.

m4 Audit Fix: Grid ID Breaks at 26 Rows.
Tests for spreadsheet-style column naming (A-Z, AA-AZ, BA-BZ, etc.).
"""


from tap_tone_pi.core.grid import Grid, _row_to_letters


class TestRowToLetters:
    """Test _row_to_letters helper function."""

    def test_single_letters_a_to_z(self):
        """Rows 0-25 should produce A-Z."""
        assert _row_to_letters(0) == "A"
        assert _row_to_letters(1) == "B"
        assert _row_to_letters(12) == "M"
        assert _row_to_letters(25) == "Z"

    def test_double_letters_start(self):
        """Row 26 should produce AA."""
        assert _row_to_letters(26) == "AA"

    def test_double_letters_sequence(self):
        """Rows 26-51 should produce AA-AZ."""
        assert _row_to_letters(26) == "AA"
        assert _row_to_letters(27) == "AB"
        assert _row_to_letters(51) == "AZ"

    def test_double_letters_ba_sequence(self):
        """Rows 52-77 should produce BA-BZ."""
        assert _row_to_letters(52) == "BA"
        assert _row_to_letters(53) == "BB"
        assert _row_to_letters(77) == "BZ"

    def test_double_letters_zz(self):
        """Row 701 should produce ZZ."""
        # ZZ is the 702nd column (1-indexed): 26 + 26*26 = 26 + 676 = 702
        # So 0-indexed: 701
        assert _row_to_letters(701) == "ZZ"

    def test_triple_letters_start(self):
        """Row 702 should produce AAA."""
        assert _row_to_letters(702) == "AAA"

    def test_consistent_with_excel(self):
        """Verify consistency with Excel column naming convention."""
        # Excel column naming:
        # A=1, Z=26, AA=27, AZ=52, BA=53, ZZ=702, AAA=703
        # Our 0-indexed: A=0, Z=25, AA=26, AZ=51, BA=52, ZZ=701, AAA=702
        expected = [
            (0, "A"),
            (25, "Z"),
            (26, "AA"),
            (51, "AZ"),
            (52, "BA"),
            (701, "ZZ"),
            (702, "AAA"),
        ]
        for row, expected_id in expected:
            assert _row_to_letters(row) == expected_id, f"Row {row} should be {expected_id}"


class TestGridRectangularExtended:
    """Test Grid.rectangular with extended row counts."""

    def test_26_rows_uses_single_letters(self):
        """A 26-row grid should use A-Z."""
        grid = Grid.rectangular(rows=26, cols=1, spacing=10)

        # Check first and last row IDs
        assert grid.points[0].id == "A1"
        assert grid.points[25].id == "Z1"
        assert len(grid.points) == 26

    def test_27_rows_uses_double_letters(self):
        """A 27-row grid should extend to AA."""
        grid = Grid.rectangular(rows=27, cols=1, spacing=10)

        assert grid.points[0].id == "A1"
        assert grid.points[25].id == "Z1"
        assert grid.points[26].id == "AA1"
        assert len(grid.points) == 27

    def test_52_rows_uses_az(self):
        """A 52-row grid should include AZ."""
        grid = Grid.rectangular(rows=52, cols=1, spacing=10)

        assert grid.points[51].id == "AZ1"

    def test_53_rows_starts_ba(self):
        """A 53-row grid should start BA sequence."""
        grid = Grid.rectangular(rows=53, cols=1, spacing=10)

        assert grid.points[52].id == "BA1"

    def test_large_grid_100x100(self):
        """A 100x100 grid should work without errors."""
        grid = Grid.rectangular(rows=100, cols=100, spacing=10)

        assert len(grid.points) == 10000

        # Verify some specific IDs
        # Row 0, Col 0 = A1
        assert grid.points[0].id == "A1"
        # Row 0, Col 99 = A100
        assert grid.points[99].id == "A100"
        # Row 99, Col 0 = CV1 (row 99 = 99 in 0-indexed = "CV")
        assert grid.points[99 * 100].id == "CV1"

    def test_columns_increment_correctly(self):
        """Column numbers should increment within each row."""
        grid = Grid.rectangular(rows=3, cols=5, spacing=10)

        # Row A: A1, A2, A3, A4, A5
        assert grid.points[0].id == "A1"
        assert grid.points[1].id == "A2"
        assert grid.points[4].id == "A5"

        # Row B: B1, B2, B3, B4, B5
        assert grid.points[5].id == "B1"
        assert grid.points[9].id == "B5"

        # Row C: C1, C2, C3, C4, C5
        assert grid.points[10].id == "C1"
        assert grid.points[14].id == "C5"


class TestGridPointLabels:
    """Test that point labels are also updated."""

    def test_label_matches_id_for_extended_rows(self):
        """Point label should match ID for extended rows."""
        grid = Grid.rectangular(rows=30, cols=2, spacing=10)

        # Row 27 = AB
        ab1 = grid.points[27 * 2]  # AB1
        assert ab1.id == "AB1"
        assert ab1.label == "AB1"

    def test_get_point_by_extended_id(self):
        """Can retrieve point by extended ID."""
        grid = Grid.rectangular(rows=30, cols=1, spacing=10)

        point = grid.get_point("AA1")
        assert point is not None
        assert point.id == "AA1"
        # Row 26 (0-indexed) = 26 * spacing = 260
        assert point.y == 260.0
