# Bead Studio: the backend (FastAPI + CadQuery), the mock SAP and the built frontend in one
# image (decision 0018). compose.yaml runs the backend and the mock SAP as two services from
# it. No FreeCAD (decision 0009) and no Blender: renders run locally (start.cmd).

# --- the frontend --------------------------------------------------------------------------
FROM node:24.15.0-bookworm-slim AS frontend
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# --- the Python services ---------------------------------------------------------------------
FROM python:3.12.7-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
# OpenCascade (CadQuery) loads a few X and GL libraries even when nothing is drawn.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libxrender1 libxext6 libsm6 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
COPY sap-mock/requirements.txt sap-mock/requirements.txt
RUN pip install -r backend/requirements.txt -r sap-mock/requirements.txt

COPY backend/ backend/
COPY sap-mock/ sap-mock/
COPY cad/ cad/
COPY blender/ blender/
COPY docs/manual/ docs/manual/
COPY docs/gallery/ docs/gallery/
COPY docs/qa/ docs/qa/
COPY --from=frontend /src/frontend/dist frontend/dist

# Persistent data (designs, SQLite, traces) lives in a volume; the services run as a user.
RUN useradd --create-home --uid 10001 studio && mkdir -p /data && chown studio /data
USER studio
ENV DATA_DIR=/data \
    DESIGNS_ROOT=/data/designs \
    FRONTEND_DIST=/app/frontend/dist
VOLUME ["/data"]

WORKDIR /app/backend
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
