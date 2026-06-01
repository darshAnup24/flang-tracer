#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "[build] Setting up Flang Multi-Stage Compilation Pipeline Tracer"
echo ""

# Create virtual environment if not present
if [ ! -d venv ]; then
    echo "[build] Creating Python virtual environment..."
    python3 -m venv venv
fi

echo "[build] Activating virtual environment..."
source venv/bin/activate

echo "[build] Installing build dependencies..."
pip install --upgrade pip setuptools wheel --quiet

echo "[build] Installing package in development mode..."
pip install -e . --quiet

echo "[build] Installing runtime dependencies..."
pip install click rich flask pytest --quiet

echo ""
echo "[build] Done.  Run:  source venv/bin/activate"
echo "[build] Then:        scripts/run.sh"
