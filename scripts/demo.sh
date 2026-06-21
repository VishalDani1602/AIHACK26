#!/usr/bin/env bash
# One command to run + showcase everything: Redis, the 7-agent mesh, the voice
# backend, then a full guided demo (golden booking, clinical evidence, emergency,
# new-chat reset, Redis cache/stats/audit, Agentverse profiles).
#
# Usage:  ./scripts/demo.sh
set -uo pipefail
cd "$(dirname "$0")/.."
PY=./venv/bin/python

echo "▶ 1/4  Redis"
if ! docker ps --format '{{.Names}}' | grep -q '^careloop-redis$'; then
  docker start careloop-redis >/dev/null 2>&1 || \
    docker run -d --name careloop-redis -p 6379:6379 redis:7-alpine >/dev/null
fi
docker exec careloop-redis redis-cli ping >/dev/null 2>&1 && echo "  redis up" || echo "  redis NOT up"

echo "▶ 2/4  Agent mesh"
if ! lsof -nP -iTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then
  ./scripts/run_all.sh >/dev/null
  echo -n "  waiting for boot"
  until grep -q "Starting server on" logs/orchestrator.log 2>/dev/null; do echo -n "."; sleep 1; done
  echo; sleep 3
  $PY -m scripts.register_agents >/dev/null 2>&1 && echo "  agents registered on Agentverse" || echo "  registration had issues (see logs)"
else
  echo "  already running"
fi

echo "▶ 3/4  Voice backend"
if ! curl -s http://127.0.0.1:8080/api/health >/dev/null 2>&1; then
  $PY -m uvicorn voice.backend:app --host 127.0.0.1 --port 8080 --log-level warning > logs/voice.log 2>&1 &
  until curl -s http://127.0.0.1:8080/api/health >/dev/null 2>&1; do sleep 1; done
fi
echo "  voice app at http://127.0.0.1:8080"

echo "▶ 4/4  Showcase"
$PY -m scripts.showcase
