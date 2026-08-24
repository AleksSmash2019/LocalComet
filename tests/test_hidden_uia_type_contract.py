from __future__ import annotations

import ctypes
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules import computer_use_real_actions_ru as real_actions


class _ValuePattern:
    def __init__(self) -> None:
        self.IsReadOnly = False
        self.Value = ""

    def SetValue(self, value: str) -> bool:
        self.Value = value
        return True


class _EditNode:
    ControlTypeName = "EditControl"
    IsEnabled = True
    IsOffscreen = True

    def __init__(self, pattern: _ValuePattern | None) -> None:
        self.pattern = pattern
        self.set_focus_called = False

    def GetChildren(self):
        return []

    def GetValuePattern(self):
        return self.pattern

    def SetFocus(self) -> bool:
        self.set_focus_called = True
        return True


class _TextRange:
    def __init__(self, value: str) -> None:
        self.value = value

    def GetText(self, _length: int) -> str:
        return self.value


class _NativeEditNode(_EditNode):
    NativeWindowHandle = 456

    def __init__(self) -> None:
        super().__init__(None)
        self.value = ""

    def SetWindowText(self, value: str) -> bool:
        self.value = value
        return True

    def GetTextPattern(self):
        return SimpleNamespace(DocumentRange=_TextRange(self.value))


class _Window:
    Name = "Untitled - Notepad"
    ControlTypeName = "WindowControl"
    IsEnabled = True
    IsOffscreen = False

    def __init__(self, children) -> None:
        self.children = children

    def GetChildren(self):
        return self.children


class _ApiFunction:
    def __init__(self, callback) -> None:
        self.callback = callback
        self.argtypes = None
        self.restype = None

    def __call__(self, *args):
        return self.callback(*args)


class _FakeUser32:
    def __init__(self) -> None:
        self.opened = []
        self.attached = []
        self.closed = []
        self.OpenDesktopW = _ApiFunction(self._open_desktop)
        self.SetThreadDesktop = _ApiFunction(self._set_thread_desktop)
        self.CloseDesktop = _ApiFunction(self._close_desktop)

    def _open_desktop(self, name, _flags, _inherit, _access):
        self.opened.append(name)
        return 123

    def _set_thread_desktop(self, handle):
        self.attached.append(handle)
        return True

    def _close_desktop(self, handle):
        self.closed.append(handle)
        return True


class HiddenUiaTypeContractTests(unittest.TestCase):
    def test_without_hidden_desktop_never_attempts_uia_mutation(self) -> None:
        with patch.dict(real_actions.os.environ, {"LC_HIDDEN_DESKTOP_NAME": ""}, clear=False), patch.dict(
            sys.modules, {"uiautomation": None}
        ):
            self.assertIsNone(real_actions._set_hidden_notepad_text_via_uia("marker"))

    def test_value_pattern_write_requires_readback_and_returns_verified(self) -> None:
        pattern = _ValuePattern()
        node = _EditNode(pattern)
        window = _Window([node])
        fake_uia = SimpleNamespace(GetRootControl=lambda: SimpleNamespace(GetChildren=lambda: [window]))
        fake_user32 = _FakeUser32()
        with patch.object(real_actions.os, "name", "nt"), patch.dict(
            real_actions.os.environ, {"LC_HIDDEN_DESKTOP_NAME": "LocalCometHidden"}, clear=False
        ), patch.dict(sys.modules, {"uiautomation": fake_uia}), patch.object(
            ctypes, "WinDLL", return_value=fake_user32, create=True
        ):
            result = real_actions._set_hidden_notepad_text_via_uia("LocalComet isolated smoke test")

        self.assertEqual(fake_user32.opened, ["LocalCometHidden"])
        self.assertEqual(fake_user32.attached, [123])
        self.assertEqual(fake_user32.closed, [123])

        self.assertIsNotNone(result)
        self.assertTrue(result["ok"])
        self.assertTrue(result["executed"])
        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["verification"], "verified")
        self.assertEqual(result["primitive"], "uia_value_pattern")
        self.assertEqual(pattern.Value, "LocalComet isolated smoke test")
        self.assertFalse(node.set_focus_called)

    def test_native_window_settext_path_requires_uia_readback(self) -> None:
        node = _NativeEditNode()
        window = _Window([node])
        fake_uia = SimpleNamespace(GetRootControl=lambda: SimpleNamespace(GetChildren=lambda: [window]))
        fake_user32 = _FakeUser32()
        with patch.object(real_actions.os, "name", "nt"), patch.dict(
            real_actions.os.environ, {"LC_HIDDEN_DESKTOP_NAME": "LocalCometHidden"}, clear=False
        ), patch.dict(sys.modules, {"uiautomation": fake_uia}), patch.object(
            ctypes, "WinDLL", return_value=fake_user32, create=True
        ):
            result = real_actions._set_hidden_notepad_text_via_uia("native marker")

        self.assertEqual(result["primitive"], "uia_native_window_settext")
        self.assertTrue(result["ok"])
        self.assertTrue(result["executed"])
        self.assertEqual(node.value, "native marker")

    def test_hidden_uia_failure_never_falls_through_to_global_sendinput(self) -> None:
        with patch.object(real_actions.os, "name", "nt"), patch.dict(
            real_actions.os.environ, {"LC_HIDDEN_DESKTOP_NAME": "LocalCometHidden"}, clear=False
        ), patch.object(
            real_actions, "_set_hidden_notepad_text_via_uia",
            return_value={"ok": False, "executed": False, "status": "error", "reason": "hidden_notepad_edit_control_not_verified"},
        ), patch("modules.computer_use_auto_action_ru._send_unicode_text") as send:
            result = real_actions.paste_text("marker")

        self.assertFalse(result["ok"])
        self.assertEqual(result["mode"], "computer_use_real_paste_text_hidden_uia_failed")
        self.assertEqual(result["reason"], "hidden_notepad_edit_control_not_verified")
        send.assert_not_called()

    def test_missing_edit_control_fails_closed(self) -> None:
        window = _Window([])
        fake_uia = SimpleNamespace(GetRootControl=lambda: SimpleNamespace(GetChildren=lambda: [window]))
        fake_user32 = _FakeUser32()
        with patch.object(real_actions.os, "name", "nt"), patch.dict(
            real_actions.os.environ, {"LC_HIDDEN_DESKTOP_NAME": "LocalCometHidden"}, clear=False
        ), patch.dict(sys.modules, {"uiautomation": fake_uia}), patch.object(
            ctypes, "WinDLL", return_value=fake_user32, create=True
        ):
            result = real_actions._set_hidden_notepad_text_via_uia("marker")

        self.assertIsNotNone(result)
        self.assertFalse(result["ok"])
        self.assertFalse(result["executed"])
        self.assertEqual(result["reason"], "hidden_notepad_edit_control_not_verified")


if __name__ == "__main__":
    unittest.main()
