# Contributing to tap_tone_pi

This repo is an **instrumentation toolchain**. The primary success criteria are:
- measurement defensibility (evidence preserved)
- deterministic derived results (same input -> same output)
- clear boundaries (no interpretive claims baked into the tool)

Please read:
- `docs/MEASUREMENT_BOUNDARY.md`
- `docs/ADR-0001-measurement-scope.md` and other ADRs relevant to your area

---

## Table of Contents

- [Development Setup](#development-setup)
- [Code Style](#code-style)
- [Testing](#testing)
- [Branching](#branching)
- [Pull Requests](#pull-requests)
- [Architecture Guidelines](#architecture-guidelines)
- [Measurement-Only Rule](#measurement-only-rule)

---

## Development Setup

### Prerequisites

- Python 3.11 or higher
- Git
- A microphone (for testing audio capture)

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/HanzoRazer/tap_tone_pi.git
   cd tap_tone_pi
   ```

2. Create a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scriptsctivate
   ```

3. Install in development mode:
   ```bash
   pip install -e ".[dev]"
   ```

4. Verify installation:
   ```bash
   ttp --help
   python -m pytest tests/ -v --tb=short
   ```

---

## Code Style

### Formatting and Linting

We use Ruff for formatting and linting:

```bash
# Check formatting
ruff format --check .

# Format code
ruff format .

# Run linter
ruff check .

# Auto-fix linting issues
ruff check --fix .
```

### Type Hints

All public functions should have type hints.

### Docstrings

Use Google-style docstrings with Args, Returns, and Raises sections.

### General Principles

- prefer explicit dataclasses/models for run artifacts
- keep "evidence writing" separate from "derived writing"
- avoid hidden state, avoid silent fallbacks
- deterministic processing: document any randomness (and seed it)

---

## Testing

### Running Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_core_errors.py -v

# Run with coverage
python -m pytest tests/ --cov=tap_tone_pi --cov-report=html
```

### Writing Tests

1. Create test files in `tests/` with names starting with `test_`
2. Use pytest fixtures for common setup
3. Mock external dependencies (sounddevice, file I/O)
4. Test both success and failure paths

---

## Branching

Suggested branches:
- `feature/<topic>-<short-desc>`
- `fix/<topic>-<short-desc>`
- `docs/<topic>-<short-desc>`

---

## Pull Requests

PRs should include:
- purpose + scope
- test/validation steps run
- any output shape changes called out explicitly

### Evidence-bearing PRs

If a PR makes a material claim about measurement, uncertainty, hardware state,
calibration, acquisition, a physical experiment, an analyzer capability, or
validation, it also carries a claim record. The
[PR Admission Protocol](docs/TTP_PR_ADMISSION_PROTOCOL.md) explains what that
means; `.github/pull_request_template.md` carries the fields.

The rule it exists for:

> Do not increase the strength of a claim beyond the strength of the evidence
> supporting it.

Green tests are not by themselves evidence of a valid physical measurement, and
a manufacturer specification does not become a measured TTP quantity without an
executed measurement. Routine work — refactors, formatting, typos, dependency
bumps — makes no such claim and needs no claim record.

The protocol is **advisory**. It owns no scientific or hardware state; it asks a
PR to report truthfully what the existing authorities already say.

### Commit Messages

Use conventional commit format: `type(scope): short description`

Types: `feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `chore`

### Required Checks

If you change Phase 2 code:
- update docs if behavior/CLI/output changed
- update schemas under `contracts/` if JSON output shapes changed

---

## Architecture Guidelines

### Error Handling

Use the custom exception hierarchy in `tap_tone_pi.core.errors`:
- DeviceError, DeviceNotFoundError, DeviceOpenError
- CaptureError, CaptureTimeoutError
- ValidationError, AnalysisError, QualityError

Include helpful suggestions in error messages.

### Lazy Imports

Heavy dependencies (numpy, sounddevice) should be imported inside functions,
not at module level, to improve CLI startup time.

### Validation Early

Validate inputs at function entry before doing work.

---

## Measurement-Only Rule

This repo must not:
- assert tone quality labels
- suggest structural modifications
- embed prescriptive advice

It may:
- compute objective features (peaks, coherence, transfer functions)
- compute conservative heuristics (WSI)
- attach quality/confidence metadata

Anything interpretive belongs to a separate advisory layer (Phase 3), and must be
explicitly marked as advisory with provenance and uncertainty.

---

## Additional Resources

- [API Documentation](docs/API.md) - API reference
- [Quick Start Guide](docs/QUICK_START.md) - Getting started
- [Measurement Boundary](docs/MEASUREMENT_BOUNDARY.md) - Scope and limitations

Thank you for contributing!
