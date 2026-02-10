import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from tap_tone_pi.agentic.spine.uwsm_store import (
    get_uwsm_path,
    load_uwsm_state,
    save_uwsm_state,
    apply_uwsm_decay,
)
from tap_tone_pi.agentic.spine.uwsm_update import ensure_uwsm


@pytest.fixture()
def tmp_xdg(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    return tmp_path


def test_uwsm_path_respects_xdg(tmp_xdg: Path):
    p = get_uwsm_path()
    assert "xdg" in str(p)
    assert p.name == "uwsm_v1.json"


def test_load_missing_returns_defaults(tmp_xdg: Path):
    now = datetime(2026, 2, 8, 12, 0, 0, tzinfo=timezone.utc)
    uwsm, conf, ts = load_uwsm_state(now=now)
    uwsm2 = ensure_uwsm(uwsm)
    assert "dimensions" in uwsm2
    assert isinstance(conf, dict)
    assert isinstance(ts, datetime)


def test_save_then_load_roundtrip(tmp_xdg: Path):
    now = datetime(2026, 2, 8, 12, 0, 0, tzinfo=timezone.utc)
    uwsm, conf, ts = load_uwsm_state(now=now)
    uwsm["dimensions"]["guidance_density"]["confidence"] = 0.77
    conf["guidance_density"] = 0.77
    save_uwsm_state(uwsm, conf, now=now)
    uwsm2, conf2, ts2 = load_uwsm_state(now=now)
    assert abs(float(uwsm2["dimensions"]["guidance_density"]["confidence"]) - 0.77) < 1e-6
    assert abs(float(conf2["guidance_density"]) - 0.77) < 1e-6


def test_corrupt_file_falls_back(tmp_xdg: Path):
    p = get_uwsm_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{not json", encoding="utf-8")
    now = datetime(2026, 2, 8, 12, 0, 0, tzinfo=timezone.utc)
    uwsm, conf, ts = load_uwsm_state(now=now)
    uwsm = ensure_uwsm(uwsm)
    assert "dimensions" in uwsm


def test_decay_is_deterministic(tmp_xdg: Path):
    # Start with confidence 0.80, floor 0.20, half-life 10 days, after 10 days => halfway to floor.
    now = datetime(2026, 2, 18, 12, 0, 0, tzinfo=timezone.utc)
    updated_at = datetime(2026, 2, 8, 12, 0, 0, tzinfo=timezone.utc)

    uwsm = ensure_uwsm(None)
    dim = uwsm["dimensions"]["risk_posture"]
    dim["decay"]["half_life_days"] = 10
    dim["decay"]["floor"] = 0.20
    dim["confidence"] = 0.80
    conf = {"risk_posture": 0.80}

    uwsm2, conf2 = apply_uwsm_decay(uwsm, conf, updated_at, now)
    got = float(uwsm2["dimensions"]["risk_posture"]["confidence"])
    # expected = 0.20 + (0.80-0.20)*0.5 = 0.50
    assert abs(got - 0.50) < 1e-6
    assert abs(float(conf2["risk_posture"]) - 0.50) < 1e-6
