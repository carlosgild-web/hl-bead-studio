# Product families

Every new product belongs to one of seven parametric families. A family fixes the shape;
the designer chooses the parameters within the rules. The machine-readable definitions are
the JSON Schemas in `backend/app/standards/schemas/<CODE>.schema.json`.

Some older catalog products (for example *Tiny Honeybee* or *Birth Flower — Lotus*) were
sculpted by hand and have no family; SAP lists them with family `CUS` (custom). New
products are always designed in a family.

## Glass beads

All glass beads have a through hole (`hole_mm`, rules `GB-01` and `GB-02`) and a glass color
(`color`, rule `GB-07`).

| Family | Code | Shape | Parameters (mm unless stated) | Defaults |
|---|---|---|---|---|
| Round | `RND` | Sphere with a through hole | `diameter_mm` 4.0–20.0 | 8.0, hole 1.5 |
| Faceted | `FAC` | Round bead cut with flat facets in rows around the hole axis | `diameter_mm` 6.0–20.0 (across the facet corners), `facet_count` 8–32 (even), `facet_rows` 1–3 | 10.0, 16 facets, 2 rows, hole 1.5 |
| Lentil | `LEN` | Lens-shaped disc; the hole crosses the diameter through the edge | `diameter_mm` 4.0–20.0, `thickness_mm` 2.0–14.0 (at the center) | 14.0 × 7.0, hole 1.5 |
| Rondelle | `RON` | Flattened round bead; the hole runs along the height | `diameter_mm` 4.0–20.0, `height_mm` 2.0–16.0 | 8.0 × 5.0, hole 1.5 |

## Charms

All charms have a thickness (`thickness_mm`, rule `CH-01`), a hanging loop at the top
center (`loop_inner_mm` and `loop_wall_mm`, rule `CH-02`) and a plating finish (`finish`,
rule `CH-05`). Heights are measured on the body, without the loop (rule `CH-04`).

| Family | Code | Shape | Parameters (mm unless stated) | Defaults |
|---|---|---|---|---|
| Crescent | `CRS` | Crescent moon, optionally with a five-point star joined inside its curve | `height_mm` 8.0–30.0, `crescent_width_mm` 2.0–12.0 (widest part of the band), `has_star` yes/no, `star_diameter_mm` 3.0–8.0 | 16.0, width 5.0, star 5.0 |
| Initial | `INI` | One capital letter in an approved font | `letter` A–Z, `font` (see `CH-07`), `height_mm` 8.0–30.0 | "H", Pacifico, 14.0 |
| Disc | `DSC` | Flat disc with engraved text or an icon | `diameter_mm` 8.0–30.0, `engraving` none/text/icon, `engraving_text` (see `CH-06`), `icon`, `engraving_depth_mm` 0.2–0.4 | 14.0, text "LUNA", depth 0.3 |

Charm defaults for every family: thickness 1.5, loop inner diameter 2.0, loop wall 1.0,
finish gold plate.

## Ranges and rules

The ranges in the tables are the limits of the input fields. A value inside its range can
still break a rule that relates two values, such as the glass wall around the hole
(`GB-02`) or the lentil proportion (`GB-04`). Bead Studio checks both and reports every
violation with its rule id and the nearest valid value.
