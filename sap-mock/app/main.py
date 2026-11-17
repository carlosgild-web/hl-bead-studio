"""Mock SAP entry point: `uvicorn app.main:app --reload --port 8100`.

Phase 2 adds the `ZHL_MM_MATERIAL_SRV` OData service, basic auth, CSRF and chaos switches.
"""

from fastapi import FastAPI

from app import __version__

app = FastAPI(title="Mock SAP (ZHL_MM_MATERIAL_SRV)", version=__version__)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe, outside the OData path and without auth."""
    return {"status": "ok", "service": "sap-mock", "version": __version__}
