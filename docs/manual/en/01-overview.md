# Product Design Manual: overview

**Hilda & Luna Beadworks · Product Design · Edition 1 (2026-11)**

This manual is the reference for designing new glass beads and charms at Hilda & Luna
Beadworks. Every rule has an id (for example `GB-02`). Bead Studio checks designs against
these rules automatically, and the assistant cites the ids when it explains a problem.
When the manual and a tool disagree, the manual wins and the tool is fixed.

## Who uses it

- **Product designers**, who create new SKUs.
- **Cristal Dorado Vidrios S.A. de C.V.** (Guadalajara), our borosilicate glass supplier and
  lampwork partner.
- **Fundición Peltre del Bajío** (León), who makes the molds and casts and plates the charms.

## Product types

| Type | Material | How it is made | SKU prefix |
|---|---|---|---|
| Glass bead | Borosilicate glass (COE 33), density 2.23 g/cm³ | Lampwork wound on a steel mandrel, kiln annealed | `GB-1NNN` |
| Charm | Zinc alloy (Zamak 3), density 6.6 g/cm³ | Spin cast in a rubber mold, tumbled, plated | `CH-2NNN` |

The masses that Bead Studio reports are the solid volume times these densities, before
plating (plating adds less than 1%).

## How the manual is organized

| Section | Content |
|---|---|
| 01 Overview | This page, units (`GEN-01`) |
| 02 Families | The seven product families and their parameters |
| 03 Identifiers | SKU, SAP material number and design revisions (`GEN-02`, `GEN-04`) |
| 04 Glass bead rules | `GB-01` to `GB-07` |
| 05 Charm rules | `CH-01` to `CH-08` |
| 06 Naming and collections | Product names (`GEN-03`) and the three collections |
| 07 Colors and finishes | The approved glass colors and plating finishes |
| 08 Deliverables | Files per design, the technical drawing and the catalog render |

## General rules

### GEN-01 Units and resolution

All dimensions are in **millimetres**. Parameters are entered with a resolution of
**0.1 mm**; a value like 10.25 mm is rounded to 10.3 mm. The general tolerance on drawings is
**±0.1 mm** unless the drawing states another one.

*Why:* the mold maker and the lampworkers measure with calipers to 0.1 mm; finer values
give a false sense of precision.

*Example:* "a 3/8 inch bead" is entered as 9.5 mm.
