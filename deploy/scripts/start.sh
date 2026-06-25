#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DEPLOY_ENV="${DEPLOY_ENV:-development}"

echo "=== Cortex QA Platform — Starting ($DEPLOY_ENV) ==="

cd "$PROJECT_ROOT"

case "$1" in
  docker)
    echo "Starting with Docker Compose..."
    cd deploy/docker
    DEPLOY_ENV=$DEPLOY_ENV docker compose up -d --build
    echo ""
    echo "Services:"
    echo "  Frontend:  http://localhost:${FRONTEND_PORT:-80}"
    echo "  Backend:   http://localhost:${BACKEND_PORT:-8000}"
    echo "  Database:  localhost:${POSTGRES_PORT:-5432}"
    ;;

  local)
    echo "Starting local development services..."

    # Start PostgreSQL if not running
    if ! docker ps | grep -q cortex-postgres; then
      echo "Starting PostgreSQL..."
      docker compose -f deploy/docker/docker-compose.yml up -d postgres
      sleep 3
    fi

    # Build frontend
    echo "Building frontend..."
    cd cortex_frontend && npm run build && cd ..

    # Start backend
    echo "Starting backend..."
    PYTHONPATH=. nohup python -m uvicorn cortex_backend.main:app \
      --host 0.0.0.0 --port ${BACKEND_PORT:-8000} \
      > /tmp/cortex-backend.log 2>&1 &
    echo "  Backend PID: $!"

    # Start frontend dev server (optional)
    if [ "$2" = "--dev" ]; then
      echo "Starting frontend dev server..."
      cd cortex_frontend
      nohup npx vite --host 0.0.0.0 --port ${FRONTEND_PORT:-5173} \
        > /tmp/cortex-frontend.log 2>&1 &
      echo "  Frontend PID: $!"
      cd ..
    fi

    sleep 3
    echo ""
    echo "Services:"
    echo "  Backend: http://localhost:${BACKEND_PORT:-8000}"
    [ "$2" = "--dev" ] && echo "  Frontend: http://localhost:${FRONTEND_PORT:-5173}"
    ;;

  engine)
    echo "Starting engine standalone..."
    shift
    PYTHONPATH=. python -m cortex_engine.cli.run "$@"
    ;;

  *)
    echo "Usage: $0 {docker|local|engine} [options]"
    echo ""
    echo "  docker         Start all services with Docker Compose"
    echo "  local          Start local dev (PostgreSQL + backend)"
    echo "  local --dev    Start local dev with frontend dev server"
    echo "  engine [args]  Run engine CLI directly"
    echo ""
    echo "Environment: DEPLOY_ENV=development|production (default: development)"
    exit 1
    ;;
esac

echo ""
echo "=== Started ==="
