# Manufacturability rules: glass beads

Glass beads are lampworked by Cristal Dorado Vidrios: molten borosilicate is wound around a
steel mandrel coated with bead release, shaped (and, for faceted beads, pressed in a facet
mold), then annealed in a kiln. These rules keep beads makeable and strong.

### GB-01 Hole diameter and mandrel sizes

The hole is **1.0, 1.5, 2.0 or 2.5 mm**: the four mandrel sizes our lampworkers stock. Any
other value is rounded to the nearest mandrel size.

*Why:* the hole is the mandrel; a size we do not stock cannot be made.

*Violation example:* a 0.8 mm hole. Nearest valid value: 1.0 mm.

### GB-02 Glass wall around the hole

The glass wall between the hole and the outside surface is at least **1.5 mm** at its
thinnest point. With `h` the hole diameter:

| Family | Thinnest wall |
|---|---|
| Round | (diameter − h) / 2 |
| Faceted | (diameter / 2) × cos(180° / facet count) − h / 2 (measured to the facet flat) |
| Lentil | (thickness − h) / 2 (the hole crosses the disc through the edge) |
| Rondelle | (diameter − h) / 2 |

*Why:* thinner walls crack during annealing or when the bead is strung tightly.

*Violation example:* a 4.0 mm round bead with a 1.5 mm hole has a 1.25 mm wall. Nearest
valid values: a 1.0 mm hole, or a 4.5 mm diameter.

### GB-03 Bead diameter

The diameter is **4.0–20.0 mm**. Faceted beads are at least **6.0 mm**.

*Why:* below 4 mm the bead cannot be shaped by hand on the mandrel; above 20 mm it cools
unevenly and cracks. The facet mold cannot press beads under 6 mm.

*Violation example:* a 5.0 mm faceted bead. Nearest valid value: 6.0 mm.

### GB-04 Lentil proportion

A lentil's thickness is **40–70% of its diameter**.

*Why:* thinner lentils warp and break at the edge; thicker ones are no longer lentils (use
`RND` or `RON`).

*Violation example:* a 14.0 mm lentil 5.0 mm thick (36%). Nearest valid value: 5.6 mm.

### GB-05 Facets

A faceted bead has **8–32 facets per row, an even number**, in **1–3 rows**. Each facet is
at least **1.5 mm** wide at the equator: π × diameter / facet count ≥ 1.5 mm.

*Why:* the facet mold has even divisions; narrower facets do not catch light and the edges
chip.

*Violation example:* a 6.0 mm bead with 16 facets (facets 1.18 mm wide). Nearest valid
value: 12 facets.

### GB-06 Rondelle proportion

A rondelle's height is **40–80% of its diameter**.

*Why:* flatter rondelles are fragile at the rim; taller ones are round beads.

*Violation example:* an 8.0 mm rondelle 7.0 mm high (88%). Nearest valid value: 6.4 mm.

### GB-07 Glass colors

The glass color is one of the **approved colors** in section 07 (file
`cad/templates/colors.json`). Only borosilicate (COE 33) rods are used; soft glass is never
mixed in.

*Why:* glasses with a different expansion coefficient crack when combined, and each
approved color has a supplier rod code.

*Violation example:* "neon pink" is not an approved color; the closest approved color is
Rose Opal.
