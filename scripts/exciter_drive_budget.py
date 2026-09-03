#!/usr/bin/env python3
# INSTRUMENT CLASS: MEASUREMENT
"""Ohm's-law arithmetic for an exciter drive level. Read-only, stdlib only.

    python scripts/exciter_drive_budget.py --load-ohm 4 --vrms 2 --bl 1.54

This is a **calculator, not an evidence generator**. It answers one question —
"at this output voltage into this load, what current and electrical power is
that?" — and it answers it with two divisions. It knows nothing about plates,
and it cannot tell anyone what drive a measurement needs. That is what the
[characterization protocol](../docs/hardware/TTP_EXCITER_POWER_CHARACTERIZATION_PROTOCOL.md)
is for.

The one thing worth being careful about is ``BL x Irms``. It has units of
newtons and it is not the force delivered to the specimen. It is a *motor-force
scale*: what the voice-coil motor develops, before the bond, the stinger, the
tip, the preload and the plate's own mechanical impedance — none of which is
characterized. Every output path here says so, because a bare number in newtons
is exactly the kind of value that gets quoted later as though a force channel
existed.

Where BL is not published — the VISATON EX 30 S sheet does not print one — the
motor-force scale is ``UNAVAILABLE``. It is never zero, and it is never
estimated from the parameters that *are* published.
"""

from __future__ import annotations

import argparse
import json
import sys

# The caveat that must travel with every motor-force number, in text and in
# JSON. It is not a footnote: the whole commercial excitation architecture rests
# on force at the plate being unknown.
MOTOR_FORCE_CAVEAT = (
    "Motor-force scale is not force delivered to the specimen. "
    "BL x Irms is what the voice-coil motor develops; the bond, stinger, tip, "
    "preload and plate impedance sit between it and the plate, and none of "
    "them is characterized. No force channel exists in the commercial path."
)

UNAVAILABLE = "UNAVAILABLE"

# Digits kept in the output. Enough to carry a milliamp and a milliwatt without
# printing float noise that would read as precision nobody measured.
DIGITS = 6


class InvalidDrive(ValueError):
    """An input that cannot describe a physical drive condition."""


def drive_budget(
    load_ohm: float,
    vrms: float,
    bl_tm: float | None = None,
    moving_mass_g: float | None = None,
) -> dict[str, object]:
    """Current, electrical power, and — where BL is known — a motor-force scale.

    Raises ``InvalidDrive`` rather than returning a sentinel for an impossible
    input. A zero or negative load is not a low impedance, and a negative rms
    voltage is not a small one; both are input errors, and returning a number
    for either would put an arithmetic artifact into a document.
    """
    if load_ohm <= 0:
        raise InvalidDrive(
            f"load_ohm must be greater than zero, got {load_ohm!r} - "
            "a zero or negative load is not a physical impedance"
        )
    if vrms < 0:
        raise InvalidDrive(
            f"vrms must not be negative, got {vrms!r} - an rms quantity is a "
            "magnitude"
        )
    if bl_tm is not None and bl_tm <= 0:
        raise InvalidDrive(
            f"bl_tm must be greater than zero, got {bl_tm!r} - a BL of zero is "
            "not a measurement, it is a missing value, and a missing BL is "
            f"reported as {UNAVAILABLE}"
        )
    if moving_mass_g is not None and moving_mass_g <= 0:
        raise InvalidDrive(
            f"moving_mass_g must be greater than zero, got {moving_mass_g!r}"
        )

    irms = vrms / load_ohm
    electrical_power = vrms * irms

    payload: dict[str, object] = {
        "load_ohm": round(load_ohm, DIGITS),
        "vrms": round(vrms, DIGITS),
        "irms_a": round(irms, DIGITS),
        "electrical_power_w": round(electrical_power, DIGITS),
        "bl_tm": round(bl_tm, DIGITS) if bl_tm is not None else None,
        "motor_force_scale_n": (
            round(bl_tm * irms, DIGITS) if bl_tm is not None else UNAVAILABLE
        ),
        "moving_mass_g": (
            round(moving_mass_g, DIGITS) if moving_mass_g is not None else None
        ),
        # Recorded, deliberately not used. Dividing the motor-force scale by the
        # moving mass would give the acceleration of an exciter driving nothing,
        # and this exciter is coupled to a plate whose impedance is unknown.
        "acceleration_scale": "NOT_DERIVED",
        "specimen_force_n": "NOT_MEASURED",
        "caveat": MOTOR_FORCE_CAVEAT,
    }
    return payload


def format_text(payload: dict[str, object]) -> str:
    lines = [
        f"load                  {payload['load_ohm']} ohm",
        f"output voltage        {payload['vrms']} Vrms",
        f"current               {payload['irms_a']} Arms",
        f"electrical power      {payload['electrical_power_w']} W",
    ]
    if payload["bl_tm"] is None:
        lines.append(f"motor-force scale     {UNAVAILABLE} (no BL published)")
    else:
        lines.append(
            f"motor-force scale     {payload['motor_force_scale_n']} N "
            f"(BL {payload['bl_tm']} Tm x current)"
        )
    if payload["moving_mass_g"] is not None:
        lines.append(
            f"moving mass           {payload['moving_mass_g']} g "
            "(recorded; no acceleration derived)"
        )
    lines.append(f"force at the plate    {payload['specimen_force_n']}")
    lines.append("")
    lines.append(MOTOR_FORCE_CAVEAT)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Ohm's-law arithmetic for an exciter drive level. Computes no "
            "force at the specimen and establishes no measurement."
        )
    )
    parser.add_argument(
        "--load-ohm",
        type=float,
        required=True,
        help="nominal load impedance in ohms (4 for the Dayton candidates, 8 "
        "for the VISATON)",
    )
    parser.add_argument(
        "--vrms", type=float, required=True, help="amplifier output in Vrms"
    )
    parser.add_argument(
        "--bl",
        type=float,
        default=None,
        help="force factor BL in Tm, where the manufacturer publishes one",
    )
    parser.add_argument(
        "--moving-mass-g",
        type=float,
        default=None,
        help="moving mass Mms in grams; recorded, not used to derive anything",
    )
    parser.add_argument(
        "--json", action="store_true", help="emit JSON instead of text"
    )
    args = parser.parse_args(argv)

    try:
        payload = drive_budget(
            load_ohm=args.load_ohm,
            vrms=args.vrms,
            bl_tm=args.bl,
            moving_mass_g=args.moving_mass_g,
        )
    except InvalidDrive as exc:
        print(f"invalid drive condition: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(format_text(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
