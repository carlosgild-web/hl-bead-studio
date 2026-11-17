# 0001: CadQuery for the 3D geometry

**Status:** accepted (2026-11-17)

## Context

Every product family (round, faceted, lentil and rondelle beads; crescent, initial and disc
charms) is a parametric shape. The backend has to build it from validated numbers, headless,
in tests and in a Docker image, and export STEP (for the mold maker), STL and a GLB for the
web viewer. It also has to report volume and mass so the assistant can quote numbers that come
from a tool (invariant 3).

Options considered:

| Option | For | Against |
|---|---|---|
| **CadQuery** (OpenCascade via OCP) | Real B-rep solids, exact STEP, pip install, plain Python, good volume and mass | Large wheel (~50 MB), OCP wheels must exist for the Python version |
| build123d | Same kernel, more modern API | Smaller community, fewer examples for the families we need |
| FreeCAD scripting for geometry | Same tool as the drawings | Needs a FreeCAD install and `freecadcmd` for every preview, slow to start |
| OpenSCAD / trimesh only | Simple | Mesh-only (no exact STEP), weak for fillets and text |

## Decision

CadQuery, one builder function per family under `backend/app/geometry/`. STEP and STL come
from CadQuery's exporters; the GLB is built from the tessellated mesh with trimesh. Volume
comes from the B-rep solid; mass uses the material density (borosilicate 2.23 g/cm³, zinc
alloy 6.6 g/cm³). Units are millimetres.

## Consequences

- `preview_geometry` runs in-process with no external tool, so it is fast and testable in CI.
- FreeCAD is only needed for the drawings (decision 0002), and only behind a marker in tests.
- The OCP wheel ties us to Python versions it is built for (decision 0007).
