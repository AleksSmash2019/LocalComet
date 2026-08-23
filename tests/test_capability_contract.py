"""Regression tests for narrow Tauri command capability coverage."""
from __future__ import annotations

import json
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN_CAPABILITY = ROOT / "desktop" / "localcomet-desktop" / "src-tauri" / "capabilities" / "main.json"
CONTROL_PLANE_PERMISSIONS = ROOT / "desktop" / "localcomet-desktop" / "src-tauri" / "permissions" / "control-plane.toml"


class CapabilityContractTests(unittest.TestCase):
    def test_main_capability_contains_only_named_p02_acl_additions(self) -> None:
        document = json.loads(MAIN_CAPABILITY.read_text(encoding="utf-8"))
        permissions = document["permissions"]

        self.assertIn("allow-import-custom-model", permissions)
        self.assertIn("allow-cu-broker-observe", permissions)
        self.assertEqual(permissions.count("allow-import-custom-model"), 1)
        self.assertEqual(permissions.count("allow-cu-broker-observe"), 1)
        self.assertNotIn("allow-all", permissions)
        self.assertFalse(any(permission.endswith(":allow-all") for permission in permissions))

    def test_control_plane_maps_each_new_permission_to_one_command(self) -> None:
        document = tomllib.loads(CONTROL_PLANE_PERMISSIONS.read_text(encoding="utf-8"))
        permissions = {item["identifier"]: item for item in document["permission"]}

        self.assertEqual(
            permissions["allow-import-custom-model"]["commands"]["allow"],
            ["import_custom_model"],
        )
        self.assertEqual(
            permissions["allow-cu-broker-observe"]["commands"]["allow"],
            ["cu_broker_observe"],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
