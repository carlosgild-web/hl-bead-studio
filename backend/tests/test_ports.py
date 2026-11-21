"""Freeing the launcher's ports (decision 0020), with fake OS tools: nothing is stopped."""

import pytest

from app.ports import (
    Holder,
    describe,
    find_listeners,
    free_ports,
    holders,
    parse_netstat,
    stop_process,
)

BACKEND = Holder(8000, 16092, "python.exe", r".venv\Scripts\python.exe -m uvicorn app.main:app")
UI = Holder(5173, 6588, "node.exe", r'"node" "...\vite\bin\vite.js" --port 5173')
DOCKER = Holder(8000, 4242, "com.docker.backend.exe", "com.docker.backend.exe")

NETSTAT = """
Conexiones activas

  Proto  Dirección local        Dirección remota       Estado           PID
  TCP    0.0.0.0:135            0.0.0.0:0              ESCUCHANDO       1100
  TCP    127.0.0.1:8000         0.0.0.0:0              ESCUCHANDO       16092
  TCP    127.0.0.1:8000         127.0.0.1:51234        ESTABLECIDA      16092
  TCP    127.0.0.1:51234        127.0.0.1:8000         ESTABLECIDA      7000
  TCP    [::1]:5173             [::]:0                 LISTENING        6588
  TCP    0.0.0.0:18000          0.0.0.0:0              LISTENING        9
  UDP    0.0.0.0:8100           *:*                                     55
"""


class Answers:
    def __init__(self, *answers):
        self.answers, self.prompts = list(answers), []

    def __call__(self, prompt):
        self.prompts.append(prompt)
        assert self.answers, f"unexpected question: {prompt}"
        return self.answers.pop(0)


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def _free(taken, answers=None, *, after=(), interactive=True):
    """`taken` is what the first look finds; `after` what each later look finds."""
    looks, stopped, lines, clock = [list(taken), *map(list, after)], [], [], Clock()

    def find(ports):
        return looks.pop(0) if len(looks) > 1 else looks[0]

    ok = free_ports(
        find=find,
        stop=stopped.append,
        ask=answers or Answers(),
        interactive=interactive,
        say=lines.append,
        sleep=clock.sleep,
        clock=clock,
    )
    return ok, stopped, lines


# --- the launcher's step ---------------------------------------------------------------------


def test_free_ports_ask_nothing() -> None:
    assert _free([]) == (True, [], [])


def test_our_processes_are_shown_and_stopped_on_enter() -> None:
    answers = Answers("")
    ok, stopped, lines = _free([BACKEND, UI], answers, after=[[]])

    assert ok and stopped == [6588, 16092]
    assert answers.prompts == ["Stop them and continue? [Y/n] "]
    assert lines[0].startswith("Port 8000 (backend) is taken by python.exe (PID 16092)")
    assert "uvicorn app.main:app" in lines[0]
    assert lines[-1] == "Stopped. The ports are free."


def test_no_stops_nothing_and_fails() -> None:
    ok, stopped, lines = _free([BACKEND], Answers("n"))
    assert not ok and stopped == []
    assert "Nothing was stopped" in lines[-1]


def test_a_foreign_process_is_suggested_to_keep() -> None:
    answers = Answers("")
    ok, stopped, lines = _free([DOCKER], answers)

    assert not ok and stopped == []
    assert answers.prompts == ["Stop them anyway and continue? [y/N] "]
    assert "Not every one looks like Bead Studio." in lines


def test_a_foreign_process_is_stopped_only_on_yes() -> None:
    ok, stopped, _ = _free([DOCKER, UI], Answers("yes"), after=[[]])
    assert ok and stopped == [4242, 6588]


def test_without_a_terminal_nothing_is_stopped() -> None:
    ok, stopped, _ = _free([BACKEND], interactive=False)
    assert not ok and stopped == []


def test_end_of_input_stops_nothing() -> None:
    ok, stopped, _ = _free([BACKEND], Answers(None))
    assert not ok and stopped == []


def test_a_port_that_stays_taken_fails_after_the_wait() -> None:
    ok, stopped, lines = _free([BACKEND], Answers("y"))
    assert not ok and stopped == [16092]
    assert lines[-1].startswith("Still taken: Port 8000")


def test_one_pid_on_two_ports_is_stopped_once() -> None:
    twice = [BACKEND, Holder(8100, 16092, "python.exe", BACKEND.command)]
    _, stopped, _ = _free(twice, Answers("y"), after=[[]])
    assert stopped == [16092]


def test_a_missing_tool_does_not_block_the_start() -> None:
    lines = []
    assert free_ports(find=lambda ports: None, say=lines.append, ask=Answers())
    assert "Could not check the ports" in lines[0]


@pytest.mark.parametrize(
    ("holder", "ours"),
    [
        (BACKEND, True),
        (UI, True),
        (DOCKER, False),
        (Holder(8000, 1, "python", "-m http.server"), False),
    ],
)
def test_ours(holder, ours) -> None:
    assert holder.ours is ours


# --- the OS tools ----------------------------------------------------------------------------


def test_netstat_listeners_in_any_language() -> None:
    assert parse_netstat(NETSTAT, [8000, 8100, 5173]) == {8000: {16092}, 5173: {6588}}


class Tools:
    """Records the commands; answers from a table of the first word."""

    def __init__(self, **outputs):
        self.outputs, self.commands = outputs, []

    def __call__(self, command):
        self.commands.append(command)
        return self.outputs.get(command[0])


def test_windows_holders() -> None:
    tools = Tools(
        netstat=NETSTAT,
        powershell=(
            "16092\tpython.exe\tpython -m uvicorn app.main:app\r\n6588\tnode.exe\tnode vite.js\r\n"
        ),
    )
    found = holders([8000, 5173], run=tools, windows=True)

    assert found == [
        Holder(5173, 6588, "node.exe", "node vite.js"),
        Holder(8000, 16092, "python.exe", "python -m uvicorn app.main:app"),
    ]
    script = tools.commands[1][-1]
    assert "ProcessId=6588 or ProcessId=16092" in script


def test_unix_listeners_and_names() -> None:
    tools = Tools(lsof="4321\n", ps="python3 python3 -m uvicorn app.main:app --port 8000\n")
    assert find_listeners([8000], run=tools, windows=False) == {8000: {4321}}
    assert describe([4321], run=tools, windows=False) == {
        4321: ("python3", "python3 -m uvicorn app.main:app --port 8000")
    }


def test_a_missing_tool_is_none() -> None:
    assert find_listeners([8000], run=Tools(), windows=True) is None
    assert find_listeners([8000], run=Tools(), windows=False) is None


def test_stop_takes_the_children_too() -> None:
    windows, unix = Tools(), Tools()
    stop_process(16092, run=windows, windows=True)
    stop_process(4321, run=unix, windows=False)

    assert windows.commands == [["taskkill", "/PID", "16092", "/T", "/F"]]
    assert unix.commands == [["pkill", "-TERM", "-P", "4321"], ["kill", "-TERM", "4321"]]
