#!/usr/bin/env bash
# Bead Studio launcher for local development on Linux and macOS.
#   ./start.sh                checks Dahl, Groq, Ollama, then the demo model, and asks which one
#                             (LLM_PROVIDER=fake or anthropic in .env skips the check)
#   ./start.sh groq           or: dahl, anthropic, ollama, fake: that one, without the check
#   ./start.sh video [groq]   the same on fresh seed data in data-video/ (re-seeded at every
#                             start, faster renders): for the video takes; data/ is not touched
# Runs the mock SAP (:8100), the backend (:8000) and the UI (:5173), opens the browser,
# and stops all three on Ctrl+C. Setup: see "Quick start" in README.md.
set -euo pipefail
cd "$(dirname "$0")"

# Video mode (decision 0026): environment variables win over .env, so both services and the
# designs move to data-video/. The reset below empties it at every start.
video=0
if [[ "${1:-}" == video ]]; then
  video=1
  shift
  export DATA_DIR="$PWD/data-video" DESIGNS_ROOT="$PWD/data-video/designs"
  export RENDER_SAMPLES="${RENDER_SAMPLES:-16}"
fi

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

# Something left from an earlier start on 8000, 8100 or 5173: show it and offer to stop it
# (decision 0020).
if ! (cd backend && .venv/bin/python -m app.cli free-ports); then
  echo "Nothing was started." >&2
  exit 1
fi

# Video mode: back to the seed catalog in data-video/ (the same code as demo-reset, decision 0024).
# The ports are free now, so no SQLite file is open.
if [[ $video -eq 1 ]]; then
  if ! (cd backend && .venv/bin/python -m app.cli demo-reset --yes >/dev/null); then
    echo "The video data in data-video/ could not be reset; nothing was started." >&2
    exit 1
  fi
  echo "Video mode: fresh seed data in data-video/ (your data/ folder is not touched), $RENDER_SAMPLES render samples."
fi

# No provider named: check them and let the designer choose (decisions 0019 and 0021). The questions
# go to the terminal (stderr); only the chosen name comes back on stdout.
if [[ $# -eq 0 ]]; then
  if ! LLM_PROVIDER="$(cd backend && .venv/bin/python -m app.cli llm-check)"; then
    echo "The model check stopped; nothing was started." >&2
    exit 1
  fi
  export LLM_PROVIDER
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
