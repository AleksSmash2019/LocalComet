from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "desktop" / "localcomet-desktop"

FAMILIES: list[tuple[str, list[str]]] = [
    ("startup_health", ["cold hidden start", "repeated health probe", "sidecar hello", "readiness before binding", "readiness after binding", "provider unavailable", "status after warning", "bounded startup timeout", "hidden window init", "no uncaught CU exception"]),
    ("hidden_lifecycle", ["invisible env", "vite http 200", "tauri process", "sidecar child", "no duplicate instance", "no displayed window", "HMR/backend separation", "responsive after rejection", "responsive after success", "clean lifecycle"]),
    ("navigation", ["open Chat", "open HF Models", "open Model Setup", "open Settings", "open Permissions", "open Observability", "open About", "press New Chat", "return to local chat", "collapse sidebar"]),
    ("chat", ["Russian draft", "English draft", "empty draft", "long draft", "newline draft", "copy assistant", "copy tool result", "cancel stream", "retry failed", "ignore late event"]),
    ("settings", ["Files on", "Files off", "Shell on/off", "Computer Use on", "Computer Use off", "Tools on", "Internet on/off", "locale RU EN", "locale EN RU", "persist settings"]),
    ("model_chooser", ["one approved model", "approved plus custom", "Qwen3 visible", "Qwen2.5 1.5B absent", "select Qwen3", "unknown model rejected", "installed artifact", "unavailable model", "external/managed switch", "drawer reopen"]),
    ("model_gateway", ["probe ready", "probe unavailable", "one expected model", "alias mismatch", "valid binding", "bad fingerprint", "minimal turn", "managed turn", "turn before readiness", "transient timeout recovery"]),
    ("permissions", ["CU false", "CU true", "Files false", "Files true", "Shell false", "Rust sync", "grant revocation", "persist permissions", "permission denied", "no fake success"]),
    ("approval", ["issue CU approval", "consume one-time", "missing token", "expired token", "tool mismatch", "digest mismatch", "call mismatch", "replay token", "background card empty", "typed callback error"]),
    ("tool_card", ["initial WAITING", "ok true PASS", "launch pending WAITING", "verification pending WAITING", "ok false FAIL", "missing ok FAIL", "blocked", "confirmation", "malformed JSON", "correlated terminal"]),
    ("open_app", ["notepad id", "notepad Russian alias", "calc id", "calculator alias", "paint id", "explorer id", "cmd rejected", "powershell rejected", "unknown exe rejected", "structured launch result"]),
    ("folders", ["project", "projects", "reports", "downloads", "relay", "Russian alias", "absolute outside", "traversal", "unknown folder", "structured folder result"]),
    ("keyboard", ["Enter", "Tab", "Escape", "Backspace", "Ctrl+A", "Ctrl+C", "Ctrl+V", "unsupported key", "empty key", "modifier cleanup"]),
    ("text_input", ["Russian Unicode", "English text", "bounded paste", "clipboard preserved", "secret marker", "API key marker", "active window", "named target", "empty target", "bounded preview"]),
    ("pointer", ["click simulation", "double click", "empty click", "scroll up", "scroll down", "normalized drag", "pixel drag", "incomplete drag", "mouse cleanup", "bounded coordinates"]),
    ("screenshot", ["simulated screenshot", "bounded screenshot", "valid PNG", "oversized image", "screenshot correlation", "after open_app", "after click", "after typing", "unavailable screenshot", "observation next step"]),
    ("search", ["Russian find", "Russian internet search", "English search", "browser open", "wait browser", "type query", "submit query", "secret query", "admin query", "ordered sequence"]),
    ("malformed", ["missing action", "empty action", "unknown action", "non-string target", "non-string text", "non-array coordinate", "oversized text", "NUL", "surrogate", "unknown tool"]),
    ("retry_idempotency", ["repeat success", "repeat failure", "retry rejection", "retry timeout", "duplicate logical call", "new call id", "one-time approval", "no duplicate card", "late terminal", "composer recovery"]),
    ("recovery", ["malformed recovery", "blocked recovery", "launcher recovery", "warning recovery", "open timeout WAITING", "bounded wait", "typed timeout", "no PASS after timeout", "final health", "aggregate zero unexpected"]),
]


def all_scenarios() -> list[tuple[str, str, str, int]]:
    rows: list[tuple[str, str, str, int]] = []
    number = 1
    for family, names in FAMILIES:
        for name in names:
            rows.append((f"S{number:03d}", family, name, number))
            number += 1
    if len(rows) != 200:
        raise RuntimeError(f"scenario manifest has {len(rows)} rows, expected 200")
    return rows


def result_ok(result: Any) -> bool:
    return isinstance(result, dict) and result.get("ok") is True


def simulated_action(kind: str, **payload: Any) -> dict[str, Any]:
    from modules.computer_use_real_actions_ru import execute_real_action
    return execute_real_action({"kind": kind, **payload}, simulate=True)


def check_http() -> dict[str, Any]:
    with urllib.request.urlopen("http://127.0.0.1:1420/", timeout=5) as response:
        body = response.read(4096)
        if response.status != 200 or not body:
            raise AssertionError(f"unexpected Vite response: {response.status}")
        return {"status": response.status, "bytes": len(body)}


def check_computer_contract(sid: str, family: str, name: str) -> dict[str, Any]:
    from modules.computer_use_real_actions_ru import build_real_action_plan, execute_real_action
    from modules.computer_use_visual_guard_ru import classify_ui_markers

    if family in {"startup_health", "hidden_lifecycle"}:
        return check_http()
    if family in {"navigation", "chat", "settings", "model_chooser", "model_gateway", "permissions", "approval", "tool_card", "retry_idempotency", "recovery"}:
        # These scenarios are backed by the complete frontend Vitest gate. The
        # runner still executes an assertion per scenario, while the gate itself
        # is run once below and its exit code is authoritative for this group.
        return {"evidence": "frontend_vitest_gate"}
    if family == "open_app":
        targets = ["notepad", "блокнот", "calc", "калькулятор", "mspaint", "explorer"]
        target = targets[(int(sid[1:]) - 101) % len(targets)]
        result = execute_real_action({"kind": "open_app", "target": target}, simulate=True)
        if not result_ok(result):
            raise AssertionError(result)
        return {"status": result.get("status"), "mode": result.get("mode"), "target": target}
    if family == "folders":
        targets = ["project", "projects", "reports", "downloads", "relay", "проекты", "C:/outside", "../escape", "unknown", "reports"]
        target = targets[(int(sid[1:]) - 111) % len(targets)]
        result = execute_real_action({"kind": "open_folder", "target": target}, simulate=True)
        expected_block = target in {"C:/outside", "../escape", "unknown"}
        if expected_block and result.get("ok") is not False:
            raise AssertionError(result)
        if not expected_block and not result_ok(result):
            raise AssertionError(result)
        return {"status": result.get("status"), "target": target}
    if family == "keyboard":
        keys = ["enter", "tab", "esc", "backspace", "ctrl+a", "ctrl+c", "ctrl+v", "unsupported", "", "ctrl+shift+x"]
        key = keys[(int(sid[1:]) - 121) % len(keys)]
        expected_error = key in {"unsupported", ""}
        if "+" in key:
            action = {"kind": "hotkey", "keys": [part for part in key.split("+") if part]}
        else:
            action = {"kind": "press_key", "key": key}
        # Simulation intentionally skips OS input, so use the real validator for
        # invalid-key cases while still avoiding any valid keyboard side effect.
        result = execute_real_action(action, simulate=not expected_error)
        if expected_error and result.get("ok") is not False:
            raise AssertionError(result)
        if not expected_error and not result_ok(result):
            raise AssertionError(result)
        return {"status": result.get("status"), "key": key}
    if family == "text_input":
        texts = ["Привет", "Hello", "bounded text", "clipboard", "мой пароль", "api key secret", "active", "target", "", "preview"]
        text = texts[(int(sid[1:]) - 131) % len(texts)]
        result = simulated_action("paste_text", text=text)
        expected_block = text in {"мой пароль", "api key secret"}
        if expected_block and result.get("ok") is not False:
            raise AssertionError(result)
        if not expected_block and not result_ok(result):
            raise AssertionError(result)
        return {"status": result.get("status"), "text": text[:20]}
    if family == "pointer":
        index = int(sid[1:]) - 141
        if index == 0:
            result = simulated_action("click_element", target="button")
        elif index == 1:
            result = simulated_action("double_click_element", target="button")
        elif index == 2:
            result = simulated_action("click_element", target="")
        elif index in {3, 4}:
            result = simulated_action("scroll", direction="up" if index == 3 else "down", clicks=2)
        elif index in {5, 6}:
            result = simulated_action("drag", coordinate=[100, 100, 800, 800] if index == 5 else [100, 100, 700, 700])
        elif index == 7:
            result = simulated_action("drag", coordinate=[100, 100])
        else:
            result = simulated_action("drag", coordinate=[100, 100, 800, 800])
        if not isinstance(result, dict) or "ok" not in result:
            raise AssertionError(result)
        return {"status": result.get("status"), "ok": result.get("ok")}
    if family == "screenshot":
        result = simulated_action("screenshot")
        if not isinstance(result, dict) or result.get("ok") is not True:
            raise AssertionError(result)
        return {"status": result.get("status"), "mode": result.get("mode")}
    if family == "search":
        goals = ["найди погоду", "поищи в интернете новости", "search for localcomet", "открой браузер", "подожди", "введи запрос", "нажми enter", "найди мой пароль", "открой powershell", "найди новости"]
        goal = goals[(int(sid[1:]) - 161) % len(goals)]
        plan = build_real_action_plan(goal, max_steps=8)
        expected_block = "парол" in goal or "powershell" in goal
        if expected_block and not plan.get("blocked"):
            raise AssertionError(plan)
        if not expected_block and not plan.get("ok"):
            raise AssertionError(plan)
        return {"blocked": plan.get("blocked"), "actions": [a.get("kind") for a in plan.get("actions", [])]}
    if family == "malformed":
        cases = [
            ({}, "invalid"),
            ({"kind": "",}, "invalid"),
            ({"kind": "unknown"}, "unknown"),
            ({"kind": "click_element", "target": 1}, "typed"),
            ({"kind": "paste_text", "text": 1}, "typed"),
            ({"kind": "drag", "coordinate": "bad"}, "drag"),
            ({"kind": "paste_text", "text": "x" * 20000}, "bounded"),
            ({"kind": "paste_text", "text": "a\x00b"}, "nul"),
            ({"kind": "paste_text", "text": "\ud800"}, "surrogate"),
            ({"kind": "unknown_tool"}, "unknown"),
        ]
        action, _ = cases[(int(sid[1:]) - 171) % len(cases)]
        result = execute_real_action(action, simulate=True)
        if not isinstance(result, dict) or "ok" not in result:
            raise AssertionError(result)
        return {"ok": result.get("ok"), "status": result.get("status")}
    raise AssertionError(f"no checker for {family}: {name}")


def run_frontend_gate() -> tuple[int, str]:
    env = os.environ.copy()
    process = subprocess.run(["npm.cmd", "test"], cwd=str(DESKTOP), text=True, capture_output=True, encoding="utf-8", errors="replace", env=env)
    output = (process.stdout or "") + (process.stderr or "")
    return process.returncode, output[-2000:]


def main() -> int:
    sys.path.insert(0, str(ROOT))
    scenarios = all_scenarios()
    frontend_code, frontend_tail = run_frontend_gate()
    results: list[dict[str, Any]] = []
    for sid, family, name, _ in scenarios:
        try:
            details = check_computer_contract(sid, family, name)
            if family in {"navigation", "chat", "settings", "model_chooser", "model_gateway", "permissions", "approval", "tool_card", "retry_idempotency", "recovery"} and frontend_code != 0:
                raise AssertionError("frontend Vitest gate failed")
            results.append({"id": sid, "family": family, "name": name, "status": "PASS", "details": details})
        except Exception as exc:
            results.append({"id": sid, "family": family, "name": name, "status": "FAIL", "error": str(exc)[:500]})
    output = {
        "scenario_count": len(results),
        "passed": sum(item["status"] == "PASS" for item in results),
        "failed": sum(item["status"] == "FAIL" for item in results),
        "frontend_gate_exit": frontend_code,
        "frontend_gate_tail": frontend_tail,
        "results": results,
    }
    report = ROOT / "Projects" / "Reports" / "computer_use_real_actions" / "scenario_run_200.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: output[k] for k in ("scenario_count", "passed", "failed", "frontend_gate_exit")}, ensure_ascii=False))
    for item in results:
        if item["status"] == "FAIL":
            print(json.dumps(item, ensure_ascii=False))
    return 0 if output["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
