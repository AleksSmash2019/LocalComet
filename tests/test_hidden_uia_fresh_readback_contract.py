"""Regression proving hidden UIA verification uses a fresh provider readback."""

from __future__ import annotations

import ctypes
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "tools"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from modules import computer_use_real_actions_ru as real_actions  # noqa: E402


class _Pattern:
    def __init__(self, value: str = ""):
        self.IsReadOnly = False
        self.Value = value

    def SetValue(self, value: str) -> bool:
        self.Value = value
        return True


class _Node:
    ControlTypeName = "EditControl"
    IsEnabled = True
    IsOffscreen = True
    NativeWindowHandle = 9001

    def __init__(self, pattern: _Pattern):
        self.pattern = pattern
        self.focused = False

    def GetChildren(self):
        return []

    def GetValuePattern(self):
        return self.pattern

    def SetFocus(self):
        self.focused = True
        return True


class _Window:
    Name = "Untitled - Notepad"
    ControlTypeName = "WindowControl"
    IsEnabled = True
    IsOffscreen = True

    def __init__(self, node):
        self.node = node

    def GetChildren(self):
        return [self.node]


class _Root:
    def __init__(self, window):
        self.window = window

    def GetChildren(self):
        return [self.window]


class _FakeUser32:
    def __init__(self):
        self.OpenDesktopW = lambda *_args: 123
        self.SetThreadDesktop = lambda *_args: True
        self.CloseDesktop = lambda *_args: True


class FreshUiAReadbackContractTests(unittest.TestCase):
    def test_stale_new_provider_cannot_be_claimed_verified(self):
        first = _Node(_Pattern())
        second = _Node(_Pattern())
        roots = iter((_Root(_Window(first)), _Root(_Window(second))))
        fake_uia = SimpleNamespace(GetRootControl=lambda: next(roots))
        fake_user32 = _FakeUser32()
        with patch.object(real_actions.os, "name", "nt"), patch.dict(
            real_actions.os.environ, {"LC_HIDDEN_DESKTOP_NAME": "LocalCometHidden"}, clear=False
        ), patch.dict(sys.modules, {"uiautomation": fake_uia}), patch.object(
            ctypes, "WinDLL", return_value=fake_user32, create=True
        ), patch("modules.computer_use_auto_action_ru._send_unicode_text", return_value={"ok": False}):
            result = real_actions._set_hidden_notepad_text_via_uia("marker")

        self.assertIsNotNone(result)
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "hidden_notepad_edit_control_not_verified")
        self.assertEqual(first.pattern.Value, "marker")
        self.assertEqual(second.pattern.Value, "")


    def test_native_handle_identity_survives_runtime_id_regeneration(self):
        first = _Node(_Pattern())
        second = _Node(_Pattern("marker"))
        first.GetRuntimeId = lambda: [1]
        second.GetRuntimeId = lambda: [2]
        fake_uia = SimpleNamespace(GetRootControl=lambda: _Root(_Window(second)))
        self.assertTrue(
            real_actions._fresh_uia_readback_contains(
                fake_uia,
                "marker",
                target_native_hwnd=9001,
                target_runtime_id=(1,),
            )
        )


if __name__ == "__main__":
    unittest.main()
