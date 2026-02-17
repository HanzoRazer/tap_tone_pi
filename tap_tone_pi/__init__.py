"""tap_tone_pi — Unified acoustic measurement package.

Version 2.0.0 consolidates the tap_tone, tap-tone-lab, and modes namespaces
into a single coherent package structure.

Subpackages:
- core: Analysis, config, DSP fundamentals
- capture: Audio and sensor acquisition
- io: WAV I/O, manifest generation
- phase1: Single-channel tap tone analysis
- phase2: Two-channel ODS, coherence, wolf metrics
- bending: MOE/stiffness measurement
- chladni: Pattern frequency indexing
- export: Viewer pack generation
- cli: Command-line interface
- gui: Tkinter GUI

Production-grade physics modules (Phase 3):
- damping: Modal damping extraction with cross-validation
- uncertainty: ISO GUM-compliant uncertainty quantification
- transfer_function: H1/H2/Hv estimators with coherence
- multitap: Multi-tap statistical analysis

"""

from typing import Any

__version__ = "2.0.0"
__all__ = ["__version__"]

# Lazy imports for production-grade physics modules
def __getattr__(name: str) -> Any:
    """Lazy loading of submodules."""
    if name == "damping":
        from . import damping
        return damping
    elif name == "uncertainty":
        from . import uncertainty
        return uncertainty
    elif name == "transfer_function":
        from . import transfer_function
        return transfer_function
    elif name == "multitap":
        from . import multitap
        return multitap
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
