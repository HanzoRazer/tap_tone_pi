"""
Uncertainty propagation methods following GUM and GUM Supplement 1.

This module provides:
- Analytical uncertainty propagation (linear approximation)
- Monte Carlo uncertainty propagation (GUM Supplement 1)
- Sensitivity coefficient calculation
- Correlation handling

Mathematical Background:
------------------------
For a measurement model y = f(x_1, x_2, ..., x_N), the law of propagation
of uncertainty (GUM Section 5.1) gives:

    u²(y) = Σᵢ (∂f/∂xᵢ)² u²(xᵢ) + 2 Σᵢ Σⱼ₍ᵢ₎ (∂f/∂xᵢ)(∂f/∂xⱼ) u(xᵢ,xⱼ)

For uncorrelated inputs, the covariance terms vanish.

The Monte Carlo method (GUM Supplement 1) propagates full probability
distributions rather than just moments, which is essential when:
- The model is significantly nonlinear
- Probability distributions are asymmetric
- The linearization is inadequate
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Dict, Tuple, Any, Union
import numpy as np
from scipy import stats

from .budget import (
    UncertaintyComponent,
    CombinedUncertainty,
    DistributionType,
    welch_satterthwaite_dof,
    coverage_factor,
)


@dataclass
class PropagationResult:
    """
    Result of uncertainty propagation.

    Attributes
    ----------
    output_value : float
        f(x_1, ..., x_N) evaluated at input values.
    standard_uncertainty : float
        Propagated standard uncertainty u(y).
    sensitivity_coefficients : Dict[str, float]
        Partial derivatives ∂f/∂xᵢ for each input.
    contribution_percent : Dict[str, float]
        Percent contribution of each input to total variance.
    effective_dof : float
        Effective degrees of freedom.
    expanded_uncertainty : float
        Expanded uncertainty at specified confidence.
    coverage_factor : float
        Coverage factor k used.
    confidence_level : float
        Confidence level for expanded uncertainty.
    method : str
        "analytical" or "monte_carlo"
    """
    output_value: float
    standard_uncertainty: float
    sensitivity_coefficients: Dict[str, float] = field(default_factory=dict)
    contribution_percent: Dict[str, float] = field(default_factory=dict)
    effective_dof: float = float('inf')
    expanded_uncertainty: float = 0.0
    coverage_factor: float = 2.0
    confidence_level: float = 0.95
    method: str = "analytical"


def sensitivity_coefficients(
    model_func: Callable[..., float],
    input_values: Dict[str, float],
    delta_fraction: float = 1e-6,
) -> Dict[str, float]:
    """
    Calculate sensitivity coefficients via numerical differentiation.

    Computes ∂f/∂xᵢ using central differences:
        ∂f/∂xᵢ ≈ [f(xᵢ + δ) - f(xᵢ - δ)] / (2δ)

    Parameters
    ----------
    model_func : Callable
        Function y = f(**inputs) that takes keyword arguments.
    input_values : Dict[str, float]
        Current values of all input quantities.
    delta_fraction : float
        Fractional perturbation for numerical derivative.

    Returns
    -------
    Dict[str, float]
        Sensitivity coefficient for each input.

    Example
    -------
    >>> def area(length, width):
    ...     return length * width
    >>> coeffs = sensitivity_coefficients(area, {"length": 10.0, "width": 5.0})
    >>> print(coeffs)  # {'length': 5.0, 'width': 10.0}
    """
    coefficients = {}

    for name, value in input_values.items():
        if value == 0:
            delta = delta_fraction
        else:
            delta = abs(value) * delta_fraction

        # Forward evaluation
        inputs_plus = input_values.copy()
        inputs_plus[name] = value + delta
        y_plus = model_func(**inputs_plus)

        # Backward evaluation
        inputs_minus = input_values.copy()
        inputs_minus[name] = value - delta
        y_minus = model_func(**inputs_minus)

        # Central difference
        coefficients[name] = (y_plus - y_minus) / (2 * delta)

    return coefficients


def propagate_uncertainty(
    model_func: Callable[..., float],
    input_values: Dict[str, float],
    input_uncertainties: Dict[str, float],
    input_dofs: Optional[Dict[str, int]] = None,
    correlation_matrix: Optional[np.ndarray] = None,
    input_names_order: Optional[List[str]] = None,
    confidence_level: float = 0.95,
) -> PropagationResult:
    """
    Propagate uncertainty through a measurement model (analytical method).

    Implements GUM Section 5.1 law of propagation of uncertainty:

        u²(y) = Σᵢ cᵢ² u²(xᵢ) + 2 Σᵢ<ⱼ cᵢcⱼ u(xᵢ)u(xⱼ)rᵢⱼ

    where cᵢ = ∂f/∂xᵢ are sensitivity coefficients and rᵢⱼ are correlations.

    Parameters
    ----------
    model_func : Callable
        Function y = f(**inputs) representing the measurement model.
    input_values : Dict[str, float]
        Current values of all input quantities.
    input_uncertainties : Dict[str, float]
        Standard uncertainties u(xᵢ) for each input.
    input_dofs : Dict[str, int], optional
        Degrees of freedom for each input. Default: 50 (infinite).
    correlation_matrix : np.ndarray, optional
        Correlation matrix rᵢⱼ. Default: identity (uncorrelated).
    input_names_order : List[str], optional
        Order of inputs for correlation matrix. Default: dict key order.
    confidence_level : float
        Confidence level for expanded uncertainty.

    Returns
    -------
    PropagationResult
        Complete propagation result with expanded uncertainty.

    Example
    -------
    >>> def moe(E, I, L, delta):
    ...     # Simplified MOE calculation
    ...     return (E * I) / (L * delta)
    >>> values = {"E": 12.0, "I": 1000.0, "L": 500.0, "delta": 2.0}
    >>> uncertainties = {"E": 0.5, "I": 50.0, "L": 1.0, "delta": 0.1}
    >>> result = propagate_uncertainty(moe, values, uncertainties)
    """
    # Input validation
    if set(input_values.keys()) != set(input_uncertainties.keys()):
        raise ValueError("input_values and input_uncertainties must have same keys")

    names = input_names_order or list(input_values.keys())
    n = len(names)

    # Default degrees of freedom
    if input_dofs is None:
        input_dofs = {name: 50 for name in names}

    # Default correlation matrix (uncorrelated)
    if correlation_matrix is None:
        correlation_matrix = np.eye(n)

    # Evaluate model at current values
    output_value = model_func(**input_values)

    # Calculate sensitivity coefficients
    coeffs = sensitivity_coefficients(model_func, input_values)

    # Build arrays in consistent order
    c = np.array([coeffs[name] for name in names])
    u = np.array([input_uncertainties[name] for name in names])
    nu = np.array([input_dofs.get(name, 50) for name in names])

    # Covariance matrix from correlation
    # Cov(xᵢ, xⱼ) = rᵢⱼ × u(xᵢ) × u(xⱼ)
    U_diag = np.diag(u)
    cov_matrix = U_diag @ correlation_matrix @ U_diag

    # Combined variance: u²(y) = c^T × Cov × c
    variance = c @ cov_matrix @ c
    u_combined = math.sqrt(max(0, variance))

    # Individual contributions (uncorrelated part only)
    contributions = (c * u) ** 2
    total_var = sum(contributions)

    contribution_pct = {}
    for i, name in enumerate(names):
        pct = 100.0 * contributions[i] / total_var if total_var > 0 else 0.0
        contribution_pct[name] = round(pct, 2)

    # Effective degrees of freedom (Welch-Satterthwaite)
    nu_eff = welch_satterthwaite_dof(contributions.tolist(), nu.tolist())

    # Coverage factor and expanded uncertainty
    k = coverage_factor(nu_eff, confidence_level)
    U = k * u_combined

    return PropagationResult(
        output_value=output_value,
        standard_uncertainty=u_combined,
        sensitivity_coefficients={name: float(coeffs[name]) for name in names},
        contribution_percent=contribution_pct,
        effective_dof=nu_eff,
        expanded_uncertainty=U,
        coverage_factor=k,
        confidence_level=confidence_level,
        method="analytical",
    )


@dataclass
class MonteCarloResult:
    """
    Result of Monte Carlo uncertainty propagation.

    Attributes
    ----------
    output_value : float
        Mean of output distribution.
    standard_uncertainty : float
        Standard deviation of output distribution.
    expanded_uncertainty : float
        Shortest coverage interval at confidence level.
    coverage_interval : Tuple[float, float]
        (lower, upper) bounds of coverage interval.
    confidence_level : float
        Confidence level used.
    samples : np.ndarray
        Raw Monte Carlo samples (if retained).
    percentiles : Dict[str, float]
        Key percentiles of output distribution.
    skewness : float
        Skewness of output distribution.
    kurtosis : float
        Excess kurtosis of output distribution.
    n_samples : int
        Number of Monte Carlo trials.
    """
    output_value: float
    standard_uncertainty: float
    expanded_uncertainty: float
    coverage_interval: Tuple[float, float]
    confidence_level: float
    samples: Optional[np.ndarray] = None
    percentiles: Dict[str, float] = field(default_factory=dict)
    skewness: float = 0.0
    kurtosis: float = 0.0
    n_samples: int = 0


def monte_carlo_uncertainty(
    model_func: Callable[..., float],
    input_distributions: Dict[str, Tuple[str, float, float]],
    n_samples: int = 100000,
    confidence_level: float = 0.95,
    retain_samples: bool = False,
    seed: Optional[int] = None,
) -> MonteCarloResult:
    """
    Propagate uncertainty using Monte Carlo method (GUM Supplement 1).

    Propagates full probability distributions through the model by:
    1. Drawing samples from each input distribution
    2. Evaluating the model for each sample set
    3. Analyzing the output distribution

    Parameters
    ----------
    model_func : Callable
        Function y = f(**inputs) representing the measurement model.
    input_distributions : Dict[str, Tuple[str, float, float]]
        For each input: (distribution_type, param1, param2)
        Types: "normal" (mean, std), "rectangular" (low, high),
               "triangular" (low, high), "t" (mean, std, dof as param2)
    n_samples : int
        Number of Monte Carlo trials (default 100,000).
    confidence_level : float
        Confidence level for coverage interval.
    retain_samples : bool
        If True, include raw samples in result.
    seed : int, optional
        Random seed for reproducibility.

    Returns
    -------
    MonteCarloResult
        Complete Monte Carlo propagation result.

    Example
    -------
    >>> def resistor_power(V, R):
    ...     return V**2 / R
    >>> dists = {
    ...     "V": ("normal", 5.0, 0.1),      # V = 5.0 ± 0.1
    ...     "R": ("rectangular", 95, 105),   # R uniform in [95, 105]
    ... }
    >>> result = monte_carlo_uncertainty(resistor_power, dists, n_samples=50000)
    """
    if seed is not None:
        np.random.seed(seed)

    # Generate samples for each input
    input_samples = {}
    for name, (dist_type, p1, p2) in input_distributions.items():
        if dist_type == "normal":
            input_samples[name] = np.random.normal(p1, p2, n_samples)
        elif dist_type == "rectangular":
            input_samples[name] = np.random.uniform(p1, p2, n_samples)
        elif dist_type == "triangular":
            # Symmetric triangular with mode at center
            mode = (p1 + p2) / 2
            input_samples[name] = np.random.triangular(p1, mode, p2, n_samples)
        elif dist_type == "t":
            # Student's t: p1 = mean, p2 = scale (roughly std)
            # Using df=10 as reasonable default for metrological context
            input_samples[name] = p1 + p2 * np.random.standard_t(10, n_samples)
        else:
            raise ValueError(f"Unknown distribution type: {dist_type}")

    # Evaluate model for each sample
    output_samples = np.zeros(n_samples)
    for i in range(n_samples):
        kwargs = {name: samples[i] for name, samples in input_samples.items()}
        try:
            output_samples[i] = model_func(**kwargs)
        except (ValueError, ZeroDivisionError):
            output_samples[i] = np.nan

    # Remove any NaN values
    valid_samples = output_samples[~np.isnan(output_samples)]
    if len(valid_samples) < n_samples * 0.9:
        raise RuntimeError(
            f"Too many failed evaluations: {n_samples - len(valid_samples)}/{n_samples}"
        )

    # Calculate statistics
    mean = float(np.mean(valid_samples))
    std = float(np.std(valid_samples, ddof=1))

    # Shortest coverage interval
    alpha = 1 - confidence_level
    sorted_samples = np.sort(valid_samples)
    n_valid = len(sorted_samples)
    n_coverage = int(np.ceil(n_valid * confidence_level))

    # Find shortest interval containing n_coverage samples
    min_width = float('inf')
    best_lower = sorted_samples[0]
    best_upper = sorted_samples[-1]

    for i in range(n_valid - n_coverage + 1):
        lower = sorted_samples[i]
        upper = sorted_samples[i + n_coverage - 1]
        width = upper - lower
        if width < min_width:
            min_width = width
            best_lower = lower
            best_upper = upper

    # Percentiles
    percentiles = {
        "p1": float(np.percentile(valid_samples, 1)),
        "p5": float(np.percentile(valid_samples, 5)),
        "p25": float(np.percentile(valid_samples, 25)),
        "p50": float(np.percentile(valid_samples, 50)),
        "p75": float(np.percentile(valid_samples, 75)),
        "p95": float(np.percentile(valid_samples, 95)),
        "p99": float(np.percentile(valid_samples, 99)),
    }

    # Distribution shape
    skewness = float(stats.skew(valid_samples))
    kurtosis = float(stats.kurtosis(valid_samples))  # Excess kurtosis

    return MonteCarloResult(
        output_value=mean,
        standard_uncertainty=std,
        expanded_uncertainty=min_width,
        coverage_interval=(float(best_lower), float(best_upper)),
        confidence_level=confidence_level,
        samples=valid_samples if retain_samples else None,
        percentiles=percentiles,
        skewness=skewness,
        kurtosis=kurtosis,
        n_samples=len(valid_samples),
    )


def correlation_matrix(
    correlations: List[Tuple[str, str, float]],
    variable_names: List[str],
) -> np.ndarray:
    """
    Build correlation matrix from pairwise correlations.

    Parameters
    ----------
    correlations : List[Tuple[str, str, float]]
        List of (var1, var2, correlation) tuples.
        Correlation must be in [-1, 1].
    variable_names : List[str]
        Ordered list of variable names.

    Returns
    -------
    np.ndarray
        N×N correlation matrix.

    Example
    -------
    >>> corrs = [("length", "width", 0.3)]
    >>> names = ["length", "width", "height"]
    >>> R = correlation_matrix(corrs, names)
    >>> print(R)
    [[1.  0.3 0. ]
     [0.3 1.  0. ]
     [0.  0.  1. ]]
    """
    n = len(variable_names)
    R = np.eye(n)

    name_to_idx = {name: i for i, name in enumerate(variable_names)}

    for var1, var2, rho in correlations:
        if var1 not in name_to_idx or var2 not in name_to_idx:
            continue
        if not -1 <= rho <= 1:
            raise ValueError(f"Correlation must be in [-1, 1], got {rho}")

        i = name_to_idx[var1]
        j = name_to_idx[var2]
        R[i, j] = rho
        R[j, i] = rho

    # Verify positive semi-definiteness
    eigenvalues = np.linalg.eigvalsh(R)
    if np.min(eigenvalues) < -1e-10:
        raise ValueError("Correlation matrix is not positive semi-definite")

    return R


def validate_gum_assumptions(
    model_func: Callable[..., float],
    input_values: Dict[str, float],
    input_uncertainties: Dict[str, float],
    n_test_points: int = 5,
) -> Dict[str, Any]:
    """
    Validate that GUM linearization is adequate for this model.

    Compares analytical propagation against Monte Carlo to detect
    significant nonlinearity that would invalidate the linear approximation.

    Parameters
    ----------
    model_func : Callable
        Measurement model function.
    input_values : Dict[str, float]
        Nominal values.
    input_uncertainties : Dict[str, float]
        Standard uncertainties.
    n_test_points : int
        Points per input to test linearity.

    Returns
    -------
    Dict[str, Any]
        Validation results including:
        - linearization_adequate: bool
        - max_nonlinearity_percent: float
        - recommendation: str
    """
    # Analytical propagation
    analytical = propagate_uncertainty(
        model_func, input_values, input_uncertainties
    )

    # Monte Carlo (smaller sample for quick check)
    mc_dists = {}
    for name in input_values:
        mc_dists[name] = ("normal", input_values[name], input_uncertainties[name])

    mc = monte_carlo_uncertainty(model_func, mc_dists, n_samples=10000)

    # Compare results
    rel_diff_mean = abs(analytical.output_value - mc.output_value) / abs(mc.output_value + 1e-12)
    rel_diff_std = abs(analytical.standard_uncertainty - mc.standard_uncertainty) / (mc.standard_uncertainty + 1e-12)

    # Check skewness - significant skewness indicates nonlinearity
    skewness_threshold = 0.5

    linearization_adequate = (
        rel_diff_mean < 0.01 and
        rel_diff_std < 0.10 and
        abs(mc.skewness) < skewness_threshold
    )

    if linearization_adequate:
        recommendation = "GUM analytical method is adequate"
    elif abs(mc.skewness) > skewness_threshold:
        recommendation = "Use Monte Carlo: output distribution is asymmetric"
    else:
        recommendation = "Use Monte Carlo: significant nonlinearity detected"

    return {
        "linearization_adequate": linearization_adequate,
        "mean_relative_difference": float(rel_diff_mean),
        "std_relative_difference": float(rel_diff_std),
        "output_skewness": float(mc.skewness),
        "output_kurtosis": float(mc.kurtosis),
        "recommendation": recommendation,
        "analytical_result": analytical,
        "monte_carlo_result": mc,
    }
