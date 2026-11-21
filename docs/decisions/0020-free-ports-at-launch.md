# 0020: The launcher shows what holds its ports and offers to stop it

**Status:** accepted (2026-11-21). An addition outside the `PLAN.md` phases, requested by Carlos.

## Context

`start.cmd` and `start.sh` start the backend (:8000), the mock SAP (:8100) and the UI
(:5173). When an earlier start was still running, the launcher only said "Something
already answers on port 8000" and stopped, after the model questions had been answered.
The other two ports were not checked: Vite failed on its own (`--strictPort`) and the mock
SAP in its window.

## Decisions

1. **`python -m app.cli free-ports`** (`app/ports.py`) runs first in both launchers, before
   the model check, and with or without a provider argument.
2. **Finding:** `netstat -ano` on Windows, `lsof` on Linux and macOS. On Windows a listener
   is told by its foreign address (`0.0.0.0:0`, `[::]:0`), because netstat translates the
   state column ("ESCUCHANDO" on a Spanish system). The name and command line come from
   `Get-CimInstance Win32_Process` (PowerShell) or `ps`.
3. **The question:**
   - Every holder is shown with its port, name, PID and command line.
   - If all of them look like Bead Studio (uvicorn `app.main`, or Vite), the question is
     "Stop them and continue? [Y/n]". Otherwise it is "Stop them anyway and continue?
     [y/N]", so Enter never stops, say, Docker on port 8000.
   - Without a terminal, or at the end of input, nothing is stopped and the launcher
     exits without starting anything.
4. **Stopping:** `taskkill /PID <pid> /T /F` on Windows, so a uvicorn or npm child goes
   too; `pkill -TERM -P <pid>` then `kill -TERM <pid>` elsewhere. Then it waits up to 10 s
   for the ports to be free and fails if one is still taken. A window left from an earlier
   `start.cmd` stays open at its prompt.
5. **Bounded and safe (invariant 6):** every tool runs as an argument list with a 15 s
   timeout and no shell. The only values put in a command are PIDs parsed as integers.
   If netstat or lsof is missing, the launcher says so and starts anyway, as before.
6. With no input, the question helper now prints "(no input)" instead of "(no input:
   taking the suggestion)": with no input, this question and "Start Ollama?" take the
   safe answer, not the suggestion.

## Consequences

- A second launch no longer needs the old windows found and closed by hand.
- Stopping a process is always shown first and needs a yes from the designer.
- Tests use fake tool outputs and a fake stop. They stop nothing.
