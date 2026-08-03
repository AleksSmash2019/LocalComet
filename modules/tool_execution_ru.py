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

import shutil
from pathlib import Path
from typing import Any, Mapping

from modules.workspace_policy import WorkspacePolicy, WorkspacePolicyError

# Maximum bytes for a single file read/write. Bounded by the IPC payload string
# limit (MAX_STRING_CHARS = 1 MiB in desktop_ipc_contract_ru.py), NOT the 4 MiB
# frame: the file content travels as a JSON string value, so it must stay below
# the per-string limit with margin for JSON escaping overhead. No chunking in the
# first release (ADR-013): oversized payloads are rejected.
MAX_TOOL_FILE_BYTES = 1_000_000

SUPPORTED_TOOLS = frozenset(
    ("files.read", "files.list", "files.write", "files.create_folder", "files.delete")
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

    Note for future handlers: rejection must happen before the value can reach a
    message template, which is why this sits in _require_str rather than at each
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
    target = _resolve_in_workspace(policy, _require_str(input_obj, "path"))
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ToolExecutionError("internal_error", f"create_folder failed: {exc}") from exc
    except ValueError as exc:
        raise ToolExecutionError("invalid_payload", f"path is not usable: {exc}") from exc
    return {"tool": tool, "path": str(target)}


def _files_delete(policy: WorkspacePolicy, tool: str, input_obj: Mapping[str, Any]) -> dict[str, Any]:
    target = _resolve_in_workspace(policy, _require_str(input_obj, "path"))
    if target == Path(policy.canonical_path):
        raise ToolExecutionError("invalid_payload", "cannot delete the workspace root")
    if target.is_dir():
        try:
            shutil.rmtree(target)
        except OSError as exc:
            raise ToolExecutionError("internal_error", f"delete failed: {exc}") from exc
    elif target.exists():
        try:
            target.unlink()
        except OSError as exc:
            raise ToolExecutionError("internal_error", f"delete failed: {exc}") from exc
    else:
        raise ToolExecutionError("invalid_payload", "path does not exist")
    return {"tool": tool, "path": str(target)}


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
    return _files_delete(policy, tool, input_obj)
