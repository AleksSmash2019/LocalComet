"""Invoke installed LocalComet skills from the desktop sidecar.

This module is intentionally small and safety-first:
- only ENABLED skills may be executed
- entrypoint must stay within the skills root
- execution is sandboxed to subprocess.run with no shell=True
- stdout/stderr are bounded and returned to the control plane
- on Windows, Python entrypoints are executed via sys.executable
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

from modules.skills.skills_manager import SkillsManager
from modules.skills.skills_contract import ALLOWED_PERMISSIONS, SkillError

MAX_INVOKE_STDOUT_BYTES = 64 * 1024
MAX_INVOKE_STDERR_BYTES = 16 * 1024


class SkillInvokeError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _bounded_read(data: bytes, max_bytes: int) -> bytes:
    if len(data) > max_bytes:
        return data[:max_bytes] + b"\n[truncated]"
    return data


_ENV_ALLOWLIST = frozenset({
    "PATH",
    "SYSTEMROOT",
    "WINDIR",
    "TEMP",
    "TMP",
    "PYTHONIOENCODING",
    "PYTHONUTF8",
    "NUMBER_OF_PROCESSORS",
})


def _sandbox_env() -> dict[str, str]:
    """Minimal environment for skill subprocesses (SECURITY.md section 3.4).

    Host variables (tokens, API keys, LOCALCOMET_*) must never leak into an
    untrusted skill process; only lifecycle-safe variables pass. Comparison is
    case-insensitive because Windows environment keys are case-preserving.
    """
    env = {key: value for key, value in os.environ.items() if key.upper() in _ENV_ALLOWLIST}
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def _executable_for_entrypoint(entrypoint: Path) -> list[str]:
    if entrypoint.suffix.lower() == ".py":
        return [sys.executable, str(entrypoint)]
    return [str(entrypoint)]


def invoke_skill(
    skill_id: str,
    arguments: Mapping[str, Any] | list[Any] | None,
    requested_permissions: list[str],
) -> dict[str, Any]:
    try:
        manager = SkillsManager(_skills_root())
        manifest_permissions = set(manager.inspect_permissions(skill_id))
        invalid_permissions = sorted(set(requested_permissions) - set(ALLOWED_PERMISSIONS))
        if invalid_permissions:
            raise SkillInvokeError(
                "PERMISSION_UNKNOWN",
                f"unknown requested skill permissions: {', '.join(invalid_permissions)}",
            )
        missing_permissions = sorted(set(requested_permissions) - manifest_permissions)
        if missing_permissions:
            raise SkillInvokeError(
                "PERMISSION_DENIED",
                f"skill manifest does not grant requested permissions: {', '.join(missing_permissions)}",
            )
        entrypoint = manager.entrypoint_path(skill_id)
    except SkillError as exc:
        raise SkillInvokeError(exc.code.value, exc.message) from exc

    cmd = _executable_for_entrypoint(entrypoint)
    if arguments is not None:
        cmd.append(_serialize_arguments(arguments))

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            shell=False,
            check=False,
            timeout=180,
            cwd=str(entrypoint.parent),
            env=_sandbox_env(),
        )
    except FileNotFoundError as exc:
        raise SkillInvokeError("entrypoint_missing", f"skill entrypoint missing: {exc}") from exc
    except OSError as exc:
        raise SkillInvokeError("internal_error", f"skill invocation failed: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise SkillInvokeError("tool_timeout", f"skill timed out after 180s: {exc}") from exc

    stdout = _bounded_read(proc.stdout or b"", MAX_INVOKE_STDOUT_BYTES)
    stderr = _bounded_read(proc.stderr or b"", MAX_INVOKE_STDERR_BYTES)
    try:
        stdout_text = stdout.decode("utf-8", errors="replace")
        stderr_text = stderr.decode("utf-8", errors="replace")
    except Exception as exc:  # pragma: no cover - extremely unlikely
        raise SkillInvokeError("internal_error", f"skill output decode failed: {exc}") from exc

    return {
        "skill": skill_id,
        "entrypoint": str(entrypoint),
        "returncode": proc.returncode,
        "stdout": stdout_text,
        "stderr": stderr_text,
        "truncated": len(proc.stdout or b"") > MAX_INVOKE_STDOUT_BYTES or len(proc.stderr or b"") > MAX_INVOKE_STDERR_BYTES,
    }


def _skills_root() -> Path:
    root = Path(__file__).resolve().parent.parent / "skills"
    if not root.exists():
        root.mkdir(parents=True, exist_ok=True)
    return root


def _serialize_arguments(arguments: Mapping[str, Any] | list[Any]) -> str:
    if isinstance(arguments, list):
        return json.dumps(arguments, ensure_ascii=False, separators=(",", ":"))
    return json.dumps(dict(arguments), ensure_ascii=False, separators=(",", ":"))
