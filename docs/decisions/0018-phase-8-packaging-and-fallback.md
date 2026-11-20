# 0018: Phase 8 packaging, the public provider and its fallback

**Status:** accepted (2026-11-20). Deviations from `PLAN.md` Phase 8.

## Context

`PLAN.md` Phase 8 asks for a Docker image (Python, CadQuery and the built frontend; no
FreeCAD, no Blender), a `compose.yaml` with the app and the mock SAP, optional Ollama and
Blender profiles, and a Hugging Face Space on Anthropic with a fake fallback.

Carlos decided on 2026-11-20:
- the public provider is Groq (free tier, decision 0017);
- without tokens it uses Ollama when it is installed, else the fake client;
- no Hugging Face Space for now.

## Decisions

1. **The fallback chain.** `LLM_FALLBACK` (default `ollama,fake`) applies to the cloud
   providers (`groq`, `dahl`, `anthropic`), in `app/llm/fallback.py`.
   - **Without the key**, the factory uses the first available fallback.
   - **When a turn hits the daily limit**, it moves to the first available fallback for
     the rest of the turn, and the answer starts with a note that says why.
   - **Ollama counts as available** only when it answers at `OLLAMA_BASE_URL` with
     `OLLAMA_MODEL` pulled (a 1.5 s probe). The fake client is demo mode.
   - **Other errors are not hidden**, for example a rejected key.
   - **`agent-eval` turns the fallback off**, so a daily limit stops the run instead of
     scoring another model.
2. **One process serves the frontend.** When `frontend/dist` exists (`FRONTEND_DIST`), the
   backend serves its files at `/`, with `index.html` for any other path that is not
   `/api`. Development is unchanged: Vite serves the frontend and proxies `/api`.
3. **One image, two services.** The `Dockerfile` builds the frontend in a Node stage, then
   installs the backend and the mock SAP in a Python 3.12 slim image as a non-root user,
   with the data in a `/data` volume.
   - `compose.yaml` runs `sap-mock` and `app` from that image, with health checks.
   - The `ollama` profile adds an Ollama container.
   - `LLM_PROVIDER` defaults to `groq`. Keys come from `.env` when it exists.
4. **No Blender profile.** A Blender image would add about 1 GB and a second render setup
   to maintain. Renders run locally with `start.cmd` (Blender installed), as the Renders
   tab already says. The gallery shows the pre-generated renders.
5. **No Hugging Face Space** for now. The image serves everything on one port, so a Space
   (or any container host) can run it later. It would need the mock SAP inside the same
   container, or `SAP_BASE_URL` pointing at it.

## Consequences

- `docker compose up` needs only Docker. A clean machine gets the studio on
  http://localhost:8000, in demo mode without a key.
- Tests cover the fallback (`tests/test_llm_fallback.py`) and the static serving
  (`tests/test_smoke.py`).
