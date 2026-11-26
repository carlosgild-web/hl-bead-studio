"""Read-only views of what the SSE stream and the trace don't carry (decision 0027).

Runs with the backend's venv and imports the backend's own functions, so what the video
shows is what the code computes, not a copy:

    backend/.venv/Scripts/python video/introspect.py fts "facets per row 10 mm bead"

Prints one JSON object. Writes nothing, opens no network connection.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.standards.manual_search import ManualIndex, fts_query

# The column weights of ManualIndex.search: source, lang (not indexed), heading, text.
WEIGHTS = (0.0, 0.0, 3.0, 1.0)


def fts(query: str, lang: str, limit: int) -> dict:
    """The words FTS5 gets, the rule ids that go first, and the bm25 ranking that
    `ManualIndex.search` sorts by (same index, same weights). `search` is the method's own
    answer, to compare."""
    index = ManualIndex()
    match = fts_query(query)
    rules = list(
        dict.fromkeys(
            m.upper()
            for m in re.findall(r"\b(?:gen|gb|ch)-\d{2}\b", query, re.IGNORECASE)
        )
    )
    ranked, seen = [], set()
    if match:
        rows = index._db.execute(  # the index's in-memory table, read only
            "SELECT source, heading, bm25(passages, ?, ?, ?, ?) AS score "
            "FROM passages WHERE passages MATCH ? AND lang = ? ORDER BY score LIMIT ?",
            [*WEIGHTS, match, lang, limit * 2],
        ).fetchall()
        for source, heading, score in rows:
            if source not in seen:
                seen.add(source)
                ranked.append(
                    {"source": source, "heading": heading, "bm25": round(score, 3)}
                )
    return {
        "query": query,
        "terms": match,
        "rule_ids_first": rules,
        "weights": {"heading": WEIGHTS[2], "text": WEIGHTS[3]},
        "ranked": ranked[:limit],
        "search": [p.source for p in index.search(query, lang, limit)],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    f = sub.add_parser("fts", help="FTS terms and BM25 ranking for a query")
    f.add_argument("query")
    f.add_argument("--lang", default="en")
    f.add_argument("--limit", type=int, default=3)
    args = parser.parse_args()
    print(json.dumps(fts(args.query, args.lang, args.limit), ensure_ascii=False))


if __name__ == "__main__":
    main()
