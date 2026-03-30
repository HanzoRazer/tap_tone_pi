"""
PATCH: scripts/phase2/export_viewer_pack_v1.py
Adds _validate_wolf_candidates_clean() before wolf bundle inclusion.

Apply with:
    python scripts/apply_wolf_clean_gate_patch.py

This patch adds the purity gate from ADR-0009 §3 to the export pipeline.
If wolf_candidates.json contains any advisory fields (from WolfAdvisor),
the export raises ValueError and refuses to produce the bundle.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

GATE_FUNCTION = '''
# ---------------------------------------------------------------------------
# Wolf candidates purity gate (ADR-0009)
# ---------------------------------------------------------------------------

#: Fields that indicate WolfAdvisor output has leaked into wolf_candidates.json.
#: These are decision-support fields and must never appear in viewer_pack_v1.
_PROHIBITED_WOLF_ADVISORY_FIELDS = frozenset({
    "mitigation_suggestions",
    "recommendations",
    "advisor_output",
    "mitigations",
    "recommended_action",
    "confidence_level",   # WolfAdvisor.ConfidenceLevel
    "mitigation_type",    # WolfAdvisor.MitigationType
    "wolf_directive",
    "directive_id",
})


def _validate_wolf_candidates_clean(wc_path: Path) -> None:
    """
    Assert wolf_candidates.json contains no advisory fields.

    Raises ValueError if any WolfAdvisor-specific field is present.
    This is a hard stop — the export fails rather than silently
    contaminating the bundle with decision-support data.

    See docs/ADR-0009-advisory-boundary.md §3.
    """
    try:
        data = json.loads(wc_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return  # Parse errors are caught by other validators

    if not isinstance(data, dict):
        return

    # Check top-level keys
    found_top = _PROHIBITED_WOLF_ADVISORY_FIELDS & set(data.keys())

    # Also check inside a "wolf_candidates" or "candidates" list if present
    found_nested: set[str] = set()
    for candidate_key in ("wolf_candidates", "candidates", "results"):
        candidates = data.get(candidate_key, [])
        if isinstance(candidates, list):
            for item in candidates:
                if isinstance(item, dict):
                    found_nested |= _PROHIBITED_WOLF_ADVISORY_FIELDS & set(item.keys())

    found = found_top | found_nested
    if found:
        raise ValueError(
            f"wolf_candidates.json contains advisory fields: {sorted(found)}. "
            f"WolfAdvisor output (WolfAdvisor.get_recommendations(), "
            f"generate_wolf_directive()) must not appear in viewer_pack_v1. "
            f"Route advisory output to the agentic spine (AttentionDirectiveV1) "
            f"instead. See docs/ADR-0009-advisory-boundary.md"
        )

'''

CALL_SITE_REPLACEMENT = """\
        add_file_fn(wc, "wolf/wolf_candidates.json")"""

CALL_SITE_WITH_GATE = """\
        _validate_wolf_candidates_clean(wc)
        add_file_fn(wc, "wolf/wolf_candidates.json")"""


def patch_export_script() -> bool:
    target = REPO_ROOT / "scripts" / "phase2" / "export_viewer_pack_v1.py"
    if not target.exists():
        print(f"[SKIP] {target} not found")
        return False

    content = target.read_text(encoding="utf-8")

    # --- 1. Insert gate function before export_viewer_pack() ---
    if "_validate_wolf_candidates_clean" in content:
        print("[OK] wolf clean gate already present")
    else:
        insert_anchor = "\ndef export_viewer_pack("
        if insert_anchor in content:
            content = content.replace(insert_anchor, GATE_FUNCTION + insert_anchor)
            print("[PATCH] added _validate_wolf_candidates_clean()")
        else:
            print("[WARN] could not find export_viewer_pack anchor — add manually")
            return False

    # --- 2. Wire call site in _add_derived ---
    if CALL_SITE_REPLACEMENT in content and CALL_SITE_WITH_GATE not in content:
        content = content.replace(CALL_SITE_REPLACEMENT, CALL_SITE_WITH_GATE)
        print("[PATCH] wired _validate_wolf_candidates_clean() before add_file_fn")
    elif CALL_SITE_WITH_GATE in content:
        print("[OK] call site already patched")
    else:
        print("[WARN] could not find add_file_fn call site — add manually")

    target.write_text(content, encoding="utf-8")
    print(f"[DONE] patched {target}")
    return True


if __name__ == "__main__":
    ok = patch_export_script()
    sys.exit(0 if ok else 1)
