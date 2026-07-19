#!/usr/bin/env python3
"""
test_plot_f_vs_d_canonical.py — Canonicality guard tests for F-vs-d plotting.

Ensures that the legacy import path (modes.bending_rig.plot_f_vs_d) resolves
to the same implementation as the canonical path (tap_tone_pi.bending.plot_f_vs_d).

This prevents accidental divergence where patches are applied to one location
but not the other. The canonical version includes an M2 fix in percentile_bounds()
that must not be lost.

ADR reference: ADR-0009 (advisory boundary), GOVERNANCE.md section 4
"""

import warnings

import pytest


class TestPlotFVsDCanonical:
    """Verify legacy shim points to canonical implementation."""

    def test_legacy_main_is_canonical_main(self):
        """Legacy main() must be the exact same function object as canonical."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            import modes.bending_rig.plot_f_vs_d as legacy

        import tap_tone_pi.bending.plot_f_vs_d as canonical

        assert legacy.main is canonical.main, (
            "legacy.main is not canonical.main — "
            "modes/bending_rig/plot_f_vs_d.py must be a shim, not a duplicate"
        )

    def test_legacy_load_pairs_is_canonical(self):
        """Legacy load_pairs must be the exact same function object."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            import modes.bending_rig.plot_f_vs_d as legacy

        import tap_tone_pi.bending.plot_f_vs_d as canonical

        assert legacy.load_pairs is canonical.load_pairs

    def test_legacy_linear_fit_is_canonical(self):
        """Legacy linear_fit must be the exact same function object."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            import modes.bending_rig.plot_f_vs_d as legacy

        import tap_tone_pi.bending.plot_f_vs_d as canonical

        assert legacy.linear_fit is canonical.linear_fit

    def test_legacy_percentile_bounds_is_canonical(self):
        """Legacy percentile_bounds must be the exact same function (includes M2 fix)."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            import modes.bending_rig.plot_f_vs_d as legacy

        import tap_tone_pi.bending.plot_f_vs_d as canonical

        assert legacy.percentile_bounds is canonical.percentile_bounds, (
            "legacy.percentile_bounds diverged from canonical — "
            "canonical has M2 fix for edge cases that must be preserved"
        )


class TestCanonicalPercentileBoundsM2Fix:
    """Verify canonical percentile_bounds has M2 edge-case handling."""

    def test_empty_array_raises(self):
        """Empty array must raise ValueError (M2 fix)."""
        import tap_tone_pi.bending.plot_f_vs_d as canonical

        with pytest.raises(ValueError, match="empty"):
            canonical.percentile_bounds([], 10.0, 90.0)

    def test_single_value_returns_same(self):
        """Single value must return (val, val) without error (M2 fix)."""
        import tap_tone_pi.bending.plot_f_vs_d as canonical

        lo, hi = canonical.percentile_bounds([42.0], 10.0, 90.0)
        assert lo == 42.0
        assert hi == 42.0

    def test_percentiles_clamped(self):
        """Percentiles outside [0.1, 99.9] must be clamped (M2 fix)."""
        import tap_tone_pi.bending.plot_f_vs_d as canonical

        vals = list(range(100))
        # Extreme percentiles should not raise
        lo, hi = canonical.percentile_bounds(vals, -10.0, 110.0)
        assert lo is not None
        assert hi is not None

    def test_swapped_percentiles_handled(self):
        """lo_pct > hi_pct must be swapped (M2 fix)."""
        import tap_tone_pi.bending.plot_f_vs_d as canonical

        vals = list(range(100))
        # Swapped: lo=90, hi=10 should still work
        lo, hi = canonical.percentile_bounds(vals, 90.0, 10.0)
        assert lo <= hi


class TestLegacyEmitsDeprecationWarning:
    """Verify legacy import emits deprecation warning."""

    def test_legacy_import_warns(self):
        """Importing legacy module must emit DeprecationWarning."""
        import sys

        # Remove from cache to get fresh import
        modules_to_remove = [
            k for k in sys.modules if k.startswith("modes.bending_rig.plot_f_vs_d")
        ]
        for k in modules_to_remove:
            del sys.modules[k]

        with pytest.warns(
            DeprecationWarning, match="modes.bending_rig.plot_f_vs_d is deprecated"
        ):
            import modes.bending_rig.plot_f_vs_d  # noqa: F401
