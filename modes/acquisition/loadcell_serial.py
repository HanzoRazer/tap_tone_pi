#!/usr/bin/env python3
"""
Read a load cell over serial and save force vs time => load_series.json

Config JSON example:
{
  "port": "COM4",          // or "/dev/ttyUSB0"
  "baud": 115200,
  "timeout_s": 0.2,
  "unit": "N",             // output unit; if raw counts are in the stream, use calibration
  "parse": {               // tell the parser how to read a line
    "kind": "csv_idx",     // "csv_idx" | "regex"
    "index": 0             // when csv_idx: take column 0
    // OR
    // "kind": "regex", "pattern": "F:(-?[0-9.]+)"
  },
  "calibration": {
    "kind": "linear",      // y = a*x + b
    "a": 1.0,
    "b": 0.0
  },
  "sample_rate_hz": 50,
  "duration_s": 10
}
"""
from __future__ import annotations
import argparse, json, time, re, pathlib, serial

def parse_line(line: str, parse_cfg: dict):
    k = parse_cfg.get("kind","csv_idx")
    if k == "csv_idx":
        idx = int(parse_cfg.get("index",0))
        parts = [p.strip() for p in line.split(",")]
        return float(parts[idx])
    elif k == "regex":
        pat = re.compile(parse_cfg["pattern"])
        m = pat.search(line)
        if not m: return None
        return float(m.group(1))
    else:
        return None

def calibrate(raw: float, calib: dict):
    if calib and calib.get("kind") == "linear":
        return calib.get("a",1.0)*raw + calib.get("b",0.0)
    return raw

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    cfg = json.load(open(args.config,"r",encoding="utf-8"))
    ser = serial.Serial(cfg["port"], cfg.get("baud",115200), timeout=cfg.get("timeout_s",0.2))
    unit = cfg.get("unit","N")
    parse_cfg = cfg.get("parse",{"kind":"csv_idx","index":0})
    calib = cfg.get("calibration",{"kind":"linear","a":1.0,"b":0.0})
    fs = float(cfg.get("sample_rate_hz",50))
    dur = float(cfg.get("duration_s",10))
    nmax = int(fs*dur)

    t0 = time.time()
    rows = []
    try:
        while len(rows) < nmax:
            line = ser.readline().decode(errors="ignore").strip()
            if not line: continue
            val_raw = parse_line(line, parse_cfg)
            if val_raw is None: continue
            val = calibrate(val_raw, calib)
            t = time.time() - t0
            rows.append([round(t,5), float(val)])
    finally:
        ser.close()

    out = {
      "artifact_type":"load_series",
      "unit": unit,
      "sample_rate_hz": fs,
      "ts_utc_start": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(t0))),
      "data": rows
    }
    pathlib.Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(args.out,"w",encoding="utf-8"), indent=2)
    print(f"Wrote {args.out} ({len(rows)} samples)")

if __name__ == "__main__":
    main()
