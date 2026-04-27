#!/usr/bin/env bash
# Quick shell-level CPU chaos - runs stress on the host/container.
# Usage: ./chaos_cpu.sh [duration_seconds]
set -euo pipefail

DURATION=${1:-60}
APP_URL="${APP_URL:-http://localhost:5000}"

echo "=================================================="
echo "  TechStream Chaos: CPU Spike via app API"
echo "  Duration: ${DURATION}s"
echo "=================================================="

# Trigger CPU spike through the app's chaos endpoint
curl -s -X POST "${APP_URL}/chaos/cpu/start" \
  -H "Content-Type: application/json" | python3 -m json.tool

echo ""
echo "CPU spike active. Monitoring for ${DURATION} seconds..."

for i in $(seq "${DURATION}" -10 1); do
    echo "  [$(date +%H:%M:%S)] ${i}s remaining - CPU: $(curl -s "${APP_URL}/health" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"{d.get('cpu','?')}%\")" 2>/dev/null || echo '?')"
    sleep 10
done

echo ""
echo "Stopping CPU spike..."
curl -s -X POST "${APP_URL}/chaos/cpu/stop" \
  -H "Content-Type: application/json" | python3 -m json.tool

echo "Done."
