
## Analyzer GUI UX Issues (Noted 2026-02-18)

### From User Testing Session

**Context:** First-time user testing the PyQt6 Analyzer GUI with sample data.

#### Issues Identified:

1. **Wood Properties Not Populating**
   - "Full Analysis" button doesn't populate Est. Stiffness, Damping, Quality Factor
   - Root cause: Sample pack missing required specimen dimensions (length, width, thickness, mass)
   - Fix: Either require metadata in pack OR prompt user for dimensions

2. **No Onboarding/Tutorial**
   - User comment: "Would take some really explaining to make the user comfortable"
   - Need: First-run wizard or guided walkthrough
   - Suggested: "What do I do first?" prompt on empty state

3. **Missing Tooltips**
   - Metrics like "Coherence", "Quality Factor", "Est. Stiffness" not explained
   - Add hover tooltips with brief explanations

4. **No Feedback on Failed Operations**
   - When wood properties can't be calculated, no error/explanation shown
   - Need: Status message explaining what's missing

5. **Sample Data Gap**
   - Project ships without working sample data
   - Need: Include complete viewer pack with full metadata for demo

#### Working Features (Validated):
- ✅ Pack loading (ZIP format)
- ✅ Spectrum visualization
- ✅ Zoom in/out
- ✅ Coherence plot with threshold
- ✅ Tab navigation (Spectrum, Bode Plot, WSI Curve, Plate Tuning)
- ✅ Overall visual feel ("nice feel")

#### Priority: P2 (Polish)
These are UX improvements, not blocking core functionality.

---

## Feature Gap: Per-Point Thickness/Density Tracking (Noted 2026-02-28)

**See:** [FEATURE_GAP_THICKNESS_TRACKING.md](FEATURE_GAP_THICKNESS_TRACKING.md)

**Summary:** The `TuningPoint` dataclass tracks mass, frequency, and deflection but not thickness. Since thickness changes at each thinning step, density and stiffness cannot be auto-calculated per measurement point.

**Priority:** P3 (Enhancement)

---
