"""Offline contract tests for independent hidden-desktop UIA observation."""

from __future__ import annotations

import ctypes
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import run_isolated_hidden_desktop_cu as harness  # noqa: E402


class _FakeUser32:
    def __init__(self, *, open_handle=101, set_thread=True):
        self.open_handle = open_handle
        self.set_thread = set_thread
        self.calls = []

    def OpenDesktopW(self, name, flags, inherit, access):
        self.calls.append(("OpenDesktopW", name, flags, inherit, access))
        return self.open_handle

    def SetThreadDesktop(self, handle):
        self.calls.append(("SetThreadDesktop", handle))
        return self.set_thread

    def CloseDesktop(self, handle):
        self.calls.append(("CloseDesktop", handle))
        return True

    def GetWindowThreadProcessId(self, hwnd, process_id):
        ctypes.cast(process_id, ctypes.POINTER(ctypes.c_uint32)).contents.value = 1
        return 11

    def GetThreadDesktop(self, thread_id):
        return 202

    def GetUserObjectInformationW(self, handle, info, buffer, size, needed):
        buffer.value = "LocalCometHiddenCU_test"
        ctypes.cast(needed, ctypes.POINTER(ctypes.c_uint32)).contents.value = len(buffer.value) + 1
        return True


class _FakeControl:
    Name = "LocalComet isolated smoke test."
    ControlTypeName = "DocumentControl"


class _FakeWindow:
    Name = "Безымянный — Блокнот"
    NativeWindowHandle = 777


class _FakeRoot:
    def GetChildren(self):
        return [_FakeWindow()]


class _FakeAuto:
    def GetRootControl(self):
        return _FakeRoot()


class HiddenReaderAttachContractTests(unittest.TestCase):
    def setUp(self):
        harness._hidden_reader_desktop_name = ""
        harness._hidden_reader_desktop_attached = False
        self.old_name = os.environ.get("LC_HIDDEN_DESKTOP_NAME")

    def tearDown(self):
        if self.old_name is None:
            os.environ.pop("LC_HIDDEN_DESKTOP_NAME", None)
        else:
            os.environ["LC_HIDDEN_DESKTOP_NAME"] = self.old_name
        harness._hidden_reader_desktop_name = ""
        harness._hidden_reader_desktop_attached = False

    def test_attach_uses_named_desktop_read_access_only(self):
        os.environ["LC_HIDDEN_DESKTOP_NAME"] = "LocalCometHiddenCU_test"
        fake = _FakeUser32()
        with patch.object(harness, "user32", fake):
            result = harness.attach_reader_to_hidden_desktop()
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["desktop_name"], "LocalCometHiddenCU_test")
        self.assertEqual([call[0] for call in fake.calls], [
            "OpenDesktopW", "SetThreadDesktop", "CloseDesktop",
        ])
        self.assertEqual(fake.calls[0][4], harness.DESKTOP_READOBJECTS | harness.DESKTOP_ENUMERATE)

    def test_reader_fails_closed_when_named_desktop_attach_fails(self):
        with patch.object(harness, "attach_reader_to_hidden_desktop", return_value={
            "ok": False,
            "reason": "OpenDesktopW_failed",
        }), patch.object(_FakeAuto, "GetRootControl", side_effect=AssertionError("scan must not run")):
            result = harness.read_hidden_window_text(_FakeAuto(), "LocalComet isolated smoke test.", timeout=0.01)
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "hidden_uia_desktop_attach_failed")
        self.assertEqual(result["windows_scanned"], 0)
        self.assertFalse(result["desktop_attachment"]["ok"])

    def test_reader_scans_only_after_successful_attach(self):
        os.environ["LC_HIDDEN_DESKTOP_NAME"] = "LocalCometHiddenCU_test"
        fake = _FakeUser32()
        with patch.object(harness, "user32", fake), patch.object(
            harness, "uia_walk", side_effect=lambda _root: [_FakeControl()]
        ):
            result = harness.read_hidden_window_text(_FakeAuto(), "LocalComet isolated smoke test.", timeout=0.01)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["desktop_attachment"]["desktop_name"], "LocalCometHiddenCU_test")
        self.assertEqual(result["source"], "uia_name")
        self.assertEqual(result["windows_scanned"], 1)


if __name__ == "__main__":
    unittest.main()

# Пользовательские данные не подставляются: marker синтетический, Win32 вызовы — mock.
