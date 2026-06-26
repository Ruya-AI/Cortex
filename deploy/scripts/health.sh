#!/bin/bash

echo "=== Cortex QA Platform — Health Check ==="
echo ""

BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"
FRONTEND_URL="${FRONTEND_URL:-http://localhost:80}"

# Backend
echo -n "Backend ($BACKEND_URL): "
BACKEND_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BACKEND_URL/api/admin/system-info" 2>/dev/null)
if [ "$BACKEND_STATUS" = "200" ]; then
  echo "HEALTHY"
  curl -s "$BACKEND_URL/api/admin/system-info" 2>/dev/null | python3 -c "
import sys,json
d=json.load(sys.stdin)
print(f'  Version: {d.get(\"engine_version\",\"?\")}, Features: {sum(d.get(\"features_enabled\",{}).values())}/4 enabled')
" 2>/dev/null
else
  echo "UNHEALTHY (HTTP $BACKEND_STATUS)"
fi

# Frontend
echo -n "Frontend ($FRONTEND_URL): "
FRONTEND_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$FRONTEND_URL" 2>/dev/null)
if [ "$FRONTEND_STATUS" = "200" ]; then
  echo "HEALTHY"
else
  echo "UNHEALTHY (HTTP $FRONTEND_STATUS)"
fi

# Database
echo -n "Database: "
if docker exec cortex-postgres pg_isready -U cortex > /dev/null 2>&1; then
  EXEC_COUNT=$(docker exec cortex-postgres psql -U cortex -t -c "SELECT count(*) FROM qa_executions;" 2>/dev/null | tr -d ' \n')
  echo "HEALTHY ($EXEC_COUNT executions)"
else
  echo "UNHEALTHY"
fi

# Engine tools
echo -n "Engine tools: "
TOOLS_OK=0
TOOLS_TOTAL=5
for tool in trivy gitleaks osv-scanner bandit ruff; do
  which $tool > /dev/null 2>&1 && TOOLS_OK=$((TOOLS_OK+1))
done
echo "$TOOLS_OK/$TOOLS_TOTAL available"

# Graphify (code graph)
echo -n "Graphify: "
python3 -c "from graphify.extract import extract; print('AVAILABLE')" 2>/dev/null || echo "NOT INSTALLED (optional)"

echo ""
echo "=== Done ==="
