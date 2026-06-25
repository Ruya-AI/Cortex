#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Cortex QA Platform — Restarting ==="

"$SCRIPT_DIR/stop.sh" "${1:-all}"
sleep 2
"$SCRIPT_DIR/start.sh" "${1:-local}"
sleep 3
"$SCRIPT_DIR/health.sh"
