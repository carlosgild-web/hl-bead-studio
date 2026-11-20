"""Reading a 429: a per-minute limit to wait out, or a daily quota that is used up."""

import httpx
import pytest

from app.llm.ratelimit import classify_429, format_duration, parse_duration

TPD = (
    "Rate limit reached for model `openai/gpt-oss-120b` on tokens per day (TPD): Limit 200000, "
    "Used 199500, Requested 2500. Please try again in 7m12.5s."
)
TPM = "Rate limit reached on tokens per minute (TPM): Limit 8000. Please try again in 7.66s."


def _429(text: str = "", **headers: str) -> httpx.Response:
    return httpx.Response(429, headers=headers, json={"error": {"message": text}})


@pytest.mark.parametrize(
    ("text", "seconds"),
    [("30", 30.0), ("7.66s", 7.66), ("2m59.56s", 179.56), ("1h2m", 3720.0), ("120ms", 0.12)],
)
def test_groq_durations(text, seconds) -> None:
    assert parse_duration(text) == pytest.approx(seconds)


@pytest.mark.parametrize("text", ["", "soon", "5x", "2m oops"])
def test_unreadable_durations(text) -> None:
    assert parse_duration(text) is None


def test_durations_for_people() -> None:
    assert (format_duration(7.4), format_duration(432.5), format_duration(3720)) == (
        "7s",
        "7m12s",
        "1h02m",
    )


def test_the_text_names_the_daily_limit() -> None:
    limit = classify_429(_429(TPD, **{"retry-after": "433"}))
    assert limit.kind == "day" and limit.reset == "in 7m13s"


def test_a_per_minute_limit_says_how_long_to_wait() -> None:
    limit = classify_429(_429(TPM, **{"retry-after": "8", "x-ratelimit-reset-tokens": "7.66s"}))
    assert limit.kind == "minute" and limit.wait_s == 8.0


def test_headers_only_are_judged_by_the_wait() -> None:
    assert classify_429(_429(**{"retry-after": "30"})).kind == "minute"
    assert classify_429(_429(**{"x-ratelimit-reset-tokens": "2h"})).kind == "day"
    assert classify_429(_429()).kind == "minute"  # nothing said: worth one short retry


def test_the_daily_request_reset_counts_only_when_no_request_is_left() -> None:
    headers = {"retry-after": "8", "x-ratelimit-reset-requests": "2m59.56s"}
    assert classify_429(_429(TPM, **headers, **{"x-ratelimit-remaining-requests": "12"})).kind == (
        "minute"
    )
    used_up = classify_429(_429(**headers, **{"x-ratelimit-remaining-requests": "0"}))
    assert used_up.kind == "day" and used_up.reset == "in 3m00s"


def test_usage_from_the_headers() -> None:
    limit = classify_429(
        _429(
            TPD,
            **{
                "x-ratelimit-limit-tokens": "8000",
                "x-ratelimit-remaining-tokens": "0",
                "x-ratelimit-limit-requests": "1000",
                "x-ratelimit-remaining-requests": "981",
            },
        )
    )
    assert limit.usage == "tokens 0 of 8000 left; requests 981 of 1000 left"
