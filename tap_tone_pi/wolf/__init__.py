"""
Wolf note analysis and advisory module.

Physics-based detection and decision support for coupled oscillator
(wolf note) phenomena in acoustic instruments.

Modules:
    wolf_beat: Peak-pair detection, linewidth extraction, beat analysis
    wolf_advisor: Decision support engine with mitigation recommendations

Usage:
    from tap_tone_pi.wolf import analyze_wolf_beat, WolfAdvisor

    result = analyze_wolf_beat(frequencies, magnitude, phase)
    advisor = WolfAdvisor(result)
    recommendations = advisor.get_recommendations()
"""

from tap_tone_pi.wolf.wolf_beat import (
    # Data structures
    PeakInfo,
    PeakPair,
    WolfBeatResult,
    AvoidedCrossingModel,
    # Analysis functions
    find_peaks_in_frf,
    find_peak_pairs,
    extract_linewidth,
    extract_linewidth_lorentzian,
    analyze_wolf_beat,
    estimate_coupling_from_split,
    predict_wolf_severity_change,
    # Simulation
    simulate_mass_addition,
    simulate_damping_increase,
)

from tap_tone_pi.wolf.wolf_advisor import (
    # Types
    MitigationType,
    ConfidenceLevel,
    MitigationRecommendation,
    WolfAdvisorResult,
    WolfDirective,
    # Main class
    WolfAdvisor,
    # Convenience functions
    advise_on_wolf,
    generate_wolf_directive,
)

__all__ = [
    # wolf_beat
    "PeakInfo",
    "PeakPair",
    "WolfBeatResult",
    "AvoidedCrossingModel",
    "find_peaks_in_frf",
    "find_peak_pairs",
    "extract_linewidth",
    "extract_linewidth_lorentzian",
    "analyze_wolf_beat",
    "estimate_coupling_from_split",
    "predict_wolf_severity_change",
    "simulate_mass_addition",
    "simulate_damping_increase",
    # wolf_advisor
    "MitigationType",
    "ConfidenceLevel",
    "MitigationRecommendation",
    "WolfAdvisorResult",
    "WolfDirective",
    "WolfAdvisor",
    "advise_on_wolf",
    "generate_wolf_directive",
]
