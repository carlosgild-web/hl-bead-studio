# 0024: SAP's revision follows the files, revisions never skip a letter, and `demo-reset`

**Status:** accepted (2026-11-23). Additions from the hand QA of the site (2026-11-23).

## Context

After a day of hand testing the catalog listed "Test Flow Round", "Prueba Tres Lentil" and
other test SKUs. Revisions disagreed: CH-2040 had files only for revision `AA` while SAP said
`A`, and GB-1037 had files for A, B and C while SAP still said `A`. Nothing set SAP's current
revision after a generation, and the Generate form took any GEN-02 letter.

## Decisions

1. **The mock SAP accepts `MERGE MaterialSet('...')`** (OData v2; `PATCH` too) with
   `CurrentRevision`, behind the same basic auth and CSRF token. 204 No Content. It refuses
   letters outside GEN-02. `SapClient.set_revision` is the only caller (invariant 5).
2. **A confirmed generation sets SAP's current revision** to the revision it wrote, audited as
   `sap.revision_set`. The files are written first; if SAP fails then, the result says
   `sap_revision_updated: false` and the files stay (they are never deleted or overwritten).
3. **Only the next revision can be generated** (`identifiers.expected_revision`): after the
   newest revision with files, or SAP's current revision when there are none yet (`A` for a
   new SKU). The card refuses any other letter when it opens and again at the click, so a
   first revision `AA` or a gap is impossible. The catalog returns `next_revision`, and the
   existing-SKU form fills it in.
4. **`python -m app.cli demo-reset`** deletes the app database (conversations, cards, render
   jobs and the audit log, which describes the deleted designs), everything under
   `DESIGNS_ROOT`, and the mock SAP database, which the mock re-creates from its seed on the
   next start. It lists what it deletes and asks (`--yes` skips the question), refuses a
   `DESIGNS_ROOT` that is not a designs folder, and stops if a database is in use (servers
   still running). A command instead of `make demo-reset`: there is no Makefile on Windows.
5. The gallery's showcase bead `GB-1034` "Honey Glow Faceted" is not in the SAP seed (it was
   reserved during development); after a reset the gallery shows it as a showcase design,
   not as a catalog product.
