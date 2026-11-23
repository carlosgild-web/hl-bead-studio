# 0025: A SKU can be reserved while the design breaks rules; the card says so

**Status:** accepted (2026-11-23). From the hand QA of the site (2026-11-23, item 13).

## Context

With a 25 mm bead in the panel (GB-03 allows at most 20 mm), Reserve SKU opened a card and
reserved the SKU without a word about the broken rule. The QA asked to block it or to warn.

## Decision

Warn, do not block. A SKU and its product name are reserved for a product in development,
often before the design is final; what must never happen is files for a design that breaks
the manual, and Generate already refuses those (when the card opens and again at the click,
invariant 1). So the Reserve card, while it waits, shows the rules the panel's design
breaks right now ("The SKU is reserved anyway; the files can only be generated once the
design passes"). The warning comes from the panel's own check (the cached preview), not
from the model.

The Generate card lists the key parameters it will build (size, hole, color or finish,
letter, engraving), so the click confirms a design and not only a SKU.
