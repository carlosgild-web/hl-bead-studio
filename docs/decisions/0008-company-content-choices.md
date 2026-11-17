# 0008: Company content choices (Phase 1)

**Status:** accepted (2026-11-17, reviewed with Carlos before writing)

## Context

Phase 1 writes the Product Design Manual, the family schemas, the color and finish lists, the
SAP seed and the logo. `PLAN.md` gives the rules as examples ("the manual holds the full list
with ids") and leaves the Initial charm fonts as an open question. Several gaps had to be
filled, and a few choices differ from the plan's wording.

## Decisions

1. **Logo: reuse the luna mark** instead of drawing a new H&L monogram (same choice as
   hl-create-design, decision 0006 there). `cad/templates/hl_logo.svg` is luna's mark
   without the wordmark; `frontend/public/favicon.svg` is luna's `hl-mark.svg`. It is
   original artwork of the same fictional company, so invariant "the logo is original"
   holds.
2. **Initial charm fonts** (open question 1 in `PLAN.md`): Pacifico (script, the style of
   the existing CH-2033), Cinzel Bold and Montserrat ExtraBold, all SIL Open Font License.
   Fonts with hairline strokes were left out because of the 0.6 mm feature limit (`CH-03`).
   Each font has a provisional minimum letter height in `CH-07`; the font files and the
   stroke measurements come in Phase 3.
3. **Rules added** to complete the families: `GB-05` (facets: even count 8–32, rows 1–3,
   facet width ≥ 1.5 mm), `GB-06` (rondelle height 40–80% of the diameter), `CH-06` (disc
   engraving: text, icon, depth) and `CH-07` (initial letter and fonts). `GB-04` gains an
   upper limit (70%). General rules `GEN-01` (units and 0.1 mm resolution), `GEN-02`
   (revisions), `GEN-03` (names) and `GEN-04` (SKU and SAP material) give ids to standards
   the plan already described.
4. **`CH-05` split.** The plan's `CH-05` covered both charm finishes and glass colors. Glass
   colors are a bead rule, so they are `GB-07`; `CH-05` keeps the three finishes.
5. **Family `CUS` (custom)** in the SAP seed for older catalog products sculpted by hand
   (Opal Mist Swirl, Tiny Honeybee, Birth Flower — Lotus, Desert Cactus). They exist in SAP
   but cannot be designed in Bead Studio; new products always use one of the seven families.
6. **Names before the naming convention keep their names** (`GEN-03`), so luna's catalog
   (for example *Terracotta Sunrise*) stays as it is.
7. **Schema conventions.** One JSON Schema (draft 2020-12) per family in
   `backend/app/standards/schemas/`, with `x-unit`, `x-step`, `x-rule` (rule ids) and
   `x-label` (ES and EN) on every parameter and `x-family` metadata. The schemas check
   structure and single-value ranges only; rules that relate values (wall thickness,
   proportions, facet width) belong to `standards/validators.py` (Phase 3). `multipleOf` is
   not used for the 0.1 mm step because floating-point division makes it reject valid
   values; `GEN-01` rounding is the validators' job.
8. **Charm supplier** is luna's "Fundición Peltre del Bajío", which casts zinc alloy
   (Zamak 3, 6.6 g/cm³ as in the plan) for the charms.
9. **SAP seed numbering.** SKUs of each type and material numbers increase with the
   creation date. The highest are GB-1033, CH-2033 and 50000133, so the first reservations
   are GB-1034, CH-2034 and 50000134.

## Consequences

- New dependency: `jsonschema` in the backend (tests now, parameter structure in Phase 3).
- Tests keep the content consistent: every rule id has one heading per language, schema
  enums match the color and finish lists, and every rule cited by a schema exists.
- The manual is still a draft until Carlos reviews it (Phase 1 "Done when").
