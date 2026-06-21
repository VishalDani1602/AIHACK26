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
redis_up() { (exec 3<>/dev/tcp/127.0.0.1/6379) >/dev/null 2>&1; }
if redis_up; then
  echo "  redis already up on :6379"
elif command -v redis-server >/dev/null 2>&1; then
  redis-server --daemonize yes --save '' --appendonly no >/dev/null 2>&1
  sleep 1
  redis_up && echo "  started local redis-server" || echo "  redis-server failed"
elif docker info >/dev/null 2>&1; then
  docker start careloop-redis >/dev/null 2>&1 || \
    docker run -d --name careloop-redis -p 6379:6379 redis:7-alpine >/dev/null
  sleep 2
  redis_up && echo "  started redis (docker)" || echo "  redis NOT up"
else
  echo "  redis unavailable — CareLoop runs without it (graceful)"
fi

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
