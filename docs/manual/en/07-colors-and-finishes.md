# Colors and finishes

The approved lists below are the only values allowed by rules `GB-07` (glass colors) and
`CH-05` (charm finishes). Bead Studio reads them from `cad/templates/colors.json` and
`cad/templates/finishes.json`; the render presets for Blender come from the same files.

## Glass colors (borosilicate, Cristal Dorado Vidrios)

| Id | Color | Look | Rod code |
|---|---|---|---|
| `clear` | Clear | Transparent | CDV-B100 |
| `amber` | Amber | Transparent | CDV-B210 |
| `honey` | Honey | Transparent | CDV-B215 |
| `desert_sand` | Desert Sand | Translucent | CDV-B230 |
| `terracotta` | Terracotta | Opaque | CDV-B240 |
| `ruby` | Ruby | Transparent | CDV-B310 |
| `rose_opal` | Rose Opal | Translucent | CDV-B320 |
| `amethyst` | Amethyst | Transparent | CDV-B410 |
| `cobalt` | Cobalt | Transparent | CDV-B510 |
| `midnight_blue` | Midnight Blue | Transparent | CDV-B520 |
| `aqua` | Aqua | Transparent | CDV-B530 |
| `sea_green` | Sea Green | Transparent | CDV-B610 |
| `emerald` | Emerald | Transparent | CDV-B620 |
| `deep_forest` | Deep Forest | Transparent | CDV-B630 |
| `opal_white` | Opal White | Opaque | CDV-B710 |
| `jet` | Jet | Opaque | CDV-B720 |

Borosilicate glass has a refractive index of about 1.47; the renders use that value.

## Charm finishes (Fundición Peltre del Bajío)

| Id | Finish | Plating thickness | Notes |
|---|---|---|---|
| `gold_plate` | Gold plate | 1.0 µm | Bright, the brand's signature finish (CH-2004) |
| `rhodium` | Rhodium | 0.5 µm | Bright white, tarnish resistant |
| `antique_bronze` | Antique bronze | 1.0 µm | Darkened in the recesses, satin on the high points |

All finishes go over a nickel-free underlayer.
