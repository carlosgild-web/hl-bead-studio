"""Free the launcher's ports before it starts anything (decision 0020).

`python -m app.cli free-ports` looks for processes listening on the ports `start.cmd` and
`start.sh` need (backend, mock SAP, UI), shows each one with its command line and offers
to stop it and its children. Stopping is the suggestion only when every holder looks like
a Bead Studio process (uvicorn `app.main`, Vite); anything else is suggested to keep.
Without a terminal nothing is stopped. The OS tools are used (netstat, taskkill,
PowerShell on Windows; lsof, ps, kill elsewhere), as argument lists with timeouts; the
PIDs put in a command are integers parsed from their output.
"""

from __future__ import annotations

import subprocess
import sys
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from app.llm.check import Questions, ask_stdin, say_stderr

PORTS: dict[int, str] = {8000: "backend", 8100: "mock SAP", 5173: "UI"}
TOOL_TIMEOUT_S = 15.0
FREE_WAIT_S = 10.0
OURS = (("uvicorn", "app.main"), ("vite",))

Run = Callable[[list[str]], str | None]


@dataclass(frozen=True)
class Holder:
    port: int
    pid: int
    name: str = "?"
    command: str = ""

    @property
    def ours(self) -> bool:
        text = self.command.lower()
        return any(all(word in text for word in words) for words in OURS)

    def line(self) -> str:
        what = f"{self.name} (PID {self.pid})" + (f": {self.command}" if self.command else "")
        return f"Port {self.port} ({PORTS.get(self.port, 'needed')}) is taken by {what}"


def run_tool(command: list[str]) -> str | None:
    """The tool's stdout, or None when it is missing, fails to start or times out."""
    try:
        done = subprocess.run(
            command, capture_output=True, text=True, timeout=TOOL_TIMEOUT_S, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return done.stdout


# --- finding ---------------------------------------------------------------------------------


def parse_netstat(text: str, ports: Iterable[int]) -> dict[int, set[int]]:
    """Listening TCP sockets from `netstat -ano`. The state column is translated on some
    Windows languages, so a listener is told by its foreign address (0.0.0.0:0, [::]:0)."""
    wanted, found = set(ports), {}
    for row in text.splitlines():
        parts = row.split()
        if len(parts) < 4 or parts[0].upper() != "TCP":
            continue
        local, foreign, pid = parts[1], parts[2], parts[-1]
        if foreign not in ("0.0.0.0:0", "[::]:0") or not pid.isdigit():
            continue
        port = local.rsplit(":", 1)[-1]
        if port.isdigit() and int(port) in wanted and int(pid) > 0:
            found.setdefault(int(port), set()).add(int(pid))
    return found


def find_listeners(
    ports: Iterable[int], *, run: Run = run_tool, windows: bool = sys.platform == "win32"
) -> dict[int, set[int]] | None:
    """PIDs listening on each port; None when the OS tool is missing."""
    ports = list(ports)
    if windows:
        text = run(["netstat", "-ano"])
        return None if text is None else parse_netstat(text, ports)
    found: dict[int, set[int]] = {}
    for port in ports:
        text = run(["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"])
        if text is None:
            return None
        pids = {int(p) for p in text.split() if p.isdigit()}
        if pids:
            found[port] = pids
    return found


def describe(
    pids: Iterable[int], *, run: Run = run_tool, windows: bool = sys.platform == "win32"
) -> dict[int, tuple[str, str]]:
    """Name and command line of each PID, as far as the OS tells."""
    pids = sorted(set(pids))
    if not pids:
        return {}
    info: dict[int, tuple[str, str]] = {}
    if windows:
        where = " or ".join(f"ProcessId={pid:d}" for pid in pids)
        script = (
            f"Get-CimInstance Win32_Process -Filter '{where}' | "
            'ForEach-Object { "$($_.ProcessId)`t$($_.Name)`t$($_.CommandLine)" }'
        )
        text = run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script]) or ""
        for row in text.splitlines():
            pid, _, rest = row.partition("\t")
            name, _, command = rest.partition("\t")
            if pid.strip().isdigit():
                info[int(pid)] = (name.strip() or "?", command.strip())
        return info
    for pid in pids:
        text = run(["ps", "-o", "comm=,args=", "-p", str(pid)]) or ""
        name, _, command = text.strip().partition(" ")
        if name:
            info[pid] = (name.rsplit("/", 1)[-1], command.strip())
    return info


def holders(
    ports: Iterable[int], *, run: Run = run_tool, windows: bool = sys.platform == "win32"
) -> list[Holder] | None:
    found = find_listeners(ports, run=run, windows=windows)
    if found is None:
        return None
    info = describe((pid for pids in found.values() for pid in pids), run=run, windows=windows)
    return [
        Holder(port, pid, *info.get(pid, ("?", "")))
        for port in sorted(found)
        for pid in sorted(found[port])
    ]


def stop_process(pid: int, *, run: Run = run_tool, windows: bool = sys.platform == "win32") -> None:
    """Stop the process and its children."""
    if windows:
        run(["taskkill", "/PID", str(pid), "/T", "/F"])
    else:
        run(["pkill", "-TERM", "-P", str(pid)])
        run(["kill", "-TERM", str(pid)])


# --- the launcher's step ---------------------------------------------------------------------


def free_ports(
    ports: Iterable[int] = PORTS,
    *,
    find: Callable[[list[int]], list[Holder] | None] = holders,
    stop: Callable[[int], None] = stop_process,
    ask: Callable[[str], str | None] = ask_stdin,
    interactive: bool = True,
    say: Callable[[str], None] = say_stderr,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> bool:
    """True when the ports are free (now, or after stopping what the designer agreed to)."""
    ports = list(ports)
    taken = find(ports)
    if taken is None:
        say("Could not check the ports (netstat or lsof not found); starting anyway.")
        return True
    if not taken:
        return True
    for holder in taken:
        say(holder.line())
    if all(holder.ours for holder in taken):
        prompt, suggestion = "Stop them and continue? [Y/n] ", "y"
    else:
        say("Not every one looks like Bead Studio.")
        prompt, suggestion = "Stop them anyway and continue? [y/N] ", "n"
    if Questions(ask, interactive)(prompt, "yn", suggestion, unattended="n") != "y":
        say("Nothing was stopped; close them, or answer y to stop them.")
        return False

    for pid in sorted({holder.pid for holder in taken}):
        stop(pid)
    deadline = clock() + FREE_WAIT_S
    while True:
        left = find(ports)
        if not left:
            say("Stopped. The ports are free.")
            return True
        if clock() >= deadline:
            for holder in left:
                say("Still taken: " + holder.line())
            return False
        sleep(0.5)
