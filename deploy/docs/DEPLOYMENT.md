# Cortex QA Platform — Deployment Guide

## Architecture

```
cortex_engine/    Independent QA engine (28 tools, 5 agents)
cortex_backend/   FastAPI service layer (APIs, DB, WebSocket)
cortex_frontend/  React web UI (served by Nginx or backend)
```

## System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 4 cores | 8 cores |
| RAM | 16 GB | 32 GB |
| Disk | 50 GB SSD | 100 GB SSD |
| Python | 3.11+ | 3.12 |
| Node.js | 18+ | 22+ |
| Docker | 24+ | 25+ |
| PostgreSQL | 15+ | 16+ |

## Quick Start

### Docker (Recommended)

```bash
# Start all services
./deploy/scripts/start.sh docker

# Check health
./deploy/scripts/health.sh

# Stop
./deploy/scripts/stop.sh docker
```

### Local Development

```bash
# Prerequisites: Docker (for PostgreSQL), Python 3.12, Node.js 22

# 1. Start PostgreSQL
docker compose -f deploy/docker/docker-compose.yml up -d postgres

# 2. Install Python dependencies
pip install -e ".[tier1,backend,graph]"

# 3. Build frontend
cd cortex_frontend && npm install && npm run build && cd ..

# 4. Start backend (serves frontend)
PYTHONPATH=. uvicorn cortex_backend.main:app --host 0.0.0.0 --port 8000

# Or use the script:
./deploy/scripts/start.sh local --dev
```

### Engine Standalone (CI/CD)

```bash
# Install engine only
pip install -e ".[tier1]"

# Run QA scan
PYTHONPATH=. python -m cortex_engine.cli.run --repo https://github.com/org/repo.git --tiers 1
```

## Environment Configuration

### Development
```bash
cp deploy/config/development/.env .env
# Edit .env with your values
```

### Production
```bash
cp deploy/config/production/.env .env
# REQUIRED: Change POSTGRES_PASSWORD, CORTEX_SECRET_KEY
# REQUIRED: Set LLM credentials (Vertex AI or Anthropic API key)
```

### Key Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `CORTEX_DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://cortex:cortex@localhost:5432/cortex` |
| `CORTEX_SECRET_KEY` | Session encryption key | `change-me-in-production` |
| `CORTEX_DEBUG` | Enable debug mode | `false` |
| `CLAUDE_CODE_USE_VERTEX` | Use Vertex AI for LLM | (unset) |
| `ANTHROPIC_VERTEX_PROJECT_ID` | GCP project for Vertex AI | (unset) |
| `ANTHROPIC_API_KEY` | Direct Anthropic API key | (unset) |
| `QA_LLM_PRIMARY_MODEL` | Primary LLM model | `claude-opus-4-6` |
| `QA_LLM_FALLBACK_MODEL` | Fallback LLM model | `claude-sonnet-4-6` |

## Service Management

### Scripts

| Script | Description |
|--------|-------------|
| `deploy/scripts/start.sh docker` | Start all services via Docker Compose |
| `deploy/scripts/start.sh local` | Start local dev (PostgreSQL + backend) |
| `deploy/scripts/start.sh local --dev` | Start local dev with frontend dev server |
| `deploy/scripts/start.sh engine --repo . --tiers 1` | Run engine CLI directly |
| `deploy/scripts/stop.sh docker` | Stop Docker Compose services |
| `deploy/scripts/stop.sh local` | Stop local services |
| `deploy/scripts/stop.sh all` | Stop everything |
| `deploy/scripts/restart.sh` | Restart + health check |
| `deploy/scripts/health.sh` | Check all service health |

### Ports

| Service | Default Port | Variable |
|---------|-------------|----------|
| Frontend (Nginx) | 80 | `FRONTEND_PORT` |
| Backend (FastAPI) | 8000 | `BACKEND_PORT` |
| PostgreSQL | 5432 | `POSTGRES_PORT` |
| Frontend Dev (Vite) | 5173 | — |

## Docker Build

### Build individual services

```bash
# Engine only (for CI/CD)
docker build -f deploy/docker/Dockerfile.engine -t cortex-engine .

# Backend (includes engine)
docker build -f deploy/docker/Dockerfile.backend -t cortex-backend .

# Frontend
docker build -f deploy/docker/Dockerfile.frontend -t cortex-frontend .
```

### CI/CD Pipeline Integration

```bash
# Run engine in CI
docker compose -f deploy/docker/docker-compose.ci.yml run engine \
  --repo https://github.com/org/repo.git --tiers 1 --report json

# Reports available at /tmp/cortex-ci-reports/
```

## GCP Deployment

### Recommended Instance

| Type | Specs | Cost/month |
|------|-------|------------|
| `e2-standard-8` | 8 vCPU, 32 GB RAM | ~$195 |

### Steps

1. Create GCE instance with Container-Optimized OS
2. Install Docker and Docker Compose
3. Clone repo and configure `deploy/config/production/.env`
4. Run `./deploy/scripts/start.sh docker`
5. Configure Vertex AI ADC: `gcloud auth application-default login`

## Troubleshooting

### Backend won't start
```bash
# Check logs
cat /tmp/cortex-backend.log

# Verify PostgreSQL
docker exec cortex-postgres pg_isready -U cortex

# Test import
PYTHONPATH=. python -c "from cortex_backend.main import app; print('OK')"
```

### Engine scan fails
```bash
# Test engine standalone
PYTHONPATH=. python -m cortex_engine.cli.run --repo . --tiers 1 --dry-run

# Check tool availability
for tool in trivy gitleaks osv-scanner bandit ruff; do
  which $tool && echo "$tool: OK" || echo "$tool: MISSING"
done
```

### Frontend build fails
```bash
cd cortex_frontend
rm -rf node_modules
npm install
npm run build
```

### Stale executions stuck in "running"
Handled automatically by the stale execution reaper (checks every 2 min, default 60 min timeout). Configure timeout in Admin → QA Execution Settings.
