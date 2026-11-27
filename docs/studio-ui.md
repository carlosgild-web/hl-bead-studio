# The studio UI

`npm run dev` in `frontend/` opens the studio on http://localhost:5173 (decision 0013); the
launcher and Docker serve the built UI on http://localhost:8000.

- **Chat** (left): the assistant's answers, the tools it used (collapsed), and the
  confirmation cards. Only **Confirm** on a card reserves a SKU, writes files or queues a
  render.
- **Parameters** (center): the family's fields with units and ranges. Values the assistant
  proposed stay amber until you edit them. Every edit is checked by the backend's
  validators; a violation shows its rule id and buttons with the nearest valid values.
- **Workflow**: a stepper at the bottom of the panel (reserve a SKU, generate the files,
  render) opens the same confirmation cards as the assistant, with the same checks, so the
  flow also works without a language model (decision 0014). Each step shows whether it is
  done, in progress or blocked and why, derived from what the studio has. The product name
  is checked against GEN-03 and the catalog while you type, with a suggested fix. The chat's
  **Next step** chip opens the next card the same way. A SKU can be reserved while the design
  still breaks a rule; the card says so (decision 0025).
- **Out-of-date files**: when the panel no longer matches the generated revision, the
  Drawing tab and the workflow list what changed (old → new) and offer **Generate Rev B**
  (existing revisions are never overwritten) or **Revert** to the saved parameters.
- **3D model** (right): the GLB built from the valid parameters, orbit controls, the glass
  color or plating finish, and the size, volume and mass.
- **Drawing** and **Renders** tabs: the PDF with the title block and the STEP, STL and GLB
  downloads; the render job followed live, and the pre-generated gallery.
- **Catalog**: the SAP materials, the SKUs reserved in Bead Studio and their drawings.
- ES/EN switch and a "How this demo works" guide.

## Routes the UI uses

`POST /api/actions` opens a card from the panel, and only the card's Confirm acts. The UI
also reads these routes, none of which has a side effect: `GET /api/families[/{code}]`,
`POST /api/validate`, `POST /api/preview`, `GET /api/catalog`,
`GET /api/designs/{sku}/{rev}[/files/{kind}]` and `GET /api/gallery`.

Renders: `GET /api/renders/{id}`, `/api/renders/{id}/events` (server-sent events) and
`/api/renders/{id}/image` follow a job. Renders are queued only by the CLI and by the
designer's confirmation.
