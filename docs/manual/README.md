# Product Design Manual

The (fictional) Hilda & Luna Beadworks Product Design Manual, in English (`en/`) and Spanish
(`es/`). Both languages have the same files and the same rule ids.

| File | Content | Rules |
|---|---|---|
| `01-overview.md` | Purpose, product types, materials, units | `GEN-01` |
| `02-families.md` | The seven parametric families and their parameters | — |
| `03-identifiers.md` | SKU, SAP material number, revisions | `GEN-02`, `GEN-04` |
| `04-rules-glass-beads.md` | Glass bead manufacturability | `GB-01`…`GB-07` |
| `05-rules-charms.md` | Charm manufacturability | `CH-01`…`CH-07` |
| `06-naming-and-collections.md` | Product names, collections, catalog text | `GEN-03` |
| `07-colors-and-finishes.md` | Approved glass colors and plating finishes | — |
| `08-deliverables.md` | Design flow, files, drawing title block, render | — |

Conventions:

- Each rule is a heading that starts with its id (`### GB-02 Glass wall around the hole`),
  followed by the rule, *Why* and a *Violation example* with the nearest valid value. Bead
  Studio's manual search (SQLite FTS5, Phase 5) returns these passages with their ids.
- Numbers in the manual must agree with the family schemas
  (`backend/app/standards/schemas/`) and the lists in `cad/templates/`;
  `backend/tests/test_content.py` checks the parts that can be checked automatically.
