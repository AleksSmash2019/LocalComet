import base64
import hashlib
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules import computer_use_observe_vision_ru as vision
from modules import computer_use_real_actions_ru as real_actions
from modules import desktop_observer
from modules import pc_desktop_primitives


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"localcomet-observation-test"
PNG_B64 = base64.b64encode(PNG_BYTES).decode("ascii")


class ObservationContractTests(unittest.TestCase):
    def setUp(self):
        self.temp_root = self.enterContext(__import__("tempfile").TemporaryDirectory())
        root = Path(self.temp_root)
        self.screenshots = root / "screenshots"
        self.reports = root / "reports"
        self.patches = [
            patch.object(desktop_observer, "SCREENSHOTS_DIR", self.screenshots),
            patch.object(desktop_observer, "REPORTS_DIR", self.reports),
            patch.object(desktop_observer, "_active_window", lambda: {"title": "Notepad", "hwnd": 100}),
            patch.object(desktop_observer, "_visible_windows", lambda: [{"title": "Notepad", "hwnd": 100}]),
            patch(
                "modules.pc_ui_parser_adapter._uia_elements_for_desktop",
                return_value=([{"text": "Edit", "source": "uia_automation"},], "ok"),
            ),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def test_real_frame_is_persisted_with_backend_hash_and_uia(self):
        fake_backend = SimpleNamespace(
            capture_screenshot=lambda simulate=False: {
                "ok": True,
                "status": "executed",
                "screenshot": PNG_B64,
                "width": 640,
                "height": 480,
                "scale": 1.0,
                "capture_backend": "printwindow",
                "capture_window_title": "Notepad",
                "capture_hwnd": 100,
            }
        )
        with patch.dict(sys.modules, {"modules.computer_use_real_actions_ru": fake_backend}):
            observed = desktop_observer.observe_desktop(write_report=False)

        expected_hash = hashlib.sha256(PNG_BYTES).hexdigest()
        self.assertTrue(observed["ok"])
        self.assertEqual(observed["observation_state"], "available")
        self.assertEqual(observed["screenshot_backend"], "printwindow")
        self.assertEqual(observed["screenshot_meta"]["sha256"], expected_hash)
        self.assertEqual(observed["screenshot_meta"]["bytes"], len(PNG_BYTES))
        self.assertEqual(observed["uia_status"], "ok")
        self.assertEqual(len(observed["ui_elements"]), 1)
        self.assertTrue(Path(observed["screenshot_path"]).is_file())

    def test_empty_real_capture_is_failed_not_green(self):
        fake_backend = SimpleNamespace(
            capture_screenshot=lambda simulate=False: {
                "ok": False,
                "status": "error",
                "reason": "no capturable window on this desktop",
                "capture_backend": "printwindow",
            }
        )
        with patch.object(desktop_observer, "_active_window", lambda: {}), patch.object(
            desktop_observer, "_visible_windows", lambda: []
        ), patch(
            "modules.pc_ui_parser_adapter._uia_elements_for_desktop",
            return_value=([], "uia root error"),
        ), patch.dict(sys.modules, {"modules.computer_use_real_actions_ru": fake_backend}):
            observed = desktop_observer.observe_desktop(write_report=False)

        self.assertFalse(observed["ok"])
        self.assertEqual(observed["observation_state"], "failed")
        self.assertEqual(observed["screenshot_backend"], "printwindow")
        self.assertIn("no capturable window", observed["screenshot_error"])

    def test_bgra_encoder_emits_valid_png_evidence(self):
        bgra = bytes([
            0, 0, 255, 255, 0, 255, 0, 255, 255, 0, 0, 255, 255, 255, 255, 255,
            255, 255, 0, 255, 0, 128, 255, 255, 128, 64, 32, 255, 32, 64, 128, 255,
        ])
        encoded, width, height, _scale = real_actions._encode_bgra_png(bgra, 4, 2)
        payload = real_actions._with_png_evidence({"screenshot": encoded, "width": width, "height": height})
        raw = base64.b64decode(encoded, validate=True)
        self.assertEqual(raw[:8], PNG_BYTES[:8])
        self.assertEqual(payload["screenshot_bytes"], len(raw))
        self.assertEqual(payload["screenshot_sha256"], hashlib.sha256(raw).hexdigest())

    def test_hidden_screenshot_owner_context_requires_exact_desktop_and_pid(self):
        context = self.screenshots.parent / "screenshot_owner_context.json"
        context.write_text(json.dumps({"pid": 4242, "desktop": "LocalCometHiddenCU_test"}), encoding="utf-8")
        with patch.dict(
            real_actions.os.environ,
            {
                "LC_HIDDEN_DESKTOP_NAME": "LocalCometHiddenCU_test",
                "LC_HIDDEN_SCREENSHOT_OWNER_CONTEXT": str(context),
            },
            clear=False,
        ):
            self.assertEqual(real_actions._hidden_screenshot_owner_context()["pid"], 4242)
            context.write_text(json.dumps({"pid": 0, "desktop": "LocalCometHiddenCU_test"}), encoding="utf-8")
            self.assertEqual(real_actions._hidden_screenshot_owner_context(), {})
            context.write_text(json.dumps({"pid": 4242, "desktop": "another-desktop"}), encoding="utf-8")
            self.assertEqual(real_actions._hidden_screenshot_owner_context(), {})

    def test_screenshot_metadata_preserves_truthful_state(self):
        fake_backend = SimpleNamespace(
            capture_screenshot=lambda simulate=False: {
                "ok": True,
                "status": "executed",
                "screenshot": PNG_B64,
                "width": 640,
                "height": 480,
                "scale": 1.0,
                "capture_backend": "printwindow",
            }
        )
        with patch.dict(sys.modules, {"modules.computer_use_real_actions_ru": fake_backend}):
            payload = pc_desktop_primitives.screenshot_metadata()

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["observation_state"], "available")
        self.assertEqual(payload["screenshot_backend"], "printwindow")
        self.assertEqual(payload["screenshot_sha256"], hashlib.sha256(PNG_BYTES).hexdigest())
        self.assertEqual(payload["screenshot_bytes"], len(PNG_BYTES))


if __name__ == "__main__":
    unittest.main()
