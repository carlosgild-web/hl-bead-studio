# Deliverables: files, drawing and render

## Design flow

1. Describe the product and choose its family and parameters.
2. Check the parameters against this manual. Bead Studio lists every violation with its rule
   id and the nearest valid value; a design with violations cannot be generated.
3. Reserve the SKU and SAP material (`GEN-04`). This needs the designer's confirmation.
4. Generate the design files for revision `A` (or the next revision, `GEN-02`). This also
   needs confirmation.
5. Queue the catalog renders, one per color or finish. This also needs confirmation.

## Files per design

All files of a revision are kept together, named after the SKU and the revision:

```text
<SKU>/<Rev>/
  <SKU>_<Rev>.step           3D model for the mold maker (exact solid)
  <SKU>_<Rev>.stl            mesh, for 3D-printed master models
  <SKU>_<Rev>.glb            mesh for the web viewer
  <SKU>_<Rev>_drawing.pdf    technical drawing with the H&L title block
  params.json                the validated parameters and the rule edition used
  render/<SKU>_<Rev>_<finish>.png   catalog renders
```

Files of a released revision are never overwritten; a change creates the next revision.

## Technical drawing

A4 landscape, first-angle projection, scale chosen to fit (typically 5:1 for beads and 2:1
for charms). It shows a front and a side view, the main dimensions with the general
tolerance of `GEN-01`, and the **H&L title block**:

| Field | Example |
|---|---|
| Company and logo | Hilda & Luna Beadworks |
| Product name | Honey Glow Faceted |
| SKU / revision | GB-1034 / A |
| SAP material | 50000134 |
| Family | Faceted (FAC) |
| Material and color or finish | Borosilicate, Honey (CDV-B215) |
| Mass | 1.0 g |
| Scale, units, projection | 5:1, mm, first angle |
| Date and designer | 2026-11-20, Product Design |

## Catalog render

1024 × 1024 px PNG on a light studio background, with the product's glass color or finish
(section 07). One render per color or finish offered.
