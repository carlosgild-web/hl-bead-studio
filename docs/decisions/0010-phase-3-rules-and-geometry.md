# 0010: Phase 3 rule measurements and geometry choices

**Status:** accepted (2026-11-17). Deviations from the Phase 1 manual and schemas.

## Context

Phase 3 implemented every rule in `standards/validators.py` and a CadQuery builder per
family. Measuring the real fonts and building the shapes showed that some Phase 1 numbers
were wrong and that one family needed a rule it did not have.

## Decisions

1. **CH-03 is checked on the actual outline.** The charm's outline (or a disc's engraving)
   is sampled into a polygon and checked with a morphological opening and closing at
   0.3 mm (half the 0.6 mm limit), using **shapely**: a split, a lost stroke, a closed or
   new counter, or an area change over 3% fails. OpenCascade's own 2D offset failed on most
   font outlines ("Null shape"), so shapely is a new dependency, used only for analysis; the
   models stay exact.
2. **Fonts are the upstream static builds** (Montserrat ExtraBold from JulietaUla/Montserrat,
   Cinzel Bold from NDISCOVER/Cinzel, Pacifico from google/fonts), in `cad/fonts/` with their
   OFL licenses. The google/fonts variable fonts, instanced with fontTools, kept overlapping
   contours that OpenCascade turns into overlapping solids.
3. **CH-07 heights are measured** (`python -m app.cli measure-fonts`, 0.5 mm steps, the
   smallest height from which a letter passes at every larger height): Pacifico 10.5 mm
   (was 10.0) with Y at 18.5 mm, Cinzel Bold 16.5 mm (was 12.0), Montserrat ExtraBold
   8.0 mm (passes from 4.5 mm; CH-04 sets the floor). Cinzel Bold's **K is not available**:
   the font draws it in two separate pieces.
4. **CH-06 engraved text:** the minimum letter height is 3.0 mm (was 2.5 mm) and the text
   must also pass CH-03 (most characters need 2.5–3.9 mm; M, W, X about 4.5 mm; the digit 4
   6.3 mm). Engraved text is **letter-spaced** (a gap of 0.2 × the letter height): the font's
   own spacing leaves gaps under 0.6 mm. The letter height is the largest that fits 80% of
   the diameter, up to 35% of it.
5. **Disc default diameter 20.0 mm** (was 14.0): "LUNA" on a 14 mm disc would have 2.5 mm
   letters; it needs at least 19.5 mm. Family defaults must be valid designs.
6. **New rule CH-08 Crescent proportions:** band width 20–45% of the height, star at most 50%
   of the height. Without it, schema-valid values (for example an 8 mm crescent with a
   12 mm band) have no crescent shape. The star's left point goes 1.0 mm into the band.
7. **Initial loop placement:** the loop goes above the highest stroke nearest the letter's
   center line, joined with a short connector (an H has no stroke at the top center).
8. **Faceted bead shape:** a convex polyhedron with corners on the bead diameter at the
   equator (so the GB-02 formula is exact): one row is a faceted barrel, two rows a bicone
   (30° facets), three rows a barrel with 45° bevels; flat ends keep a glass ring around the
   hole. It is built face by face (convex clipping), because 48–96 boolean cuts took
   minutes.
9. **Lentil** is a lens with a rounded rim (rim radius 25% of the thickness); **rondelle** a
   cylinder with filleted rims and flat ends. The GLB is in metres with Y up (glTF
   conventions); STEP and STL are in millimetres.
10. **Relational rules skip values that already broke a single-value rule** (zero facets, a
    zero diameter, an unknown font), so the result lists each problem once and never
    crashes.

## Consequences

- The manual (EN and ES) quotes the measured values; `tests/test_validators.py` checks that
  the CH-07 table and CH-08 numbers in both languages match `standards/rules.py`.
- `tests/test_profile.py` checks every letter at its minimum and that the minimums are tight.
- Charm validation builds the model to check CH-03 (about 0.3–0.6 s per call).
