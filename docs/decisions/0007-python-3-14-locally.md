# 0007: Develop on Python 3.14, support 3.12+

**Status:** accepted (2026-11-17). Deviation from `PLAN.md` and `CLAUDE.md` ("Python 3.11+").

## Context

The development laptop has Python 3.14 only. CadQuery depends on the `cadquery-ocp` wheel,
which is built per Python version. On 2026-11-17, `cadquery-ocp 8.0.1.1.0` has a
`cp314-win_amd64` wheel, so CadQuery installs on 3.14 without building anything.

## Decision

- Develop on Python 3.14.
- Support Python 3.12 and newer: `requires-python = ">=3.12"`, ruff `target-version = "py312"`.
- CI runs both Python packages on 3.12 and 3.14.
- Python 3.11 is dropped: nothing in the stack needs it, and supporting it would block
  language features used in 3.12+ (for example the `type` statement).

## Consequences

- The Docker image (Phase 8) can use either version; 3.12 has the widest wheel coverage if a
  dependency lags behind.
- If a future dependency has no 3.14 wheel, CI shows it on day one.
