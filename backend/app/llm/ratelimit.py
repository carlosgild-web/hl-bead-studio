"""Read a 429 answer: a per-minute limit worth waiting for, or a daily quota that is used up
(decision 0019). Shared by the startup check and the OpenAI-compatible client.

Groq says which limit it is in the error text ("tokens per day (TPD)"), and in headers:
`retry-after` (seconds), `x-ratelimit-reset-tokens` / `-requests` (durations such as `7.66s`
or `2m59.56s`) and `x-ratelimit-{limit,remaining}-{tokens,requests}` (on Groq the token
headers are per minute, the request headers per day). A 429 whose text says nothing is
judged by the wait: more than a minute means the quota is gone for now.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

import httpx

# The longest wait still treated as a per-minute limit (and slept through at runtime).
MINUTE_WAIT_S = 60.0

_PER_DAY_RE = re.compile(r"per day|\((?:TPD|RPD)\)", re.IGNORECASE)
_TRY_AGAIN_RE = re.compile(r"try again in ([\d.hms]+)", re.IGNORECASE)
_PART_RE = re.compile(r"(\d+(?:\.\d+)?)(ms|h|m|s)")
_UNIT_S = {"h": 3600.0, "m": 60.0, "s": 1.0, "ms": 0.001}


@dataclass(frozen=True)
class RateLimit:
    kind: Literal["minute", "day"]
    wait_s: float | None  # None: no header or text said how long
    usage: str = ""  # e.g. "tokens 1200 of 200000 left; requests 980 of 1000 left"

    @property
    def reset(self) -> str:
        """When it resets, for a person: "in 7m12s", or "" when unknown."""
        return f"in {format_duration(self.wait_s)}" if self.wait_s is not None else ""


def parse_duration(text: str) -> float | None:
    """`7.66s`, `2m59.56s`, `1h2m`, `120ms` or plain seconds (`30`) → seconds; None if neither."""
    text = text.strip()
    try:
        return float(text)
    except ValueError:
        pass
    parts = _PART_RE.findall(text)
    if not parts or "".join(n + u for n, u in parts) != text:
        return None
    return sum(float(n) * _UNIT_S[u] for n, u in parts)


def format_duration(seconds: float) -> str:
    seconds = max(0, round(seconds))
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}h{minutes:02d}m"
    if minutes:
        return f"{minutes}m{secs:02d}s"
    return f"{secs}s"


def classify_429(response: httpx.Response) -> RateLimit:
    headers, text = response.headers, response.text
    candidates = [headers.get("retry-after", ""), headers.get("x-ratelimit-reset-tokens", "")]
    # Groq's request headers count requests per day: their reset time is long even when only
    # the per-minute token limit was hit, so it counts only when no request is left.
    if headers.get("x-ratelimit-remaining-requests", "").strip() == "0":
        candidates.append(headers.get("x-ratelimit-reset-requests", ""))
    waits = [w for w in map(parse_duration, candidates) if w is not None]
    said = _TRY_AGAIN_RE.search(text)
    if said and (w := parse_duration(said.group(1).rstrip("."))) is not None:
        waits.append(w)
    wait = max(waits) if waits else None
    daily = bool(_PER_DAY_RE.search(text)) or (wait is not None and wait > MINUTE_WAIT_S)
    return RateLimit("day" if daily else "minute", wait, _usage(headers))


def _usage(headers: httpx.Headers) -> str:
    parts = []
    for what in ("tokens", "requests"):
        limit = headers.get(f"x-ratelimit-limit-{what}")
        left = headers.get(f"x-ratelimit-remaining-{what}")
        if limit and left:
            parts.append(f"{what} {left} of {limit} left")
    return "; ".join(parts)
