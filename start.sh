#!/usr/bin/env bash
# Bead Studio launcher for local development on Linux and macOS.
#   ./start.sh                checks Groq, then Ollama, then the demo model, and asks which one
#                             (LLM_PROVIDER=fake, anthropic or dahl in .env skips the check)
#   ./start.sh groq           or: dahl, anthropic, ollama, fake: that one, without the check
# Runs the mock SAP (:8100), the backend (:8000) and the UI (:5173), opens the browser,
# and stops all three on Ctrl+C. Setup: see "Quick start" in README.md.
set -euo pipefail
cd "$(dirname "$0")"

if [[ $# -gt 0 ]]; then
  case "$1" in
    fake | ollama | anthropic | dahl | groq) export LLM_PROVIDER="$1" ;;
    *) echo "Unknown LLM provider '$1'. Use fake, ollama, anthropic, dahl or groq." >&2; exit 1 ;;
  esac
fi

missing=0
for venv in backend sap-mock; do
  if [[ ! -x "$venv/.venv/bin/python" ]]; then
    echo "Missing $venv/.venv: cd $venv && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements-dev.txt" >&2
    missing=1
  fi
done
if [[ ! -d frontend/node_modules ]]; then
  echo "Missing frontend/node_modules: cd frontend && npm ci" >&2
  missing=1
fi
[[ $missing -eq 0 ]] || exit 1

if [[ "${LLM_PROVIDER:-}" == anthropic && -z "${ANTHROPIC_API_KEY:-}" && ! -f .env ]]; then
  echo "LLM_PROVIDER=anthropic needs ANTHROPIC_API_KEY in the environment or in .env." >&2
  exit 1
fi
if [[ "${LLM_PROVIDER:-}" == dahl && -z "${DAHL_API_KEY:-}" && ! -f .env ]]; then
  echo "LLM_PROVIDER=dahl needs DAHL_API_KEY in the environment or in .env." >&2
  exit 1
fi
LLM_PROVIDER_LC="$(printf '%s' "${LLM_PROVIDER:-}" | tr '[:upper:]' '[:lower:]')"
if [[ "$LLM_PROVIDER_LC" == groq && -z "${GROQ_API_KEY:-}" && ! -f .env ]]; then
  echo "LLM_PROVIDER=groq needs GROQ_API_KEY in the environment or in .env." >&2
  exit 1
fi

# No provider named: check them and let the designer choose (decision 0019). The questions
# go to the terminal (stderr); only the chosen name comes back on stdout.
if [[ $# -eq 0 ]]; then
  if ! LLM_PROVIDER="$(cd backend && .venv/bin/python -m app.cli llm-check)"; then
    echo "The model check stopped; nothing was started." >&2
    exit 1
  fi
  export LLM_PROVIDER
fi

if curl -s -o /dev/null http://localhost:8000/api/health; then
  echo "Something already answers on port 8000. Stop the running backend first." >&2
  exit 1
fi

pids=()
stop() {
  echo
  echo "Stopping Bead Studio..."
  kill "${pids[@]}" 2>/dev/null || true
  wait 2>/dev/null || true
}
trap stop EXIT INT TERM

echo "Starting Bead Studio (LLM: ${LLM_PROVIDER:-from .env, default fake})"
(cd sap-mock && exec .venv/bin/python -m uvicorn app.main:app --port 8100) &
pids+=($!)
(cd backend && exec .venv/bin/python -m uvicorn app.main:app --port 8000) &
pids+=($!)
(cd frontend && exec npm run dev -- --port 5173 --strictPort) &
pids+=($!)

for _ in $(seq 1 90); do
  if curl -sf -o /dev/null http://localhost:8000/api/health && curl -sf -o /dev/null http://localhost:5173; then
    echo "Bead Studio is running: http://localhost:5173 (Ctrl+C to stop)"
    if command -v xdg-open >/dev/null; then xdg-open http://localhost:5173 >/dev/null 2>&1 || true
    elif command -v open >/dev/null; then open http://localhost:5173 || true
    fi
    wait
    exit 0
  fi
  sleep 1
done
echo "The services did not answer within 90 s; see the output above." >&2
exit 1
