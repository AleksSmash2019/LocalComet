"""Explicit user-consent gate for console/legacy Computer Use bridges.

The desktop app routes dangerous tools through the Rust approval boundary
(decision card -> scoped token -> execution grant re-verified by the sidecar).
The legacy console bridges (LocalComet_Control_Panel.py, premium task panel)
reach the real GUI primitives directly through computer_use_core_ru.dispatch,
so they carry their own consent gate with the same deny-by-default semantics:

- read-only / simulated / planning commands pass through;
- everything that can perform a real desktop action requires an explicit
  interactive confirmation (y/N), and non-interactive sessions are denied.

The prefix list intentionally mirrors the read-only command space of
computer_use_core_ru.dispatch; anything unrecognized requires confirmation.
"""

from __future__ import annotations

import re
from typing import Any, Dict

_SAFE_BRIDGE_PREFIXES = (
    # status / observation / planning / queue inspection (no real actions)
    "pc computer status",
    "computer status",
    "pc computer map",
    "computer map",
    "pc computer find",
    "computer find",
    "найди элемент",
    "pc computer ground",
    "computer ground",
    "заземли элемент",
    "pc computer observe",
    "computer observe",
    "pc computer plan",
    "computer plan",
    "спланируй действие",
    "pc computer simulate",
    "computer simulate",
    "pc computer dry",
    "computer dry",
    "сухой запуск",
    "pc computer queue",
    "computer queue",
    "поставь действие в очередь",
    "pc computer stop",
    "computer stop",
    "останови действие",
    "pc computer clear",
    "computer clear",
    "очисти очередь",
    "grounding status",
    "computer grounding status",
    "pc computer grounding status",
)

_CONFIRM_QUESTION = "Computer Use: выполнить реальное действие на этом компьютере? (y/N): "


def _normalize(command: str) -> str:
    return re.sub(r"\s+", " ", str(command or "").strip().lower().replace("ё", "е"))


def is_read_only_bridge_command(command: str) -> bool:
    lowered = _normalize(command)
    if not lowered:
        return False
    return any(lowered == prefix or lowered.startswith(prefix + " ") for prefix in _SAFE_BRIDGE_PREFIXES)


def bridge_gate_decision(command: str) -> Dict[str, Any]:
    """Decide whether a console bridge command needs explicit user consent."""
    if is_read_only_bridge_command(command):
        return {
            "requires_confirmation": False,
            "reason": "",
        }
    return {
        "requires_confirmation": True,
        "reason": (
            "Real Computer Use actions require explicit confirmation in console "
            "bridges. Re-run interactively and confirm, or use a read-only/simulate "
            "command, or 'pc exec run подтверждаю: <goal>' for scripted runs."
        ),
    }


def confirm_interactively(command: str) -> bool:
    """Ask the human console user for consent; non-tty sessions deny."""
    import sys

    decision = bridge_gate_decision(command)
    if not decision["requires_confirmation"]:
        return True
    if not sys.stdin.isatty():
        return False
    try:
        answer = input(_CONFIRM_QUESTION).strip().lower()
    except EOFError:
        return False
    return answer in ("y", "yes", "д", "да")
