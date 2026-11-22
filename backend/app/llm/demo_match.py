"""Match a designer's message to an entry of the Q&A bank, for demo mode (decision 0022).

Plain Python, no model and no dependency:

- `normalize` lowercases, strips accents, splits `10mm` into `10 mm`, turns a decimal comma
  into a dot and keeps rule ids (`GB-02`) whole;
- a message and a bank phrasing (the question or a variant) are compared as sets of tokens
  without stopwords, by the overlap coefficient |A∩B| / min(|A|, |B|). A single shared
  token counts only when it is one of the entry's keywords ("bead" alone matches nothing);
- each of the entry's keywords found in the message adds a small bonus; ties go to the
  closer phrasing (Jaccard), then to the UI language, then to the earlier entry;
- a rule id in the message picks the first knowledge entry that cites it;
- both languages are scored (a designer may type English in the Spanish UI); below
  `THRESHOLD` nothing matches and demo mode gives the fallback.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from app.core.content import QaBank, QaEntry, qa_bank

THRESHOLD = 0.5
KEYWORD_BONUS = 0.15
MAX_KEYWORD_BONUS = 0.3

RULE_ID = re.compile(r"\b(?:gb|ch|gen)-\d{2}\b")
_TOKEN = re.compile(r"(?:gb|ch|gen)-\d{2}|\d+(?:\.\d+)?|[a-z]+")

_STOP_EN = (
    "a an the of for to in on at by with and or is are be can could would should will do does "
    "did i me my we our you your it its this that these those what whats which how why when "
    "s am please want need make made get use some any there here just so if then than as from "
    "mm millimetre millimetres millimeter millimeters"
)
_STOP_ES = (
    "de la el los las una un unos unas con para por que en y o es son ser puedo puede pueden "
    "se me mi mis tu te le lo al del como cual cuales cuanto cuanta cuantos cuantas su sus "
    "quiero hay esta este esto estos estas ese esa eso muy mas tan hacer haces ponle pon "
    "milimetros milimetro"
)
STOPWORDS = frozenset(_STOP_EN.split() + _STOP_ES.split())


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"(\d),(\d)", r"\1.\2", text)  # 1,5 -> 1.5
    text = re.sub(r"(\d)([a-z])", r"\1 \2", text)  # 10mm -> 10 mm
    return text


def _stem(token: str) -> str:
    """A crude plural strip, the same on both sides: beads -> bead, colores -> colore."""
    if len(token) > 3 and token.endswith("s") and not token[0].isdigit():
        return token[:-1]
    return token


def tokens(text: str) -> frozenset[str]:
    return frozenset(_stem(t) for t in _TOKEN.findall(normalize(text)) if t not in STOPWORDS)


def _overlap(a: frozenset[str], b: frozenset[str], keys: frozenset[str]) -> tuple[float, float]:
    """(overlap coefficient, Jaccard); zero when only one non-keyword token is shared."""
    shared = a & b
    if not shared or (len(shared) == 1 and not shared & keys):
        return (0.0, 0.0)
    return (len(shared) / min(len(a), len(b)), len(shared) / len(a | b))


def _has_keyword(message: str, keyword: str) -> bool:
    return (
        re.search(rf"(?<![a-z0-9]){re.escape(normalize(keyword))}(?![a-z0-9])", message) is not None
    )


@dataclass(frozen=True)
class Match:
    entry: QaEntry
    score: float
    language: str  # the language the message matched in


def score(entry: QaEntry, message: str, language: str) -> tuple[float, float]:
    """(score, Jaccard of the closest phrasing) of the message against one language."""
    text = entry.text(language)
    keywords = entry.keywords.es if language == "es" else entry.keywords.en
    keys = frozenset(t for k in keywords for t in tokens(k))
    words = tokens(message)
    best = max(_overlap(words, tokens(p), keys) for p in (text.question, *text.variants))
    if best[0] == 0.0:
        return best
    normalized = normalize(message)
    hits = sum(_has_keyword(normalized, k) for k in keywords)
    return (best[0] + min(hits * KEYWORD_BONUS, MAX_KEYWORD_BONUS), best[1])


def match(message: str, language: str = "en", bank: QaBank | None = None) -> Match | None:
    """The best entry for the message, or None (demo mode then gives the fallback)."""
    bank = bank or qa_bank()
    rule = RULE_ID.search(normalize(message))
    if rule:
        wanted = rule.group(0).upper()
        for entry in bank.entries:
            if entry.kind == "knowledge" and wanted in entry.rules:
                return Match(entry, 1.0, language)
    other = "en" if language == "es" else "es"
    scored = [
        (score(entry, message, lang), lang == language, -index, entry, lang)
        for lang in (language, other)
        for index, entry in enumerate(bank.entries)
    ]
    (best, _), _, _, entry, lang = max(scored, key=lambda t: t[:3])
    return Match(entry, best, lang) if best >= THRESHOLD else None
