#!/usr/bin/env python
from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import start_localcomet as start


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def runtime_paths(root: Path) -> SimpleNamespace:
    runtime_root = root / "LocalCometDev"
    return SimpleNamespace(
        root=runtime_root,
        workspace=runtime_root / "workspace",
        cargo_target=runtime_root / "cargo-target",
        app_data=runtime_root / "app-data",
        resource_cache=runtime_root / "runtime-cache",
        state=runtime_root / "state.json",
        logs=runtime_root / "logs",
    )


def passing_report(paths: SimpleNamespace, dependency: str = "REUSED") -> start.DoctorReport:
    return start.DoctorReport(
        release=start.RELEASE,
        legacy_release=start.EXPECTED_LEGACY_RELEASE,
        source_root=str(paths.root.parent),
        runtime_root=str(paths.root),
        workspace=str(paths.workspace),
        cargo_target=str(paths.cargo_target),
        app_data=str(paths.app_data),
        dependency_action=dependency,
        dev_url="http://127.0.0.1:1420",
        checks=(start.Check("synthetic", "PASS", "ready"),),
    )


class StartLocalCometTests(unittest.TestCase):
    def test_release_and_legacy_contract_are_explicit(self) -> None:
        self.assertEqual(start.RELEASE, "v6.84.5.1d4")
        self.assertEqual(start.EXPECTED_LEGACY_RELEASE, "v6.84.5.1d2")
        self.assertEqual(start.legacy.RELEASE, start.EXPECTED_LEGACY_RELEASE)

    def test_parser_defaults_to_start(self) -> None:
        args = start._build_parser().parse_args([])
        self.assertEqual(args.command, "start")
        self.assertFalse(args.json)
        self.assertFalse(args.offline)

    def test_windowsapps_python_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lc_start_python_") as text:
            executable = Path(text) / "WindowsApps" / "python.exe"
            write(executable, "")
            with mock.patch.object(start.sys, "executable", str(executable)):
                with self.assertRaisesRegex(start.StartHold, "WindowsApps"):
                    start._canonical_python()

    def test_real_python_path_is_accepted(self) -> None:
        observed = start._canonical_python()
        self.assertTrue(observed.is_file())
        self.assertNotIn("windowsapps", {part.casefold() for part in observed.parts})

    def test_loopback_dev_url_is_loaded(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lc_start_url_") as text:
            root = Path(text)
            config = (
                root
                / "desktop"
                / "localcomet-desktop"
                / "src-tauri"
                / "tauri.conf.json"
            )
            write(
                config,
                json.dumps({"build": {"devUrl": "http://127.0.0.1:1420"}}),
            )
            self.assertEqual(
                start._load_dev_url(root),
                "http://127.0.0.1:1420",
            )

    def test_non_loopback_dev_url_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lc_start_bad_url_") as text:
            root = Path(text)
            config = (
                root
                / "desktop"
                / "localcomet-desktop"
                / "src-tauri"
                / "tauri.conf.json"
            )
            write(
                config,
                json.dumps({"build": {"devUrl": "https://example.invalid:1420"}}),
            )
            with self.assertRaisesRegex(start.StartHold, "loopback"):
                start._load_dev_url(root)

    def test_port_probe_reports_available_and_occupied(self) -> None:
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        probe.bind(("127.0.0.1", 0))
        occupied_port = probe.getsockname()[1]
        available, _ = start._port_available(
            f"http://127.0.0.1:{occupied_port}"
        )
        self.assertFalse(available)
        probe.close()

        temporary = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        temporary.bind(("127.0.0.1", 0))
        free_port = temporary.getsockname()[1]
        temporary.close()
        available, detail = start._port_available(
            f"http://127.0.0.1:{free_port}"
        )
        self.assertTrue(available)
        self.assertIn(str(free_port), detail)

    def test_existing_installed_or_dev_process_holds_launch(self) -> None:
        with mock.patch.object(
            start,
            "_running_localcomet_processes",
            return_value=((1234, "LocalComet.exe"),),
        ):
            check = start._localcomet_process_check()
        self.assertEqual(check.status, "ERROR")
        self.assertIn("PID 1234", check.detail)

    def test_tail_is_line_and_byte_bounded(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lc_start_tail_") as text:
            path = Path(text) / "launch.log"
            lines = [f"line-{index:04d}-" + ("x" * 300) for index in range(400)]
            write(path, "\n".join(lines) + "\n")
            tail = start._tail_text(path, 5)
            self.assertEqual(len(tail.splitlines()), 5)
            self.assertIn("line-0399", tail)
            self.assertLessEqual(
                len(tail.encode("utf-8")),
                start.MAX_LOG_TAIL_BYTES,
            )
            with self.assertRaises(start.StartHold):
                start._tail_text(path, 0)
            with self.assertRaises(start.StartHold):
                start._tail_text(path, 501)

    def test_lock_is_created_and_released(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lc_start_lock_") as text:
            root = Path(text) / "runtime"
            lock_path = root / start.LOCK_NAME
            with start.LauncherLock(root):
                self.assertTrue(lock_path.is_file())
                payload = json.loads(lock_path.read_text(encoding="utf-8"))
                self.assertEqual(payload["pid"], os.getpid())
                self.assertEqual(payload["release"], start.RELEASE)
            self.assertFalse(lock_path.exists())

    def test_active_lock_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lc_start_active_") as text:
            root = Path(text) / "runtime"
            root.mkdir()
            write(
                root / start.LOCK_NAME,
                json.dumps(
                    {
                        "release": start.RELEASE,
                        "pid": os.getpid(),
                        "token": "active",
                        "created_at_utc": "2026-07-16T00:00:00+00:00",
                    }
                ),
            )
            with self.assertRaisesRegex(start.StartHold, "already running"):
                start.LauncherLock(root).acquire()

    def test_stale_lock_is_recovered(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lc_start_stale_") as text:
            root = Path(text) / "runtime"
            root.mkdir()
            write(
                root / start.LOCK_NAME,
                json.dumps(
                    {
                        "release": start.RELEASE,
                        "pid": 2_000_000_000,
                        "token": "stale",
                        "created_at_utc": "2026-07-16T00:00:00+00:00",
                    }
                ),
            )
            with mock.patch.object(start, "_is_process_alive", return_value=False):
                with start.LauncherLock(root):
                    payload = json.loads(
                        (root / start.LOCK_NAME).read_text(encoding="utf-8")
                    )
                    self.assertNotEqual(payload["token"], "stale")
            self.assertFalse((root / start.LOCK_NAME).exists())

    def test_malformed_lock_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lc_start_malformed_") as text:
            root = Path(text) / "runtime"
            root.mkdir()
            write(root / start.LOCK_NAME, "{not-json")
            with self.assertRaisesRegex(start.StartHold, "safely recover"):
                start.LauncherLock(root).acquire()
            self.assertTrue((root / start.LOCK_NAME).is_file())

    def test_offline_launch_requires_reusable_dependencies(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lc_start_offline_") as text:
            paths = runtime_paths(Path(text))
            report = passing_report(paths, dependency="INSTALLED")
            with (
                mock.patch.object(start, "collect_doctor_report", return_value=report),
                mock.patch.object(start.legacy, "resolve_runtime_paths", return_value=paths),
                mock.patch.object(start.legacy, "main") as legacy_main,
                contextlib.redirect_stdout(io.StringIO()),
                contextlib.redirect_stderr(io.StringIO()),
            ):
                result = start.run_start(offline=True)
            self.assertEqual(result, 2)
            legacy_main.assert_not_called()
            self.assertFalse((paths.root / start.LOCK_NAME).exists())

    def test_successful_launch_calls_legacy_once_and_restores_environment(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lc_start_success_") as text:
            paths = runtime_paths(Path(text))
            report = passing_report(paths)
            before = {
                "PYTHONDONTWRITEBYTECODE": os.environ.get("PYTHONDONTWRITEBYTECODE"),
                "PYTHONUTF8": os.environ.get("PYTHONUTF8"),
                "PYTHONUNBUFFERED": os.environ.get("PYTHONUNBUFFERED"),
            }

            def fake_main() -> int:
                self.assertEqual(os.environ["PYTHONDONTWRITEBYTECODE"], "1")
                self.assertEqual(os.environ["PYTHONUTF8"], "1")
                self.assertEqual(os.environ["PYTHONUNBUFFERED"], "1")
                self.assertTrue((paths.root / start.LOCK_NAME).is_file())
                return 0

            with (
                mock.patch.object(start, "collect_doctor_report", return_value=report),
                mock.patch.object(start.legacy, "resolve_runtime_paths", return_value=paths),
                mock.patch.object(start.legacy, "main", side_effect=fake_main) as legacy_main,
                contextlib.redirect_stdout(io.StringIO()),
                contextlib.redirect_stderr(io.StringIO()),
            ):
                result = start.run_start(offline=False)

            self.assertEqual(result, 0)
            legacy_main.assert_called_once_with()
            self.assertFalse((paths.root / start.LOCK_NAME).exists())
            for key, value in before.items():
                self.assertEqual(os.environ.get(key), value)

    def test_failed_doctor_never_calls_legacy(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lc_start_hold_") as text:
            paths = runtime_paths(Path(text))
            report = start.DoctorReport(
                release=start.RELEASE,
                legacy_release=start.EXPECTED_LEGACY_RELEASE,
                source_root=str(Path(text)),
                runtime_root=str(paths.root),
                workspace=str(paths.workspace),
                cargo_target=str(paths.cargo_target),
                app_data=str(paths.app_data),
                dependency_action="REUSED",
                dev_url="http://127.0.0.1:1420",
                checks=(start.Check("failure", "ERROR", "synthetic"),),
            )
            with (
                mock.patch.object(start, "collect_doctor_report", return_value=report),
                mock.patch.object(start.legacy, "main") as legacy_main,
                contextlib.redirect_stdout(io.StringIO()),
                contextlib.redirect_stderr(io.StringIO()),
            ):
                result = start.run_start(offline=False)
            self.assertEqual(result, 2)
            legacy_main.assert_not_called()

    def test_keyboard_interrupt_maps_to_130_and_releases_lock(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lc_start_interrupt_") as text:
            paths = runtime_paths(Path(text))
            report = passing_report(paths)
            with (
                mock.patch.object(start, "collect_doctor_report", return_value=report),
                mock.patch.object(start.legacy, "resolve_runtime_paths", return_value=paths),
                mock.patch.object(start.legacy, "main", side_effect=KeyboardInterrupt),
                contextlib.redirect_stdout(io.StringIO()),
                contextlib.redirect_stderr(io.StringIO()),
            ):
                result = start.run_start(offline=False)
            self.assertEqual(result, 130)
            self.assertFalse((paths.root / start.LOCK_NAME).exists())

    def test_status_is_read_only_and_bounded(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lc_start_status_") as text:
            base = Path(text)
            source = base / "source"
            paths = runtime_paths(base)
            write(source / "desktop/localcomet-desktop/package-lock.json", "{}\n")
            paths.logs.mkdir(parents=True)
            write(paths.logs / "launch_1.log", "ready\n")
            state = {
                "package_lock_sha256": "a" * 64,
                "npm_ci_completed": True,
                "synced_files": ["a", "b"],
            }
            before = sorted(
                (path.relative_to(base).as_posix(), path.stat().st_size)
                for path in base.rglob("*")
                if path.is_file()
            )
            with (
                mock.patch.object(start.legacy, "source_root_from_launcher", return_value=source),
                mock.patch.object(start.legacy, "resolve_runtime_paths", return_value=paths),
                mock.patch.object(start.legacy, "read_state", return_value=(state, False)),
            ):
                status = start.collect_status()
            after = sorted(
                (path.relative_to(base).as_posix(), path.stat().st_size)
                for path in base.rglob("*")
                if path.is_file()
            )
            self.assertEqual(before, after)
            self.assertEqual(status["synced_file_count"], 2)
            self.assertTrue(status["source_generated_paths_ignored"])
            self.assertTrue(str(status["latest_log"]).endswith("launch_1.log"))

    def test_cli_rejects_json_for_interactive_start(self) -> None:
        with (
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            result = start.main(["start", "--json"])
        self.assertEqual(result, 2)

    def test_logs_command_is_truthful_when_empty(self) -> None:
        with tempfile.TemporaryDirectory(prefix="lc_start_logs_") as text:
            paths = runtime_paths(Path(text))
            output = io.StringIO()
            with (
                mock.patch.object(start.legacy, "resolve_runtime_paths", return_value=paths),
                contextlib.redirect_stdout(output),
            ):
                result = start.main(["logs"])
            self.assertEqual(result, 0)
            self.assertIn("No LocalComet launcher logs found", output.getvalue())

    def test_source_contains_no_shell_or_authority_expansion(self) -> None:
        source = (ROOT / "tools" / "start_localcomet.py").read_text(encoding="utf-8")
        self.assertNotIn("shell=True", source)
        self.assertNotIn("localStorage", source)
        self.assertNotIn("knowledge.review.decision.create", source)
        self.assertNotIn("Vault.write", source)
        self.assertNotIn("git reset", source)
        self.assertNotIn("git clean", source)
        self.assertNotIn("git restore", source)
        self.assertNotIn("git checkout", source)
        self.assertNotIn("git add", source)
        self.assertNotIn("git commit", source)
        self.assertNotIn("git push", source)

    def test_wrapper_delegates_runtime_ownership_to_existing_launcher(self) -> None:
        source = (ROOT / "tools" / "start_localcomet.py").read_text(encoding="utf-8")
        self.assertIn("from tools import launch_localcomet_dev as legacy", source)
        self.assertIn("result = legacy.main()", source)
        self.assertNotIn("npm run tauri dev", source)
        self.assertNotIn("DesktopSidecarSupervisor", source)
        self.assertNotIn("run_localcomet_desktop_sidecar.py", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
