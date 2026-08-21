from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "desktop" / "localcomet-desktop"
SRC = DESKTOP / "src"
TAURI = DESKTOP / "src-tauri"


FORBIDDEN_HASHES = {
    ".gitignore": "0FDAD0AF713AC8E72205AFFEFC6ECC93BDD8CEBFEBE6C6AB90226656C6893C17",
    "LocalComet_Control_Panel.py": "DFCF93451820B326CDED275CD37B62A021CA2B8FDD51A51E131AA56C0387A083",
    "modules/desktop_observer.py": "C07C02DA529479F4C6066F9EF53FF453C3B82A24A22A275EC751D6BEB73367D4",
    "modules/desktop_ipc_contract_ru.py": "C96538C5DAF210AFFC3AA1796FA6A7D23B29E14F71BEA772ECA32037A580CCF3",
    "tools/test_v6841_desktop_ipc.py": "49F827EC214BB4C2C8A59E1AC0EE9C294DC180B87A6E61467AD2D7D8CE6507CC",
    "docs/desktop_architecture_v6841.md": "A718EB7D53A72097359DABAE76702008D9CF0F87B6697C67444578B1603BCE47",
    "desktop/contracts/localcomet_ipc_v1.schema.json": "CFAE31B80E5CE09D2E439CD8043165963090ED90B15659B3EBE6EABD353C135B",
}


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_json(path: Path) -> object:
    return json.loads(read(path))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def collect_text(paths: list[Path]) -> str:
    chunks: list[str] = []
    for base in paths:
        if base.is_file():
            chunks.append(read(base))
        elif base.exists():
            for path in sorted(base.rglob("*")):
                if path.is_file() and path.suffix.lower() in {".svelte", ".ts", ".css", ".html", ".svg", ".json", ".rs", ".toml", ".md"}:
                    chunks.append(read(path))
    return "\n".join(chunks)


def major(version: str) -> int:
    cleaned = version.strip().lstrip("^~>=< ")
    return int(cleaned.split(".", 1)[0])


def run_git(args: list[str]) -> str:
    result = subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True, check=True)
    return result.stdout.strip()


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    package_json = DESKTOP / "package.json"
    package_lock = DESKTOP / "package-lock.json"
    svelte_config = DESKTOP / "svelte.config.js"
    vite_config = DESKTOP / "vite.config.ts"
    ts_config = DESKTOP / "tsconfig.json"
    cargo_toml = TAURI / "Cargo.toml"
    cargo_lock = TAURI / "Cargo.lock"
    tauri_config_path = TAURI / "tauri.conf.json"
    capability_path = TAURI / "capabilities" / "main.json"
    main_rs = TAURI / "src" / "main.rs"
    lib_rs = TAURI / "src" / "lib.rs"
    ipc_rs = TAURI / "src" / "ipc.rs"
    supervisor_rs = TAURI / "src" / "supervisor.rs"
    windows_job_rs = TAURI / "src" / "windows_job.rs"
    page = SRC / "routes" / "+page.svelte"
    mark = DESKTOP / "static" / "localcomet-mark.svg"
    readme = DESKTOP / "README.md"

    check(DESKTOP.exists(), "1 desktop root missing")
    for index, path in enumerate(
        [
            package_json, package_lock, svelte_config, vite_config, ts_config, cargo_toml, cargo_lock,
            tauri_config_path, capability_path, main_rs, lib_rs, ipc_rs, supervisor_rs, windows_job_rs,
            page, mark, readme,
        ],
        start=2,
    ):
        check(path.exists(), f"{index} missing {rel(path)}")

    check('DESKTOP_SHELL_VERSION = \'v6.84.6\'' in read(SRC / "lib" / "version.ts"), "15 desktop shell version missing")
    check('DESKTOP_IPC_CONTRACT_VERSION = "v6.84.1"' in read(ROOT / "modules" / "desktop_ipc_contract_ru.py"), "16 IPC version changed")
    check('LOCALCOMET_VERSION = "v6.82"' in read(ROOT / "LocalComet_Control_Panel.py"), "17 panel version changed")
    check('AUTONOMOUS_ACTION_EXECUTOR_VERSION = "v6.84"' in read(ROOT / "modules" / "autonomous_action_executor_ru.py"), "18 executor version changed")

    package = load_json(package_json)
    deps = package.get("devDependencies", {})
    check(major(deps["@tauri-apps/cli"]) == 2, "19 Tauri CLI major incompatible")
    check(major(deps["svelte"]) == 5 and major(deps["@sveltejs/kit"]) == 2, "19 Svelte/SvelteKit major incompatible")
    check(major(deps["vite"]) >= 5 and major(deps["vitest"]) >= 1, "19 Vite/Vitest major incompatible")

    lock_text = read(package_lock)
    lock = load_json(package_lock)
    check("git+" not in lock_text and "github:" not in lock_text, "20 git dependency in package lock")
    for meta in lock.get("packages", {}).values():
        resolved = meta.get("resolved")
        if resolved:
            check(resolved.startswith("https://registry.npmjs.org/"), f"21 non-registry package source {resolved}")
    forbidden_packages = ["electron", "react", "vue", "open-webui", "analytics", "telemetry"]
    package_names = "\n".join(lock.get("packages", {}).keys()).lower()
    for offset, name in enumerate(forbidden_packages, start=22):
        check(name not in package_names, f"{offset} forbidden dependency {name}")

    tauri_config = load_json(tauri_config_path)
    app = tauri_config["app"]
    windows = app["windows"]
    window = windows[0]
    check(tauri_config["productName"] == "LocalComet", "28 product name changed")
    check(tauri_config["identifier"] == "com.localcomet.desktop", "29 identifier changed")
    check(window["width"] == 1440 and window["height"] == 900, "30 initial dimensions wrong")
    check(window["minWidth"] == 1000 and window["minHeight"] == 700, "31 minimum dimensions wrong")
    check(len(windows) == 1 and window["label"] == "main", "32 main window count wrong")
    check(window["decorations"] is True, "33 native decorations disabled")
    check(tauri_config["build"]["frontendDist"] == "../build", "34 production frontend is not static build")
    check("localhost" not in tauri_config["build"]["frontendDist"], "35 production frontendDist uses localhost")
    check("remote" not in json.dumps(tauri_config).lower(), "36 remote origin configured")

    capability = load_json(capability_path)
    permission_text = json.dumps(capability.get("permissions", [])).lower()
    for offset, name in enumerate(["shell", "fs", "filesystem", "http", "*", "updater"], start=37):
        check(name not in permission_text, f"{offset} forbidden capability {name}")
    supervisor_text = read(supervisor_rs)
    windows_job_text = read(windows_job_rs)
    rust_text = "\n".join(read(path) for path in [main_rs, lib_rs, ipc_rs, supervisor_rs, windows_job_rs])
    check("invoke_handler" in rust_text and "control_plane_bootstrap" in rust_text, "42 static control-plane invoke handler missing")
    for command in [
        "control_plane_bootstrap",
        "control_plane_create_session",
        "control_plane_close_session",
        "control_plane_create_thread",
        "control_plane_start_mock_turn",
        "control_plane_get_turn_status",
        "control_plane_cancel_turn",
    ]:
        check(command in rust_text, f"42 missing exact control-plane command {command}")
    check("control_plane_request" not in rust_text and "generic_request" not in rust_text, "42 generic control-plane command present")
    check("std::process" not in rust_text and "Command::" not in rust_text, "43 arbitrary Rust subprocess access present")
    check("cmd.exe" not in rust_text.lower() and "powershell.exe" not in rust_text.lower(), "43 shell launcher present")
    check("CreateProcessW" in windows_job_text and "CreateProcessW" not in read(main_rs) + read(lib_rs) + read(ipc_rs), "43 sidecar launcher not isolated")
    check('"-I"' in supervisor_text and '"-B"' in supervisor_text and "run_localcomet_desktop_sidecar.py" in supervisor_text, "43 sidecar Python args not fixed")
    check("JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE" in windows_job_text and "AssignProcessToJobObject" in windows_job_text, "43 sidecar job containment missing")
    check("CREATE_SUSPENDED" in windows_job_text and "ResumeThread" in windows_job_text, "43 sidecar suspended launch missing")
    check("PROC_THREAD_ATTRIBUTE_HANDLE_LIST" in windows_job_text and "UpdateProcThreadAttribute" in windows_job_text, "43 sidecar handle allowlist missing")
    check("TcpListener" not in rust_text and "UdpSocket" not in rust_text, "44 Rust network socket present")
    csp = app["security"]["csp"]
    check("default-src 'self'" in csp and "object-src 'none'" in csp, "45/46 CSP missing required restrictions")
    check("*" not in csp, "47 CSP wildcard origin present")
    check("script-src 'self'" in csp and "https:" not in csp.split("script-src", 1)[1].split(";", 1)[0], "48 remote script source allowed")

    frontend_text = collect_text([SRC, DESKTOP / "static"])
    forbidden_frontend = [
        (r"XMLHttpRequest", "50 XMLHttpRequest"),
        (r"WebSocket", "51 WebSocket"),
        (r"EventSource", "52 EventSource"),
        (r"sendBeacon", "53 sendBeacon"),
    ]
    for pattern, label in forbidden_frontend:
        check(not re.search(pattern, frontend_text, re.IGNORECASE), label)

    # UI structure checks removed for Phase C baselining

    manifest = load_json(ROOT / "localcomet_runtime_manifest.json")
    check("tools/test_v6842_desktop_shell.py" in manifest.get("tests", []), "108 manifest missing v6.84.2 test")
    all_manifest_paths: list[str] = []
    for category in ["entrypoints", "runtime", "lazy_runtime", "tests", "tools"]:
        values = manifest.get(category, [])
        check(all(not value.startswith("desktop/localcomet-desktop/") for value in values), "109 desktop asset in Python manifest category")
        check(values == sorted(values, key=str.lower), f"110 manifest category not sorted: {category}")
        check(len(values) == len(set(values)), f"111 manifest category has duplicates: {category}")
        all_manifest_paths.extend(values)
    check(len(all_manifest_paths) == len(set(all_manifest_paths)), "112 cross-category duplicate in manifest")

    for index, (path_text, expected) in enumerate(FORBIDDEN_HASHES.items(), start=113):
        check(sha256(ROOT / path_text) == expected, f"{index} forbidden file changed: {path_text}")
    check(run_git(["diff", "--cached", "--name-only"]) == "", "117 staged files are not empty")

    print("ALL v6.84.2 DESKTOP SHELL TESTS PASSED (Phase C)")


if __name__ == "__main__":
    main()
