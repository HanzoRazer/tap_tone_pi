"""Hardware-free tests for scripts/repeatability_run.py artifact behavior.

These drive `run_repeatability` through injected capture/analyze/persist seams,
so no audio hardware, PortAudio, or numpy is required. They assert the evidence
and manifest behavior the C-002 dependency needs: every attempt is preserved
(accepted and rejected), rejections carry a reason and never a synthesized
frequency, the instrument gate configuration is recorded, and the emitted
RepeatabilityEvidenceV1 validates against its TTP-owned schema.
"""

from __future__ import annotations

import importlib.util
import json
from dataclasses import dataclass
from pathlib import Path

import jsonschema

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "repeatability_run.py"
SCHEMA = REPO_ROOT / "contracts" / "schemas" / "repeatability_evidence_v1.schema.json"


def _load_module():
    spec = importlib.util.spec_from_file_location("repeatability_run", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MOD = _load_module()


@dataclass
class FakeCap:
    audio: object
    sample_rate: int


@dataclass
class FakeRes:
    dominant_hz: float | None
    rms: float = 0.05
    clipped: bool = False
    confidence: float = 0.9
    peaks: tuple = ()


@dataclass
class FakePersist:
    capture_dir: str


def _fns(plan: list[tuple], tmp_path: Path):
    """Build injected capture/analyze/persist fns driven by a per-take plan.

    Each plan step is ("ok", freq_hz), ("none",), ("raise",) for capture,
    ("analysis_raise",), or ("persist_raise",).
    """
    state = {"i": 0, "last": None}

    def capture_fn(**kw):
        idx = state["i"]
        state["i"] += 1
        step = plan[idx]
        state["last"] = step
        if step[0] == "raise":
            raise RuntimeError("simulated device error")
        return FakeCap(audio=f"audio-{idx}", sample_rate=kw["sample_rate"])

    def analyze_fn(audio, sample_rate):
        step = state["last"]
        if step[0] == "analysis_raise":
            raise RuntimeError("simulated analysis error")
        if step[0] == "none":
            return FakeRes(dominant_hz=None)
        if step[0] == "missing_metrics":
            return FakeRes(dominant_hz=float(step[1]), rms=None, confidence=None)
        if step[0] == "clipped":
            return FakeRes(dominant_hz=float(step[1]), clipped=True)
        return FakeRes(dominant_hz=float(step[1]))

    def persist_fn(**kw):
        if state["last"][0] == "persist_raise":
            raise RuntimeError("simulated persistence error")
        d = Path(kw["out_dir"]) / "capture_20260928T120000Z"
        d.mkdir(parents=True, exist_ok=True)
        (d / "audio.wav").write_text(str(kw["audio"]), encoding="utf-8")
        return FakePersist(capture_dir=str(d))

    def write_raw_fn(path, audio, sample_rate):
        path.write_text(str(audio), encoding="utf-8")

    return capture_fn, analyze_fn, persist_fn, write_raw_fn


def _run(tmp_path: Path, plan: list[tuple], **kw):
    capture_fn, analyze_fn, persist_fn, write_raw_fn = _fns(plan, tmp_path)
    takes = kw.pop("takes", len(plan))
    seconds = kw.pop("seconds", 1.0)
    sample_rate = kw.pop("sample_rate", 48000)
    return MOD.run_repeatability(
        out_dir=str(tmp_path / "run"),
        device=0,
        takes=takes,
        seconds=seconds,
        sample_rate=sample_rate,
        label="R001C002",
        capture_fn=capture_fn,
        analyze_fn=analyze_fn,
        persist_fn=persist_fn,
        write_raw_fn=write_raw_fn,
        now_fn=lambda: "2026-09-28T00:00:00Z",
        software_version="test-1.2.3",
        analysis_settings={"unit_test": True},
        **kw,
    )


def _schema() -> dict:
    return json.loads(SCHEMA.read_text(encoding="utf-8"))


class TestAcceptedRejectedAccounting:
    def test_all_accepted_counts_and_schema_valid(self, tmp_path: Path) -> None:
        result = _run(tmp_path, [("ok", 185.0), ("ok", 186.0), ("ok", 184.5)])
        ev = result["evidence"]
        assert ev["repetitions_completed"] == 3
        assert ev.get("repetitions_rejected", 0) == 0
        assert ev["dominant_frequency_mean_hz"] is not None
        jsonschema.validate(ev, _schema())
        m = result["manifest"]
        assert m["attempted"] == 3 and m["accepted"] == 3 and m["rejected"] == 0
        assert all(a["status"] == "ACCEPTED" for a in m["attempts"])
        assert all(a["source"] for a in m["attempts"])

    def test_mixed_rejects_preserved_with_reason(self, tmp_path: Path) -> None:
        result = _run(tmp_path, [("ok", 185.0), ("none",), ("ok", 186.0)])
        m = result["manifest"]
        assert m["accepted"] == 2 and m["rejected"] == 1
        rejected = [a for a in m["attempts"] if a["status"] == "REJECTED"]
        assert len(rejected) == 1
        assert rejected[0]["reason"] == "no_dominant_frequency"
        assert rejected[0]["dominant_hz"] is None  # never synthesized
        # A rejected-for-no-frequency attempt still has its source capture dir.
        assert rejected[0]["source"]
        assert result["evidence"]["repetitions_completed"] == 2
        assert result["evidence"]["repetitions_rejected"] == 1

    def test_capture_error_is_a_recorded_reject(self, tmp_path: Path) -> None:
        result = _run(tmp_path, [("ok", 185.0), ("raise",)])
        m = result["manifest"]
        assert m["accepted"] == 1 and m["rejected"] == 1
        assert len(m["attempts"]) == 2  # nothing silently dropped
        rej = [a for a in m["attempts"] if a["status"] == "REJECTED"][0]
        assert rej["reason"].startswith("capture_error:")
        assert rej["dominant_hz"] is None
        assert rej["source"] is None

    def test_analysis_failure_preserves_raw_audio(self, tmp_path: Path) -> None:
        result = _run(tmp_path, [("analysis_raise",)])
        attempt = result["manifest"]["attempts"][0]
        assert attempt["reason"].startswith("analysis_error:")
        assert Path(attempt["raw_audio"]).read_text() == "audio-0"
        assert attempt["source"] is None

    def test_persistence_failure_preserves_raw_audio(self, tmp_path: Path) -> None:
        result = _run(tmp_path, [("persist_raise", 185.0)])
        attempt = result["manifest"]["attempts"][0]
        assert attempt["reason"].startswith("persistence_error:")
        assert Path(attempt["raw_audio"]).read_text() == "audio-0"
        assert attempt["source"] is None

    def test_same_second_captures_remain_distinct(self, tmp_path: Path) -> None:
        result = _run(tmp_path, [("ok", 185.0), ("ok", 186.0)])
        first, second = result["manifest"]["attempts"]
        assert first["source"] != second["source"]
        assert (Path(first["source"]) / "audio.wav").read_text() == "audio-0"
        assert (Path(second["source"]) / "audio.wav").read_text() == "audio-1"
        assert Path(first["raw_audio"]).read_text() == "audio-0"
        assert Path(second["raw_audio"]).read_text() == "audio-1"

    def test_clipped_capture_is_preserved_but_excluded(self, tmp_path: Path) -> None:
        result = _run(tmp_path, [("clipped", 185.0), ("ok", 186.0)])
        first = result["manifest"]["attempts"][0]
        assert first["reason"] == "clipped"
        assert Path(first["raw_audio"]).exists()
        assert result["evidence"]["repetitions_completed"] == 1


class TestNoFrequencySynthesis:
    def test_all_rejected_synthesizes_no_frequency(self, tmp_path: Path) -> None:
        result = _run(tmp_path, [("none",), ("none",)])
        ev = result["evidence"]
        assert ev["repetitions_completed"] == 0
        assert ev["passed_repeatability_gate"] is False
        assert ev.get("gate_failure_reason")
        # No frequency mean is invented when there were no usable taps.
        assert "dominant_frequency_mean_hz" not in ev
        jsonschema.validate(ev, _schema())
        assert all(a["dominant_hz"] is None for a in result["manifest"]["attempts"])


class TestInstrumentGateConfig:
    def test_configured_gate_recorded_as_instrument_output(
        self, tmp_path: Path
    ) -> None:
        result = _run(
            tmp_path,
            [("ok", 185.0), ("ok", 186.0)],
            repetitions_required=7,
            max_frequency_variance_pct=1.5,
        )
        gate = result["manifest"]["gate_config"]
        assert gate["repetitions_required"] == 7
        assert gate["max_frequency_variance_pct"] == 1.5
        assert "not a laboratory acceptance threshold" in gate["note"]
        # required flows into the evidence contract as recorded config.
        assert result["evidence"]["repetitions_required"] == 7
        # Fewer completed than required -> gate not passed, recorded not invented.
        assert result["evidence"]["passed_repeatability_gate"] is False


class TestArtifactsOnDisk:
    def test_three_artifacts_written_and_v1_file_validates(
        self, tmp_path: Path
    ) -> None:
        result = _run(tmp_path, [("ok", 185.0), ("ok", 185.5)])
        assert result["takes_path"].exists()
        assert result["evidence_path"].exists()
        assert result["manifest_path"].exists()
        on_disk = json.loads(result["evidence_path"].read_text(encoding="utf-8"))
        jsonschema.validate(on_disk, _schema())
        assert on_disk["schema_version"] == "repeatability_evidence_v1"

    def test_takes_json_backward_compatible(self, tmp_path: Path) -> None:
        result = _run(tmp_path, [("ok", 185.0), ("ok", 185.5)])
        takes = json.loads(result["takes_path"].read_text(encoding="utf-8"))
        for key in ("takes", "device", "sample_rate", "seconds", "label", "results"):
            assert key in takes
        assert len(takes["results"]) == 2
        assert all("peaks" in take for take in takes["results"])

    def test_missing_optional_metric_is_explicit(self, tmp_path: Path) -> None:
        result = _run(tmp_path, [("missing_metrics", 185.0), ("ok", 186.0)])
        assert result["evidence"]["repetitions_completed"] == 2
        assert "rms_mean" not in result["evidence"]
        assert result["manifest"]["omitted_optional_metrics"] == {
            "rms": ["attempt_01"],
            "confidence": ["attempt_01"],
        }

    def test_invalid_configuration_before_capture(self, tmp_path: Path) -> None:
        import pytest

        for override in (
            {"takes": 0},
            {"repetitions_required": 0},
            {"seconds": -1},
            {"max_frequency_variance_pct": -1},
            {"sample_rate": 0},
        ):
            with pytest.raises(ValueError):
                _run(tmp_path / str(override), [("ok", 185.0)], **override)

    def test_manifest_records_software_version_and_sources(
        self, tmp_path: Path
    ) -> None:
        result = _run(tmp_path, [("ok", 185.0), ("none",)])
        m = result["manifest"]
        assert m["software_version"] == "test-1.2.3"
        # source_capture_dirs lists only attempts that produced a capture dir.
        assert len(m["source_capture_dirs"]) == 2  # both ok and none persisted
        assert m["analysis_settings"] == {"unit_test": True}


class TestDeterminism:
    def test_same_plan_same_counts(self, tmp_path: Path) -> None:
        plan = [("ok", 185.0), ("none",), ("ok", 186.0), ("raise",)]
        a = _run(tmp_path / "a", plan)
        b = _run(tmp_path / "b", plan)
        assert a["manifest"]["accepted"] == b["manifest"]["accepted"] == 2
        assert a["manifest"]["rejected"] == b["manifest"]["rejected"] == 2
