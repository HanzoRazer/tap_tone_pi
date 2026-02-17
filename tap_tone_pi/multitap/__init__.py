"""
Multi-tap statistical analysis module.

This module provides production-grade statistical analysis for
measurements derived from multiple tap tests.

Key Capabilities:
- Outlier detection using Chauvenet's criterion and MAD
- Convergence monitoring for adaptive stopping
- Weighted averaging based on signal quality
- Confidence interval computation
- Specimen comparison with statistical tests

Statistical Methods:
- Chauvenet's criterion for outlier rejection
- Median Absolute Deviation (MAD) for robust statistics
- Inverse-variance weighted averaging
- Grubbs' test for single outlier detection
- T-test for specimen comparison
- ANOVA for multi-group comparison

Design Philosophy:
All methods are designed to be conservative—preferring to keep
borderline data rather than over-reject. The goal is to support
operator decision-making, not replace it.
"""

from .statistical import (
    MultiTapResult,
    TapMeasurement,
    StatisticalSummary,
    OutlierMethod,
    analyze_multi_tap,
    detect_outliers_chauvenet,
    detect_outliers_mad,
    weighted_average,
    compute_confidence_interval,
    check_convergence,
)

from .comparison import (
    ComparisonResult,
    compare_specimens,
    compare_conditions,
    pairwise_comparison,
)

from .quality import (
    TapQualityMetrics,
    assess_tap_quality,
    rank_tap_quality,
    suggest_tap_rejection,
)

__all__ = [
    # Core analysis
    "MultiTapResult",
    "TapMeasurement",
    "StatisticalSummary",
    "OutlierMethod",
    "analyze_multi_tap",
    # Outlier detection
    "detect_outliers_chauvenet",
    "detect_outliers_mad",
    # Averaging
    "weighted_average",
    "compute_confidence_interval",
    "check_convergence",
    # Comparison
    "ComparisonResult",
    "compare_specimens",
    "compare_conditions",
    "pairwise_comparison",
    # Quality
    "TapQualityMetrics",
    "assess_tap_quality",
    "rank_tap_quality",
    "suggest_tap_rejection",
]
