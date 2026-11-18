"""Keyword search over the Product Design Manual with SQLite FTS5.

`docs/manual/{en,es}/NN-topic.md` is split into one passage per `##` or `###` section. A
section whose heading starts with a rule id (`### CH-02 Hanging loop`) carries that id, so
the assistant can cite it. Every passage has a source id that is the same in both languages:
`05-rules-charms#CH-02` for a rule, or `06-naming-and-collections#catalog-text` (the slug of
the English heading) for the other sections. The two languages have the same sections in the
same order, which `tests/test_manual_search.py` checks.

The index lives in memory and is built once per process (about eighty passages).
"""

from __future__ import annotations

import re
import sqlite3
import threading
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.core.content import MANUAL_DIR

LANGUAGES = ("en", "es")
MAX_TEXT_CHARS = 1200

_RULE_RE = re.compile(r"^((?:GEN|GB|CH)-\d{2})\b")
_WORD_RE = re.compile(r"\w+", re.UNICODE)


@dataclass(frozen=True)
class Passage:
    source: str  # "05-rules-charms#CH-02"
    lang: str
    rule: str | None  # "CH-02", or None for a section that is not a rule
    heading: str  # "CH-02 Hanging loop"
    text: str

    def to_dict(self, max_chars: int = MAX_TEXT_CHARS) -> dict[str, str | None]:
        text = self.text if len(self.text) <= max_chars else self.text[:max_chars] + " …"
        return {
            "source": self.source,
            "rule": self.rule,
            "lang": self.lang,
            "heading": self.heading,
            "text": text,
        }


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def sections(path: Path) -> list[tuple[str, str]]:
    """(heading, body) of every `##`/`###` section of one file, in order."""
    found: list[tuple[str, list[str]]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## ") or line.startswith("### "):
            found.append((line.lstrip("#").strip(), []))
        elif found:
            found[-1][1].append(line)
    return [(heading, "\n".join(body).strip()) for heading, body in found]


def load_passages(manual_dir: Path = MANUAL_DIR) -> list[Passage]:
    passages: list[Passage] = []
    for path in sorted((manual_dir / "en").glob("*.md")):
        english = sections(path)
        ids = []
        for heading, _ in english:
            rule = _RULE_RE.match(heading)
            ids.append((rule.group(1) if rule else None, rule.group(1) if rule else slug(heading)))
        for lang in LANGUAGES:
            secs = english if lang == "en" else sections(manual_dir / lang / path.name)
            for (heading, body), (rule, anchor) in zip(secs, ids, strict=True):
                if body:
                    passages.append(Passage(f"{path.stem}#{anchor}", lang, rule, heading, body))
    return passages


def fts_query(text: str) -> str:
    """Free text -> an FTS5 query that can't be a syntax error: quoted words joined by OR.
    A rule id such as `ch-02` stays one token pair, which FTS5 matches as a phrase."""
    words = [w for w in _WORD_RE.findall(text.lower()) if len(w) > 1 or w.isdigit()]
    return " OR ".join(f'"{w}"' for w in dict.fromkeys(words))


class ManualIndex:
    def __init__(self, manual_dir: Path = MANUAL_DIR) -> None:
        self._lock = threading.Lock()
        self._db = sqlite3.connect(":memory:", check_same_thread=False)
        self._db.execute(
            "CREATE VIRTUAL TABLE passages USING fts5("
            "source UNINDEXED, lang UNINDEXED, heading, text, "
            "tokenize = 'porter unicode61 remove_diacritics 2')"
        )
        self.passages = load_passages(manual_dir)
        self._db.executemany(
            "INSERT INTO passages VALUES (?, ?, ?, ?)",
            [(p.source, p.lang, p.heading, p.text) for p in self.passages],
        )
        self._by_key = {(p.source, p.lang): p for p in self.passages}
        self._by_rule = {(p.rule, p.lang): p for p in self.passages if p.rule}

    def search(self, query: str, lang: str | None = None, limit: int = 3) -> list[Passage]:
        """Best passages first (bm25, headings weigh more). A rule id in the query puts that
        rule first. Without `lang`, each source appears once, in the language that matched
        best."""
        found: list[Passage] = []
        for rule in dict.fromkeys(
            m.upper() for m in re.findall(r"\b(?:gen|gb|ch)-\d{2}\b", query, re.I)
        ):
            passage = self.rule(rule, lang or "en")
            if passage:
                found.append(passage)
        match = fts_query(query)
        rows: list[tuple[str, str]] = []
        if match:
            sql = "SELECT source, lang FROM passages WHERE passages MATCH ?"
            params: list[object] = [match]
            if lang in LANGUAGES:
                sql += " AND lang = ?"
                params.append(lang)
            # One weight per column: source, lang (not indexed), heading, text.
            sql += " ORDER BY bm25(passages, 0.0, 0.0, 3.0, 1.0) LIMIT ?"
            params.append(limit * 2 + len(found))
            with self._lock:
                rows = self._db.execute(sql, params).fetchall()
        seen = {p.source for p in found}
        for source, row_lang in rows:
            if len(found) >= limit:
                break
            if source not in seen:
                seen.add(source)
                found.append(self._by_key[(source, row_lang)])
        return found[:limit]

    def get(self, source: str, lang: str = "en") -> Passage | None:
        return self._by_key.get((source, lang))

    def rule(self, rule: str, lang: str = "en") -> Passage | None:
        return self._by_rule.get((rule, lang)) or self._by_rule.get((rule, "en"))


@lru_cache
def get_manual_index() -> ManualIndex:
    return ManualIndex()
