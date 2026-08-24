"""Tool execution for the LocalComet desktop sidecar (ADR-013).

Executes files.* tool calls dispatched by the Rust control plane AFTER the
authorization boundary (execute_approved) has been crossed. The sidecar trusts
the control plane for approval (INV-APPROVAL-001 lives in Rust); its own
responsibility is workspace confinement: every target path is resolved and
checked against the confirmed workspace via WorkspacePolicy.validate_path
(resolve-before-containment, so symlink/junction escape is rejected).

No chunking in the first release: payloads larger than MAX_TOOL_FILE_BYTES are
rejected (read -> payload_too_large, write -> invalid_payload). The limit is
bounded by the IPC per-string payload limit (MAX_STRING_CHARS = 1 MiB), since
file content travels as a JSON string value.
"""

from __future__ import annotations

import collections
import hashlib
import queue
import re
import time
from pathlib import Path
import threading

import os
from typing import Any, Mapping

from modules.workspace_policy import WorkspacePolicy, WorkspacePolicyError

# Maximum bytes for a single file read/write. Bounded by the IPC payload string
# limit (MAX_STRING_CHARS = 1 MiB in desktop_ipc_contract_ru.py), NOT the 4 MiB
# frame: the file content travels as a JSON string value, so it must stay below
# the per-string limit with margin for JSON escaping overhead. No chunking in
# the first release (ADR-013): oversized payloads are rejected.
MAX_TOOL_FILE_BYTES = 1_000_000

SUPPORTED_TOOLS = frozenset(
    ("files.read", "files.list", "files.write", "files.create_folder", "files.delete", "shell", "computer_use", "web.search", "web.fetch", "skills.invoke", "system.time")
)

# Dangerous sidecar tools per security/invariants/tool_risk_levels.toml (the
# single source of truth). The Rust boundary (approval_commands::
# risk_level_for_tool) and scripts/check_tool_risk_registry.py +
# tools/test_tool_risk_rust_parity.py keep both sides in sync. Dangerous tools
# must present a Rust execution grant that is re-verified here: Rust-side
# validation alone is not sufficient defense-in-depth (master prompt §3.3).
DANGEROUS_TOOLS = frozenset(("files.delete", "shell", "computer_use", "skills.invoke"))
# `computer_use` remains dangerous at the capability level in the canonical
# registry, while Rust resolves the effective risk from the action. These
# actions are the only no-grant subset; every other action stays grant-bound.
COMPUTER_USE_READ_ONLY_ACTIONS = frozenset(
    ("screenshot", "wait", "observe", "cursor_position", "mouse_move", "scroll")
)


class ToolExecutionError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _require_str(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ToolExecutionError("invalid_payload", f"{key} must be a non-empty string")
    _reject_unrenderable(value, key)
    return value


def _reject_unrenderable(value: str, key: str) -> None:
    """Reject strings that cannot survive the outbound frame encoder.

    Guarding only `path` was insufficient: every required string field is echoed
    back into an error message (`unsupported tool: {tool}`, `workspace does not
    exist: {resolved}`), and the response frame is serialized with
    ensure_ascii=False, so a lone UTF-16 surrogate anywhere in that message raises
    IPCProtocolError("invalid_json") from encode_frame -- outside any
    ToolExecutionError handler, terminating the sidecar. An embedded NUL is
    rejected for the same reason it is rejected in a path: the OS layer raises
    ValueError, not OSError, at use time.

    Note for future handlers: rejection must happen before the value can reach
    a message template, which is why this sits in _require_str rather than at each
    use site.
    """
    if "\x00" in value:
        raise ToolExecutionError(
            "invalid_payload", f"{key} contains an embedded null character"
        )
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        # The exception text itself is ASCII-safe: it names the code point in
        # escaped form rather than embedding the offending character.
        raise ToolExecutionError("invalid_payload", f"{key} is not encodable: {exc}") from exc


# --- Execution grant verification (master prompt §3.3) -----------------------
#
# Rust mints a scoped ExecutionGrant when the one-time approval token is
# consumed and forwards it with the tool.call payload. The Python execution
# boundary re-verifies it before executing dangerous tools, so a forged or
# replayed payload that never crossed the Rust boundary cannot reach real
# actions: grant must bind the exact tool, canonical input digest, workspace,
# session, an unexpired TTL, and must be single-use at this boundary too.

_GRANT_STRING_FIELDS = ("grant_id", "tool", "input_digest", "workspace", "session")
_MAX_CONSUMED_GRANTS = 4096
_consumed_grants: dict[str, int] = {}
_consumed_grants_order: collections.deque[str] = collections.deque()
_consumed_grants_lock = threading.Lock()

_FLOAT_EXPONENT_RE = re.compile(r"e([+-])?(0+)(\d)")


def _canonical_json_number(value: Any) -> str:
    """Mirror serde_json float Display for digest parity.

    repr() on CPython already produces the shortest round-trip form; it only
    differs in exponent zero-padding ('1.5e-07' vs serde_json's '1.5e-7'),
    which is normalized here. The exponent sign is kept as-is: serde_json
    prints 1e+30 with the plus (verified by the shared parity vector).
    """
    if isinstance(value, int):
        return str(value)
    if value != value or value in (float("inf"), float("-inf")):
        raise ToolExecutionError(
            "invalid_payload", "input contains a non-finite number"
        )
    return _FLOAT_EXPONENT_RE.sub(
        lambda m: "e" + (m.group(1) or "") + m.group(3), repr(value)
    )


def _escape_canonical_json_string(value: str) -> str:
    out: list[str] = []
    for ch in value:
        if ch == '"':
            out.append('\\"')
        elif ch == "\\":
            out.append("\\\\")
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\r":
            out.append("\\r")
        elif ch == "\t":
            out.append("\\t")
        elif ord(ch) < 0x20:
            out.append("\\u%04x" % ord(ch))
        else:
            out.append(ch)
    return "".join(out)


def _canonicalize_tool_input(value: Any) -> str:
    """Byte-exact port of approval.rs canonicalize_json (sorted keys, no
    whitespace, minimal escaping with non-ASCII kept literal)."""
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, int) or isinstance(value, float):
        return _canonical_json_number(value)
    if isinstance(value, str):
        return '"' + _escape_canonical_json_string(value) + '"'
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(_canonicalize_tool_input(item) for item in value) + "]"
    if isinstance(value, Mapping):
        keys = sorted(value.keys())
        return (
            "{"
            + ",".join(
                '"%s":%s' % (_escape_canonical_json_string(str(key)), _canonicalize_tool_input(value[key]))
                for key in keys
            )
            + "}"
        )
    raise ToolExecutionError(
        "invalid_payload", f"input contains unsupported type: {type(value).__name__}"
    )


def canonical_input_digest_hex(input_obj: Any) -> str:
    """SHA-256 hex of the canonical input serialization; parity-tested
    against Rust approval::canonical_input_digest."""
    try:
        raw = _canonicalize_tool_input(input_obj).encode("utf-8")
    except UnicodeEncodeError as exc:
        # Real IPC frames cannot carry lone surrogates (valid UTF-8 required),
        # but direct in-process callers can; reject fail-closed with the same
        # code the string validators use. The message must stay ASCII-safe
        # (escaped code point, not the raw character) so the error envelope
        # itself remains frame-encodable (ADR-015 B10 class).
        raise ToolExecutionError(
            "invalid_payload",
            "input is not encodable: code point U+{:04X}".format(
                ord(exc.object[exc.start])
            ),
        ) from exc
    return hashlib.sha256(raw).hexdigest()


def _verify_execution_grant(
    payload: Mapping[str, Any],
    tool: str,
    input_obj: Mapping[str, Any],
    workspace: str,
    session: str,
) -> None:
    grant = payload.get("grant")
    if not isinstance(grant, Mapping):
        raise ToolExecutionError(
            "approval_required",
            f"dangerous tool {tool} requires a Rust execution grant",
        )
    for key in _GRANT_STRING_FIELDS:
        value = grant.get(key)
        if not isinstance(value, str) or not value:
            raise ToolExecutionError("invalid_payload", f"grant.{key} must be a non-empty string")
    expires = grant.get("expires_at_unix_ms")
    if isinstance(expires, bool) or not isinstance(expires, (int, float)) or expires <= 0:
        raise ToolExecutionError(
            "invalid_payload", "grant.expires_at_unix_ms must be a positive number"
        )
    outer_grant_id = payload.get("grant_id")
    if outer_grant_id is not None and outer_grant_id != grant["grant_id"]:
        raise ToolExecutionError(
            "invalid_payload", "grant_id must match the grant envelope"
        )
    if grant["tool"] != tool:
        raise ToolExecutionError(
            "approval_operation_mismatch",
            "grant was issued for a different tool",
        )
    if grant["workspace"] != workspace:
        raise ToolExecutionError(
            "approval_workspace_mismatch",
            "grant was issued for a different workspace",
        )
    if grant["session"] != session:
        raise ToolExecutionError(
            "approval_session_mismatch",
            "grant was issued for a different session",
        )
    if grant["input_digest"] != canonical_input_digest_hex(input_obj):
        raise ToolExecutionError(
            "approval_arguments_mismatch",
            "grant input digest does not match the tool input",
        )
    now_ms = int(time.time() * 1000)
    if expires <= now_ms:
        raise ToolExecutionError("approval_grant_expired", "execution grant expired")
    with _consumed_grants_lock:
        if grant["grant_id"] in _consumed_grants:
            raise ToolExecutionError(
                "approval_grant_replayed", "execution grant was already used"
            )
        _consumed_grants[grant["grant_id"]] = int(expires)
        _consumed_grants_order.append(grant["grant_id"])
        while _consumed_grants_order and (
            len(_consumed_grants) > _MAX_CONSUMED_GRANTS
            or _consumed_grants.get(_consumed_grants_order[0], 0) <= now_ms
        ):
            stale = _consumed_grants_order.popleft()
            _consumed_grants.pop(stale, None)


def _resolve_in_workspace(policy: WorkspacePolicy, raw_path: str) -> Path:
    # A malicious sidecar/model can emit a schema-valid `path` string that the OS
    # layer refuses only at use time (embedded NUL raises ValueError from mkdir/
    # write, not OSError), which would escape ToolExecutionError handling and kill
    # the sidecar process. Reject the whole class here, before any filesystem call.
    if "\x00" in raw_path:
        raise ToolExecutionError("invalid_payload", "path contains an embedded null character")
    # A lone UTF-16 surrogate survives JSON decoding and the envelope check, but the
    # resolved path is echoed back in the response payload, where frame encoding then
    # raises IPCProtocolError outside any ToolExecutionError handler and kills the
    # sidecar. Reject it here, alongside the NUL class, before any filesystem call.
    try:
        raw_path.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ToolExecutionError("invalid_payload", f"path is not encodable: {exc}") from exc
    try:
        candidate = Path(raw_path)
        if not candidate.is_absolute():
            candidate = Path(policy.canonical_path) / candidate
        return policy.validate_path(candidate)
    except WorkspacePolicyError as exc:
        raise ToolExecutionError("policy_blocked", str(exc)) from exc
    except ValueError as exc:
        raise ToolExecutionError("invalid_payload", f"path is not usable: {exc}") from exc


def _files_read(policy: WorkspacePolicy, tool: str, input_obj: Mapping[str, Any]) -> dict[str, Any]:
    target = _resolve_in_workspace(policy, _require_str(input_obj, "path"))
    if not target.is_file():
        raise ToolExecutionError("invalid_payload", "path is not an existing file")
    try:
        size = target.stat().st_size
    except OSError as exc:
        raise ToolExecutionError("internal_error", f"read failed: {exc}") from exc
    if size > MAX_TOOL_FILE_BYTES:
        raise ToolExecutionError("payload_too_large", "file exceeds the readable size limit")
    try:
        content = target.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ToolExecutionError("invalid_payload", "file is not valid utf-8") from exc
    except OSError as exc:
        raise ToolExecutionError("internal_error", f"read failed: {exc}") from exc
    return {"tool": tool, "path": str(target), "content": content, "size_bytes": size}


def _files_list(policy: WorkspacePolicy, tool: str, input_obj: Mapping[str, Any]) -> dict[str, Any]:
    target = _resolve_in_workspace(policy, _require_str(input_obj, "path"))
    if not target.is_dir():
        raise ToolExecutionError("invalid_payload", "path is not an existing directory")
    entries: list[dict[str, Any]] = []
    skipped_unencodable = 0
    try:
        for child in sorted(target.iterdir(), key=lambda p: p.name):
            # An on-disk name carrying a lone surrogate cannot be encoded into the
            # response frame; emitting it would raise IPCProtocolError outside any
            # ToolExecutionError handler and kill the sidecar, making the directory
            # permanently unlistable. Such names are also unaddressable, because the
            # path guard rejects them on every subsequent call, so they are skipped
            # and reported as a count instead.
            try:
                child.name.encode("utf-8")
            except UnicodeEncodeError:
                skipped_unencodable += 1
                continue
            entries.append({"name": child.name, "is_dir": child.is_dir()})
    except OSError as exc:
        raise ToolExecutionError("internal_error", f"list failed: {exc}") from exc
    return {
        "tool": tool,
        "path": str(target),
        "entries": entries,
        "skipped_unencodable": skipped_unencodable,
    }


def _files_write(policy: WorkspacePolicy, tool: str, input_obj: Mapping[str, Any]) -> dict[str, Any]:
    target = _resolve_in_workspace(policy, _require_str(input_obj, "path"))
    content = input_obj.get("content")
    if not isinstance(content, str):
        raise ToolExecutionError("invalid_payload", "content must be a string")
    try:
        # A lone UTF-16 surrogate survives JSON decoding and the IPC envelope check,
        # but raises UnicodeEncodeError (a ValueError subclass) here. Outside a guard
        # it escapes ToolExecutionError handling and kills the sidecar, exactly like
        # the embedded-NUL path class.
        encoded = content.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ToolExecutionError("invalid_payload", f"content is not encodable: {exc}") from exc
    if len(encoded) > MAX_TOOL_FILE_BYTES:
        raise ToolExecutionError("invalid_payload", "content exceeds the writable size limit")
    # A resolved Path is not an authorization handle: an attacker can replace a
    # missing parent with a link between validation and mkdir/write. Python has
    # no portable Windows handle-relative, no-reparse writer, so fail closed
    # rather than retaining a workspace-escape primitive. Tool execution is
    # feature-disabled at the control plane; a later enablement must provide a
    # tested platform-specific secure write primitive first.
    raise ToolExecutionError(
        "feature_disabled",
        "files.write is unavailable until secure no-reparse writes are implemented",
    )


def _files_create_folder(
    policy: WorkspacePolicy, tool: str, input_obj: Mapping[str, Any]
) -> dict[str, Any]:
    _require_str(input_obj, "path")
    # Path resolution is not an authorization handle. A junction can replace a
    # component after validation and before mkdir on Windows, so this operation
    # must remain unavailable until a handle-relative no-reparse primitive is
    # implemented and covered by platform-specific tests.
    raise ToolExecutionError(
        "feature_disabled",
        "files.create_folder is unavailable until secure no-reparse folder creation is implemented",
    )


def _files_delete(policy: WorkspacePolicy, tool: str, input_obj: Mapping[str, Any]) -> dict[str, Any]:
    _require_str(input_obj, "path")
    # Recursive delete has the same validation/use race as writes and folder
    # creation. Fail closed rather than accepting a workspace escape primitive.
    raise ToolExecutionError(
        "feature_disabled",
        "files.delete is unavailable until secure no-reparse deletion is implemented",
    )


_COMPUTER_USE_RESULT_SCHEMA = "computer_use.result.v1"
_PENDING_COMPUTER_USE_STATUSES = frozenset({"launch_pending", "awaiting_observation", "pending"})
_TERMINAL_COMPUTER_USE_STATUSES = frozenset({"completed", "failed", "blocked", "unavailable", "cancelled"})


_VERIFICATION_ENUM = frozenset({"verified", "pending", "failed", "not_applicable"})


def _normalize_computer_use_result(
    raw: Mapping[str, Any],
    *,
    action: str,
    request_id: str = "",
    action_id: str = "",
) -> dict[str, Any]:
    """Normalize legacy real-action results without hiding pending or failures.

    Existing real_actions functions intentionally keep their compact public shape.
    The sidecar boundary adds one stable envelope so Rust and UI do not infer
    terminal success from ``ok`` alone. In particular, launch_pending is never
    converted into PASS just because the shell broker accepted the request.

    Verification semantics (acceptance finding P2): a bare legacy ``ok=true``
    never earns ``verified`` — only an explicit backend postcondition check
    (e.g. window readiness) may claim it. Successes without verification
    evidence are marked ``not_applicable`` (the action's own execution report
    is the result; no independent postcondition applies), so no protocol
    consumer can read "verified" without a basis.
    """
    result = dict(raw)
    raw_status = str(result.get("status") or "").strip().lower()
    verification = str(result.get("verification") or "").strip().lower()
    pending = raw_status in _PENDING_COMPUTER_USE_STATUSES or verification == "pending"

    if pending:
        status = "launch_pending" if raw_status in {"", "executed", "simulated"} else raw_status
        terminal = False
        succeeded = False
    elif raw_status in {"executed", "verified", "success", "completed"} and result.get("ok") is True:
        status = "completed"
        terminal = True
        succeeded = True
    elif raw_status == "cancelled":
        status = "cancelled"
        terminal = True
        succeeded = False
    elif result.get("status") in {"blocked", "requires_confirmation"} or result.get("blocked") is True:
        status = "blocked"
        terminal = True
        succeeded = False
    elif result.get("ok") is True:
        status = "completed"
        terminal = True
        succeeded = True
    else:
        status = "unavailable" if raw_status in {"", "unsupported"} else "failed"
        terminal = True
        succeeded = False

    if verification in _VERIFICATION_ENUM:
        normalized_verification = verification
    elif pending:
        normalized_verification = "pending"
    elif succeeded:
        # Legacy ok=true without an explicit postcondition report: executed,
        # but never auto-"verified".
        normalized_verification = "not_applicable"
    else:
        normalized_verification = "failed"

    normalized: dict[str, Any] = {
        **result,
        "schema_version": _COMPUTER_USE_RESULT_SCHEMA,
        "action": action,
        "status": status,
        "terminal": terminal,
        "succeeded": succeeded,
        "verification": normalized_verification,
        "execution": result,
    }
    if request_id:
        normalized["request_id"] = request_id
    if action_id:
        normalized["action_id"] = action_id
    return normalized


def _trace_tool_result(action: str, result: Mapping[str, Any]) -> None:
    """Env-gated one-line trace of computer_use results (see sidecar runtime).

    Records only the outcome fields — never text payloads or screenshots.
    """
    trace_path = os.environ.get("LOCALCOMET_TOOLCALL_TRACE", "").strip()
    if not trace_path:
        return
    try:
        reason = str(result.get("reason") or result.get("error") or "")[:140].replace("\t", " ").replace("\n", " ")
        with open(trace_path, "a", encoding="utf-8") as trace:
            trace.write(
                f"{time.strftime('%Y-%m-%dT%H:%M:%S')}\tresult\t{action}\t"
                f"status={result.get('status')}\tok={result.get('ok')}\t"
                f"succeeded={result.get('succeeded')}\tverification={result.get('verification')}\t"
                f"reason={reason}\n"
            )
    except OSError:
        pass


def _execute_real_action_bounded(execute_real_action, dispatched: dict[str, Any], kind: str):
    """Bound only GUI app launch; other actions retain their normal semantics."""
    if kind != "open_app":
        return execute_real_action(dispatched, simulate=False)

    result_queue = queue.Queue(maxsize=1)

    def worker():
        try:
            result_queue.put((True, execute_real_action(dispatched, simulate=False)))
        except BaseException as exc:
            result_queue.put((False, exc))

    thread = threading.Thread(target=worker, name="computer-use-real-action", daemon=True)
    thread.start()
    thread.join(timeout=5.0)
    if thread.is_alive():
        return {
            "ok": True,
            "status": "launch_pending",
            "verification": "pending",
            "mode": "computer_use_real_open_app_pending",
            "app": dispatched.get("target", ""),
            "result": "Команда запуска передана приложению.",
        }

    succeeded, value = result_queue.get_nowait()
    if not succeeded:
        raise ToolExecutionError("internal_error", f"computer_use backend failed: {value}")
    return value


def _computer_use(
    policy: WorkspacePolicy | None,
    tool: str,
    input_obj: Mapping[str, Any],
    *,
    request_id: str = "",
    action_id: str = "",
) -> dict[str, Any]:
    """Real computer_use dispatch (delegation).

    The local model calls `computer_use` with a high-level `action` string.
    We delegate to the already-hardened `computer_use_real_actions_ru` module
    (allowlisted apps, blocked goals, clipboard/keyboard guards). The action
    field carries a normalized action key; optional `text`/`target` carry the
    payload. We intentionally do NOT accept raw OS shell commands here.

    This keeps Desktop Control Plane as the sole approval boundary (INV-APPROVAL-001)
    and WorkspacePolicy as the confinement boundary — computer_use is dangerous
    and must still go through approval, but does not escape the sidecar process
    lifetime.
    """
    # Normalize inputs — reuse _reject_unrenderable for text safety.
    action_raw = input_obj.get("action", "")
    if not isinstance(action_raw, str) or not action_raw.strip():
        raise ToolExecutionError("invalid_payload", "action must be a non-empty string")
    _reject_unrenderable(action_raw, "action")
    action = action_raw.strip().lower()

    # Optional fields
    text_val = input_obj.get("text", "")
    if text_val is not None and not isinstance(text_val, str):
        raise ToolExecutionError("invalid_payload", "text must be a string")
    if isinstance(text_val, str) and text_val:
        _reject_unrenderable(text_val, "text")

    coordinate = input_obj.get("coordinate")
    if coordinate is not None and not isinstance(coordinate, list):
        raise ToolExecutionError("invalid_payload", "coordinate must be an array")

    target_val = input_obj.get("target", "")
    if target_val is not None and not isinstance(target_val, str):
        raise ToolExecutionError("invalid_payload", "target must be a string")
    target = str(target_val or "").strip()
    url_val = input_obj.get("url", "")
    if url_val is not None and not isinstance(url_val, str):
        raise ToolExecutionError("invalid_payload", "url must be a string")
    url = str(url_val or "").strip()
    if target:
        _reject_unrenderable(target, "target")
    if not target and action in ("open_app", "open_folder") and isinstance(text_val, str):
        target = text_val.strip()

    # Canonical bounded wait (seconds, 0.1..=30.0): the same field name and
    # range the Rust schema and the intent parser use.
    goal_val = input_obj.get("goal", "")
    if goal_val is not None and not isinstance(goal_val, str):
        raise ToolExecutionError("invalid_payload", "goal must be a string")
    goal = str(goal_val or "").strip()
    if goal:
        _reject_unrenderable(goal, "goal")
        if len(goal) > 1200:
            raise ToolExecutionError("invalid_payload", "goal exceeds 1200 chars")

    max_steps_val = input_obj.get("max_steps", 6)
    if isinstance(max_steps_val, bool) or not isinstance(max_steps_val, int):
        raise ToolExecutionError("invalid_payload", "max_steps must be an integer")
    if not (1 <= max_steps_val <= 8):
        raise ToolExecutionError("invalid_payload", "max_steps must be within 1..8")

    seconds_val = input_obj.get("seconds")
    if seconds_val is not None:
        if isinstance(seconds_val, bool) or not isinstance(seconds_val, (int, float)):
            raise ToolExecutionError("invalid_payload", "seconds must be a number")
        if not (0.1 <= float(seconds_val) <= 30.0):
            raise ToolExecutionError("invalid_payload", "seconds must be within 0.1..30.0")

    # Explicit allowlist of delegated actions — no open-ended dispatch.
    # Anything outside this is a deterministic error, not a side effect.
    ALLOWED_ACTIONS = {
        "open_app",
        "open_folder",
        "open_url",
        "click",
        "double_click",
        "type",
        "paste",
        "key",
        "hotkey",
        "scroll",
        "drag",
        "wait",
        "screenshot",
        "task",
    }
    if action not in ALLOWED_ACTIONS:
        raise ToolExecutionError("invalid_payload", f"unsupported computer_use action: {action}")

    try:
        from modules.computer_use_real_actions_ru import execute_real_action
    except Exception as exc:
        raise ToolExecutionError("internal_error", f"computer_use backend unavailable: {exc}") from exc

    # Map normalized action to the real_actions module's action kinds.
    kind_map = {
        "open_app": "open_app",
        "open_folder": "open_folder",
        "open_url": "open_url",
        "click": "click_element",
        "double_click": "double_click_element",
        "type": "paste_text",
        "paste": "paste_text",
        "key": "press_key",
        "hotkey": "hotkey",
        "scroll": "scroll",
        "drag": "drag",
        "wait": "wait_for_window",
        "screenshot": "screenshot",
        "task": "task",
    }
    kind = kind_map[action]
    if action == "open_url":
        # Browser navigation is host-broker-only. Never let a malformed or
        # direct sidecar call fall back to an interactive-desktop launcher.
        raise ToolExecutionError(
            "feature_disabled",
            "computer_use.open_url requires the host broker",
        )

    dispatched: dict[str, Any] = {"kind": kind, "target": target}
    if action == "task":
        if not goal:
            raise ToolExecutionError("invalid_payload", "task action requires a non-empty goal")
        dispatched["goal"] = goal
        dispatched["max_steps"] = max_steps_val
    if url:
        dispatched["url"] = url

    if text_val:
        dispatched["text"] = text_val
    if action in ("key", "hotkey") and text_val:
        dispatched["key"] = text_val
        dispatched["keys"] = [k.strip() for k in text_val.split("+") if k.strip()]
    if coordinate is not None:
        dispatched["coordinate"] = coordinate
    if action == "wait" and seconds_val is not None:
        dispatched["seconds"] = float(seconds_val)
    # Caller-provided coordinate is treated as advisory — real click planning
    # is delegated to computer_use_click_planner_ru via the backend.

    result = _execute_real_action_bounded(execute_real_action, dispatched, kind)
    result = _normalize_computer_use_result(
        result,
        action=action,
        request_id=request_id,
        action_id=action_id,
    )
    # The digest is public correlation evidence, not grant material: it lets
    # the UI/harness prove that the executed action corresponds to the exact
    # canonical input without exposing token/workspace/session secrets.
    input_digest = canonical_input_digest_hex(input_obj)
    result["input_digest"] = input_digest
    execution = result.get("execution")
    if isinstance(execution, Mapping):
        result["execution"] = {**execution, "input_digest": input_digest}

    # Normalize sidecar response shape — always include tool identity.
    result.setdefault("tool", tool)
    _trace_tool_result(action, result)
    return result


# ── web.search / web.fetch ───────────────────────────────────────
# Guarded, rate-limited, no eval. search = DuckDuckGo HTML scrape (no key).
# fetch = GET with 10kB limit + html strip + MAX_FILE_BYTES guard.
# Both share a tiny in-memory cache so repeated calls don't hammer the net.
import http.client
import ipaddress
import socket
import urllib.parse
import urllib.request
import html as _html

_web_cache: dict[str, tuple[float, str]] = {}
_WEB_CACHE_TTL = 600.0  # 10 min
_MAX_WEB_RESULTS = 5
_MAX_FETCH_BYTES = 10 * 1024
_ALLOWED_FETCH_SCHEMES = ("https://", "http://")

def _web_cache_get(key: str) -> str | None:
    import time
    ent = _web_cache.get(key)
    if ent and (time.time() - ent[0]) < _WEB_CACHE_TTL:
        return ent[1]
    return None

def _web_cache_put(key: str, val: str) -> None:
    import time
    # cap cache to 50 entries — cheap LRU
    if len(_web_cache) >= 50:
        oldest = min(_web_cache.items(), key=lambda kv: kv[1][0])[0]
        _web_cache.pop(oldest, None)
    _web_cache[key] = (time.time(), val)

def _strip_html(text: str) -> str:
    # minimal sanitizer: strip tags, unescape entities, collapse whitespace
    import re
    text = re.sub(r"<script[^>]*>.*?</script>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = _html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:8192]

def _web_search(policy: WorkspacePolicy, tool: str, input_obj) -> dict:
    query = input_obj.get("query")
    if not isinstance(query, str) or not query.strip():
        raise ToolExecutionError("invalid_payload", "query must be a non-empty string")
    _reject_unrenderable(query, "query")
    if len(query) > 200:
        raise ToolExecutionError("invalid_payload", "query exceeds 200 chars")
    cached = _web_cache_get(f"s:{query.strip().lower()}")
    if cached is not None:
        return {"tool": tool, "query": query, "results": cached, "cached": True}
    # DuckDuckGo lite HTML — no API key, single GET
    import urllib.request, urllib.parse, re
    q = urllib.parse.quote_plus(query.strip())
    url = f"https://lite.duckduckgo.com/lite/?q={q}"
    req = urllib.request.Request(url, headers={"User-Agent": "LocalComet/6.84 web.search"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception as exc:
        raise ToolExecutionError("internal_error", f"web.search fetch failed: {exc}") from exc
    # parse: lite DDG has <a href="URL">Title</a> + snippet
    results = []
    for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>([^<]+)</a>.*?<td[^>]*>([^<]{20,400})</td>', html, re.S | re.I):
        href, title, snippet = m.groups()
        if href.startswith("/") or "duckduckgo" in href:
            continue
        results.append({"url": href[:500], "title": _strip_html(title)[:200], "snippet": _strip_html(snippet)[:300]})
        if len(results) >= _MAX_WEB_RESULTS:
            break
    if not results:
        results = [{"url": url, "title": "No results parsed", "snippet": "Try a different query or use web.fetch with a direct URL."}]
    out = __import__("json").dumps(results, ensure_ascii=False)
    _web_cache_put(f"s:{query.strip().lower()}", out)
    return {"tool": tool, "query": query, "results": results, "cached": False}

def _resolve_public_fetch_target(url: str) -> tuple[urllib.parse.ParseResult, str]:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ToolExecutionError("invalid_payload", "url must use http(s) with a hostname and no credentials")
    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError as exc:
        raise ToolExecutionError("invalid_payload", "url has an invalid port") from exc
    if port not in {80, 443}:
        raise ToolExecutionError("policy_denied", "web.fetch only permits standard HTTP(S) ports")
    host = parsed.hostname
    try:
        candidate_ips = {ipaddress.ip_address(host)}
    except ValueError:
        try:
            infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
        except OSError as exc:
            raise ToolExecutionError("invalid_payload", f"unable to resolve URL host: {exc}") from exc
        candidate_ips = {ipaddress.ip_address(info[4][0]) for info in infos}
    if not candidate_ips or any(
        ip.is_loopback
        or ip.is_private
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_unspecified
        or ip.is_multicast
        for ip in candidate_ips
    ):
        raise ToolExecutionError(
            "policy_denied",
            "web.fetch does not allow private, loopback, link-local, reserved, or multicast hosts",
        )
    # The selected address is used directly below, so a hostile DNS answer cannot
    # rebind the connection after validation to an internal address.
    return parsed, str(sorted(candidate_ips, key=lambda item: (item.version, int(item)))[0])



class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class _PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, host: str, *, connect_ip: str, **kwargs) -> None:
        self._connect_ip = connect_ip
        super().__init__(host, **kwargs)

    def connect(self) -> None:
        self.sock = socket.create_connection((self._connect_ip, self.port), self.timeout, self.source_address)


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host: str, *, connect_ip: str, server_hostname: str, **kwargs) -> None:
        self._connect_ip = connect_ip
        self._server_hostname = server_hostname
        super().__init__(host, **kwargs)

    def connect(self) -> None:
        self.sock = socket.create_connection((self._connect_ip, self.port), self.timeout, self.source_address)
        self.sock = self._context.wrap_socket(self.sock, server_hostname=self._server_hostname)


class _PinnedHTTPHandler(urllib.request.HTTPHandler):
    def __init__(self, connect_ip: str) -> None:
        super().__init__()
        self._connect_ip = connect_ip

    def http_open(self, req):
        return self.do_open(
            lambda host, **kwargs: _PinnedHTTPConnection(host, connect_ip=self._connect_ip, **kwargs),
            req,
        )


class _PinnedHTTPSHandler(urllib.request.HTTPSHandler):
    def __init__(self, connect_ip: str, server_hostname: str) -> None:
        super().__init__()
        self._connect_ip = connect_ip
        self._server_hostname = server_hostname

    def https_open(self, req):
        return self.do_open(
            lambda host, **kwargs: _PinnedHTTPSConnection(
                host,
                connect_ip=self._connect_ip,
                server_hostname=self._server_hostname,
                **kwargs,
            ),
            req,
        )


def _pinned_fetch_opener(connect_ip: str, server_hostname: str):
    # ProxyHandler({}) deliberately ignores HTTP(S)_PROXY and NO_PROXY inherited
    # from the desktop. The connection is pinned to the checked public address.
    return urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        _NoRedirectHandler(),
        _PinnedHTTPHandler(connect_ip),
        _PinnedHTTPSHandler(connect_ip, server_hostname),
    )

def _web_fetch(policy: WorkspacePolicy, tool: str, input_obj) -> dict:
    url = input_obj.get("url")
    if not isinstance(url, str) or not url.strip():
        raise ToolExecutionError("invalid_payload", "url must be a non-empty string")
    _reject_unrenderable(url, "url")
    url = url.strip()
    parsed, connect_ip = _resolve_public_fetch_target(url)
    if not url.startswith(_ALLOWED_FETCH_SCHEMES):
        raise ToolExecutionError("invalid_payload", "url must start with https:// or http://")
    if len(url) > 2000:
        raise ToolExecutionError("invalid_payload", "url exceeds 2000 chars")
    cached = _web_cache_get(f"f:{url}")
    if cached is not None:
        return {"tool": tool, "url": url, "content": cached, "cached": True}
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "LocalComet/6.84 web.fetch"})
    try:
        with _pinned_fetch_opener(connect_ip, parsed.hostname).open(req, timeout=12) as resp:
            ctype = (resp.headers.get("Content-Type") or "").lower()
            if "text/html" not in ctype and "text/plain" not in ctype and "application/json" not in ctype and "application/xml" not in ctype and "text/" not in ctype:
                raise ToolExecutionError("invalid_payload", f"unsupported content-type: {ctype[:80]}")
            raw = resp.read(_MAX_FETCH_BYTES + 1)
            if len(raw) > _MAX_FETCH_BYTES:
                raw = raw[:_MAX_FETCH_BYTES]
            text = raw.decode("utf-8", errors="replace")
    except ToolExecutionError:
        raise
    except Exception as exc:
        raise ToolExecutionError("internal_error", f"web.fetch failed: {exc}") from exc
    if len(text.encode("utf-8")) > MAX_TOOL_FILE_BYTES:
        text = text[:MAX_TOOL_FILE_BYTES]
    content = _strip_html(text) if "<" in text else text[:8192]
    _web_cache_put(f"f:{url}", content)
    return {"tool": tool, "url": url, "content": content, "cached": False}


def _shell(
    policy: WorkspacePolicy, tool: str, input_obj: Mapping[str, Any]
) -> dict[str, Any]:
    """Stub for shell — intentionally not executable in Desktop sidecar.

    Shell execution would require a separate allowlisted subprocess path with
    explicit approval + workspace confinement + no-sandbox-escape guarantees.
    Until that is designed and tested, Desktop returns a deterministic error
    rather than executing anything.

    The tool remains registered so the model can discover it, but invocation
    is rejected at the handler — distinct from the dispatcher-level
    \"not implemented\" gate.
    """
    raise ToolExecutionError(
        "unsupported_method",
        "shell is registered but not executable in this build (requires explicit allowlisted subprocess path)",
    )


def _skills_invoke(policy: WorkspacePolicy, tool: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    from modules.skills.skills_invoker import SkillInvokeError, invoke_skill

    skill_id = _require_str(payload, "skill_id")
    arguments = payload.get("arguments")
    if arguments is not None and not isinstance(arguments, (Mapping, list)):
        raise ToolExecutionError(
            "invalid_payload",
            "arguments must be an object or array",
        )
    requested_permissions = payload.get("permissions")
    if (
        not isinstance(requested_permissions, list)
        or not requested_permissions
        or any(not isinstance(permission, str) or not permission for permission in requested_permissions)
        or len(set(requested_permissions)) != len(requested_permissions)
    ):
        raise ToolExecutionError(
            "invalid_payload",
            "permissions must be a non-empty list of unique strings",
        )
    try:
        return invoke_skill(skill_id, arguments, requested_permissions)
    except SkillInvokeError as exc:
        raise ToolExecutionError(exc.code, exc.message) from exc


def _computer_use_action_requires_grant(input_obj: Mapping[str, Any]) -> bool:
    action = input_obj.get("action")
    return not isinstance(action, str) or action.strip().lower() not in COMPUTER_USE_READ_ONLY_ACTIONS


def execute_tool_call(payload: Mapping[str, Any]) -> dict[str, Any]:
    tool = _require_str(payload, "tool")
    workspace = _require_str(payload, "workspace")
    workspace_digest = _require_str(payload, "workspace_digest")
    session = _require_str(payload, "session")
    if tool not in SUPPORTED_TOOLS:
        raise ToolExecutionError("unsupported_method", f"unsupported tool: {tool}")
    input_obj = payload.get("input")
    if not isinstance(input_obj, Mapping):
        raise ToolExecutionError("invalid_payload", "input must be an object")
    requires_grant = tool in DANGEROUS_TOOLS
    if tool == "computer_use":
        requires_grant = _computer_use_action_requires_grant(input_obj)
    if requires_grant:
        # Downstream defense-in-depth: the Rust boundary already consumed the
        # one-time token for guarded/dangerous actions; this boundary re-verifies
        # the grant material before any action runs. Rust's ReadOnly Computer Use
        # subset is intentionally exempt and cannot spawn, type, click, or
        # navigate because those actions remain grant-bound above.
        _verify_execution_grant(payload, tool, input_obj, workspace, session)
    elif isinstance(payload.get("grant"), Mapping):
        # A grant presented for a guarded tool must still be valid.
        _verify_execution_grant(payload, tool, input_obj, workspace, session)
    if tool == "computer_use":
        return _computer_use(
            None,
            tool,
            input_obj,
            request_id=str(payload.get("request_id") or "").strip(),
            action_id=str(payload.get("action_id") or "").strip(),
        )
    try:
        policy = WorkspacePolicy(workspace, workspace_digest, session)
    except WorkspacePolicyError as exc:
        raise ToolExecutionError("policy_blocked", str(exc)) from exc
    if tool == "files.read":
        return _files_read(policy, tool, input_obj)
    if tool == "files.list":
        return _files_list(policy, tool, input_obj)
    if tool == "files.write":
        return _files_write(policy, tool, input_obj)
    if tool == "files.create_folder":
        return _files_create_folder(policy, tool, input_obj)
    if tool == "files.delete":
        return _files_delete(policy, tool, input_obj)
    
    if tool == "shell":
        return _shell(policy, tool, input_obj)
    if tool == "web.search":
        return _web_search(policy, tool, input_obj)
    if tool == "web.fetch":
        return _web_fetch(policy, tool, input_obj)
    if tool == "skills.invoke":
        return _skills_invoke(policy, tool, input_obj)
    if tool == "system.time":
        return _system_time(policy, tool, input_obj)
    raise ToolExecutionError(
        "unsupported_method",
        f"tool not implemented: {tool}",
    )

def _system_time(policy: WorkspacePolicy, tool: str, input_obj) -> dict:
    import datetime
    now = datetime.datetime.now().astimezone()
    return {
        "tool": tool,
        "time": now.isoformat(),
        "human_readable": now.strftime("%Y-%m-%d %H:%M:%S %Z"),
    }
