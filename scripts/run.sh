#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Activate virtual environment if not already active
if [ -z "${VIRTUAL_ENV:-}" ]; then
    if [ ! -d venv ]; then
        echo "[run] No virtual environment found. Run scripts/build.sh first."
        exit 1
    fi
    source venv/bin/activate
fi

mkdir -p output

echo "========================================"
echo " Flang Multi-Stage Compilation Tracer"
echo "========================================"
echo ""

# ---- Trace all example/testcase files ----
CASES=(
    "C01:testcases/C01_array_assign.f90"
    "C02:testcases/C02_array_section.f90"
    "C03:testcases/C03_where_block.f90"
    "C04:testcases/C04_forall.f90"
    "C05:testcases/C05_do_concurrent.f90"
    "C06:testcases/C06_derived_type.f90"
    "C07:testcases/C07_polymorph.f90"
    "C08:testcases/C08_coarray.f90"
    "C09:testcases/C09_assumed_shape.f90"
    "C10:testcases/C10_associate.f90"
)

HTML_FILES=()
for entry in "${CASES[@]}"; do
    LABEL="${entry%%:*}"
    FILE="${entry##*:}"

    echo "--- [$LABEL] Tracing: $FILE ---"

    HTML_OUT="output/${LABEL}_trace.html"
    JSON_OUT="output/${LABEL}_trace.json"
    TEXT_OUT="output/${LABEL}_trace.txt"
    HTML_FILES+=("$HTML_OUT")

    ftrace trace "$FILE" --format html  -o "$HTML_OUT"  2>/dev/null && echo "  HTML -> $HTML_OUT"   || echo "  [skip] HTML"
    ftrace trace "$FILE" --format json  -o "$JSON_OUT"  2>/dev/null && echo "  JSON -> $JSON_OUT"   || true
    ftrace trace "$FILE" --format text  -o "$TEXT_OUT"  2>/dev/null && echo "  TEXT -> $TEXT_OUT"   || true

    echo ""
done

echo "========================================"
echo " All traces complete."
echo " Output directory: $ROOT/output/"
echo "========================================"
echo ""

# ---- Launch the Web Application ----
echo "Starting web application..."

# Kill any previous instance on port 8081
lsof -ti:8081 2>/dev/null | xargs kill -9 2>/dev/null || true

python3 web/app.py &
WEB_PID=$!
echo "  Web app PID: $WEB_PID"
echo ""

# Wait for the web app to be ready
for i in $(seq 1 15); do
    if curl -s http://127.0.0.1:8081/api/health >/dev/null 2>&1; then
        break
    fi
    sleep 0.3
done

# Open browser to the web app (with results area ready for interaction)
echo "  Opening browser to web app..."
xdg-open "http://127.0.0.1:8081/" 2>/dev/null || \
    open "http://127.0.0.1:8081/" 2>/dev/null || \
    echo "  Open http://127.0.0.1:8081/ in your browser."

echo ""
echo "========================================"
echo " Web app running at: http://127.0.0.1:8081/"
echo " Generated reports: output/*.html (shown in UI tabs)"
echo " Press Ctrl+C to stop the web server."
echo "========================================"

wait "$WEB_PID"
