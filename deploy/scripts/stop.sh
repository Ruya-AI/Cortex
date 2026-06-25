#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "=== Cortex QA Platform — Stopping ==="

case "$1" in
  docker)
    echo "Stopping Docker Compose services..."
    cd "$PROJECT_ROOT/deploy/docker"
    docker compose down
    ;;

  local)
    echo "Stopping local services..."
    pkill -f "uvicorn cortex_backend" 2>/dev/null && echo "  Backend stopped" || echo "  Backend not running"
    pkill -f "vite.*cortex_frontend" 2>/dev/null && echo "  Frontend stopped" || echo "  Frontend not running"
    ;;

  all)
    echo "Stopping all services..."
    pkill -f "uvicorn cortex_backend" 2>/dev/null || true
    pkill -f "vite.*cortex_frontend" 2>/dev/null || true
    cd "$PROJECT_ROOT/deploy/docker" 2>/dev/null && docker compose down 2>/dev/null || true
    ;;

  *)
    echo "Usage: $0 {docker|local|all}"
    exit 1
    ;;
esac

echo "=== Stopped ==="
