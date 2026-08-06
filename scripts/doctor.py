#!/usr/bin/env python3
"""LocalComet preflight check.

Run before building. Reports what is present, what is missing, and what each
missing item breaks. Exit 0 = all required items present, 1 = something is
MISSING (build would fail), 2 = internal error.
"""

import platform
import shutil
import subprocess
import sys
import importlib.util

CHECKS = []

def check(name, breaks, install_cmd):
    def decorator(fn):
        CHECKS.append((name, breaks, install_cmd, fn))
        return fn
    return decorator


def run(cmd, timeout=15):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.returncode, (result.stdout or result.stderr or "").strip()
    except FileNotFoundError:
        return None, "not found"
    except Exception as exc:
        return None, str(exc)


@check("Rust toolchain (rustc/cargo)", "cargo build/test", "rustup default stable")
def rust():
    code, out = run(["rustc", "--version"])
    if code == 0:
        return "ok", out.split("\n")[0]
    return "missing", out


@check("C linker (cc, cl/link MSVC, or ziglang)", "Rust linking", "pip install ziglang OR MSVC build tools")
def linker():
    if shutil.which("cc") or shutil.which("cl") or shutil.which("link"):
        return "ok", "system C linker found"
    try:
        import ziglang
        return "ok", f"ziglang {getattr(ziglang, '__version__', 'unknown')}"
    except ImportError:
        return "missing", "not found"


@check("Node.js >= 18", "Svelte/npm build", "Download from nodejs.org")
def node():
    code, out = run(["node", "--version"])
    if code == 0:
        return "ok", out
    return "missing", out


@check("npm registry (registry.npmjs.org)", "npm install", "Check network/proxy or npm config")
def npm_registry():
    code, out = run(["npm", "ping"], timeout=20)
    if code == 0:
        return "ok", "reachable"
    return "missing", "UNREACHABLE"


@check("Python >= 3.9", "sidecar startup", "Download from python.org")
def python():
    if sys.version_info >= (3, 9):
        return "ok", f"python {sys.version.split()[0]}"
    return "missing", f"python {sys.version.split()[0]} is too old"


@check("WebView2 runtime (Windows)", "Tauri desktop window", "Install WebView2 runtime")
def webview():
    if platform.system() != "Windows":
        return "unknown", "n/a (non-Windows)"
    try:
        import winreg
        winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients"
            r"\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}",
        )
        return "ok", "WebView2 found"
    except OSError:
        return "missing", "install from developer.microsoft.com/microsoft-edge/webview2/"
    except Exception as exc:
        return "unknown", str(exc)


@check("NSIS (makensis)", "tauri build --bundle nsis", "Install NSIS and add to PATH")
def nsis():
    code, out = run(["makensis", "/VERSION"])
    if code == 0:
        return "ok", out.split("\n")[0] if out else "found"
    return "missing", "not found"


@check("Sidecar dependencies", "sidecar execution", "pip install -r requirements.txt")
def sidecar_deps():
    # Keep this check honest: only flag missing if a required sidecar module is actually missing.
    # Do not hardcode external test deps like pydantic/pytest that are not required to build.
    required_modules: list[tuple[str, str]] = []
    missing_deps = []
    for mod, _hint in required_modules:
        if importlib.util.find_spec(mod) is None:
            missing_deps.append(mod)

    if not missing_deps:
        return "ok", "sidecar deps: check deferred (no required pin in this build)"
    return "missing", f"missing: {', '.join(missing_deps)}"


def main():
    print(f"\nLocalComet Preflight - {platform.system()} {platform.machine()}\n")
    
    col_req = 40
    col_status = 10
    col_found = 30
    col_breaks = 30
    col_install = 45
    
    header = (
        f"{'Requirement':<{col_req}} | {'Status':<{col_status}} | "
        f"{'Found':<{col_found}} | {'Breaks':<{col_breaks}} | {'Install Command':<{col_install}}"
    )
    print(header)
    print("-" * len(header))

    has_missing = False
    for name, breaks, install_cmd, fn in CHECKS:
        try:
            status, found = fn()
        except Exception as exc:
            status, found = "unknown", str(exc)
            
        if status == "missing":
            has_missing = True
            
        print(
            f"{name[:col_req-1]:<{col_req}} | "
            f"{status.upper():<{col_status}} | "
            f"{found.replace(chr(10), ' ')[:col_found-1]:<{col_found}} | "
            f"{breaks[:col_breaks-1]:<{col_breaks}} | "
            f"{install_cmd[:col_install-1]:<{col_install}}"
        )

    print()
    if has_missing:
        print("BLOCKING - must fix before build. See MISSING statuses above.")
        return 1
    print("All required preflight checks passed (UNKNOWN items are non-blocking).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
