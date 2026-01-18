#!/usr/bin/env bash
set -euo pipefail
echo "== Local CI dry run =="

echo "• Running unit tests (pytest)…"
pytest -q

echo "• Running coverage (>=80% gate)…"
pytest --cov=modes --cov=scripts --cov-report=term --cov-report=xml -q

echo "• Running hardware-free demos (Chladni, Phase-2)…"
make examples-chladni-demo
make examples-phase2-demo

echo "• Validating Analyzer schemas (out/**)…"
make validate-schemas

echo "✅ Local CI dry run passed."
