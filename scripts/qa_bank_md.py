"""Write `docs/qa/qa_bank.md` from `docs/qa/qa_bank.json`: `python scripts/qa_bank_md.py`.

The JSON is the source of truth (decision 0022); the Markdown is the readable copy for
review. `backend/tests/test_qa_bank.py` checks that the committed copy is up to date.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
BANK = REPO / "docs" / "qa" / "qa_bank.json"
OUT = REPO / "docs" / "qa" / "qa_bank.md"
KINDS = ("design", "knowledge", "howto", "guardrail")


def render(bank: dict[str, Any]) -> str:
    entries = bank["entries"]
    edition = bank["manual_edition"].replace("Edition ", "edition ")
    counts = Counter(e["kind"] for e in entries)
    lines = [
        "# Bead Studio · Q&A bank (EN / ES)",
        "",
        f"Generated from `qa_bank.json`; edit the JSON, not this file. {len(entries)} entries, "
        f"manual {edition}.",
        "",
        "| Kind | Count |",
        "|---|---|",
        *(f"| {kind} | {counts[kind]} |" for kind in KINDS),
        "",
    ]
    for e in entries:
        rules = ", ".join(e["rules"]) or "—"
        en, es = e["en"], e["es"]
        lines += [
            f"## `{e['id']}` · {e['kind']} · {rules}",
            "",
            f"**EN · Q:** {en['question']}  ",
            f"**EN · A:** {en['answer']}",
            "",
            f"**ES · P:** {es['question']}  ",
            f"**ES · R:** {es['answer']}",
            "",
        ]
        variants = [*en["variants"], *es["variants"]]
        if variants:
            lines += [f"*Variants:* {' · '.join(variants)}", ""]
        if e["proposal"]:
            p = e["proposal"]
            lines += [
                f"*Demo proposal:* `{p['family']}` `{json.dumps(p['params'], ensure_ascii=False)}`",
                "",
            ]
    lines += [
        "## Fallback (no match)",
        "",
        f"**EN:** {bank['fallback']['en']}",
        "",
        f"**ES:** {bank['fallback']['es']}",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    bank = json.loads(BANK.read_text(encoding="utf-8"))
    OUT.write_bytes(render(bank).encode("utf-8"))
    print(f"wrote {OUT.relative_to(REPO)}")


if __name__ == "__main__":
    main()
