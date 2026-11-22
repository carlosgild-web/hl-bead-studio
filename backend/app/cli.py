"""Command line: `python -m app.cli <command>` (run from `backend/`).

validate      check parameters against the manual and print the result as JSON
generate      write STEP, STL, GLB, drawing PDF and params.json for one revision
measure-fonts measure the approved fonts against CH-03 (the numbers behind CH-07)
render        render a catalog image of a generated revision with Blender
chat          send one message to the assistant (LLM_PROVIDER; SAP must be running)
agent-eval    run the evaluation scenarios (--fake in CI, or --provider ollama|anthropic|dahl|groq)
confirm       confirm a pending action, as the designer's click would (developer use)
cancel        cancel a pending action
llm-check     check Groq, Ollama and the demo model, and choose one (prints its name)
free-ports    stop what holds the launcher's ports (8000, 8100, 5173), after asking
"""

import argparse
import json
import string
import sys
from datetime import date
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.standards.families import FAMILY_CODES


def _read_params(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _cmd_validate(args: argparse.Namespace) -> int:
    from app.standards.validators import validate_parameters

    result = validate_parameters(args.family, _read_params(args.params))
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    return 0 if result.ok else 2


def _cmd_generate(args: argparse.Namespace) -> int:
    from app.designs import DesignError, InvalidDesignError, generate_design

    try:
        design = generate_design(
            args.family,
            _read_params(args.params),
            sku=args.sku,
            rev=args.rev,
            settings=get_settings(),
            name=args.name,
            sap_material=args.sap_material,
            on_date=date.fromisoformat(args.date) if args.date else None,
        )
    except InvalidDesignError as error:
        print(error, file=sys.stderr)
        for v in error.result.violations:
            hint = ", ".join(f"{s.parameter}={s.value}" for s in v.suggestions)
            print(f"  {v.rule}: {v.message}" + (f" Try {hint}." if hint else ""), file=sys.stderr)
        return 2
    except (DesignError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(f"{design.sku} rev {design.rev} ({design.family}) -> {design.folder}")
    for kind, path in design.files.items():
        print(f"  {kind:8} {path.name}")
    m = design.measurements
    print(f"  volume {m['volume_mm3']} mm3, mass {m['mass_g']} g, drawing {design.drawing_scale}")
    return 0


def _cmd_measure_fonts(args: argparse.Namespace) -> int:
    from app.geometry.font_metrics import (
        font_minimum,
        measure_engraving_character,
        measure_font,
    )
    from app.standards.rules import FONT_FILES

    for font in FONT_FILES:
        measures = measure_font(font)
        print(f"{font}: CH-07 minimum {font_minimum(measures):.1f} mm")
        for m in sorted(measures, key=lambda m: -(m.min_height_mm or 99))[: args.top]:
            detail = f"{m.pieces} pieces" if m.pieces != 1 else f"{m.min_height_mm} mm"
            print(f"  {m.letter}: {detail}")
    if args.engraving:
        chars = string.ascii_uppercase + string.digits
        results = {c: measure_engraving_character(c) for c in chars}
        print("engraving (capital height):")
        for char, height in sorted(results.items(), key=lambda kv: -(kv[1] or 99))[: args.top]:
            print(f"  {char}: {height} mm")
    return 0


def _cmd_render(args: argparse.Namespace) -> int:
    from app.render import RenderError, queue_render, run_job

    settings = get_settings()
    try:
        job = queue_render(
            settings, args.sku, args.rev, args.finish, actor="cli", samples=args.samples
        )
    except (RenderError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(f"job {job['id']}: {job['sku']} rev {job['rev']} in {job['finish']}, rendering...")
    done = run_job(settings, job["id"])
    if done is None:  # the server's worker took it first
        print(f"job {job['id']} is being rendered by the server's worker")
        return 0
    if done["status"] != "done":
        print(f"failed: {done['error']}", file=sys.stderr)
        return 1
    print(f"  {settings.designs_root / done['image']} ({done['duration_s']} s)")
    return 0


def _print_event(kind: str, data: dict[str, Any]) -> None:
    if kind == "message":
        print(f"\nassistant> {data['content']}\n")
    elif kind == "thinking":
        print(f"  (model) {data['content']}")
    elif kind == "tool_call":
        print(f"  -> {data['name']}({json.dumps(data['arguments'], ensure_ascii=False)})")
    elif kind == "tool_result":
        text = json.dumps(data["result"], ensure_ascii=False)
        print(
            f"  <- {'ok' if data['ok'] else 'ERROR'} {text[:300]}{'...' if len(text) > 300 else ''}"
        )
    elif kind == "pending_action":
        action = data["action"]
        print(f"  [card] {action['kind']} {action['id']}: {json.dumps(action['payload'])}")
    elif kind in ("parameter_proposal", "preview"):
        print(f"  [{kind}]")
    elif kind == "error":
        print(f"  error: {data['message']}", file=sys.stderr)
    elif kind == "done":
        print(
            f"conversation {data.get('conversation_id')} run {data.get('run_id')}: {data['status']}"
        )


def _cmd_chat(args: argparse.Namespace) -> int:
    from app.agent.service import AgentDeps, chat_turn
    from app.agent.tools import PreviewCache
    from app.db.store import Store
    from app.llm import LLMError, make_client
    from app.sap import SapClient
    from app.standards.manual_search import get_manual_index

    settings = get_settings()
    if args.provider:
        settings = settings.model_copy(update={"llm_provider": args.provider})
    try:
        client = make_client(settings)
    except LLMError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(f"{client.provider} / {client.model}")
    status = "error"
    with SapClient.from_settings(settings) as sap:
        deps = AgentDeps(
            settings=settings,
            store=Store(settings.data_dir),
            client=client,
            sap=sap,
            manual=get_manual_index(),
            previews=PreviewCache(),
        )
        for event in chat_turn(
            deps, text=args.message, conversation_id=args.conversation, language=args.language
        ):
            _print_event(event.type, event.data)
            if event.type == "done":
                status = event.data["status"]
    client.close()
    return 0 if status in ("answered", "limit") else 1


def _cmd_agent_eval(args: argparse.Namespace) -> int:
    from app.eval.harness import fake_clients
    from app.eval.report import EvalReport, ScenarioResult, run_eval, write_report
    from app.eval.scenarios import get_scenarios
    from app.llm import LLMError, make_client

    try:
        scenarios = get_scenarios(args.scenario, args.start_at)
    except KeyError as error:
        print(f"error: {error.args[0]}", file=sys.stderr)
        return 2
    settings = get_settings()
    provider = "fake" if args.fake else args.provider or settings.llm_provider
    # No fallback in an eval: a daily limit stops the run instead of scoring another model.
    settings = settings.model_copy(update={"llm_provider": provider, "llm_fallback": ""})
    if provider == "fake":
        clients = fake_clients
    else:
        try:
            make_client(settings).close()  # fail early on a missing key
        except LLMError as error:
            print(f"error: {error}", file=sys.stderr)
            return 2
        clients = lambda turn: make_client(settings)  # noqa: E731

    def progress(result: ScenarioResult) -> None:
        failed = ", ".join(c.name for c in result.failed)
        status = "pass" if result.passed else f"FAIL ({failed})"
        print(f"  {result.scenario.id:28} {status}  [{result.run.seconds:.0f} s]", flush=True)

    print(f"agent-eval: {len(scenarios)} scenarios on {provider}")

    def save(partial: EvalReport) -> None:
        write_report(partial, Path(args.out), args.label or "")

    report = run_eval(
        scenarios, clients, settings, on_result=progress, checkpoint=save if args.out else None
    )
    if report.stopped:
        first = report.stopped.split(":", 1)[0]
        print(f"stopped: {report.stopped}")
        print(f"continue later with: --start-at {first} --label <label>-part2")
    print(f"{report.provider} / {report.model}: {report.passed}/{report.total} pass")
    for name, (passed, scored) in report.check_rates().items():
        print(f"  {name:20} {passed}/{scored}")
    if args.out:
        md, js = write_report(report, Path(args.out), args.label or "")
        print(f"wrote {md} and {js.name}")
    return 0 if report.passed == report.total else 1


def _cmd_decide(args: argparse.Namespace) -> int:
    from app.actions import ActionNotFound, ActionNotPending, cancel_action, confirm_action
    from app.db.store import Store
    from app.sap import SapClient

    settings = get_settings()
    store = Store(settings.data_dir)
    try:
        if args.command == "cancel":
            action = cancel_action(args.action_id, store=store)
            print(json.dumps(action.to_dict(), indent=2, ensure_ascii=False))
            return 0
        with SapClient.from_settings(settings) as sap:
            outcome = confirm_action(args.action_id, settings=settings, store=store, sap=sap)
    except ActionNotFound:
        print(f"error: no action {args.action_id}", file=sys.stderr)
        return 2
    except ActionNotPending as error:
        print(f"error: the action is {error.reason}", file=sys.stderr)
        return 2
    print(json.dumps(outcome.action.to_dict(), indent=2, ensure_ascii=False))
    return 0 if outcome.ok else 1


def _cmd_llm_check(args: argparse.Namespace) -> int:
    from app.llm.check import check

    # Questions and status lines go to stderr: stdout carries only the name.
    try:
        name = check(get_settings(), interactive=sys.stdin.isatty())
    except KeyboardInterrupt:
        print(file=sys.stderr)
        return 130
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(name + "\n", encoding="utf-8")
    print(name)
    return 0


def _cmd_free_ports(args: argparse.Namespace) -> int:
    from app.ports import free_ports

    try:
        return 0 if free_ports(interactive=sys.stdin.isatty()) else 1
    except KeyboardInterrupt:
        print(file=sys.stderr)
        return 130


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description=__doc__.split("\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)

    validate = commands.add_parser("validate", help="validate parameters against the manual")
    validate.add_argument("--family", required=True, choices=FAMILY_CODES)
    validate.add_argument("--params", required=True, help="JSON file with the parameters")
    validate.set_defaults(func=_cmd_validate)

    generate = commands.add_parser("generate", help="generate the files of a design revision")
    generate.add_argument("--family", required=True, choices=FAMILY_CODES)
    generate.add_argument("--params", required=True, help="JSON file with the parameters")
    generate.add_argument("--sku", required=True, help="GB-1NNN or CH-2NNN (GEN-04)")
    generate.add_argument("--rev", required=True, help="revision letter (GEN-02)")
    generate.add_argument("--name", help="product name for the title block (GEN-03)")
    generate.add_argument("--sap-material", help="SAP material number, without leading zeros")
    generate.add_argument("--date", help="drawing date YYYY-MM-DD (default: today)")
    generate.set_defaults(func=_cmd_generate)

    fonts = commands.add_parser("measure-fonts", help="measure the fonts against CH-03")
    fonts.add_argument("--top", type=int, default=5, help="letters to list per font")
    fonts.add_argument("--engraving", action="store_true", help="also measure engraved text")
    fonts.set_defaults(func=_cmd_measure_fonts)

    render = commands.add_parser("render", help="render a catalog image with Blender")
    render.add_argument("--sku", required=True, help="a generated SKU (GB-1NNN or CH-2NNN)")
    render.add_argument("--rev", required=True, help="revision letter (GEN-02)")
    render.add_argument(
        "--finish", help="glass color (beads) or plating finish (charms); default: the design's"
    )
    render.add_argument("--samples", type=int, help="Cycles samples (default RENDER_SAMPLES)")
    render.set_defaults(func=_cmd_render)

    chat = commands.add_parser("chat", help="send one message to the assistant")
    chat.add_argument("message")
    chat.add_argument("--conversation", help="continue a conversation (its id)")
    chat.add_argument("--language", choices=("en", "es"), default="en")
    chat.add_argument("--provider", choices=("fake", "ollama", "anthropic", "dahl", "groq"))
    chat.set_defaults(func=_cmd_chat)

    evaluation = commands.add_parser("agent-eval", help="run the agent evaluation scenarios")
    which = evaluation.add_mutually_exclusive_group()
    which.add_argument("--fake", action="store_true", help="the ideal scripts (no model; CI)")
    which.add_argument("--provider", choices=("fake", "ollama", "anthropic", "dahl", "groq"))
    evaluation.add_argument("--scenario", action="append", help="run only this id (repeatable)")
    evaluation.add_argument(
        "--start-at", help="run the scenarios from this id onwards (after a daily limit)"
    )
    evaluation.add_argument("--out", help="folder for the Markdown and JSON report")
    evaluation.add_argument("--label", help="suffix of the report file names, e.g. run2")
    evaluation.set_defaults(func=_cmd_agent_eval)

    for name, text in (("confirm", "confirm a pending action"), ("cancel", "cancel one")):
        decide = commands.add_parser(name, help=text)
        decide.add_argument("action_id")
        decide.set_defaults(func=_cmd_decide)

    llm_check = commands.add_parser(
        "llm-check", help="check Dahl, Groq, Ollama and the demo model, and choose one"
    )
    llm_check.add_argument("--out", help="also write the chosen name to this file")
    llm_check.set_defaults(func=_cmd_llm_check)

    ports = commands.add_parser(
        "free-ports", help="stop what holds the launcher's ports, after asking"
    )
    ports.set_defaults(func=_cmd_free_ports)

    args = parser.parse_args(argv)
    # Spanish answers on a Windows console or pipe (cp1252 by default).
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
