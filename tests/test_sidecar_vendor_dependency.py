from __future__ import annotations

import importlib
import sys
from pathlib import Path


def test_vendored_uia_dependencies_import_from_project_tree() -> None:
    vendor = Path(__file__).resolve().parents[1] / "modules" / "_vendor"
    assert (vendor / "uiautomation" / "uiautomation.py").is_file()
    assert (vendor / "comtypes" / "__init__.py").is_file()

    original_path = list(sys.path)
    try:
        sys.path.insert(0, str(vendor))
        uiautomation = importlib.import_module("uiautomation")
        comtypes = importlib.import_module("comtypes")
        assert Path(uiautomation.__file__).resolve().is_relative_to(vendor.resolve())
        assert Path(comtypes.__file__).resolve().is_relative_to(vendor.resolve())
    finally:
        sys.path[:] = original_path
        for name in ("uiautomation", "comtypes"):
            sys.modules.pop(name, None)
