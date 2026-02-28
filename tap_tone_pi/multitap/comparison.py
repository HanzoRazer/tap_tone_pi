"""
Statistical comparison between specimens and conditions.

This module provides methods to determine whether observed differences
between specimens or measurement conditions are statistically significant.

Methods:
- Two-sample t-test for comparing means
- Welch's t-test (unequal variances)
- Effect size calculation (Cohen's d)
- ANOVA for multi-group comparison
- Pairwise comparisons with correction

Important considerations:
- Statistical significance ≠ practical significance
- Always report effect size alongside p-values
- Consider the measurement uncertainty context
"""

from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict, Any
import numpy as np
from scipy import stats


@dataclass
class ComparisonResult:
    """
    Result of statistical comparison between groups.

    Attributes
    ----------
    statistically_different : bool
        Whether groups are statistically different at alpha.
    p_value : float
        P-value from statistical test.
    test_statistic : float
        Test statistic (t, F, etc.).
    test_used : str
        Name of statistical test used.
    effect_size : float
        Cohen's d or eta-squared.
    effect_interpretation : str
        "negligible", "small", "medium", "large"
    confidence_interval_diff : Tuple[float, float]
        CI for difference between means.
    group1_mean : float
        Mean of first group.
    group2_mean : float
        Mean of second group.
    mean_difference : float
        group1_mean - group2_mean
    percent_difference : float
        100 × (group1 - group2) / group2
    practical_significance : str
        Assessment of practical importance.
    alpha : float
        Significance level used.
    """

    statistically_different: bool
    p_value: float
    test_statistic: float
    test_used: str
    effect_size: float
    effect_interpretation: str
    confidence_interval_diff: Tuple[float, float]
    group1_mean: float
    group2_mean: float
    mean_difference: float
    percent_difference: float
    practical_significance: str
    alpha: float = 0.05


def cohens_d(group1: np.ndarray, group2: np.ndarray) -> float:
    """
    Calculate Cohen's d effect size.

    Cohen's d = (mean1 - mean2) / pooled_std

    Interpretation (Cohen, 1988):
    - |d| < 0.2: negligible
    - 0.2 ≤ |d| < 0.5: small
    - 0.5 ≤ |d| < 0.8: medium
    - |d| ≥ 0.8: large

    Parameters
    ----------
    group1 : np.ndarray
        First group of measurements.
    group2 : np.ndarray
        Second group of measurements.

    Returns
    -------
    float
        Cohen's d effect size.
    """
    n1, n2 = len(group1), len(group2)

    if n1 < 2 or n2 < 2:
        return np.nan

    mean1 = np.mean(group1)
    mean2 = np.mean(group2)

    var1 = np.var(group1, ddof=1)
    var2 = np.var(group2, ddof=1)

    # Pooled standard deviation
    pooled_std = np.sqrt(((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2))

    if pooled_std < 1e-12:
        return np.nan

    return (mean1 - mean2) / pooled_std


def interpret_effect_size(d: float) -> str:
    """Interpret Cohen's d magnitude."""
    abs_d = abs(d)
    if np.isnan(abs_d):
        return "undefined"
    elif abs_d < 0.2:
        return "negligible"
    elif abs_d < 0.5:
        return "small"
    elif abs_d < 0.8:
        return "medium"
    else:
        return "large"


def compare_specimens(
    specimen1_values: np.ndarray,
    specimen2_values: np.ndarray,
    alpha: float = 0.05,
    paired: bool = False,
    practical_threshold_percent: float = 1.0,
) -> ComparisonResult:
    """
    Compare measurements from two specimens.

    Uses appropriate t-test and reports both statistical and
    practical significance.

    Parameters
    ----------
    specimen1_values : np.ndarray
        Measurements from first specimen.
    specimen2_values : np.ndarray
        Measurements from second specimen.
    alpha : float
        Significance level (default 0.05).
    paired : bool
        If True, use paired t-test (same tap locations).
    practical_threshold_percent : float
        Difference threshold for practical significance.

    Returns
    -------
    ComparisonResult
        Complete comparison result.

    Example
    -------
    >>> spruce = np.array([440.1, 440.3, 439.9, 440.0])
    >>> maple = np.array([435.2, 435.5, 435.0, 435.3])
    >>> result = compare_specimens(spruce, maple)
    >>> print(f"Different: {result.statistically_different}, p={result.p_value:.4f}")
    """
    g1 = np.asarray(specimen1_values, dtype=float)
    g2 = np.asarray(specimen2_values, dtype=float)

    n1, n2 = len(g1), len(g2)

    if n1 < 2 or n2 < 2:
        raise ValueError("Each group needs at least 2 measurements")

    mean1 = float(np.mean(g1))
    mean2 = float(np.mean(g2))
    mean_diff = mean1 - mean2

    # Percent difference (relative to group2)
    if abs(mean2) > 1e-12:
        pct_diff = 100 * mean_diff / mean2
    else:
        pct_diff = np.nan

    # Choose test
    if paired:
        if n1 != n2:
            raise ValueError("Paired test requires equal group sizes")
        test_stat, p_value = stats.ttest_rel(g1, g2)
        test_name = "paired_t_test"
    else:
        # Check for equal variances using Levene's test
        _, levene_p = stats.levene(g1, g2)

        if levene_p < 0.05:
            # Unequal variances: use Welch's t-test
            test_stat, p_value = stats.ttest_ind(g1, g2, equal_var=False)
            test_name = "welch_t_test"
        else:
            # Equal variances: use Student's t-test
            test_stat, p_value = stats.ttest_ind(g1, g2, equal_var=True)
            test_name = "student_t_test"

    # Effect size
    d = cohens_d(g1, g2)
    effect_interp = interpret_effect_size(d)

    # Confidence interval for difference
    if paired:
        diffs = g1 - g2
        se_diff = np.std(diffs, ddof=1) / np.sqrt(len(diffs))
        dof = len(diffs) - 1
    else:
        # Pooled standard error
        se1 = np.std(g1, ddof=1) / np.sqrt(n1)
        se2 = np.std(g2, ddof=1) / np.sqrt(n2)
        se_diff = np.sqrt(se1**2 + se2**2)
        # Welch-Satterthwaite dof
        var1 = np.var(g1, ddof=1)
        var2 = np.var(g2, ddof=1)
        num = (var1 / n1 + var2 / n2) ** 2
        denom = (var1 / n1) ** 2 / (n1 - 1) + (var2 / n2) ** 2 / (n2 - 1)
        dof = num / denom if denom > 0 else n1 + n2 - 2

    t_crit = stats.t.ppf(1 - alpha / 2, dof)
    ci_lower = mean_diff - t_crit * se_diff
    ci_upper = mean_diff + t_crit * se_diff

    # Practical significance
    if abs(pct_diff) > practical_threshold_percent:
        if effect_interp in ["medium", "large"]:
            practical = "likely_meaningful"
        else:
            practical = "potentially_meaningful"
    else:
        practical = "not_practically_significant"

    # Statistical significance
    stat_different = p_value < alpha

    return ComparisonResult(
        statistically_different=stat_different,
        p_value=float(p_value),
        test_statistic=float(test_stat),
        test_used=test_name,
        effect_size=float(d),
        effect_interpretation=effect_interp,
        confidence_interval_diff=(float(ci_lower), float(ci_upper)),
        group1_mean=mean1,
        group2_mean=mean2,
        mean_difference=float(mean_diff),
        percent_difference=float(pct_diff),
        practical_significance=practical,
        alpha=alpha,
    )


def compare_conditions(
    baseline_values: np.ndarray,
    treatment_values: np.ndarray,
    alpha: float = 0.05,
    min_detectable_change_percent: float = 0.5,
) -> ComparisonResult:
    """
    Compare measurements under different conditions.

    Specialized for before/after or control/treatment comparisons
    where paired measurements are natural.

    Parameters
    ----------
    baseline_values : np.ndarray
        Measurements under baseline/control condition.
    treatment_values : np.ndarray
        Measurements under treatment condition.
    alpha : float
        Significance level.
    min_detectable_change_percent : float
        Minimum change of interest.

    Returns
    -------
    ComparisonResult
        Comparison result.
    """
    baseline = np.asarray(baseline_values, dtype=float)
    treatment = np.asarray(treatment_values, dtype=float)

    # If same length, assume paired
    paired = len(baseline) == len(treatment)

    return compare_specimens(
        treatment,
        baseline,  # Treatment - baseline to show change direction
        alpha=alpha,
        paired=paired,
        practical_threshold_percent=min_detectable_change_percent,
    )


@dataclass
class PairwiseResult:
    """Result of pairwise comparison with multiple comparison correction."""

    group_i: int
    group_j: int
    group_i_name: str
    group_j_name: str
    mean_difference: float
    p_value_raw: float
    p_value_adjusted: float
    significant_after_correction: bool
    effect_size: float


def pairwise_comparison(
    groups: List[np.ndarray],
    group_names: Optional[List[str]] = None,
    alpha: float = 0.05,
    correction: str = "bonferroni",
) -> Tuple[Dict[str, Any], List[PairwiseResult]]:
    """
    Compare multiple groups with pairwise tests and correction.

    First performs ANOVA to test overall difference, then performs
    pairwise comparisons with multiple comparison correction.

    Parameters
    ----------
    groups : List[np.ndarray]
        List of measurement arrays, one per group.
    group_names : List[str], optional
        Names for each group.
    alpha : float
        Family-wise significance level.
    correction : str
        "bonferroni", "sidak", or "holm".

    Returns
    -------
    Tuple containing:
        - anova_result: Dict with F-statistic, p-value, eta_squared
        - pairwise: List[PairwiseResult] for each pair

    Example
    -------
    >>> spruce = np.array([440, 441, 439])
    >>> maple = np.array([435, 436, 434])
    >>> cedar = np.array([420, 421, 419])
    >>> anova, pairs = pairwise_comparison([spruce, maple, cedar],
    ...     ["spruce", "maple", "cedar"])
    """
    k = len(groups)

    if k < 2:
        raise ValueError("Need at least 2 groups for comparison")

    if group_names is None:
        group_names = [f"Group_{i}" for i in range(k)]

    groups = [np.asarray(g, dtype=float) for g in groups]

    # ANOVA
    f_stat, anova_p = stats.f_oneway(*groups)

    # Eta-squared (effect size for ANOVA)
    grand_mean = np.mean(np.concatenate(groups))
    ss_between = sum(len(g) * (np.mean(g) - grand_mean) ** 2 for g in groups)
    ss_total = sum(np.sum((g - grand_mean) ** 2) for g in groups)
    eta_sq = ss_between / ss_total if ss_total > 0 else 0

    anova_result = {
        "f_statistic": float(f_stat),
        "p_value": float(anova_p),
        "eta_squared": float(eta_sq),
        "significant": anova_p < alpha,
        "n_groups": k,
    }

    # Pairwise comparisons
    n_pairs = k * (k - 1) // 2
    pairwise_results = []
    raw_p_values = []

    for i in range(k):
        for j in range(i + 1, k):
            # Two-sample t-test (Welch's)
            _t_stat, p_raw = stats.ttest_ind(groups[i], groups[j], equal_var=False)
            d = cohens_d(groups[i], groups[j])
            mean_diff = np.mean(groups[i]) - np.mean(groups[j])

            pairwise_results.append(
                {
                    "i": i,
                    "j": j,
                    "name_i": group_names[i],
                    "name_j": group_names[j],
                    "mean_diff": mean_diff,
                    "p_raw": p_raw,
                    "d": d,
                }
            )
            raw_p_values.append(p_raw)

    # Apply correction
    raw_p_values = np.array(raw_p_values)

    if correction == "bonferroni":
        adjusted_p = np.minimum(raw_p_values * n_pairs, 1.0)
    elif correction == "sidak":
        adjusted_p = 1 - (1 - raw_p_values) ** n_pairs
    elif correction == "holm":
        # Holm-Bonferroni step-down
        sorted_idx = np.argsort(raw_p_values)
        adjusted_p = np.zeros(n_pairs)
        for rank, idx in enumerate(sorted_idx):
            adjusted_p[idx] = min(raw_p_values[idx] * (n_pairs - rank), 1.0)
        # Enforce monotonicity
        for rank in range(1, n_pairs):
            idx = sorted_idx[rank]
            prev_idx = sorted_idx[rank - 1]
            adjusted_p[idx] = max(adjusted_p[idx], adjusted_p[prev_idx])
    else:
        adjusted_p = raw_p_values

    # Build final results
    final_pairwise = []
    for result, p_adj in zip(pairwise_results, adjusted_p):
        final_pairwise.append(
            PairwiseResult(
                group_i=result["i"],
                group_j=result["j"],
                group_i_name=result["name_i"],
                group_j_name=result["name_j"],
                mean_difference=float(result["mean_diff"]),
                p_value_raw=float(result["p_raw"]),
                p_value_adjusted=float(p_adj),
                significant_after_correction=p_adj < alpha,
                effect_size=float(result["d"]),
            )
        )

    return anova_result, final_pairwise


def equivalence_test(
    group1: np.ndarray,
    group2: np.ndarray,
    equivalence_margin: float,
    alpha: float = 0.05,
) -> Dict[str, Any]:
    """
    Test whether two groups are equivalent (TOST procedure).

    Unlike standard tests that test for difference, this tests
    whether groups are similar within a specified margin.

    The Two One-Sided Tests (TOST) procedure:
    - Reject H0 if difference is significantly < margin (upper test)
    - AND difference is significantly > -margin (lower test)

    Parameters
    ----------
    group1 : np.ndarray
        First group of measurements.
    group2 : np.ndarray
        Second group of measurements.
    equivalence_margin : float
        Maximum acceptable difference.
    alpha : float
        Significance level.

    Returns
    -------
    Dict with:
        - equivalent: bool
        - p_value: maximum of the two one-sided p-values
        - mean_difference: observed difference
        - margin: equivalence margin used
    """
    g1 = np.asarray(group1, dtype=float)
    g2 = np.asarray(group2, dtype=float)

    mean_diff = np.mean(g1) - np.mean(g2)

    # Pooled standard error (Welch approximation)
    n1, n2 = len(g1), len(g2)
    se = np.sqrt(np.var(g1, ddof=1) / n1 + np.var(g2, ddof=1) / n2)

    # Welch-Satterthwaite degrees of freedom
    var1, var2 = np.var(g1, ddof=1), np.var(g2, ddof=1)
    num = (var1 / n1 + var2 / n2) ** 2
    denom = (var1 / n1) ** 2 / (n1 - 1) + (var2 / n2) ** 2 / (n2 - 1)
    dof = num / denom if denom > 0 else n1 + n2 - 2

    # Lower test: H0: diff <= -margin
    t_lower = (mean_diff - (-equivalence_margin)) / se
    p_lower = 1 - stats.t.cdf(t_lower, dof)

    # Upper test: H0: diff >= margin
    t_upper = (mean_diff - equivalence_margin) / se
    p_upper = stats.t.cdf(t_upper, dof)

    # TOST: both tests must reject
    p_value = max(p_lower, p_upper)
    equivalent = p_value < alpha

    return {
        "equivalent": equivalent,
        "p_value": float(p_value),
        "p_lower": float(p_lower),
        "p_upper": float(p_upper),
        "mean_difference": float(mean_diff),
        "margin": equivalence_margin,
        "confidence_interval": (
            float(mean_diff - stats.t.ppf(1 - alpha, dof) * se),
            float(mean_diff + stats.t.ppf(1 - alpha, dof) * se),
        ),
    }
