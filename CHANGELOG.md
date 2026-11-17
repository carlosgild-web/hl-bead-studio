# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Phase 0 skeleton: backend and sap-mock FastAPI packages with health endpoints, Vite React
  TypeScript frontend (Tailwind, shadcn/ui, react-three-fiber), CI, decision records 0001–0007.
- Phase 1 company content: Product Design Manual in English and Spanish (rules GEN-01…04,
  GB-01…07, CH-01…07), JSON Schemas for the seven families, approved glass colors, finishes
  and materials, SAP seed (luna's 10 products plus 15 fictional ones), the H&L logo for the
  title block, content tests and decision 0008.
- Phase 2 mock SAP service `ZHL_MM_MATERIAL_SRV`: OData v2 material lookup, `$filter`,
  `$top`/`$skip`, `$metadata`, SKU reservation (next number per type, atomic, never
  reissued), Basic auth, CSRF handshake, SAP-style errors, chaos switches and curl examples.
- Phase 3 geometry, drawing and validation: `standards/validators.py` checks every manual rule
  and returns each violation with its rule id and the nearest valid values; one CadQuery
  builder per family with STEP, STL and GLB export, volume and mass; the CH-03 smallest-feature
  check on charm outlines (shapely); technical drawings with OpenCascade hidden-line views and
  the H&L title block, rendered to PDF in Python (decision 0009, after a failed TechDraw
  spike); confined design folders, an audit log and the `validate`, `generate` and
  `measure-fonts` CLI commands; the OFL fonts in `cad/fonts/`; showcase drawings in
  `docs/showcase/`; property-based geometry tests (Hypothesis).

### Changed

- Manual and schemas after measuring the fonts (decision 0010): CH-07 minimum heights
  (Pacifico 10.5 mm, Y 18.5 mm; Cinzel Bold 16.5 mm, no K), CH-06 engraved letters at least
  3.0 mm and letter-spaced, disc default diameter 20.0 mm, new rule CH-08 (crescent
  proportions).

### Fixed

- Settings failed to read `ANTHROPIC_API_KEY` from the environment in any process that had
  imported CadQuery (its multimethod dispatch makes `typing.Union` look like a sequence to
  pydantic-settings).
