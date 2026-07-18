#!/usr/bin/env python3
"""
test_merge_and_moe_canonical.py — Canonicality guard tests for MOE calculation.

Ensures that the legacy import path (modes.bending_rig.merge_and_moe) resolves
to the same implementation as the canonical path (tap_tone_pi.bending.merge_and_moe).

This prevents accidental divergence where patches are applied to one location
but not the other.

ADR reference: ADR-0009 (advisory boundary), GOVERNANCE.md section 4
"""

import warnings

import pytest


class TestMergeAndMoeCanonical:
    """Verify legacy shim points to canonical implementation."""

    def test_legacy_main_is_canonical_main(self):
        """Legacy main() must be the exact same function object as canonical."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            import modes.bending_rig.merge_and_moe as legacy

        import tap_tone_pi.bending.merge_and_moe as canonical

        assert legacy.main is canonical.main, (
            "legacy.main is not canonical.main — "
            "modes/bending_rig/merge_and_moe.py must be a shim, not a duplicate"
        )

    def test_legacy_calculate_moe_is_canonical(self):
        """Legacy _calculate_moe must be the exact same function object."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            import modes.bending_rig.merge_and_moe as legacy

        import tap_tone_pi.bending.merge_and_moe as canonical

        assert legacy._calculate_moe is canonical._calculate_moe, (
            "legacy._calculate_moe diverged from canonical — "
            "MOE calculation must have single source of truth"
        )

    def test_legacy_linear_fit_is_canonical(self):
        """Legacy _linear_fit must be the exact same function object."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            import modes.bending_rig.merge_and_moe as legacy

        import tap_tone_pi.bending.merge_and_moe as canonical

        assert legacy._linear_fit is canonical._linear_fit

    def test_legacy_timoshenko_correction_is_canonical(self):
        """Legacy _timoshenko_correction_factor must be the exact same function."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            import modes.bending_rig.merge_and_moe as legacy

        import tap_tone_pi.bending.merge_and_moe as canonical

        assert legacy._timoshenko_correction_factor is canonical._timoshenko_correction_factor

    def test_legacy_linear_fit_result_is_canonical(self):
        """Legacy LinearFitResult must be the exact same class."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            import modes.bending_rig.merge_and_moe as legacy

        import tap_tone_pi.bending.merge_and_moe as canonical

        assert legacy.LinearFitResult is canonical.LinearFitResult


class TestCanonicalImplementationFeatures:
    """Verify canonical implementation has required features."""

    def test_canonical_has_timoshenko_correction(self):
        """Canonical implementation must have Timoshenko shear correction."""
        import tap_tone_pi.bending.merge_and_moe as moe

        assert hasattr(moe, "_timoshenko_correction_factor"), (
            "Canonical implementation missing _timoshenko_correction_factor — "
            "Timoshenko shear correction is required for accurate MOE on short beams"
        )

    def test_canonical_has_linear_fit_result(self):
        """Canonical implementation must have LinearFitResult dataclass."""
        import tap_tone_pi.bending.merge_and_moe as moe

        assert hasattr(moe, "LinearFitResult")

        # Dataclass fields are in __dataclass_fields__
        fields = moe.LinearFitResult.__dataclass_fields__
        assert "slope" in fields
        assert "r_squared" in fields
        assert "valid" in fields
        assert "warning" in fields

    def test_timoshenko_correction_physics(self):
        """Timoshenko correction must reduce apparent modulus for short beams."""
        import tap_tone_pi.bending.merge_and_moe as moe

        # For a typical soundboard strip: L/h = 400mm / 3mm ≈ 133
        # Should have minimal correction
        factor_long = moe._timoshenko_correction_factor(l_over_h=133.0)
        assert 1.0 <= factor_long < 1.01, f"Long beam (L/h=133) factor={factor_long}"

        # For a short/thick beam: L/h = 150mm / 10mm = 15
        # Should have significant correction (8-15% per audit)
        factor_short = moe._timoshenko_correction_factor(l_over_h=15.0)
        assert 1.05 < factor_short < 1.20, f"Short beam (L/h=15) factor={factor_short}"

        # Correction must always be >= 1.0 (shear makes beam appear stiffer)
        assert factor_long >= 1.0
        assert factor_short >= 1.0


class TestLegacyEmitsDeprecationWarning:
    """Verify legacy import emits deprecation warning."""

    def test_legacy_import_warns(self):
        """Importing legacy module must emit DeprecationWarning."""
        import sys

        # Remove from cache to get fresh import
        modules_to_remove = [
            k for k in sys.modules if k.startswith("modes.bending_rig.merge_and_moe")
        ]
        for k in modules_to_remove:
            del sys.modules[k]

        with pytest.warns(DeprecationWarning, match="modes.bending_rig.merge_and_moe is deprecated"):
            import modes.bending_rig.merge_and_moe  # noqa: F401
