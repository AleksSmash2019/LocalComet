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
    ".gitignore": "FCACAA783618F355DE7C85BFF33D2EB8B5FC992B623257CD26E46A747DB1A88D",
    "LocalComet_Control_Panel.py": "DFCF93451820B326CDED275CD37B62A021CA2B8FDD51A51E131AA56C0387A083",
    "modules/desktop_observer.py": "5639B13FF29134953C71B1EE425B5182899B3472D8F7CBEA7B045DC944AB021C",
    "modules/desktop_ipc_contract_ru.py": "C96538C5DAF210AFFC3AA1796FA6A7D23B29E14F71BEA772ECA32037A580CCF3",
    "tools/test_v6841_desktop_ipc.py": "49F827EC214BB4C2C8A59E1AC0EE9C294DC180B87A6E61467AD2D7D8CE6507CC",
    "docs/desktop_architecture_v6841.md": "A718EB7D53A72097359DABAE76702008D9CF0F87B6697C67444578B1603BCE47",
    "desktop/contracts/localcomet_ipc_v1.schema.json": "A6F5009788DD55246040029E2BAA1D15CE4E365DC4B339EBB7C991AC88D5333A",
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

    check('DESKTOP_SHELL_VERSION = \'v6.84.2\'' in read(SRC / "lib" / "version.ts"), "15 desktop shell version missing")
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
        (r"\bfetch\s*\(", "49 fetch call"),
        (r"XMLHttpRequest", "50 XMLHttpRequest"),
        (r"WebSocket", "51 WebSocket"),
        (r"EventSource", "52 EventSource"),
        (r"sendBeacon", "53 sendBeacon"),
        (r"<iframe|\biframe\b", "54 iframe"),
        (r"(src|href)=[\"']https?://|url\(\s*https?://", "55 remote image URL"),
        (r"localStorage", "56 local storage"),
        (r"sessionStorage", "57 session storage"),
        (r"IndexedDB|indexedDB", "58 indexed database"),
        (r"fs\.|filesystem|readFile|writeFile", "59 filesystem invocation"),
        (r"@tauri-apps/plugin-shell|invoke\(['\"]shell|Command::|std::process", "60 shell invocation"),
        (r"python\s+|Python spawn", "61 Python spawn"),
        (r"[A-Z]:\\|C:/Users|/Users/", "62 absolute machine path"),
    ]
    for pattern, label in forbidden_frontend:
        check(not re.search(pattern, frontend_text, re.IGNORECASE), label)

    component_paths = {
        "63": SRC / "lib" / "components" / "shell" / "NavigationRail.svelte",
        "64": SRC / "lib" / "components" / "shell" / "ConversationSidebar.svelte",
        "65": SRC / "lib" / "components" / "shell" / "ChatHeader.svelte",
        "66": SRC / "lib" / "components" / "chat" / "MessageComposer.svelte",
        "67": SRC / "lib" / "components" / "chat" / "ToolCallCard.svelte",
        "68": SRC / "lib" / "components" / "chat" / "ApprovalCard.svelte",
        "69": SRC / "lib" / "components" / "shell" / "AgentInspector.svelte",
    }
    for number, path in component_paths.items():
        check(path.exists(), f"{number} component missing {rel(path)}")
    css = read(SRC / "app.css")
    check("--color-bg: #f8fafc" in css, "70 light theme tokens missing")
    check('[data-theme="dark"]' in css, "71 dark theme tokens missing")
    check("--focus-ring" in css, "72 focus ring token missing")
    check("prefers-reduced-motion" in css, "73 reduced motion rule missing")
    check("@media (max-width: 999px)" in css and ".sidebar" in css, "74 responsive sidebar rule missing")
    check("@media (max-width: 1199px)" in css and ".inspector" in css, "75 responsive inspector rule missing")
    readme_text = read(readme)
    check("1000 x 700" in readme_text or ("1000" in readme_text and "700" in readme_text), "76 minimum window layout not documented")
    for path in sorted((SRC / "lib" / "components").rglob("*.svelte")):
        check(len(read(path).splitlines()) <= 500, f"77 component too large {rel(path)}")

    app_shell = read(SRC / "lib" / "components" / "shell" / "AppShell.svelte")
    nav = read(component_paths["63"])
    approval = read(component_paths["68"])
    composer = read(component_paths["66"])
    check("skip-link" in app_shell, "78 skip link missing")
    check("<main" in app_shell, "79 main landmark missing")
    check("<nav" in nav, "80 navigation landmark missing")
    check("aria-label" in nav and "aria-label" in composer, "81 icon controls missing labels")
    check("aria-expanded" in nav + read(component_paths["64"]) + read(component_paths["65"]) + composer, "82 collapsible control missing aria-expanded")
    check("aria-current" in nav + read(component_paths["64"]), "83 selected navigation state missing")
    check("disabled" in approval, "84 disabled approval actions missing")
    check('for="composer-draft"' in composer and 'id="composer-draft"' in composer, "85 composer label missing")
    check(":focus-visible" in css, "86 focus visible styling missing")
    check("Visual Shell / Not Connected" in read(component_paths["65"]), "87 status text missing")

    check("LocalComet" in collect_text([DESKTOP / "README.md", SRC, DESKTOP / "static"]), "88 LocalComet branding missing")
    check("open webui" not in frontend_text.lower(), "89 Open WebUI branding in frontend")
    check("open-webui" not in frontend_text.lower(), "90 Open WebUI asset reference in frontend")
    check("OpenWebUI" not in frontend_text, "91 copied component name present")
    check("<image" not in read(mark) and "href=\"http" not in read(mark) and "url(http" not in read(mark), "92/93 external SVG reference present")

    mock_data = read(SRC / "lib" / "data" / "mockData.ts")
    check("mockToolCall" in mock_data and "inspectorMock" in mock_data, "94 mock data module missing")
    check("<PROJECT_ROOT>/modules/example.py" in mock_data and "C:\\" not in mock_data, "95 mock data path not sanitized")
    check("disabled" in approval, "96 approval controls enabled")
    check("Visual Shell / Not Connected" in read(component_paths["65"]), "97 disconnected core status missing")
    check("Backend connected" not in frontend_text and "execution completed" not in frontend_text.lower(), "98/99 backend or execution claim present")
    for label in ["Skills", "Memory", "Artifacts", "Channels"]:
        check(label in mock_data and "Coming later" in mock_data, f"100 deferred label missing {label}")

    build_dir = DESKTOP / "build"
    index_html = build_dir / "index.html"
    check(build_dir.exists(), "101 build directory missing")
    check(index_html.exists(), "102 build index missing")
    build_text = collect_text([build_dir])
    check(not re.search(r"<script[^>]+src=[\"']https?://", build_text, re.IGNORECASE), "103 remote script in build")
    check(not re.search(r"<link[^>]+stylesheet[^>]+https?://", build_text, re.IGNORECASE), "104 remote stylesheet in build")
    check("localhost" not in build_text.lower(), "105 localhost API endpoint in build")
    check("open webui" not in build_text.lower(), "106 copied branding in build")
    build_size = sum(path.stat().st_size for path in build_dir.rglob("*") if path.is_file())
    check(build_size < 5_000_000, f"107 build too large: {build_size}")

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

    print(f"ALL v6.84.2 DESKTOP SHELL TESTS PASSED ({build_size} build bytes)")


if __name__ == "__main__":
    main()
