#!/usr/bin/env python3
# INSTRUMENT CLASS: MEASUREMENT
"""Run N repeatability takes, preserve every attempt, and emit V1 evidence.

Backward compatible with the original CLI and with ``takes.json``. In addition
to the raw takes summary, this now:

  * classifies every attempt as ACCEPTED or REJECTED and preserves rejected
    attempts with an explicit reason and their source path (a bad tap is never
    silently replaced, and an unusable tap never gets a synthesized frequency);
  * emits ``repeatability_evidence.json`` conforming to
    ``contracts/schemas/repeatability_evidence_v1.schema.json`` via
    :func:`tap_tone_pi.core.repeatability.compute_repeatability_evidence`;
  * emits ``repeatability_run_manifest.json`` recording attempted/accepted/
    rejected counts, per-attempt records, source IDs, the analysis settings, the
    instrument gate configuration, and the software version.

The configured frequency gate and required-repetition count are recorded as
INSTRUMENT output, not as a scientifically validated acceptance threshold. This
script makes no hardware selection and encodes no laboratory acceptance
criterion; both belong to laboratory artifacts, not to this tool.

The measurement work is injected through ``capture_fn`` / ``analyze_fn`` /
``persist_fn`` so the artifact behavior can be exercised without audio hardware.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, pstdev
from typing import Any, Callable

from tap_tone_pi.core.repeatability import compute_repeatability_evidence

# Existing script defaults/examples, NOT validated scientific requirements.
DEFAULT_TAKES = 10
DEFAULT_SECONDS = 2.5
DEFAULT_SAMPLE_RATE = 48000
# Default of compute_repeatability_evidence's frequency gate, surfaced here so it
# can be recorded and overridden. It is an instrument configuration value.
DEFAULT_MAX_FREQUENCY_VARIANCE_PCT = 3.0

EVIDENCE_SCHEMA = "repeatability_evidence_v1.schema.json"
CONTRACTS = Path(__file__).resolve().parents[1] / "contracts" / "schemas"


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _software_version() -> str:
    try:
        from importlib.metadata import PackageNotFoundError, version

        try:
            return version("tap-tone-pi")
        except PackageNotFoundError:
            pass
    except Exception:
        pass
    try:
        import tap_tone_pi

        return str(getattr(tap_tone_pi, "__version__", "unknown"))
    except Exception:
        return "unknown"


def _default_capture(*, device: int, sample_rate: int, channels: int, seconds: float):
    from tap_tone_pi.capture import record_audio

    return record_audio(
        device=device, sample_rate=sample_rate, channels=channels, seconds=seconds
    )


def _analysis_config() -> Any:
    from tap_tone_pi.core.config import AnalysisConfig

    return AnalysisConfig()


def _default_analyze(audio: Any, sample_rate: int, *, config: Any = None) -> Any:
    from tap_tone_pi.core.analysis import analyze_tap

    cfg = config or _analysis_config()
    return analyze_tap(
        audio,
        sample_rate,
        highpass_hz=cfg.highpass_hz,
        peak_min_hz=cfg.peak_min_hz,
        peak_max_hz=cfg.peak_max_hz,
        peak_min_prominence=cfg.peak_min_prominence,
        peak_min_spacing_hz=cfg.peak_min_spacing_hz,
        max_peaks=cfg.max_peaks,
    )


def _default_persist(**kwargs: Any) -> Any:
    from tap_tone_pi.io.storage import persist_capture

    return persist_capture(**kwargs)


def _validate_evidence(evidence: dict[str, Any]) -> str | None:
    """Validate emitted V1 against its TTP-owned schema, where jsonschema exists.

    Returns None on success (or when jsonschema is unavailable), or an error
    message. Emitting an artifact that does not conform to its own contract is a
    defect, so the caller raises on a real validation error.
    """
    schema_path = CONTRACTS / EVIDENCE_SCHEMA
    try:
        import jsonschema
    except ImportError:
        return None
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        jsonschema.validate(evidence, schema)
    except jsonschema.ValidationError as exc:  # type: ignore[attr-defined]
        return f"emitted repeatability_evidence_v1 does not validate: {exc.message}"
    return None


def run_repeatability(
    *,
    out_dir: str,
    device: int,
    takes: int = DEFAULT_TAKES,
    seconds: float = DEFAULT_SECONDS,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    label: str | None = None,
    repetitions_required: int | None = None,
    max_frequency_variance_pct: float = DEFAULT_MAX_FREQUENCY_VARIANCE_PCT,
    capture_fn: Callable[..., Any] = _default_capture,
    analyze_fn: Callable[..., Any] = _default_analyze,
    persist_fn: Callable[..., Any] = _default_persist,
    now_fn: Callable[[], str] = _utc_now,
    software_version: str | None = None,
    analysis_settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run the series, preserve all attempts, and write the three artifacts.

    Returns a dict with the written paths and the in-memory evidence, manifest,
    and legacy summary. ``capture_fn``/``analyze_fn``/``persist_fn`` are injected
    so this runs without audio hardware in tests.
    """
    out_root = Path(out_dir).expanduser().resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    required = repetitions_required if repetitions_required is not None else takes

    attempts: list[dict[str, Any]] = []
    freqs: list[float] = []
    rms_values: list[float] = []
    conf_values: list[float] = []
    legacy_results: list[dict[str, Any]] = []

    for i in range(1, takes + 1):
        label_i = label or "repeatability"
        label_take = f"{label_i}_take_{i:02d}"
        attempt: dict[str, Any] = {
            "attempt_id": f"attempt_{i:02d}",
            "take": i,
            "label": label_take,
            "timestamp": now_fn(),
            "status": None,
            "reason": None,
            "source": None,
            "dominant_hz": None,
            "rms": None,
            "clipped": None,
            "confidence": None,
        }
        try:
            cap = capture_fn(
                device=device,
                sample_rate=sample_rate,
                channels=1,
                seconds=seconds,
            )
            res = analyze_fn(cap.audio, cap.sample_rate)
            persisted = persist_fn(
                out_dir=str(out_root),
                label=label_take,
                sample_rate=cap.sample_rate,
                audio=cap.audio,
                analysis=res,
            )
            dom = getattr(res, "dominant_hz", None)
            attempt["source"] = str(getattr(persisted, "capture_dir", "")) or None
            attempt["dominant_hz"] = dom
            attempt["rms"] = getattr(res, "rms", None)
            attempt["clipped"] = getattr(res, "clipped", None)
            attempt["confidence"] = getattr(res, "confidence", None)
            if dom is not None:
                attempt["status"] = "ACCEPTED"
                freqs.append(float(dom))
                if attempt["rms"] is not None:
                    rms_values.append(float(attempt["rms"]))
                if attempt["confidence"] is not None:
                    conf_values.append(float(attempt["confidence"]))
            else:
                # An unusable tap is preserved and never given a synthesized
                # frequency.
                attempt["status"] = "REJECTED"
                attempt["reason"] = "no_dominant_frequency"
        except Exception as exc:  # noqa: BLE001 - any capture/analysis failure is a recorded reject
            attempt["status"] = "REJECTED"
            attempt["reason"] = (
                f"capture_or_analysis_error: {type(exc).__name__}: {exc}"
            )

        attempts.append(attempt)
        legacy_results.append(
            {
                "take": i,
                "label": label_take,
                "capture_dir": attempt["source"],
                "dominant_hz": attempt["dominant_hz"],
                "rms": attempt["rms"],
                "clipped": attempt["clipped"],
                "confidence": attempt["confidence"],
            }
        )
        print(
            f"[{i:02d}/{takes}] {attempt['status']} "
            f"dominant={attempt['dominant_hz']} reason={attempt['reason']}"
        )

    accepted = sum(1 for a in attempts if a["status"] == "ACCEPTED")
    rejected = sum(1 for a in attempts if a["status"] == "REJECTED")

    # Only pass aligned optional series; a length mismatch is dropped rather than
    # padded, so no value is invented.
    rms_arg = rms_values if len(rms_values) == len(freqs) else None
    conf_arg = conf_values if len(conf_values) == len(freqs) else None

    # observation_window_seconds is intentionally NOT passed: the V1 schema is
    # additionalProperties:false and does not include it, so setting it would
    # make the emitted artifact fail its own contract.
    evidence = compute_repeatability_evidence(
        frequencies_hz=freqs,
        rms_values=rms_arg,
        confidence_values=conf_arg,
        repetitions_required=required,
        repetitions_rejected=rejected,
        max_frequency_variance_pct=max_frequency_variance_pct,
    )
    evidence_dict = evidence.to_dict()

    validation_error = _validate_evidence(evidence_dict)
    if validation_error is not None:
        raise ValueError(validation_error)

    manifest = {
        "artifact": "ttp_repeatability_run_manifest",
        "generated_at": now_fn(),
        "software_version": software_version or _software_version(),
        "device": device,
        "sample_rate": sample_rate,
        "seconds_per_take": seconds,
        "label": label,
        "attempted": takes,
        "accepted": accepted,
        "rejected": rejected,
        "gate_config": {
            "repetitions_required": required,
            "max_frequency_variance_pct": max_frequency_variance_pct,
            "note": "instrument configuration and output; not a laboratory acceptance threshold",
        },
        "analysis_settings": analysis_settings
        if analysis_settings is not None
        else asdict(_analysis_config()),
        "source_capture_dirs": [a["source"] for a in attempts if a["source"]],
        "attempts": attempts,
        "evidence_artifact": "repeatability_evidence.json",
    }

    doms = list(freqs)
    legacy_summary = {
        "takes": takes,
        "device": device,
        "sample_rate": sample_rate,
        "seconds": seconds,
        "label": label,
        "dominant_hz_mean": mean(doms) if doms else None,
        "dominant_hz_std": pstdev(doms) if len(doms) > 1 else (0.0 if doms else None),
        "results": legacy_results,
    }

    takes_path = out_root / "takes.json"
    evidence_path = out_root / "repeatability_evidence.json"
    manifest_path = out_root / "repeatability_run_manifest.json"
    takes_path.write_text(
        json.dumps(legacy_summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    evidence_path.write_text(
        json.dumps(evidence_dict, indent=2, sort_keys=True), encoding="utf-8"
    )
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )

    return {
        "takes_path": takes_path,
        "evidence_path": evidence_path,
        "manifest_path": manifest_path,
        "evidence": evidence_dict,
        "manifest": manifest,
        "summary": legacy_summary,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Run N repeatability takes; preserve all attempts and emit V1 evidence."
    )
    ap.add_argument("--device", type=int, required=True)
    ap.add_argument("--out", type=str, required=True)
    ap.add_argument("--label", type=str, default=None)
    ap.add_argument("--takes", type=int, default=DEFAULT_TAKES)
    ap.add_argument("--seconds", type=float, default=DEFAULT_SECONDS)
    ap.add_argument("--sample-rate", type=int, default=DEFAULT_SAMPLE_RATE)
    ap.add_argument(
        "--repetitions-required",
        type=int,
        default=None,
        help="repetitions the workflow requires (recorded in evidence); defaults to --takes",
    )
    ap.add_argument(
        "--max-frequency-variance-pct",
        type=float,
        default=DEFAULT_MAX_FREQUENCY_VARIANCE_PCT,
        help="instrument frequency gate (recorded as instrument config, not a lab threshold)",
    )
    args = ap.parse_args(argv)

    result = run_repeatability(
        out_dir=args.out,
        device=args.device,
        takes=args.takes,
        seconds=args.seconds,
        sample_rate=args.sample_rate,
        label=args.label,
        repetitions_required=args.repetitions_required,
        max_frequency_variance_pct=args.max_frequency_variance_pct,
    )
    print(f"[OK] Wrote {result['takes_path']}")
    print(f"[OK] Wrote {result['evidence_path']}")
    print(f"[OK] Wrote {result['manifest_path']}")
    m = result["manifest"]
    print(
        f"[SUMMARY] attempted={m['attempted']} accepted={m['accepted']} "
        f"rejected={m['rejected']} gate_passed={result['evidence']['passed_repeatability_gate']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
