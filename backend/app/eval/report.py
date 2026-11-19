"""Run a set of scenarios and report: a Markdown page for people (`docs/eval/`) and JSON with
every answer, check and trace summary."""

from __future__ import annotations

import json
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.eval.harness import ClientFactory, ScenarioRun, run_scenario
from app.eval.scenarios import Scenario
from app.eval.score import CHECK_NAMES, Check, score
from app.llm.base import DAILY_LIMIT

ANSWER_PREVIEW = 700


@dataclass
class ScenarioResult:
    scenario: Scenario
    run: ScenarioRun
    checks: list[Check]

    @property
    def passed(self) -> bool:
        return all(c.ok for c in self.checks)

    @property
    def failed(self) -> list[Check]:
        return [c for c in self.checks if not c.ok]

    def to_dict(self) -> dict[str, Any]:
        run = self.run
        return {
            "id": self.scenario.id,
            "title": self.scenario.title,
            "language": self.scenario.language,
            "tags": list(self.scenario.tags),
            "passed": self.passed,
            "checks": [c.to_dict() for c in self.checks],
            "model_calls": run.model_calls,
            "tokens": run.tokens,
            "seconds": run.seconds,
            "turns": [
                {
                    "text": t.text,
                    "answer": t.answer,
                    "status": t.status,
                    "error": t.error,
                    "seconds": t.seconds,
                    "tools": [
                        {"name": s["name"], "arguments": s["arguments"], "ok": s["ok"]}
                        for s in t.trace.get("steps", [])
                        if s["type"] == "tool_call"
                    ],
                    "checks": [
                        s["check"] for s in t.trace.get("steps", []) if s["type"] == "check"
                    ],
                }
                for t in run.turns
            ],
            "clicks": [vars(c) for c in run.clicks],
            "cards": [{"kind": a["kind"], "status": a["status"]} for a in run.actions],
            "effects": {
                "reserved": run.reserved,
                "designs": run.designs,
                "renders": run.renders,
            },
        }


@dataclass
class EvalReport:
    provider: str
    model: str
    started: datetime
    results: list[ScenarioResult] = field(default_factory=list)
    planned: int = 0  # scenarios asked for; more than `total` while running or after a crash
    stopped: str = ""  # why the run stopped early (a provider's daily limit), else ""

    @property
    def complete(self) -> bool:
        return self.total >= self.planned

    @property
    def passed(self) -> int:
        return sum(r.passed for r in self.results)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def rate(self) -> float:
        return self.passed / self.total if self.total else 0.0

    def check_rates(self) -> dict[str, tuple[int, int]]:
        """name -> (passed, scored) over the scenarios that score that check."""
        rates: dict[str, tuple[int, int]] = {}
        for name in CHECK_NAMES:
            scored = [c for r in self.results for c in r.checks if c.name == name]
            if scored:
                rates[name] = (sum(c.ok for c in scored), len(scored))
        return rates

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "started": self.started.isoformat(timespec="seconds"),
            "passed": self.passed,
            "total": self.total,
            "planned": self.planned,
            "complete": self.complete,
            "stopped": self.stopped,
            "checks": {k: {"passed": p, "scored": n} for k, (p, n) in self.check_rates().items()},
            "scenarios": [r.to_dict() for r in self.results],
        }

    def to_markdown(self) -> str:
        tokens = sum(r.run.tokens for r in self.results)
        seconds = sum(r.run.seconds for r in self.results)
        lines = [
            f"# Agent eval: {self.provider} / {self.model}",
            "",
            f"Run {self.started:%Y-%m-%d %H:%M} UTC with `python -m app.cli agent-eval`. "
            f"**{self.passed}/{self.total} scenarios pass ({self.rate:.0%}).** "
            f"{tokens} tokens, {seconds:.0f} s in total.",
            "",
            *(
                []
                if self.complete
                else [
                    f"**Incomplete run: {self.total} of {self.planned} scenarios finished.** "
                    "The rates below cover only the finished ones."
                    + (f" Stopped: {_cell(self.stopped)}" if self.stopped else ""),
                    "",
                ]
            ),
            "A scenario passes only when every check passes. The checks read the traces, the "
            "cards and the side effects; see `backend/app/eval/score.py`.",
            "",
            "| Check | Passed |",
            "|---|---|",
        ]
        lines += [f"| {k} | {p}/{n} |" for k, (p, n) in self.check_rates().items()]
        lines += [
            "",
            "| Scenario | Lang | Result | Failed checks | Calls | Tokens | s |",
            "|---|---|---|---|---|---|---|",
        ]
        for r in self.results:
            failed = "; ".join(
                f"{c.name}" + (f" ({_cell(c.detail)})" if c.detail else "") for c in r.failed
            )
            lines.append(
                f"| `{r.scenario.id}` | {r.scenario.language} | "
                f"{'pass' if r.passed else '**FAIL**'} | {failed} | {r.run.model_calls} | "
                f"{r.run.tokens} | {r.run.seconds:.0f} |"
            )
        failures = [r for r in self.results if not r.passed]
        if failures:
            lines += ["", "## Failures", ""]
            for r in failures:
                lines += [f"### `{r.scenario.id}`: {r.scenario.title}", ""]
                for c in r.failed:
                    lines.append(f"- **{c.name}**: {c.detail or 'failed'}")
                lines.append("")
                for i, t in enumerate(r.run.turns, 1):
                    tools = ", ".join(
                        s["name"] + ("" if s["ok"] else " (error)")
                        for s in t.trace.get("steps", [])
                        if s["type"] == "tool_call"
                    )
                    lines += [
                        f"Turn {i}. Designer: {_quote(t.text)}",
                        "",
                        f"Tools: {tools or 'none'}",
                        "",
                        "> " + _quote(t.answer or f"({t.status}: {t.error})").replace("\n", "\n> "),
                        "",
                    ]
        return "\n".join(lines).rstrip() + "\n"


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def _quote(text: str) -> str:
    text = text.strip()
    return text if len(text) <= ANSWER_PREVIEW else text[:ANSWER_PREVIEW] + " [...]"


def run_eval(
    scenarios: Sequence[Scenario],
    clients: ClientFactory,
    base: Settings,
    on_result: Callable[[ScenarioResult], None] | None = None,
    checkpoint: Callable[[EvalReport], None] | None = None,
) -> EvalReport:
    """Run each scenario in its own temporary folder and score it.

    `checkpoint` gets the report after every scenario, so a long real-provider run that dies
    (out of memory, a timeout) still leaves the finished scenarios on disk.
    """
    report = EvalReport("", "", datetime.now(UTC), planned=len(scenarios))
    for scenario in scenarios:
        # ignore_cleanup_errors: on Windows the SQLite file may still be open when the
        # folder is removed.
        with tempfile.TemporaryDirectory(prefix="bead-eval-", ignore_cleanup_errors=True) as tmp:
            run = run_scenario(scenario, clients, base, Path(tmp))
        limit = next((t.error for t in run.turns if (t.error or "").startswith(DAILY_LIMIT)), "")
        if limit:
            # Not the model's fault: leave the scenario out and stop; the rest would fail too.
            report.stopped = f"{scenario.id}: {limit}"
            break
        result = ScenarioResult(scenario, run, score(run))
        report.results.append(result)
        report.provider = report.provider or run.provider
        report.model = report.model or run.model
        if on_result:
            on_result(result)
        if checkpoint:
            checkpoint(report)
    return report


def write_report(report: EvalReport, out_dir: Path, label: str = "") -> tuple[Path, Path]:
    """`<date>-<provider>-<model>[-<label>].md` and `.json` in `out_dir`."""
    out_dir.mkdir(parents=True, exist_ok=True)
    model = "".join(ch if ch.isalnum() or ch in ".-" else "-" for ch in report.model)
    stem = f"{report.started:%Y-%m-%d}-{report.provider}-{model}"
    if label:
        stem += "-" + "".join(ch if ch.isalnum() or ch == "-" else "-" for ch in label)
    md, js = out_dir / f"{stem}.md", out_dir / f"{stem}.json"
    md.write_text(report.to_markdown(), encoding="utf-8")
    js.write_text(
        json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return md, js
