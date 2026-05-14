# Shadow Mode Integration Plan (Cross-repo PR Checklist)

**Goal:** Turn the agentic spine from "docs + reference code" into a live integration running in shadow mode (M0) across repos.

**Non-goal:** Emit any user-visible directives. This plan is purely observational.

---

## Overview

| Phase | Scope | Risk | Outcome |
|-------|-------|------|---------|
| 1 | Lock spine into CI | None | Hard floor, can't regress |
| 2 | Contracts as versioned artifacts | None | No shape debates |
| 3 | Emit events from tools/analyzer | Low | Uniform Layer 0 stream |
| 4 | Shadow replay on real sessions | None | Tune without touching UX |
| 5 | Shadow scoreboard | None | Numerical handle on usefulness |

---

## Phase 1: Lock the spine into CI

### PR #1A: luthiers-toolbox CI job

**Files to add/modify:**

```
.github/workflows/spine-ci.yml   (new)
```

**Content:**

```yaml
name: Spine Tests

on:
  push:
    branches: [main]
    paths:
      - 'services/api/app/agentic/**'
      - 'services/api/tests/test_*_engine_v1.py'
      - 'services/api/tests/test_replay_smoke.py'
      - 'services/api/tests/test_event_contract_parity.py'
  pull_request:
    paths:
      - 'services/api/app/agentic/**'
      - 'services/api/tests/test_*_engine_v1.py'
      - 'services/api/tests/test_replay_smoke.py'
      - 'services/api/tests/test_event_contract_parity.py'

jobs:
  spine:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: services/api
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install deps
        run: |
          pip install --upgrade pip
          pip install -r requirements-dev.txt
          pip install -e .
      - name: Run spine tests
        run: |
          pytest -q \
            tests/test_event_contract_parity.py \
            tests/test_moments_engine_v1.py \
            tests/test_policy_engine_v1.py \
            tests/test_replay_smoke.py
```

---

### PR #1B: tap_tone_pi CI job

**Files to add/modify:**

```
.github/workflows/spine-ci.yml   (new)
```

**Content:**

```yaml
name: Spine Tests

on:
  push:
    branches: [main]
    paths:
      - 'tap_tone_pi/agentic/**'
      - 'tests/test_*_engine_v1.py'
      - 'tests/test_replay_smoke.py'
      - 'tests/test_event_contract_parity.py'
  pull_request:
    paths:
      - 'tap_tone_pi/agentic/**'
      - 'tests/test_*_engine_v1.py'
      - 'tests/test_replay_smoke.py'
      - 'tests/test_event_contract_parity.py'

jobs:
  spine:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install deps
        run: |
          pip install --upgrade pip
          pip install -r requirements-dev.txt
          pip install -e .
      - name: Run spine tests
        run: |
          pytest -q \
            tests/test_event_contract_parity.py \
            tests/test_moments_engine_v1.py \
            tests/test_policy_engine_v1.py \
            tests/test_replay_smoke.py
```

**Test locally:**

```bash
make test-spine
```

**Merge gate:** PR must not be merged if spine tests fail.

---

## Phase 2: Contracts as versioned artifacts

### PR #2: Create contracts directory

**Repo:** luthiers-toolbox (canonical source), sync to tap_tone_pi

**Files to add:**

```
contracts/
├── agent_event_v1.schema.json
├── tool_capability_v1.schema.json
├── attention_directive_v1.schema.json
├── uwsm_v1.schema.json
├── CONTRACTS_VERSION.json
└── CHANGELOG.md
```

**CONTRACTS_VERSION.json:**

```json
{
  "version": "1.0.0",
  "schemas": {
    "agent_event_v1": "1.0.0",
    "tool_capability_v1": "1.0.0",
    "attention_directive_v1": "1.0.0",
    "uwsm_v1": "1.0.0"
  },
  "updated_at": "2026-02-06"
}
```

---

## Phase 3: Wire event emission (minimal)

### PR #3B: tap_tone_pi event emitter

**Files to add:**

```
tap_tone_pi/agentic/emitter.py
tap_tone_pi/agentic/emitter_config.py
```

**emitter_config.py:**

```python
"""
Event emission configuration.

Flag-gated: set AGENTIC_EMIT_EVENTS=1 to enable.
Default: disabled (no events emitted).
"""

import os

EMIT_EVENTS = os.environ.get("AGENTIC_EMIT_EVENTS", "0") == "1"
EVENT_SINK = os.environ.get("AGENTIC_EVENT_SINK", "jsonl")  # jsonl | stdout | null
EVENT_LOG_PATH = os.environ.get("AGENTIC_EVENT_LOG", "events.jsonl")
```

**emitter.py:**

```python
"""
Minimal event emitter for Layer 0 facts.

Usage:
    from tap_tone_pi.agentic.emitter import emit_event

    emit_event("analysis_completed", {"artifacts_created": ["ods_snapshot_v1"]})
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from .emitter_config import EMIT_EVENTS, EVENT_SINK, EVENT_LOG_PATH


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _new_event_id() -> str:
    return f"evt_{uuid4().hex[:12]}"


_SESSION_ID: Optional[str] = None


def set_session_id(sid: str) -> None:
    global _SESSION_ID
    _SESSION_ID = sid


def get_session_id() -> str:
    global _SESSION_ID
    if _SESSION_ID is None:
        _SESSION_ID = f"session_{uuid4().hex[:8]}"
    return _SESSION_ID


def emit_event(
    event_type: str,
    payload: Dict[str, Any],
    *,
    source_component: str = "analyzer",
    source_version: str = "2.0.0",
    privacy_layer: int = 2,
) -> Optional[Dict[str, Any]]:
    """
    Emit an AgentEventV1-shaped event.

    Returns the event dict if emitted, None if disabled.
    """
    if not EMIT_EVENTS:
        return None

    event = {
        "event_id": _new_event_id(),
        "event_type": event_type,
        "source": {
            "repo": "tap_tone_pi",
            "component": source_component,
            "version": source_version,
        },
        "payload": payload,
        "privacy_layer": privacy_layer,
        "occurred_at": _now_iso(),
        "schema_version": "1.0.0",
        "session": {
            "session_id": get_session_id(),
        },
    }

    _write_event(event)
    return event


def _write_event(event: Dict[str, Any]) -> None:
    if EVENT_SINK == "null":
        return
    if EVENT_SINK == "stdout":
        print(json.dumps(event))
        return
    if EVENT_SINK == "jsonl":
        with open(EVENT_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
```

**Minimal integration points:**

| Location | Event Type | Payload |
|----------|-----------|---------|
| Analysis started | `analysis_started` | `{"analysis_type": "..."}` |
| Analysis completed | `analysis_completed` | `{"artifacts_created": [...]}` |
| Analysis failed | `analysis_failed` | `{"error": "..."}` |
| Artifact created | `artifact_created` | `{"artifact_type": "...", "confidence": 0.85}` |
| Decision required | `decision_required` | `{"decision_type": "...", "options": [...]}` |

**Test:**

```bash
AGENTIC_EMIT_EVENTS=1 AGENTIC_EVENT_SINK=stdout python -c "
from tap_tone_pi.agentic.emitter import emit_event
emit_event('analysis_completed', {'artifacts_created': ['ods_v1']})
"
```

---

## Phase 4: Shadow replay on real sessions

### PR #4: Recording capture script

**Files to add:**

```
scripts/capture_session.py
scripts/replay_session.py
recordings/.gitkeep
recordings/README.md
```

**replay_session.py:**

```python
#!/usr/bin/env python3
"""
Replay a recorded session through the agentic spine.

Usage:
    python scripts/replay_session.py recordings/session_001.jsonl
    python scripts/replay_session.py recordings/*.jsonl --mode M1
"""

import sys
from pathlib import Path

from tap_tone_pi.agentic.spine.replay import load_events, run_shadow_replay, ReplayConfig
import json


def main():
    import argparse

    ap = argparse.ArgumentParser(description="Replay recorded sessions")
    ap.add_argument("paths", nargs="+", help="JSONL files to replay")
    ap.add_argument("--mode", default="M0", choices=["M0", "M1", "M2"])
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--summary-only", action="store_true")
    args = ap.parse_args()

    all_events = []
    for p in args.paths:
        all_events.extend(load_events(p))

    config = ReplayConfig(mode=args.mode, verbose=args.verbose)
    report = run_shadow_replay(all_events, config)

    if args.summary_only:
        print(json.dumps(report["summary"], indent=2))
    else:
        print(json.dumps(report, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

---

## Phase 5: Shadow scoreboard

Same as luthiers-toolbox. See that document for full script.

---

## Flag gates (safety)

| Flag | Default | Effect |
|------|---------|--------|
| `AGENTIC_EMIT_EVENTS` | `0` | Enable event emission |
| `AGENTIC_EVENT_SINK` | `jsonl` | Where events go (jsonl/stdout/null) |
| `AGENTIC_EVENT_LOG` | `events.jsonl` | Path for JSONL sink |
| `AGENTIC_MODE` | `M0` | Operating mode (M0/M1/M2) |

All flags default to off. Shadow mode is the only enabled path initially.

---

## Rollback plan

### If event emission causes issues:

```bash
# Immediate: disable emission
unset AGENTIC_EMIT_EVENTS
# Or: AGENTIC_EMIT_EVENTS=0
```

### If spine tests fail after merge:

```bash
# Revert the PR
git revert <commit>
```

### If recorded sessions have PII:

```bash
# Delete recordings
rm recordings/*.jsonl
```

---

## PR order (strict sequence)

| PR | Repo | Depends on | Can merge independently |
|----|------|------------|-------------------------|
| #1A | luthiers-toolbox | None | Yes |
| #1B | tap_tone_pi | None | Yes |
| #2 | luthiers-toolbox | #1A | Yes |
| #3A | luthiers-toolbox | #2 | Yes |
| #3B | tap_tone_pi | #1B | Yes |
| #4 | luthiers-toolbox | #3A | Yes |
| #5 | luthiers-toolbox | #4 | Yes |

Each PR is independently mergeable. No cross-repo dependencies block progress.

---

## Success criteria

Before moving to Phase 6 (Advisory mode):

- [ ] Spine CI passes on both repos for 2 weeks
- [ ] 10+ real sessions captured and replayed
- [ ] Shadow scoreboard shows moment distribution is reasonable
- [ ] No false positives in OVERLOAD detection
- [ ] UWSM changes are gradual, not erratic
- [ ] Team has reviewed shadow reports

---

## What's NOT in this plan

- UI changes (Phase 6)
- Analyzer commands (Phase 7)
- User preferences persistence
- Cross-session UWSM state
- Real-time streaming (batch replay only)

These come after shadow mode proves value.
