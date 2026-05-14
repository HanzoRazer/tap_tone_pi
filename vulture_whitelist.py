"""Vulture whitelist — dummy references to suppress false positives.

Run vulture with:
    vulture tap_tone_pi/ tests/ vulture_whitelist.py --min-confidence 80
"""

# ---------------------------------------------------------------------------
# PyAudio / sounddevice callback signature args (required by protocol)
# ---------------------------------------------------------------------------
time_info  # noqa: F821  # sounddevice callback arg in core/auto_trigger.py
frames  # noqa: F821  # sounddevice callback arg in core/auto_trigger.py

# ---------------------------------------------------------------------------
# Context-manager __exit__ args (required by protocol)
# ---------------------------------------------------------------------------
exc_type  # noqa: F821  # viewer_pack/manifest.py
exc_val  # noqa: F821
exc_tb  # noqa: F821

# ---------------------------------------------------------------------------
# Test fixtures — injected by pytest fixture mechanism, appear unused to
# static analysis but are required to activate the fixture side-effects.
# ---------------------------------------------------------------------------
patch_passing  # noqa: F821  # test_event_emission_operator_loop, test_spine_shadow_hook
patch_all_passing  # noqa: F821  # test_workflow_operator_loop
patch_with_fail  # noqa: F821  # test_workflow_operator_loop
patch_with_warn  # noqa: F821  # test_workflow_operator_loop
patch_failing  # noqa: F821  # test_event_emission_operator_loop, test_spine_shadow_hook
patch_analysis_error  # noqa: F821  # test_event_emission_operator_loop, test_spine_shadow_hook
kw  # noqa: F821  # test_cli_export_pack, test_cli_record_qc
tmp_xdg  # noqa: F821  # test_uwsm_persistence
severe_wolf_frf  # noqa: F821  # test_wolf_advisor

# ---------------------------------------------------------------------------
# Test imports used indirectly (e.g., numpy.testing helpers)
# ---------------------------------------------------------------------------
assert_array_less  # noqa: F821  # test_production_physics

# ---------------------------------------------------------------------------
# Tkinter binding callbacks — `event` parameter required by Tk protocol
# even when the handler doesn't inspect the event object.
# (grid_widgets.py ×3, widgets.py ×3, session_browser.py ×2)
# ---------------------------------------------------------------------------
event  # noqa: F821  # Tk binding callback arg

# ---------------------------------------------------------------------------
# CLI sub-command entry points — `args` parameter is the argparse namespace,
# required by the dispatcher but not always inspected in the handler.
# (calibrate.py, generate.py)
# ---------------------------------------------------------------------------
args  # noqa: F821  # CLI sub-command handler

# ---------------------------------------------------------------------------
# Public-API / keyword-passed parameters — currently unused in function body
# but part of the stable call signature or passed via **kwargs by callers.
# ---------------------------------------------------------------------------
tolerance_hz  # noqa: F821  # modes/chladni/policy.py, chladni policy threshold
a  # noqa: F821  # bending/alpha_beta.py
b  # noqa: F821  # bending/alpha_beta.py
brace_stiffness_total  # noqa: F821  # bending/alpha_beta.py
n_averages  # noqa: F821  # transfer_function/estimators.py
method  # noqa: F821  # wolf/wolf_beat.py
is_calibrated  # noqa: F821  # uncertainty/frequency.py, uncertainty/stiffness.py
width_mm  # noqa: F821  # uncertainty/stiffness.py
width_uncertainty_mm  # noqa: F821  # uncertainty/stiffness.py
guidance  # noqa: F821  # agentic/spine/policy.py (_build_directive)

# ---------------------------------------------------------------------------
# Protocol / event-system parameters — required by caller contract.
# ---------------------------------------------------------------------------
evs  # noqa: F821  # agentic/spine/moments.py — event list param

# ---------------------------------------------------------------------------
# Test classes — discovered by pytest collector, appear unused to static
# analysis but are executed as test suites.
# ---------------------------------------------------------------------------
TestGoldenExport  # noqa: F821  # scripts/phase2/test_export_viewer_pack_v1_golden.py
TestBothSessionsExportIdentically  # noqa: F821  # scripts/phase2/test_export_viewer_pack_v1_golden.py
