#!/usr/bin/env bash
# Start all CareLoop agents (each in its own process, each with its own mailbox).
# On first run, open each agent's Inspector URL (printed in its log) and click
# "Connect -> Mailbox" to register it on Agentverse.
#
# Usage:
#   ./scripts/run_all.sh          # start everything (logs in ./logs)
#   ./scripts/run_all.sh stop     # stop everything
set -euo pipefail
cd "$(dirname "$0")/.."

PY="./venv/bin/python"
LOGDIR="logs"
PIDFILE=".careloop.pids"

stop() {
  if [[ -f "$PIDFILE" ]]; then
    while read -r pid; do
      kill "$pid" 2>/dev/null || true
    done < "$PIDFILE"
    rm -f "$PIDFILE"
    echo "Stopped CareLoop agents."
  else
    echo "No PID file; nothing to stop."
  fi
}

if [[ "${1:-}" == "stop" ]]; then stop; exit 0; fi

mkdir -p "$LOGDIR"
: > "$PIDFILE"

start() { # name module
  local name="$1" module="$2"
  echo "Starting $name ..."
  $PY -m "$module" > "$LOGDIR/$name.log" 2>&1 &
  echo $! >> "$PIDFILE"
}

# Specialists first, then the orchestrator.
start triage          agents.triage
start provider-finder agents.provider_finder
start cost            agents.cost
start scheduler       agents.scheduler
sleep 2
start orchestrator    agents.orchestrator

echo
echo "All agents starting (logs in ./$LOGDIR)."
echo "Next: auto-register their mailboxes on Agentverse (no browser needed):"
echo "  ./venv/bin/python -m scripts.register_agents"
echo "Stop with: ./scripts/run_all.sh stop"
