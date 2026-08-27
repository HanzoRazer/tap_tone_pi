# INSTRUMENT CLASS: MEASUREMENT
"""Evidence contract for the E0 ADC bench characterization (DO-106).

E0 turns one board purchase into measured answers for the four questions that
block the analog front-end design. It is a **characterization protocol, not a
selection test**: T1 states outright that it has no pass condition, and a board
that characterizes badly is evidence for reopening the choice rather than a
failure to be flagged.

Three rules shape every record here, and each exists because breaking it would
produce something that reads as evidence and is not.

**Every field is measured.** The protocol says so explicitly: *"There are no
``proposed`` values in this file - that is the point of the exercise."* So a key
named ``expected_noise_floor``, ``proposed_corner_hz`` or ``assumed_full_scale``
is refused rather than ignored. Those belong in a specification. Letting one into
an evidence record is how a design assumption comes back later wearing the
clothes of a measurement.

**Preparation is not measurement.** :class:`E0ExecutionStatus` separates a
prepared record from a partially executed one, a completed one, and one halted at
its gate. ``PREPARED`` carries no observations at all. ``EXECUTED`` means every
required observation was actually recorded - **not** that the board passed, is
approved, or has been selected for anything.

**What the bench could not do is recorded, not hidden.** T4 asks for injections
to 200 kHz from a phone or a second computer, which cannot generate them. The
requested frequency set is not quietly reduced to match the equipment on hand:
each frequency beyond the source's demonstrated bandwidth is recorded as
:attr:`E0SourceCapability.BLOCKED_BY_SOURCE_CAPABILITY`. A partial T4 is a
partial T4, and B-014 stays open across the untested range.

Nothing here grades the device. There is no pass field, no verdict, and no
threshold, and :data:`_QUALITY_KEYS` refuses one being added later.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Sequence

from tap_tone_pi.grant_readiness.errors import (
    E0CharacterizationError,
    GrantReadinessErrorCode,
)

E0_SCHEMA_VERSION = "e0_adc_characterization_v1"

_ERR = E0CharacterizationError

# Prefixes that name an expectation rather than an observation.
_SPECULATIVE_PREFIXES = ("expected_", "proposed_", "assumed_", "predicted_", "target_")

# Field names that would turn characterization into judgement.
_QUALITY_KEYS = frozenset(
    {
        "pass",
        "passed",
        "pass_fail",
        "verdict",
        "grade",
        "quality",
        "acceptable",
        "meets_spec",
        "within_tolerance",
        "score",
    }
)


# ---------------------------------------------------------------------------
# Vocabularies
# ---------------------------------------------------------------------------


class E0ExecutionStatus(str, Enum):
    """How much of E0 actually happened.

    The distinction that matters is between the first value and the rest.
    ``PREPARED`` is the state this repository is in now: the protocol exists,
    the contract exists, and no bench has been touched.
    """

    PREPARED = "PREPARED"
    PARTIALLY_EXECUTED = "PARTIALLY_EXECUTED"
    EXECUTED = "EXECUTED"
    HALTED_AT_GATE = "HALTED_AT_GATE"


class E0SourceCapability(str, Enum):
    """Whether the independent source could produce a requested frequency."""

    MEASURED = "MEASURED"
    BLOCKED_BY_SOURCE_CAPABILITY = "BLOCKED_BY_SOURCE_CAPABILITY"


class E0InputPath(str, Enum):
    """Which physical input a level was measured on.

    Balanced and unbalanced full-scale figures differ by roughly 6 dB, so
    conflating them would corrupt the level budget in the direction that looks
    like extra headroom.
    """

    UNBALANCED = "UNBALANCED"
    BALANCED = "BALANCED"


class E0ControlGranularity(str, Enum):
    """Scope of the ALSA input-mode control found in T5.

    ``UNKNOWN`` is a legitimate outcome and is not a synonym for ``GLOBAL``: an
    unread control and a control demonstrated to be board-wide have different
    consequences for whether the E1 rig can use the balanced microphone path.
    """

    PER_CHANNEL = "PER_CHANNEL"
    GLOBAL = "GLOBAL"
    UNKNOWN = "UNKNOWN"


# ---------------------------------------------------------------------------
# Shared guards
# ---------------------------------------------------------------------------


def _reject_unknown_keys(
    payload: Mapping[str, Any], allowed: Sequence[str], *, record: str
) -> None:
    """Refuse extra keys, and name speculative or judgemental ones specifically.

    A generic "unknown field" message would be technically correct and useless
    here. The two kinds of extra key this contract most needs to refuse are a
    specification leaking in and a verdict being added, so both get their own
    error code and their own explanation.
    """
    unknown = sorted(set(payload) - set(allowed))
    if not unknown:
        return

    speculative = [k for k in unknown if k.startswith(_SPECULATIVE_PREFIXES)]
    if speculative:
        raise _ERR(
            GrantReadinessErrorCode.E0_SPECULATIVE_FIELD,
            f"{record} carries field(s) naming an expectation rather than an "
            f"observation: {', '.join(speculative)}. Every field in an E0 record "
            "is measured; expectations belong in a specification",
            {"record": record, "fields": speculative},
        )

    judgement = [k for k in unknown if k.lower() in _QUALITY_KEYS]
    if judgement:
        raise _ERR(
            GrantReadinessErrorCode.E0_QUALITY_JUDGEMENT,
            f"{record} carries a quality judgement field: {', '.join(judgement)}. "
            "E0 is characterization and has no pass condition; inventing one "
            "decides the question the protocol exists to ask",
            {"record": record, "fields": judgement},
        )

    raise _ERR(
        GrantReadinessErrorCode.E0_OBSERVATION_MISSING,
        f"{record} payload carries unknown field(s): {', '.join(unknown)}",
        {"record": record, "unknown_fields": unknown},
    )


def _text(payload: Mapping[str, Any], key: str, *, record: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise _ERR(
            GrantReadinessErrorCode.E0_OBSERVATION_MISSING,
            f"{record}.{key} must be a non-empty string",
            {"record": record, "field": key},
        )
    return value


def _optional_text(payload: Mapping[str, Any], key: str, *, record: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise _ERR(
            GrantReadinessErrorCode.E0_OBSERVATION_MISSING,
            f"{record}.{key} must be a non-empty string when present",
            {"record": record, "field": key},
        )
    return value


def _number(
    payload: Mapping[str, Any],
    key: str,
    *,
    record: str,
    code: GrantReadinessErrorCode = GrantReadinessErrorCode.E0_OBSERVATION_MISSING,
) -> float:
    """A required finite number. NaN and Infinity are refused, not stored."""
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _ERR(
            code,
            f"{record}.{key} must be a number",
            {"record": record, "field": key},
        )
    number = float(value)
    if not math.isfinite(number):
        raise _ERR(
            code,
            f"{record}.{key} must be finite, not {value!r}",
            {"record": record, "field": key},
        )
    return number


def _optional_number(
    payload: Mapping[str, Any], key: str, *, record: str
) -> float | None:
    """A number that may be absent.

    ``None`` means *not measured*. It is not zero, and the two are kept
    distinguishable everywhere this appears - a measured offset of exactly zero
    samples is a real and useful result.
    """
    if payload.get(key) is None:
        return None
    return _number(payload, key, record=record)


def _positive(payload: Mapping[str, Any], key: str, *, record: str) -> float:
    value = _number(payload, key, record=record)
    if value <= 0:
        raise _ERR(
            GrantReadinessErrorCode.E0_OBSERVATION_MISSING,
            f"{record}.{key} must be greater than zero, not {value}",
            {"record": record, "field": key},
        )
    return value


def _enum(
    payload: Mapping[str, Any],
    key: str,
    enum_cls: type[Enum],
    *,
    record: str,
    code: GrantReadinessErrorCode = GrantReadinessErrorCode.E0_OBSERVATION_MISSING,
) -> Any:
    raw = payload.get(key)
    try:
        return enum_cls(raw)
    except ValueError as exc:
        raise _ERR(
            code,
            f"{record}.{key} is not a known {enum_cls.__name__}: {raw!r}",
            {
                "record": record,
                "field": key,
                "permitted": [m.value for m in enum_cls],
            },
        ) from exc


def _rows(payload: Mapping[str, Any], key: str, *, record: str) -> Sequence[Any]:
    value = payload.get(key, ())
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise _ERR(
            GrantReadinessErrorCode.E0_OBSERVATION_MISSING,
            f"{record}.{key} must be an array",
            {"record": record, "field": key},
        )
    return value


# ---------------------------------------------------------------------------
# Device and provenance
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class E0DeviceIdentityV1:
    """Which board was measured, and the software stack that read it."""

    local_id: str
    manufacturer: str
    model: str
    asset_label: str | None = None
    serial_number: str | None = None
    driver: str | None = None
    kernel: str | None = None
    device_tree_overlay: str | None = None
    alsa_device: str | None = None

    _FIELDS = (
        "local_id",
        "manufacturer",
        "model",
        "asset_label",
        "serial_number",
        "driver",
        "kernel",
        "device_tree_overlay",
        "alsa_device",
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "local_id": self.local_id,
            "manufacturer": self.manufacturer,
            "model": self.model,
            "asset_label": self.asset_label,
            "serial_number": self.serial_number,
            "driver": self.driver,
            "kernel": self.kernel,
            "device_tree_overlay": self.device_tree_overlay,
            "alsa_device": self.alsa_device,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> E0DeviceIdentityV1:
        record = "E0DeviceIdentityV1"
        _reject_unknown_keys(payload, cls._FIELDS, record=record)
        return cls(
            local_id=_text(payload, "local_id", record=record),
            manufacturer=_text(payload, "manufacturer", record=record),
            model=_text(payload, "model", record=record),
            asset_label=_optional_text(payload, "asset_label", record=record),
            serial_number=_optional_text(payload, "serial_number", record=record),
            driver=_optional_text(payload, "driver", record=record),
            kernel=_optional_text(payload, "kernel", record=record),
            device_tree_overlay=_optional_text(
                payload, "device_tree_overlay", record=record
            ),
            alsa_device=_optional_text(payload, "alsa_device", record=record),
        )


@dataclass(frozen=True)
class E0ArtifactRefV1:
    """One externally retained capture, identified by digest rather than path.

    E0's WAVs are **not** Phase 2 sessions and do not enter Phase 2 ingestion.
    They are standalone artifacts, and the digest is what makes a later reader
    able to tell whether the bytes behind a result are the bytes that produced it.
    """

    artifact_id: str
    kind: str
    sha256: str
    byte_length: int | None = None
    locator: str | None = None

    _FIELDS = ("artifact_id", "kind", "sha256", "byte_length", "locator")

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "kind": self.kind,
            "sha256": self.sha256,
            "byte_length": self.byte_length,
            "locator": self.locator,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> E0ArtifactRefV1:
        record = "E0ArtifactRefV1"
        _reject_unknown_keys(payload, cls._FIELDS, record=record)
        digest = _text(payload, "sha256", record=record)
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise _ERR(
                GrantReadinessErrorCode.E0_OBSERVATION_MISSING,
                f"{record}.sha256 must be 64 lowercase hex characters",
                {"record": record, "field": "sha256"},
            )
        length = payload.get("byte_length")
        if length is not None:
            if isinstance(length, bool) or not isinstance(length, int) or length <= 0:
                raise _ERR(
                    GrantReadinessErrorCode.E0_OBSERVATION_MISSING,
                    f"{record}.byte_length must be a positive integer when present",
                    {"record": record, "field": "byte_length"},
                )
        return cls(
            artifact_id=_text(payload, "artifact_id", record=record),
            kind=_text(payload, "kind", record=record),
            sha256=digest,
            byte_length=length,
            locator=_optional_text(payload, "locator", record=record),
        )


@dataclass(frozen=True)
class E0ProvenanceV1:
    """When, by whom, under what conditions, and with what source equipment."""

    performed_utc: str
    operator: str
    ambient_temp_c: float | None = None
    ambient_rh_percent: float | None = None
    source_equipment: tuple[str, ...] = ()
    source_verified_bandwidth_hz: float | None = None
    artifacts: tuple[E0ArtifactRefV1, ...] = ()
    notes: str = ""

    _FIELDS = (
        "performed_utc",
        "operator",
        "ambient_temp_c",
        "ambient_rh_percent",
        "source_equipment",
        "source_verified_bandwidth_hz",
        "artifacts",
        "notes",
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "performed_utc": self.performed_utc,
            "operator": self.operator,
            "ambient_temp_c": self.ambient_temp_c,
            "ambient_rh_percent": self.ambient_rh_percent,
            "source_equipment": list(self.source_equipment),
            "source_verified_bandwidth_hz": self.source_verified_bandwidth_hz,
            "artifacts": [a.to_dict() for a in self.artifacts],
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> E0ProvenanceV1:
        record = "E0ProvenanceV1"
        _reject_unknown_keys(payload, cls._FIELDS, record=record)
        equipment = _rows(payload, "source_equipment", record=record)
        for item in equipment:
            if not isinstance(item, str) or not item.strip():
                raise _ERR(
                    GrantReadinessErrorCode.E0_OBSERVATION_MISSING,
                    f"{record}.source_equipment entries must be non-empty strings",
                    {"record": record},
                )
        bandwidth = payload.get("source_verified_bandwidth_hz")
        return cls(
            performed_utc=_text(payload, "performed_utc", record=record),
            operator=_text(payload, "operator", record=record),
            ambient_temp_c=_optional_number(payload, "ambient_temp_c", record=record),
            ambient_rh_percent=_optional_number(
                payload, "ambient_rh_percent", record=record
            ),
            source_equipment=tuple(str(i) for i in equipment),
            source_verified_bandwidth_hz=(
                None
                if bandwidth is None
                else _positive(payload, "source_verified_bandwidth_hz", record=record)
            ),
            artifacts=tuple(
                E0ArtifactRefV1.from_dict(a)
                for a in _rows(payload, "artifacts", record=record)
            ),
            notes=payload.get("notes", "") or "",
        )


# ---------------------------------------------------------------------------
# T1 - input-shorted noise floor and spurs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class E0NoiseObservationV1:
    """One cell of T1's (sample rate x PGA) noise table."""

    sample_rate_hz: float
    pga_db: float
    rms_dbfs: float

    _FIELDS = ("sample_rate_hz", "pga_db", "rms_dbfs")

    def to_dict(self) -> dict[str, Any]:
        return {
            "sample_rate_hz": self.sample_rate_hz,
            "pga_db": self.pga_db,
            "rms_dbfs": self.rms_dbfs,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> E0NoiseObservationV1:
        record = "E0NoiseObservationV1"
        _reject_unknown_keys(payload, cls._FIELDS, record=record)
        return cls(
            sample_rate_hz=_positive(payload, "sample_rate_hz", record=record),
            pga_db=_number(payload, "pga_db", record=record),
            rms_dbfs=_number(payload, "rms_dbfs", record=record),
        )


@dataclass(frozen=True)
class E0SpurObservationV1:
    """One discrete tone found with the inputs shorted.

    These are the board's own. Anything found later that is not in this table
    came from the front end - which is the entire reason each spur is recorded
    individually rather than summarized.
    """

    frequency_hz: float
    level_dbfs: float
    sample_rate_hz: float | None = None
    pga_db: float | None = None

    _FIELDS = ("frequency_hz", "level_dbfs", "sample_rate_hz", "pga_db")

    def to_dict(self) -> dict[str, Any]:
        return {
            "frequency_hz": self.frequency_hz,
            "level_dbfs": self.level_dbfs,
            "sample_rate_hz": self.sample_rate_hz,
            "pga_db": self.pga_db,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> E0SpurObservationV1:
        record = "E0SpurObservationV1"
        _reject_unknown_keys(payload, cls._FIELDS, record=record)
        rate = payload.get("sample_rate_hz")
        return cls(
            frequency_hz=_positive(payload, "frequency_hz", record=record),
            level_dbfs=_number(payload, "level_dbfs", record=record),
            sample_rate_hz=(
                None
                if rate is None
                else _positive(payload, "sample_rate_hz", record=record)
            ),
            pga_db=_optional_number(payload, "pga_db", record=record),
        )


# ---------------------------------------------------------------------------
# T2 - PGA gain accuracy and noise scaling
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class E0PgaObservationV1:
    """One PGA setting: what it promised, what it did, and what it cost.

    ``input_referred_noise_dbfs`` is the load-bearing column. If it stays flat
    as gain rises the PGA is analog ahead of the modulator and software
    auto-ranging is sound; if it rises with gain the PGA is partly digital and
    the gain architecture needs revisiting. **This contract records the numbers
    and draws neither conclusion** - the architecture question is answered by
    reading the table, not by a field in it.
    """

    setting_db: float
    nominal_change_db: float
    measured_change_db: float
    input_referred_noise_dbfs: float | None = None

    _FIELDS = (
        "setting_db",
        "nominal_change_db",
        "measured_change_db",
        "input_referred_noise_dbfs",
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "setting_db": self.setting_db,
            "nominal_change_db": self.nominal_change_db,
            "measured_change_db": self.measured_change_db,
            "input_referred_noise_dbfs": self.input_referred_noise_dbfs,
        }

    @property
    def gain_error_db(self) -> float:
        """Measured minus nominal. Derived on read, never stored."""
        return self.measured_change_db - self.nominal_change_db

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> E0PgaObservationV1:
        record = "E0PgaObservationV1"
        _reject_unknown_keys(payload, cls._FIELDS, record=record)
        return cls(
            setting_db=_number(payload, "setting_db", record=record),
            nominal_change_db=_number(payload, "nominal_change_db", record=record),
            measured_change_db=_number(payload, "measured_change_db", record=record),
            input_referred_noise_dbfs=_optional_number(
                payload, "input_referred_noise_dbfs", record=record
            ),
        )


# ---------------------------------------------------------------------------
# T3 - AC-coupling corner
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class E0CouplingObservationV1:
    """Amplitude **and phase** at one frequency of the coupling sweep.

    Phase is required, not optional. A first-order high-pass at 20 Hz costs
    0.3 dB at 70 Hz and contributes about 16 degrees of phase lead: amplitude
    error is correctable and phase error corrupts modal identification, so a
    missing phase defaulting to zero would destroy exactly the quantity T3 is
    run to obtain.
    """

    frequency_hz: float
    amplitude_db: float
    phase_deg: float

    _FIELDS = ("frequency_hz", "amplitude_db", "phase_deg")

    def to_dict(self) -> dict[str, Any]:
        return {
            "frequency_hz": self.frequency_hz,
            "amplitude_db": self.amplitude_db,
            "phase_deg": self.phase_deg,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> E0CouplingObservationV1:
        record = "E0CouplingObservationV1"
        _reject_unknown_keys(payload, cls._FIELDS, record=record)
        if payload.get("phase_deg") is None:
            raise _ERR(
                GrantReadinessErrorCode.E0_PHASE_NOT_RECORDED,
                f"{record}.phase_deg is required. Amplitude error is correctable; "
                "phase error is not, and a missing phase must not become zero",
                {"record": record, "field": "phase_deg"},
            )
        return cls(
            frequency_hz=_positive(payload, "frequency_hz", record=record),
            amplitude_db=_number(payload, "amplitude_db", record=record),
            phase_deg=_number(
                payload,
                "phase_deg",
                record=record,
                code=GrantReadinessErrorCode.E0_PHASE_NOT_RECORDED,
            ),
        )


@dataclass(frozen=True)
class E0CouplingResultV1:
    """T3 as a whole: the sweep, and the corner derived from it."""

    measured_corner_hz: float | None = None
    points: tuple[E0CouplingObservationV1, ...] = ()
    separated_from_dac: bool | None = None

    _FIELDS = ("measured_corner_hz", "points", "separated_from_dac")

    def to_dict(self) -> dict[str, Any]:
        return {
            "measured_corner_hz": self.measured_corner_hz,
            "points": [p.to_dict() for p in self.points],
            "separated_from_dac": self.separated_from_dac,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> E0CouplingResultV1:
        record = "E0CouplingResultV1"
        _reject_unknown_keys(payload, cls._FIELDS, record=record)
        corner = payload.get("measured_corner_hz")
        separated = payload.get("separated_from_dac")
        if separated is not None and not isinstance(separated, bool):
            raise _ERR(
                GrantReadinessErrorCode.E0_OBSERVATION_MISSING,
                f"{record}.separated_from_dac must be a boolean when present",
                {"record": record, "field": "separated_from_dac"},
            )
        return cls(
            measured_corner_hz=(
                None
                if corner is None
                else _positive(payload, "measured_corner_hz", record=record)
            ),
            points=tuple(
                E0CouplingObservationV1.from_dict(p)
                for p in _rows(payload, "points", record=record)
            ),
            separated_from_dac=separated,
        )


# ---------------------------------------------------------------------------
# T4 - out-of-band response and folding
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class E0OutOfBandObservationV1:
    """One injected frequency: where it landed, and how far down.

    ``injected_hz`` and ``apparent_hz`` are kept separate because the whole
    point of the test is that they differ. And a frequency the source cannot
    reach is recorded as ``BLOCKED_BY_SOURCE_CAPABILITY`` with no numbers rather
    than dropped: a silently missing row reads as a frequency that folded
    harmlessly.
    """

    injected_hz: float
    source_state: E0SourceCapability = E0SourceCapability.MEASURED
    apparent_hz: float | None = None
    attenuation_db: float | None = None
    sample_rate_hz: float | None = None

    _FIELDS = (
        "injected_hz",
        "source_state",
        "apparent_hz",
        "attenuation_db",
        "sample_rate_hz",
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "injected_hz": self.injected_hz,
            "source_state": self.source_state.value,
            "apparent_hz": self.apparent_hz,
            "attenuation_db": self.attenuation_db,
            "sample_rate_hz": self.sample_rate_hz,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> E0OutOfBandObservationV1:
        record = "E0OutOfBandObservationV1"
        _reject_unknown_keys(payload, cls._FIELDS, record=record)
        state = _enum(
            payload,
            "source_state",
            E0SourceCapability,
            record=record,
            code=GrantReadinessErrorCode.E0_SOURCE_CAPABILITY_MISREPRESENTED,
        )
        apparent = payload.get("apparent_hz")
        attenuation = payload.get("attenuation_db")

        if state is E0SourceCapability.BLOCKED_BY_SOURCE_CAPABILITY:
            if apparent is not None or attenuation is not None:
                raise _ERR(
                    GrantReadinessErrorCode.E0_SOURCE_CAPABILITY_MISREPRESENTED,
                    f"{record} is BLOCKED_BY_SOURCE_CAPABILITY at "
                    f"{payload.get('injected_hz')!r} Hz but carries a measured "
                    "result. A frequency the source cannot generate has no "
                    "measurement",
                    {"record": record, "injected_hz": payload.get("injected_hz")},
                )
        else:
            if apparent is None or attenuation is None:
                raise _ERR(
                    GrantReadinessErrorCode.E0_SOURCE_CAPABILITY_MISREPRESENTED,
                    f"{record} claims MEASURED at {payload.get('injected_hz')!r} Hz "
                    "but records no apparent frequency or attenuation",
                    {"record": record, "injected_hz": payload.get("injected_hz")},
                )

        rate = payload.get("sample_rate_hz")
        return cls(
            injected_hz=_positive(payload, "injected_hz", record=record),
            source_state=state,
            apparent_hz=(
                None
                if apparent is None
                else _number(payload, "apparent_hz", record=record)
            ),
            attenuation_db=(
                None
                if attenuation is None
                else _number(payload, "attenuation_db", record=record)
            ),
            sample_rate_hz=(
                None
                if rate is None
                else _positive(payload, "sample_rate_hz", record=record)
            ),
        )


# ---------------------------------------------------------------------------
# T5 - balanced input granularity
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class E0BalancedInputObservationV1:
    """The input-mode control, its scope, and the full-scale each path showed.

    If the control turns out to be board-wide rather than per-channel, the E1
    rig cannot use the balanced microphone path at all, because ch0 needs
    unbalanced from the conditioner. The single-channel Analyzer still can.
    ``applies_to`` records which instrument the answer bears on.
    """

    control_name: str | None = None
    granularity: E0ControlGranularity = E0ControlGranularity.UNKNOWN
    unbalanced_full_scale_vrms: float | None = None
    balanced_full_scale_vrms: float | None = None
    simultaneous_capture_verified: bool | None = None
    applies_to: str = ""

    _FIELDS = (
        "control_name",
        "granularity",
        "unbalanced_full_scale_vrms",
        "balanced_full_scale_vrms",
        "simultaneous_capture_verified",
        "applies_to",
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "control_name": self.control_name,
            "granularity": self.granularity.value,
            "unbalanced_full_scale_vrms": self.unbalanced_full_scale_vrms,
            "balanced_full_scale_vrms": self.balanced_full_scale_vrms,
            "simultaneous_capture_verified": self.simultaneous_capture_verified,
            "applies_to": self.applies_to,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> E0BalancedInputObservationV1:
        record = "E0BalancedInputObservationV1"
        _reject_unknown_keys(payload, cls._FIELDS, record=record)
        verified = payload.get("simultaneous_capture_verified")
        if verified is not None and not isinstance(verified, bool):
            raise _ERR(
                GrantReadinessErrorCode.E0_OBSERVATION_MISSING,
                f"{record}.simultaneous_capture_verified must be a boolean when present",
                {"record": record},
            )
        unbalanced = payload.get("unbalanced_full_scale_vrms")
        balanced = payload.get("balanced_full_scale_vrms")
        return cls(
            control_name=_optional_text(payload, "control_name", record=record),
            granularity=(
                E0ControlGranularity.UNKNOWN
                if payload.get("granularity") is None
                else _enum(payload, "granularity", E0ControlGranularity, record=record)
            ),
            unbalanced_full_scale_vrms=(
                None
                if unbalanced is None
                else _positive(payload, "unbalanced_full_scale_vrms", record=record)
            ),
            balanced_full_scale_vrms=(
                None
                if balanced is None
                else _positive(payload, "balanced_full_scale_vrms", record=record)
            ),
            simultaneous_capture_verified=verified,
            applies_to=payload.get("applies_to", "") or "",
        )


# ---------------------------------------------------------------------------
# T6 - full-scale input verification
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class E0FullScaleObservationV1:
    """Where one input path starts distorting, and where it stops working.

    The 0.1% THD point and hard clip are separate columns and must stay that
    way: they are different levels answering different questions, and a single
    "maximum input" would silently pick one.
    """

    path: E0InputPath
    thd_0p1pct_vrms: float | None = None
    hard_clip_vrms: float | None = None
    specified_vrms: float | None = None

    _FIELDS = ("path", "thd_0p1pct_vrms", "hard_clip_vrms", "specified_vrms")

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path.value,
            "thd_0p1pct_vrms": self.thd_0p1pct_vrms,
            "hard_clip_vrms": self.hard_clip_vrms,
            "specified_vrms": self.specified_vrms,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> E0FullScaleObservationV1:
        record = "E0FullScaleObservationV1"
        _reject_unknown_keys(payload, cls._FIELDS, record=record)
        thd = payload.get("thd_0p1pct_vrms")
        clip = payload.get("hard_clip_vrms")
        spec = payload.get("specified_vrms")
        return cls(
            path=_enum(payload, "path", E0InputPath, record=record),
            thd_0p1pct_vrms=(
                None
                if thd is None
                else _positive(payload, "thd_0p1pct_vrms", record=record)
            ),
            hard_clip_vrms=(
                None
                if clip is None
                else _positive(payload, "hard_clip_vrms", record=record)
            ),
            specified_vrms=(
                None
                if spec is None
                else _positive(payload, "specified_vrms", record=record)
            ),
        )


# ---------------------------------------------------------------------------
# T7 - loopback latency and stream offset
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class E0LoopbackObservationV1:
    """The ``sd.playrec()`` offset, its spread, and whether it holds still.

    ``mean_offset_samples`` of ``None`` means not measured. Zero means measured
    and zero. The two are different results and the contract keeps them apart.

    ``within_session_stable`` is the field the interpretation turns on: if the
    offset is constant within a session, a per-session loopback calibration
    recovers a usable phase reference for Phase 1. If it varies run to run, it
    does not, and Rev 1.5's statement stands unqualified.
    """

    run_count: int | None = None
    mean_offset_samples: float | None = None
    stddev_samples: float | None = None
    within_session_stable: bool | None = None
    sample_rate_hz: float | None = None

    _FIELDS = (
        "run_count",
        "mean_offset_samples",
        "stddev_samples",
        "within_session_stable",
        "sample_rate_hz",
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_count": self.run_count,
            "mean_offset_samples": self.mean_offset_samples,
            "stddev_samples": self.stddev_samples,
            "within_session_stable": self.within_session_stable,
            "sample_rate_hz": self.sample_rate_hz,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> E0LoopbackObservationV1:
        record = "E0LoopbackObservationV1"
        _reject_unknown_keys(payload, cls._FIELDS, record=record)
        runs = payload.get("run_count")
        if runs is not None:
            if isinstance(runs, bool) or not isinstance(runs, int) or runs <= 0:
                raise _ERR(
                    GrantReadinessErrorCode.E0_OBSERVATION_MISSING,
                    f"{record}.run_count must be a positive integer when present",
                    {"record": record},
                )
        stable = payload.get("within_session_stable")
        if stable is not None and not isinstance(stable, bool):
            raise _ERR(
                GrantReadinessErrorCode.E0_OBSERVATION_MISSING,
                f"{record}.within_session_stable must be a boolean when present",
                {"record": record},
            )
        stddev = payload.get("stddev_samples")
        if stddev is not None:
            value = _number(payload, "stddev_samples", record=record)
            if value < 0:
                raise _ERR(
                    GrantReadinessErrorCode.E0_OBSERVATION_MISSING,
                    f"{record}.stddev_samples cannot be negative",
                    {"record": record},
                )
        rate = payload.get("sample_rate_hz")
        return cls(
            run_count=runs,
            mean_offset_samples=_optional_number(
                payload, "mean_offset_samples", record=record
            ),
            stddev_samples=(
                None
                if stddev is None
                else _number(payload, "stddev_samples", record=record)
            ),
            within_session_stable=stable,
            sample_rate_hz=(
                None
                if rate is None
                else _positive(payload, "sample_rate_hz", record=record)
            ),
        )


# ---------------------------------------------------------------------------
# The record
# ---------------------------------------------------------------------------

# Observation groups that an EXECUTED record must actually carry. T5 is a single
# record rather than a list, so it is checked separately.
_REQUIRED_FOR_EXECUTED = (
    "noise_floor",
    "pga",
    "coupling",
    "out_of_band",
    "full_scale",
    "loopback",
)


@dataclass(frozen=True)
class E0AdcCharacterizationV1:
    """The whole E0 bench record.

    ``EXECUTED`` asserts only that every required observation was recorded. It
    does not mean the board passed, is approved, or has been selected - there is
    no such field here and adding one is refused.
    """

    characterization_id: str
    device: E0DeviceIdentityV1
    provenance: E0ProvenanceV1
    execution_status: E0ExecutionStatus = E0ExecutionStatus.PREPARED
    noise_floor: tuple[E0NoiseObservationV1, ...] = ()
    spurs: tuple[E0SpurObservationV1, ...] = ()
    pga: tuple[E0PgaObservationV1, ...] = ()
    coupling: E0CouplingResultV1 = field(default_factory=E0CouplingResultV1)
    out_of_band: tuple[E0OutOfBandObservationV1, ...] = ()
    balanced_scope: E0BalancedInputObservationV1 = field(
        default_factory=E0BalancedInputObservationV1
    )
    full_scale: tuple[E0FullScaleObservationV1, ...] = ()
    loopback: E0LoopbackObservationV1 = field(default_factory=E0LoopbackObservationV1)
    notes: str = ""
    schema_version: str = field(default=E0_SCHEMA_VERSION, init=False)

    _FIELDS = (
        "schema_version",
        "characterization_id",
        "device",
        "provenance",
        "execution_status",
        "noise_floor",
        "spurs",
        "pga",
        "coupling",
        "out_of_band",
        "balanced_scope",
        "full_scale",
        "loopback",
        "notes",
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "characterization_id": self.characterization_id,
            "execution_status": self.execution_status.value,
            "device": self.device.to_dict(),
            "noise_floor": [n.to_dict() for n in self.noise_floor],
            "spurs": [s.to_dict() for s in self.spurs],
            "pga": [p.to_dict() for p in self.pga],
            "coupling": self.coupling.to_dict(),
            "out_of_band": [o.to_dict() for o in self.out_of_band],
            "balanced_scope": self.balanced_scope.to_dict(),
            "full_scale": [f.to_dict() for f in self.full_scale],
            "loopback": self.loopback.to_dict(),
            "provenance": self.provenance.to_dict(),
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> E0AdcCharacterizationV1:
        record = "E0AdcCharacterizationV1"
        _reject_unknown_keys(payload, cls._FIELDS, record=record)

        version = payload.get("schema_version", E0_SCHEMA_VERSION)
        if version != E0_SCHEMA_VERSION:
            raise _ERR(
                GrantReadinessErrorCode.E0_OBSERVATION_MISSING,
                f"{record}.schema_version must be {E0_SCHEMA_VERSION!r}, not {version!r}",
                {"record": record, "field": "schema_version"},
            )

        status = _enum(
            payload,
            "execution_status",
            E0ExecutionStatus,
            record=record,
            code=GrantReadinessErrorCode.E0_EXECUTION_STATUS_INVALID,
        )

        device_payload = payload.get("device")
        if not isinstance(device_payload, Mapping):
            raise _ERR(
                GrantReadinessErrorCode.E0_DEVICE_IDENTITY_INCOMPLETE,
                f"{record}.device is required - a characterization with no device "
                "identity cannot be traced to a board",
                {"record": record, "field": "device"},
            )
        provenance_payload = payload.get("provenance")
        if not isinstance(provenance_payload, Mapping):
            raise _ERR(
                GrantReadinessErrorCode.E0_OBSERVATION_MISSING,
                f"{record}.provenance is required",
                {"record": record, "field": "provenance"},
            )

        built = cls(
            characterization_id=_text(payload, "characterization_id", record=record),
            device=E0DeviceIdentityV1.from_dict(device_payload),
            provenance=E0ProvenanceV1.from_dict(provenance_payload),
            execution_status=status,
            noise_floor=tuple(
                E0NoiseObservationV1.from_dict(n)
                for n in _rows(payload, "noise_floor", record=record)
            ),
            spurs=tuple(
                E0SpurObservationV1.from_dict(s)
                for s in _rows(payload, "spurs", record=record)
            ),
            pga=tuple(
                E0PgaObservationV1.from_dict(p)
                for p in _rows(payload, "pga", record=record)
            ),
            coupling=E0CouplingResultV1.from_dict(payload.get("coupling") or {}),
            out_of_band=tuple(
                E0OutOfBandObservationV1.from_dict(o)
                for o in _rows(payload, "out_of_band", record=record)
            ),
            balanced_scope=E0BalancedInputObservationV1.from_dict(
                payload.get("balanced_scope") or {}
            ),
            full_scale=tuple(
                E0FullScaleObservationV1.from_dict(f)
                for f in _rows(payload, "full_scale", record=record)
            ),
            loopback=E0LoopbackObservationV1.from_dict(payload.get("loopback") or {}),
            notes=payload.get("notes", "") or "",
        )
        built.validate()
        return built

    # -- invariants ---------------------------------------------------------

    def observed_groups(self) -> dict[str, bool]:
        """Which observation groups carry anything at all."""
        return {
            "noise_floor": bool(self.noise_floor),
            "spurs": bool(self.spurs),
            "pga": bool(self.pga),
            "coupling": bool(self.coupling.points),
            "out_of_band": bool(self.out_of_band),
            "balanced_scope": self.balanced_scope.granularity
            is not E0ControlGranularity.UNKNOWN,
            "full_scale": bool(self.full_scale),
            "loopback": self.loopback.mean_offset_samples is not None,
        }

    def validate(self) -> None:
        """Refuse a record whose status disagrees with what it contains."""
        observed = self.observed_groups()

        if self.execution_status is E0ExecutionStatus.PREPARED and any(
            observed.values()
        ):
            carried = sorted(k for k, v in observed.items() if v)
            raise _ERR(
                GrantReadinessErrorCode.E0_EXECUTION_STATUS_INVALID,
                "record is PREPARED but carries observations in "
                f"{', '.join(carried)}. PREPARED means no bench has been touched",
                {"record": "E0AdcCharacterizationV1", "groups": carried},
            )

        if self.execution_status is E0ExecutionStatus.EXECUTED:
            missing = [name for name in _REQUIRED_FOR_EXECUTED if not observed[name]]
            if not observed["balanced_scope"]:
                missing.append("balanced_scope")
            if missing:
                raise _ERR(
                    GrantReadinessErrorCode.E0_OBSERVATION_MISSING,
                    "record claims EXECUTED but records nothing for "
                    f"{', '.join(sorted(missing))}. EXECUTED means every required "
                    "observation was taken, not that the board was acceptable",
                    {"record": "E0AdcCharacterizationV1", "missing": sorted(missing)},
                )

        # Full-scale paths must stay distinguishable.
        paths = [f.path for f in self.full_scale]
        if len(paths) != len(set(paths)):
            raise _ERR(
                GrantReadinessErrorCode.E0_MEASUREMENT_CONFLATED,
                "full_scale records the same input path twice; balanced and "
                "unbalanced results must remain distinguishable",
                {"record": "E0AdcCharacterizationV1"},
            )

        # A source bandwidth, once declared, binds every MEASURED T4 row.
        limit = self.provenance.source_verified_bandwidth_hz
        if limit is not None:
            beyond = [
                o.injected_hz
                for o in self.out_of_band
                if o.source_state is E0SourceCapability.MEASURED
                and o.injected_hz > limit
            ]
            if beyond:
                raise _ERR(
                    GrantReadinessErrorCode.E0_SOURCE_CAPABILITY_MISREPRESENTED,
                    "out_of_band claims measurements at "
                    f"{', '.join(f'{hz:g}' for hz in sorted(beyond))} Hz, above the "
                    f"source's verified bandwidth of {limit:g} Hz",
                    {
                        "record": "E0AdcCharacterizationV1",
                        "frequencies": sorted(beyond),
                    },
                )


__all__ = [
    "E0_SCHEMA_VERSION",
    "E0AdcCharacterizationV1",
    "E0ArtifactRefV1",
    "E0BalancedInputObservationV1",
    "E0ControlGranularity",
    "E0CouplingObservationV1",
    "E0CouplingResultV1",
    "E0DeviceIdentityV1",
    "E0ExecutionStatus",
    "E0FullScaleObservationV1",
    "E0InputPath",
    "E0LoopbackObservationV1",
    "E0NoiseObservationV1",
    "E0OutOfBandObservationV1",
    "E0PgaObservationV1",
    "E0ProvenanceV1",
    "E0SourceCapability",
    "E0SpurObservationV1",
]
