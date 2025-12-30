# Usage:
#   make run-tap OUT=out/tap_tone.json DUR=4 SR=44100
#   make bend-single OUT=out/bending_test.json
#   make bend-batch CSV=data/deflection_runs.csv OUT=out/moe_results.csv
#   make provenance-hash FILE=path/to/grain_field.png OUT=out/provenance.json

PY ?= python

run-tap:
	@mkdir -p $$(dirname $(OUT))
	@$(PY) modes/tap_tone/tap_fft_logger.py --outfile $(OUT) --plot $$(dirname $(OUT))/spectrum.png --labels A0 T11 B11

bend-single:
	@mkdir -p $$(dirname $(OUT))
	@$(PY) modes/bending_stiffness/deflection_to_moe.py \
		--method 3point --span 400 --width 20 --thickness 3.0 \
		--force 5.0 --deflection 0.62 --density 0.41 \
		--out $(OUT)

bend-batch:
	@mkdir -p $$(dirname $(OUT))
	@$(PY) modes/bending_stiffness/deflection_to_moe.py --csv $(CSV) --out $(OUT)

# Force vs Displacement plot (measurement visualization)
plot-fvd:
	@mkdir -p $$(dirname $(OUT))
	@$(PY) modes/bending_stiffness/plot_f_vs_d.py \
		--pair 5,0.2 --pair 10,0.41 --pair 15,0.62 --pair 20,0.83 \
		--out $(OUT) --title "Force vs Displacement"

provenance-hash:
	@mkdir -p $$(dirname $(OUT))
	@$(PY) modes/provenance_import/attach_grain_provenance.py --file $(FILE) --out $(OUT)

validate-schemas:
	@$(PY) -m jsonschema -i examples/measurement/tap_tone.json schemas/measurement/tap_peaks.schema.json
	@$(PY) -m jsonschema -i examples/measurement/bending_test.json schemas/measurement/moe_result.schema.json
	@$(PY) -m jsonschema -i examples/measurement/manifest.json schemas/measurement/manifest.schema.json

# Emit manifest.json for one run
manifest:
	@mkdir -p $$(dirname $(OUT))
	@$(PY) modes/_shared/emit_manifest.py --out $(OUT) $(ARTIFACTS) $(RIG) $(NOTES)

# Usage:
# make manifest OUT=out/manifest.json \
#   ARTIFACTS="--artifact out/tap_tone.json --artifact out/bending_test.json" \
#   RIG="--rig fixture=3-point --rig span_mm=400 --rig operator=Ross" \
#   NOTES="--notes Run J45-0001"

# ------------------------------
# Bending stiffness bundle CLI
# ------------------------------

bend-mode-sample:
	@$(PY) scripts/bending_stiffness_mode.py \
		--out ./out \
		--specimen-id S1 \
		--material-role top \
		--wood-species spruce \
		--grain-orientation longitudinal \
		--span-mm 400 \
		--pair 5,0.2 --pair 10,0.41 --pair 15,0.62 --pair 20,0.83 \
		--method three_point_bending \
		--units-length mm \
		--units-force N

bend-mode-pack:
	@$(PY) scripts/bending_stiffness_mode.py \
		--out ./out \
		--specimen-id S1 \
		--material-role top \
		--wood-species spruce \
		--grain-orientation longitudinal \
		--span-mm 400 \
		--pair 5,0.2 --pair 10,0.41 --pair 15,0.62 --pair 20,0.83 \
		--method three_point_bending \
		--units-length mm \
		--units-force N \
		--pack

bend-mode-validate:
	@LATEST=$$(ls -dt out/bend_* | head -n 1); \
	if [ -z "$$LATEST" ]; then echo "No bundles under out/" && exit 1; fi; \
	$(PY) - << 'PY' "$$LATEST"
import sys, json
from pathlib import Path

try:
    import jsonschema
    from jsonschema import validate
except Exception as e:
    print("jsonschema not available; install via 'pip install jsonschema'")
    raise SystemExit(1)

bundle = Path(sys.argv[1])
schema_path = Path("schemas/bending_stiffness.schema.json")
data_path = bundle/"analysis"/"bending_stiffness.json"

schema = json.loads(schema_path.read_text())
data = json.loads(data_path.read_text())

validate(instance=data, schema=schema)
print("✓", str(data_path), "valid against", str(schema_path))
PY

# Offline tap from WAV
run-tap-offline:
	@mkdir -p $$(dirname $(OUT))
	@$(PY) modes/tap_tone/offline_from_wav.py --wav $(WAV) --outfile $(OUT) --labels A0 T11 B11

# ------------------------------
# Bundle v4: GUI + Serial Acquisition
# ------------------------------

# GUI
gui:
	@$(PY) gui/app.py

# Serial — Load Cell
loadcell:
	@$(PY) modes/acquisition/loadcell_serial.py --config $(CFG) --out $(OUT)

# Serial — Dial Indicator
dial:
	@$(PY) modes/acquisition/dial_indicator_serial.py --port $(PORT) --out $(OUT) --unit $(UNIT) --duration $(DUR) --rate $(RATE)

# Validate time-series schemas/examples
validate-timeseries:
	@$(PY) -m jsonschema -i examples/measurement/load_series.json schemas/measurement/load_series.schema.json
	@$(PY) -m jsonschema -i examples/measurement/displacement_series.json schemas/measurement/displacement_series.schema.json
	@echo "Time-series examples validate."
