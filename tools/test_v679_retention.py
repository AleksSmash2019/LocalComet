#!/usr/bin/env python
from __future__ import annotations

import importlib
import os
import sys
import tempfile
import time
from pathlib import Path


sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

NOW_TS = 1_800_000_000.0
DAY = 86400


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _reload(name: str):
    sys.modules.pop(name, None)
    return importlib.import_module(name)


def _paths_under(root: Path) -> set[str]:
    if not root.exists():
        return set()
    return {path.relative_to(root).as_posix() for path in root.rglob("*")}


def _write(path: Path, text: str, age_days: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    ts = NOW_TS - age_days * DAY
    os.utime(path, (ts, ts))


def _snapshot(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    if not root.exists():
        return result
    for path in sorted(root.rglob("*")):
        if path.is_file():
            result[path.relative_to(root).as_posix()] = path.read_text(encoding="utf-8")
    return result


def test_import_and_missing_root_are_read_only() -> None:
    with tempfile.TemporaryDirectory(prefix="localcomet_v679_missing_") as temp_text:
        sandbox = Path(temp_text)
        missing_root = sandbox / "missing-root"
        os.environ["LOCALCOMET_ROOT"] = str(missing_root)
        before = _paths_under(sandbox)
        project_paths = _reload("modules.project_paths")
        dry_run = _reload("modules.screenshot_retention_dry_run_ru")
        storage = _reload("modules.storage_cleanup_plan_ru")
        policy = _reload("modules.screenshot_retention_policy_config_ru")
        after_import = _paths_under(sandbox)

        _assert(project_paths.get_project_root() == missing_root.resolve(), "LOCALCOMET_ROOT was not honored.")
        _assert(dry_run.ROOT_PATH == missing_root.resolve(), "Dry-run root escaped missing override.")
        _assert(storage.ROOT_PATH == missing_root.resolve(), "Storage plan root escaped missing override.")
        _assert(policy.ROOT_PATH == missing_root.resolve(), "Policy config root escaped missing override.")
        _assert(before == after_import, "Import created files/directories under missing root.")

        plan = project_paths.build_retention_plan(missing_root)
        after_plan = _paths_under(sandbox)
        _assert(plan["mode"] == "runtime_retention_plan", "Plan mode changed.")
        _assert(plan["dry_run"] is True, "Plan must be dry-run only.")
        _assert(before == after_plan, "Missing-root plan created files/directories.")


def test_retention_plan_policy_and_protections() -> None:
    with tempfile.TemporaryDirectory(prefix="localcomet_v679_fixture_") as temp_text:
        sandbox = Path(temp_text)
        project_root = sandbox / "LocalAgent"
        runtime = project_root / "Projects" / "Reports" / "retention_fixture"
        outside = sandbox / "outside_runtime"

        _write(runtime / "old.log", "old", 8)
        _write(runtime / "new.log", "new", 1)
        _write(runtime / "latest_report.log", "latest", 30)
        _write(runtime / "current_state.json", "current", 30)
        _write(runtime / "run_manifest.json", "manifest", 30)
        _write(runtime / "source.py", "print('protected')", 30)
        _write(project_root / "Projects" / "TestFixtures" / "fixture.log", "fixture", 30)
        _write(project_root / ".incident_backup" / "backup.log", "backup", 30)
        _write(project_root / ".localcomet" / "reviewer" / "inbox" / "review.md", "review", 30)
        _write(outside / "outside.log", "outside", 30)

        count_dir = project_root / "Projects" / "ComputerUse" / "runs" / "many"
        for index in range(201):
            path = count_dir / f"run_{index:03d}.json"
            _write(path, str(index), 0.001 + index * 0.0001)

        before = _snapshot(sandbox)
        os.environ["LOCALCOMET_ROOT"] = str(project_root)
        project_paths = _reload("modules.project_paths")
        scan_roots = [
            runtime,
            count_dir,
            project_root / "Projects" / "TestFixtures",
            project_root / ".incident_backup",
            project_root / ".localcomet" / "reviewer",
            outside,
        ]
        plan_one = project_paths.build_retention_plan(
            project_root,
            scan_roots=scan_roots,
            max_age_days=7,
            max_items_per_group=200,
            now_ts=NOW_TS,
        )
        plan_two = project_paths.build_retention_plan(
            project_root,
            scan_roots=scan_roots,
            max_age_days=7,
            max_items_per_group=200,
            now_ts=NOW_TS,
        )
        after = _snapshot(sandbox)

        _assert(plan_one == plan_two, "Retention plan output is not deterministic.")
        _assert(before == after, "Retention plan changed or deleted files.")
        _assert(plan_one["policy"]["max_age_days"] == 7, "Default age policy changed.")
        _assert(plan_one["policy"]["max_items_per_group"] == 200, "Default count policy changed.")

        candidates = {item["path"]: item for item in plan_one["candidates"]}
        protected = {item["path"]: item for item in plan_one["protected"]}
        rejected = {item["path"]: item for item in plan_one["rejected"]}

        _assert("Projects/Reports/retention_fixture/old.log" in candidates, "Old file was not a candidate.")
        _assert("Projects/Reports/retention_fixture/new.log" not in candidates, "New file became a candidate.")
        _assert(
            "Projects/ComputerUse/runs/many/run_200.json" in candidates,
            "Count limit did not target the oldest file beyond newest 200.",
        )
        _assert(
            "Projects/ComputerUse/runs/many/run_000.json" not in candidates,
            "Count limit failed to keep newest file.",
        )
        _assert("Projects/Reports/retention_fixture/latest_report.log" in protected, "latest file not protected.")
        _assert("Projects/Reports/retention_fixture/current_state.json" in protected, "current file not protected.")
        _assert("Projects/Reports/retention_fixture/run_manifest.json" in protected, "manifest file not protected.")
        _assert("Projects/Reports/retention_fixture/source.py" in protected, "source file not protected.")
        _assert(
            any(path.startswith("Projects/TestFixtures") for path in protected),
            "Test fixtures not protected.",
        )
        _assert(any(path.startswith(".incident_backup") for path in protected), "Backups not protected.")
        _assert(any(path.startswith(".localcomet/reviewer") for path in protected), "Reviewer data not protected.")
        _assert(any("outside_runtime" in path for path in rejected), "Outside root was not rejected.")
        _assert(plan_one["candidates"] == sorted(plan_one["candidates"], key=lambda item: item["path"].lower()), "Candidates are not sorted.")


def test_module_entry_points_use_stable_plan_schema() -> None:
    with tempfile.TemporaryDirectory(prefix="localcomet_v679_modules_") as temp_text:
        project_root = Path(temp_text)
        os.environ["LOCALCOMET_ROOT"] = str(project_root)
        dry_run = _reload("modules.screenshot_retention_dry_run_ru")
        storage = _reload("modules.storage_cleanup_plan_ru")

        before = _paths_under(project_root)
        dry_scan = dry_run.scan()
        storage_plan = storage.generate()
        after = _paths_under(project_root)

        for plan in (dry_scan, storage_plan):
            _assert(plan["mode"] == "runtime_retention_plan", "Plan mode changed.")
            _assert(plan["version"] == "v6.79", "Plan version changed.")
            _assert(plan["dry_run"] is True, "Plan is not dry-run.")
            for key in ("roots", "policy", "candidates", "protected", "rejected", "totals", "warnings"):
                _assert(key in plan, f"Plan missing key: {key}")
        _assert(before == after, "Module scan/generate wrote files.")


def test_safety_status_remains_lightweight() -> None:
    os.environ["LOCALCOMET_ROOT"] = str(ROOT)
    safety = _reload("modules.development_safety_orchestrator_ru")
    start = time.perf_counter()
    result = safety.status()
    elapsed = time.perf_counter() - start
    evaluation = result.get("evaluation", {})
    gates = evaluation.get("gates", {})
    _assert(elapsed < 0.5, f"Safety status took {elapsed:.3f}s.")
    _assert(gates.get("contracts", {}).get("executed") is False, "Contracts ran in safety status.")
    _assert(gates.get("strict", {}).get("executed") is False, "Strict ran in safety status.")


def main() -> None:
    tests = [
        test_import_and_missing_root_are_read_only,
        test_retention_plan_policy_and_protections,
        test_module_entry_points_use_stable_plan_schema,
        test_safety_status_remains_lightweight,
    ]
    for test in tests:
        start = time.perf_counter()
        test()
        elapsed = time.perf_counter() - start
        print(f"PASS {test.__name__} {elapsed:.3f}s")
    print("ALL v6.79 RETENTION TESTS PASSED")


if __name__ == "__main__":
    main()
