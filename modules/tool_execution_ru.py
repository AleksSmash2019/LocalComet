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
    ("files.read", "files.list", "files.write", "files.create_folder", "files.delete", "shell", "computer_use", "web.search", "web.fetch")
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


def _computer_use(
    policy: WorkspacePolicy, tool: str, input_obj: Mapping[str, Any]
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

    # Explicit allowlist of delegated actions — no open-ended dispatch.
    # Anything outside this is a deterministic error, not a side effect.
    ALLOWED_ACTIONS = {
        "open_app",
        "open_folder",
        "click",
        "double_click",
        "type",
        "paste",
        "key",
        "hotkey",
        "scroll",
        "wait",
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
        "click": "click_element",
        "double_click": "double_click_element",
        "type": "paste_text",
        "paste": "paste_text",
        "key": "press_key",
        "hotkey": "hotkey",
        "scroll": "scroll",
        "wait": "wait_for_window",
    }
    kind = kind_map[action]

    dispatched: dict[str, Any] = {"kind": kind, "target": input_obj.get("target", "")}
    if text_val:
        dispatched["text"] = text_val
    if action in ("key", "hotkey") and text_val:
        dispatched["key"] = text_val
        dispatched["keys"] = [k.strip() for k in text_val.split("+") if k.strip()]
    if coordinate is not None:
        dispatched["coordinate"] = coordinate
    # Caller-provided coordinate is treated as advisory — real click planning
    # is delegated to computer_use_click_planner_ru via the backend.

    result = execute_real_action(dispatched, simulate=False)
    # Normalize sidecar response shape — always include tool identity.
    result.setdefault("tool", tool)
    result.setdefault("action", action)
    return result


# ── web.search / web.fetch ───────────────────────────────────────
# Guarded, rate-limited, no eval. search = DuckDuckGo HTML scrape (no key).
# fetch = GET with 10kB limit + html strip + MAX_FILE_BYTES guard.
# Both share a tiny in-memory cache so repeated calls don't hammer the net.
import urllib.request, urllib.parse
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

def _web_fetch(policy: WorkspacePolicy, tool: str, input_obj) -> dict:
    url = input_obj.get("url")
    if not isinstance(url, str) or not url.strip():
        raise ToolExecutionError("invalid_payload", "url must be a non-empty string")
    _reject_unrenderable(url, "url")
    url = url.strip()
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
        with urllib.request.urlopen(req, timeout=12) as resp:
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
    if tool == "files.delete":
        return _files_delete(policy, tool, input_obj)
    if tool == "computer_use":
        return _computer_use(policy, tool, input_obj)
    if tool == "shell":
        return _shell(policy, tool, input_obj)
    if tool == "web.search":
        return _web_search(policy, tool, input_obj)
    if tool == "web.fetch":
        return _web_fetch(policy, tool, input_obj)
    raise ToolExecutionError(
        "unsupported_method",
        f"tool not implemented: {tool}",
    )
