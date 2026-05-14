# Critical Systems Design Review: tap-tone-pi

**Date:** 2026-02-18
**Reviewer Role:** Top 1% Critical Systems Design Reviewer
**Project:** tap-tone-pi (Acoustic Measurement Instrument)

---

## Reviewer Assumptions

1. **Target User**: Luthiers, guitar builders, acoustic researchers, and quality-focused hobbyists who need to measure wood acoustic properties without $10K+ commercial analyzers

2. **Deployment Context**: Raspberry Pi or desktop, workshop environment, potentially dusty/humid, intermittent use

3. **Maturity Stage**: Late development/early production - Phase 3 ~95% complete per roadmap

4. **Criticality Level**: Medium - not life-safety, but professional tool where measurement errors could waste expensive tonewood ($200-2000/billet)

5. **Competitive Benchmark**: Lucchi Meter ($3K), BING analyzer ($8K), Audacity + spreadsheet (free but manual)

---

## Evaluation

### 1. Purpose Clarity
**Score: 8/10**

**Justification:**
- Clear mission: democratize tonewood acoustic measurement
- Well-defined value proposition: "$200 setup → 90% of $10K analyzer capability"
- PROJECT_ROADMAP.md articulates phases and priorities well
- Wood database (472 species) demonstrates domain expertise

**Gaps:**
- No single "elevator pitch" document
- Unclear boundary between tap-tone-pi (measurement) and luthiers-toolbox (CAM) - which does what?
- "Phase 2 ODS workflow" assumes user knows what ODS means

**Improvements:**
1. Add `docs/WHAT_IS_THIS.md` - 50-word explanation for cold visitors
2. Clarify in README: "tap-tone-pi measures, luthiers-toolbox manufactures"
3. Glossary of domain terms (ODS, MOE, radiation coefficient)

---

### 2. User Fit
**Score: 6/10**

**Justification:**
- Targets real pain point (expensive analyzers)
- CLI-first design fits technical luthiers
- Quality gate system shows understanding of measurement discipline

**Gaps:**
- Assumes significant technical sophistication
- No persona documentation - who exactly is "the user"?
- GUI requires explanation ("would take some really explaining" - user feedback)
- No consideration of non-English users (472-species database, no i18n)

**Improvements:**
1. Create 3 user personas: (a) Professional luthier, (b) Hobbyist builder, (c) Acoustic researcher
2. Add "Quick Start for Non-Technical Users" with screenshots
3. Default to GUI for novices, CLI for power users
4. Consider Spanish/German/Japanese - major lutherie markets

---

### 3. Usability
**Score: 5/10**

**Justification:**
- Two GUIs exist (Tkinter + PyQt6) - which is canonical?
- `ttp` CLI has good command structure
- Setup wizard (`ttp setup`) exists
- Auto-trigger and quality gates reduce operator error

**Gaps:**
- GUI testing revealed: no onboarding, missing tooltips, silent failures
- Empty state confusion (user didn't know what to click)
- Sample data not included - user can't explore without hardware
- 1500-line main.py is maintenance risk, not usability per se but indicates complexity

**Improvements:**
1. **Pick one GUI** - deprecate the other or clearly differentiate purposes
2. First-run wizard: "No data yet. Would you like to: [Load Sample] [Capture New] [Open File]"
3. Ship with complete sample viewer pack in repo (not just synthetic)
4. Add `--demo` flag: `ttp demo` runs simulated capture → analysis → report
5. Tooltips on every non-obvious metric

---

### 4. Reliability
**Score: 7/10**

**Justification:**
- Extensive test coverage: 1100+ tests mentioned
- Quality gate system (PASS/WARN/FAIL) with policy-based rules
- Uncertainty quantification (Phase 3.2 complete)
- Verification test suite validates against known signals
- Atomic file writes prevent corruption

**Gaps:**
- No MTBF/reliability targets documented
- Hardware failure modes not addressed (what if USB mic disconnects mid-capture?)
- No watchdog for long-running processes
- Calibration expiry exists but no enforcement visible in UI

**Improvements:**
1. Add hardware heartbeat check during capture
2. Graceful degradation: "Microphone disconnected. Last good capture saved."
3. Document expected measurement repeatability (CV < X% for same specimen)
4. Add integration tests with actual hardware (CI badge for hardware lab)
5. Implement calibration expiry warning in GUI

---

### 5. Manufacturability/Maintainability
**Score: 7/10**

**Justification:**
- Clean Python packaging with pyproject.toml
- Modular architecture (core/, limits/, calibration/, verify/)
- Type hints present
- Tests organized by feature

**Gaps:**
- Two GUIs = double maintenance burden
- 1500-line main.py violates single responsibility
- Bare `except:` clauses were found (fixed in luthiers-toolbox, unknown here)
- No architecture diagram
- Dependencies not pinned to exact versions

**Improvements:**
1. Split main.py into command modules: `cli/cmd_record.py`, `cli/cmd_measure.py`, etc.
2. Add `docs/ARCHITECTURE.md` with component diagram
3. Pin dependencies: `numpy==1.26.4` not `numpy>=1.26`
4. Deprecate one GUI, mark other as canonical
5. Add `make lint` target enforcing code standards

---

### 6. Cost
**Score: 9/10**

**Justification:**
- BOM: ~$200 (Pi + USB mic + fixture)
- 95% cost reduction vs commercial ($10K Lucchi/BING)
- Open source - no licensing fees
- Runs on existing hardware (desktop) too

**Gaps:**
- No BOM document with specific part numbers
- No cost-performance tradeoff analysis (cheap mic vs better mic)
- Time cost not considered (setup complexity)

**Improvements:**
1. Add `docs/BOM.md` with Amazon/DigiKey links and total cost
2. Document: "Budget build ($150) vs Pro build ($400)" with capability differences
3. Estimate setup time: "First capture in 30 minutes"

---

### 7. Safety
**Score: 8/10**

**Justification:**
- No physical safety hazards (unlike CNC in luthiers-toolbox)
- No network exposure by default
- No credential storage
- Data is append-only (quality_check.json, session.jsonl)

**Gaps:**
- Audio playback for calibration could damage speakers if gain wrong
- No input validation on file paths (potential path traversal?)
- Third-party dependencies not audited

**Improvements:**
1. Add amplitude limiter to calibration tone output
2. Validate all file paths are within expected directories
3. Run `pip-audit` in CI
4. Document: "This tool does not connect to internet" (trust signal)

---

### 8. Scalability
**Score: 6/10**

**Justification:**
- Single-user, single-machine design is appropriate for use case
- Viewer pack export enables data portability
- No database - JSON files scale poorly beyond ~10K sessions

**Gaps:**
- No batch processing for production QC (measure 100 billets/day)
- No cloud sync or multi-device support
- Session storage is flat files - will degrade with thousands of sessions
- No data retention policy

**Improvements:**
1. Add `ttp batch --input specimens.csv --output results/` for production
2. Consider SQLite for session index (keep JSON for portability)
3. Add `ttp archive --older-than 1y` to compress old sessions
4. Document scaling limits: "Tested with 500 sessions, expect X performance"

---

### 9. Aesthetics
**Score: 7/10**

**Justification:**
- PyQt6 dark theme looks professional
- CLI output is clean and readable
- Spectrum plots use standard matplotlib styling
- Status bar provides feedback

**Gaps:**
- Tkinter GUI looks dated
- No consistent icon set
- CLI uses Unicode symbols (✓, ⚠) - may render poorly on some terminals
- No branding/logo

**Improvements:**
1. Standardize on PyQt6 aesthetic
2. Add `--no-unicode` flag for legacy terminals
3. Create simple logo/icon for GUI window
4. Consistent color coding: green=pass, yellow=warn, red=fail everywhere

---

## Summary Scorecard

| Category | Score | Priority Fix |
|----------|-------|--------------|
| Purpose Clarity | 8/10 | Add elevator pitch doc |
| User Fit | 6/10 | Create user personas, improve onboarding |
| Usability | 5/10 | **Pick one GUI, add demo mode** |
| Reliability | 7/10 | Hardware disconnect handling |
| Maintainability | 7/10 | Split main.py, add architecture doc |
| Cost | 9/10 | Add BOM document |
| Safety | 8/10 | Amplitude limiter, pip-audit |
| Scalability | 6/10 | Batch mode for production |
| Aesthetics | 7/10 | Deprecate Tkinter GUI |

**Overall: 6.8/10** — Solid technical foundation with significant usability gaps

---

## Top 3 Critical Actions

1. **Consolidate to one GUI** — Dual GUI creates confusion, doubles maintenance, splits documentation effort. Pick PyQt6 (better aesthetics, more capable) and deprecate Tkinter.

2. **Ship working demo mode** — User cannot evaluate product without hardware. `ttp demo` should run a complete simulated workflow with included sample data.

3. **Onboarding flow** — First-run experience should guide user from "I just installed this" to "I made my first measurement" in under 10 minutes with zero prior knowledge.

---

*Review conducted as top-1% critical systems reviewer. Scores reflect professional-grade expectations, not hobbyist project standards.*
