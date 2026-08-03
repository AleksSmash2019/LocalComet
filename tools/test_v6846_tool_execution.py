#!/usr/bin/env python
"""Block 2 tests (ADR-013): sidecar tool execution with workspace confinement.

Covers modules/tool_execution_ru.py and the tool.call routing in
desktop_sidecar_runtime_ru.py. Security focus (R4): read-only and mutating
files.* calls are confined to the confirmed workspace; traversal and symlink
escape are rejected because resolution happens before the containment check.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.desktop_ipc_contract_ru import encode_frame, make_request  # noqa: E402
from modules.desktop_sidecar_runtime_ru import DesktopSidecarRuntime  # noqa: E402
from modules.tool_execution_ru import (  # noqa: E402
    MAX_TOOL_FILE_BYTES,
    ToolExecutionError,
    execute_tool_call,
)
from modules.workspace_policy import workspace_digest  # noqa: E402


def _payload(workspace: str, tool: str, input_obj: dict) -> dict:
    return {
        "tool": tool,
        "input": input_obj,
        "workspace": workspace,
        "workspace_digest": workspace_digest(workspace),
        "session": "s" * 64,
    }


class ToolExecutionConfinementTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="lc_tool_exec_")
        self.workspace = str(Path(self._tmp.name).resolve())
        self.outside = tempfile.TemporaryDirectory(prefix="lc_tool_outside_")
        self.outside_path = str(Path(self.outside.name).resolve())

    def tearDown(self) -> None:
        self._tmp.cleanup()
        self.outside.cleanup()

    def test_files_read_inside_workspace_succeeds(self) -> None:
        target = Path(self.workspace) / "notes.txt"
        target.write_text("привет", encoding="utf-8")
        result = execute_tool_call(_payload(self.workspace, "files.read", {"path": "notes.txt"}))
        self.assertEqual(result["tool"], "files.read")
        self.assertEqual(result["content"], "привет")
        self.assertEqual(result["size_bytes"], len("привет".encode("utf-8")))

    def test_files_read_absolute_path_outside_workspace_is_blocked(self) -> None:
        secret = Path(self.outside_path) / "secret.txt"
        secret.write_text("x", encoding="utf-8")
        with self.assertRaises(ToolExecutionError) as ctx:
            execute_tool_call(_payload(self.workspace, "files.read", {"path": str(secret)}))
        self.assertEqual(ctx.exception.code, "policy_blocked")

    def test_files_read_traversal_escape_is_blocked(self) -> None:
        secret = Path(self.outside_path) / "secret.txt"
        secret.write_text("x", encoding="utf-8")
        relative = f"../{Path(self.outside_path).name}/secret.txt"
        with self.assertRaises(ToolExecutionError) as ctx:
            execute_tool_call(_payload(self.workspace, "files.read", {"path": relative}))
        self.assertEqual(ctx.exception.code, "policy_blocked")

    def test_files_read_symlink_escape_is_blocked(self) -> None:
        secret = Path(self.outside_path) / "secret.txt"
        secret.write_text("x", encoding="utf-8")
        link = Path(self.workspace) / "link.txt"
        try:
            os.symlink(secret, link)
        except OSError as exc:
            self.skipTest(f"symlink creation not permitted in this environment: {exc}")
        with self.assertRaises(ToolExecutionError) as ctx:
            execute_tool_call(_payload(self.workspace, "files.read", {"path": "link.txt"}))
        self.assertEqual(ctx.exception.code, "policy_blocked")

    def test_files_write_outside_workspace_is_blocked(self) -> None:
        target = Path(self.outside_path) / "evil.txt"
        with self.assertRaises(ToolExecutionError) as ctx:
            execute_tool_call(
                _payload(self.workspace, "files.write", {"path": str(target), "content": "x"})
            )
        self.assertEqual(ctx.exception.code, "policy_blocked")
        self.assertFalse(target.exists())

    def test_files_write_is_fail_closed_until_secure_no_reparse_writer_exists(self) -> None:
        target = Path(self.workspace) / "sub" / "out.txt"
        with self.assertRaises(ToolExecutionError) as ctx:
            execute_tool_call(
                _payload(self.workspace, "files.write", {"path": "sub/out.txt", "content": "данные"})
            )
        self.assertEqual(ctx.exception.code, "feature_disabled")
        self.assertFalse(target.exists())

    def test_files_write_oversized_content_is_invalid(self) -> None:
        big = "a" * (MAX_TOOL_FILE_BYTES + 1)
        with self.assertRaises(ToolExecutionError) as ctx:
            execute_tool_call(
                _payload(self.workspace, "files.write", {"path": "big.txt", "content": big})
            )
        self.assertEqual(ctx.exception.code, "invalid_payload")

    def test_files_read_oversized_file_is_payload_too_large(self) -> None:
        target = Path(self.workspace) / "big.bin"
        with target.open("wb") as handle:
            handle.write(b"a" * (MAX_TOOL_FILE_BYTES + 1))
        with self.assertRaises(ToolExecutionError) as ctx:
            execute_tool_call(_payload(self.workspace, "files.read", {"path": "big.bin"}))
        self.assertEqual(ctx.exception.code, "payload_too_large")

    def test_files_delete_and_create_folder_and_list(self) -> None:
        execute_tool_call(_payload(self.workspace, "files.create_folder", {"path": "dir"}))
        self.assertTrue((Path(self.workspace) / "dir").is_dir())
        (Path(self.workspace) / "dir" / "a.txt").write_text("x", encoding="utf-8")
        listing = execute_tool_call(_payload(self.workspace, "files.list", {"path": "dir"}))
        self.assertEqual(listing["entries"], [{"name": "a.txt", "is_dir": False}])
        execute_tool_call(_payload(self.workspace, "files.delete", {"path": "dir"}))
        self.assertFalse((Path(self.workspace) / "dir").exists())

    def test_files_list_outside_workspace_is_blocked(self) -> None:
        with self.assertRaises(ToolExecutionError) as ctx:
            execute_tool_call(_payload(self.workspace, "files.list", {"path": self.outside_path}))
        self.assertEqual(ctx.exception.code, "policy_blocked")

    def test_files_create_folder_outside_workspace_is_blocked(self) -> None:
        target = Path(self.outside_path) / "newdir"
        with self.assertRaises(ToolExecutionError) as ctx:
            execute_tool_call(_payload(self.workspace, "files.create_folder", {"path": str(target)}))
        self.assertEqual(ctx.exception.code, "policy_blocked")
        self.assertFalse(target.exists())

    def test_files_delete_outside_workspace_is_blocked(self) -> None:
        victim = Path(self.outside_path) / "victim.txt"
        victim.write_text("x", encoding="utf-8")
        with self.assertRaises(ToolExecutionError) as ctx:
            execute_tool_call(_payload(self.workspace, "files.delete", {"path": str(victim)}))
        self.assertEqual(ctx.exception.code, "policy_blocked")
        self.assertTrue(victim.exists())

    def test_files_delete_workspace_root_is_rejected(self) -> None:
        with self.assertRaises(ToolExecutionError) as ctx:
            execute_tool_call(_payload(self.workspace, "files.delete", {"path": "."}))
        self.assertEqual(ctx.exception.code, "invalid_payload")
        self.assertTrue(Path(self.workspace).exists())

    def test_unsupported_tool_is_rejected(self) -> None:
        with self.assertRaises(ToolExecutionError) as ctx:
            execute_tool_call(_payload(self.workspace, "files.rename", {"path": "x"}))
        self.assertEqual(ctx.exception.code, "unsupported_method")

    def test_missing_workspace_field_is_invalid(self) -> None:
        with self.assertRaises(ToolExecutionError) as ctx:
            execute_tool_call(
                {"tool": "files.read", "input": {"path": "x"}, "workspace_digest": "d", "session": "s"}
            )
        self.assertEqual(ctx.exception.code, "invalid_payload")


class ToolCallRoutingTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="lc_tool_route_")
        self.workspace = str(Path(self._tmp.name).resolve())
        self.runtime = DesktopSidecarRuntime()
        self.runtime._desktop_hello_seen = True

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_tool_call_is_routed_and_returns_response_envelope(self) -> None:
        (Path(self.workspace) / "hi.txt").write_text("ok", encoding="utf-8")
        request = make_request("req-tool-1", "tool.call", _payload(self.workspace, "files.read", {"path": "hi.txt"}))
        (response,) = self.runtime.handle_message(request)
        self.assertEqual(response["type"], "response")
        self.assertEqual(response["reply_to"], "req-tool-1")
        self.assertEqual(response["payload"]["tool"], "files.read")
        self.assertEqual(response["payload"]["content"], "ok")

    def test_tool_call_confinement_error_returns_error_envelope(self) -> None:
        request = make_request(
            "req-tool-2",
            "tool.call",
            _payload(self.workspace, "files.read", {"path": "../escape.txt"}),
        )
        (response,) = self.runtime.handle_message(request)
        self.assertEqual(response["type"], "error")
        self.assertEqual(response["payload"]["code"], "policy_blocked")

    def test_embedded_null_path_returns_error_envelope_and_keeps_sidecar_alive(self) -> None:
        """ADR-015 B10: a schema-valid path with an embedded NUL must not escape
        ToolExecutionError handling. Before the fix, files.write and
        files.create_folder raised ValueError out of handle_message, which would
        terminate the sidecar process."""
        cases = [
            ("files.write", {"path": "a\x00b.txt", "content": "x"}),
            ("files.create_folder", {"path": "d\x00ir"}),
            ("files.read", {"path": "a\x00b.txt"}),
            ("files.list", {"path": ".\x00"}),
            ("files.delete", {"path": "a\x00b.txt"}),
        ]
        for index, (tool, input_obj) in enumerate(cases):
            with self.subTest(tool=tool):
                request = make_request(
                    f"req-tool-nul-{index}",
                    "tool.call",
                    _payload(self.workspace, tool, input_obj),
                )
                (response,) = self.runtime.handle_message(request)
                self.assertEqual(response["type"], "error")
                self.assertEqual(response["payload"]["code"], "invalid_payload")
        # The sidecar runtime is still usable after the hostile batch.
        (Path(self.workspace) / "alive.txt").write_text("ok", encoding="utf-8")
        request = make_request(
            "req-tool-nul-alive",
            "tool.call",
            _payload(self.workspace, "files.read", {"path": "alive.txt"}),
        )
        (response,) = self.runtime.handle_message(request)
        self.assertEqual(response["type"], "response")
        self.assertEqual(response["payload"]["content"], "ok")

    def test_lone_surrogate_path_is_rejected_and_response_frames_stay_encodable(self) -> None:
        """ADR-015 B10 follow-up: a lone surrogate in `path` was echoed back into the
        response payload, where frame encoding raised IPCProtocolError outside any
        ToolExecutionError handler and killed the sidecar."""
        cases = [
            ("files.write", {"path": "x\ud800.txt", "content": "hi"}),
            ("files.read", {"path": "x\ud800.txt"}),
            ("files.create_folder", {"path": "d\ud800"}),
            ("files.delete", {"path": "x\ud800.txt"}),
            ("files.list", {"path": "\ud800"}),
        ]
        for index, (tool, input_obj) in enumerate(cases):
            with self.subTest(tool=tool):
                request = make_request(
                    f"req-tool-surpath-{index}",
                    "tool.call",
                    _payload(self.workspace, tool, input_obj),
                )
                (response,) = self.runtime.handle_message(request)
                self.assertEqual(response["type"], "error")
                self.assertEqual(response["payload"]["code"], "invalid_payload")
                # The error envelope itself must be encodable.
                encode_frame(response)

    def test_surrogate_named_file_on_disk_does_not_break_listing(self) -> None:
        """A file whose on-disk name carries a lone surrogate must not make the
        directory permanently unlistable: emitting the name would fail frame
        encoding and terminate the sidecar."""
        try:
            open(os.path.join(self.workspace, "bad\ud801.txt"), "w").close()
        except (OSError, ValueError, UnicodeEncodeError):
            self.skipTest("filesystem refuses surrogate names")
        (Path(self.workspace) / "good.txt").write_text("ok", encoding="utf-8")
        request = make_request(
            "req-tool-surlist",
            "tool.call",
            _payload(self.workspace, "files.list", {"path": "."}),
        )
        (response,) = self.runtime.handle_message(request)
        self.assertEqual(response["type"], "response")
        encode_frame(response)
        names = [entry["name"] for entry in response["payload"]["entries"]]
        self.assertIn("good.txt", names)
        self.assertGreaterEqual(response["payload"]["skipped_unencodable"], 1)

    def test_lone_surrogate_content_returns_error_envelope_and_keeps_sidecar_alive(self) -> None:
        """ADR-015 B10 follow-up: a lone UTF-16 surrogate survives JSON decoding and
        the IPC envelope check, then raises UnicodeEncodeError (a ValueError
        subclass) from content.encode. Unguarded it escapes _tool_execution_messages
        and terminates the sidecar, the same crash class as the embedded NUL."""
        request = make_request(
            "req-tool-surrogate",
            "tool.call",
            _payload(
                self.workspace,
                "files.write",
                {"path": "surrogate.txt", "content": "\ud800"},
            ),
        )
        (response,) = self.runtime.handle_message(request)
        self.assertEqual(response["type"], "error")
        self.assertEqual(response["payload"]["code"], "invalid_payload")

        # The runtime is still usable afterwards.
        (Path(self.workspace) / "still-alive.txt").write_text("ok", encoding="utf-8")
        request = make_request(
            "req-tool-surrogate-alive",
            "tool.call",
            _payload(self.workspace, "files.read", {"path": "still-alive.txt"}),
        )
        (response,) = self.runtime.handle_message(request)
        self.assertEqual(response["type"], "response")
        self.assertEqual(response["payload"]["content"], "ok")

    def test_hostile_non_path_payload_fields_keep_response_frames_encodable(self) -> None:
        """ADR-015 B10 third follow-up: the first three fixes all guarded values that
        flow through _resolve_in_workspace. `tool`, `workspace`, `workspace_digest`
        and `session` never reach it, yet each is echoed into an error message
        ("unsupported tool: {tool}", "workspace does not exist: {resolved}"). Since
        the outbound frame is serialized with ensure_ascii=False, a lone surrogate in
        any of them raised IPCProtocolError("invalid_json") from encode_frame,
        outside any ToolExecutionError handler -- the same sidecar-termination class.

        Encodability must be asserted with the production encoder: json.dumps with
        the default ensure_ascii=True escapes surrogates and hides the defect.
        """
        hostile = ("\ud800", "\udfff", "\x00", "\x00\ud800")
        fields = ("tool", "workspace", "workspace_digest", "session")
        index = 0
        for field in fields:
            for bad in hostile:
                with self.subTest(field=field, bad=repr(bad)):
                    payload = _payload(self.workspace, "files.read", {"path": "x.txt"})
                    payload[field] = f"files.{bad}" if field == "tool" else f"pre_{bad}_post"
                    request = make_request(
                        f"req-tool-field-{index}", "tool.call", payload
                    )
                    index += 1
                    (response,) = self.runtime.handle_message(request)
                    self.assertEqual(response["type"], "error")
                    self.assertEqual(response["payload"]["code"], "invalid_payload")
                    # Must survive the real outbound encoder, not a lenient one.
                    encode_frame(response)

        # A nested workspace path with a surrogate reaches WorkspacePolicy's
        # "workspace does not exist: {resolved}" template via Path.resolve().
        payload = _payload(self.workspace, "files.read", {"path": "x.txt"})
        payload["workspace"] = str(Path(self.workspace) / "sub_\ud800")
        request = make_request("req-tool-field-wschild", "tool.call", payload)
        (response,) = self.runtime.handle_message(request)
        self.assertEqual(response["type"], "error")
        encode_frame(response)

        # The sidecar is still usable after the hostile batch.
        (Path(self.workspace) / "field-alive.txt").write_text("ok", encoding="utf-8")
        request = make_request(
            "req-tool-field-alive",
            "tool.call",
            _payload(self.workspace, "files.read", {"path": "field-alive.txt"}),
        )
        (response,) = self.runtime.handle_message(request)
        self.assertEqual(response["type"], "response")
        self.assertEqual(response["payload"]["content"], "ok")

    def test_every_tool_survives_hostile_strings_in_every_string_field(self) -> None:
        """Bounded deterministic sweep over {5 tools} x {payload string fields} x
        {hostile strings}: handle_message must never raise, and every returned
        message must survive encode_frame. This is the invariant B10 asserts; the
        per-field tests above pin the specific regressions."""
        hostile = ("\ud800", "\udfff", "\ud83d", "\x00", "\x00\ud800", "\x01\x1f", "\u202e")
        fields = ("tool", "workspace", "workspace_digest", "session", "path", "content")
        (Path(self.workspace) / "seed.txt").write_text("ok", encoding="utf-8")
        index = 0
        for tool in (
            "files.read",
            "files.list",
            "files.write",
            "files.create_folder",
            "files.delete",
        ):
            for field in fields:
                if field == "content" and tool != "files.write":
                    continue
                for bad in hostile:
                    with self.subTest(tool=tool, field=field, bad=repr(bad)):
                        # files.delete with a benign path really deletes, and the
                        # digest is not re-verified here (the sidecar trusts the
                        # control plane for approval), so give mutating tools an
                        # expendable target and keep the liveness file untouched.
                        input_obj = {"path": "expendable.txt"}
                        (Path(self.workspace) / "expendable.txt").write_text(
                            "x", encoding="utf-8"
                        )
                        if tool == "files.write":
                            input_obj["content"] = "hi"
                        payload = _payload(self.workspace, tool, input_obj)
                        if field in ("path", "content"):
                            payload["input"][field] = f"pre_{bad}_post"
                        elif field == "tool":
                            payload["tool"] = f"files.{bad}"
                        else:
                            payload[field] = f"pre_{bad}_post"
                        request = make_request(
                            f"req-tool-sweep-{index}", "tool.call", payload
                        )
                        index += 1
                        for message in self.runtime.handle_message(request):
                            encode_frame(message)

        request = make_request(
            "req-tool-sweep-alive",
            "tool.call",
            _payload(self.workspace, "files.read", {"path": "seed.txt"}),
        )
        (response,) = self.runtime.handle_message(request)
        self.assertEqual(response["type"], "response")
        self.assertEqual(response["payload"]["content"], "ok")


if __name__ == "__main__":
    unittest.main(verbosity=2)
