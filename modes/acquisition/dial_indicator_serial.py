#!/usr/bin/env python3
"""
Read a digital dial indicator over serial and save displacement vs time => displacement_series.json

Assumes the indicator streams ASCII lines; configure parse and scaling if needed.
Example quick run:
  python modes/acquisition/dial_indicator_serial.py --port COM3 --out out/disp.json --unit mm --duration 8 --rate 20
"""
from __future__ import annotations
import argparse, json, time, re, pathlib, serial

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", required=True)
    ap.add_argument("--baud", type=int, default=9600)
    ap.add_argument("--unit", default="mm")
    ap.add_argument("--pattern", default=r"(-?[0-9]+\.?[0-9]*)")  # first number in line
    ap.add_argument("--scale", type=float, default=1.0)  # if raw units need scaling to mm
    ap.add_argument("--duration", type=float, default=10.0)
    ap.add_argument("--rate", type=float, default=20.0)  # target read frequency
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    ser = serial.Serial(a.port, a.baud, timeout=0.1)
    pat = re.compile(a.pattern)
    t0 = time.time()
    rows = []
    period = 1.0/max(a.rate,1e-6)
    try:
        while (time.time() - t0) < a.duration:
            line = ser.readline().decode(errors="ignore").strip()
            if not line: 
                time.sleep(period)
                continue
            m = pat.search(line)
            if not m:
                continue
            val = float(m.group(1)) * a.scale
            t = time.time() - t0
            rows.append([round(t,5), float(val)])
            # throttle to ~rate
            time.sleep(period)
    finally:
        ser.close()

    out = {
      "artifact_type":"displacement_series",
      "unit": a.unit,
      "sample_rate_hz": round(len(rows)/max(a.duration,1e-6), 3),
      "ts_utc_start": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(t0))),
      "data": rows
    }
    pathlib.Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(a.out,"w",encoding="utf-8"), indent=2)
    print(f"Wrote {a.out} ({len(rows)} samples)")
    
if __name__ == "__main__":
    main()
