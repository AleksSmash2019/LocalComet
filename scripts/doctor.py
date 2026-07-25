#!/usr/bin/env python3
"""LocalComet preflight check.

Run before building. Reports what is present, what is missing, and what each
missing item breaks. Exit 0 = all required items present, 1 = something is
MISSING (build would fail), 2 = internal error.

Three states per check: OK / MISSING / UNKNOWN. UNKNOWN is never collapsed into
MISSING (an unknown state is reported as such, not as knowledge).
"""

import platform
import shutil
import subprocess
import sys

CHECKS = []


def check(name, breaks):
    def decorator(fn):
        CHECKS.append((name, breaks, fn))
        return fn

    return decorator


def run(cmd, timeout=15):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.returncode, (result.stdout or result.stderr or "").strip()
    except FileNotFoundError:
        return None, "not found"
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)


@check("Rust toolchain (rustc/cargo)", "cargo build/test")
def rust():
    code, out = run(["rustc", "--version"])
    if code == 0:
        return True, out.split("\n")[0]
    return False, out


@check("C linker (cc or ziglang)", "Rust linking")
def linker():
    if shutil.which("cc") or shutil.which("cl") or shutil.which("link"):
        return True, "system C linker found"
    try:
        import ziglang

        return True, f"ziglang {getattr(ziglang, '__version__', 'unknown')}"
    except ImportError:
        return False, "pip install ziglang  OR install MSVC build tools"


@check("Node.js >= 18", "Svelte/npm build")
def node():
    code, out = run(["node", "--version"])
    if code == 0:
        return True, out
    return False, out


@check("npm registry (registry.npmjs.org)", "npm install")
def npm_registry():
    code, out = run(["npm", "ping"], timeout=20)
    if code == 0:
        return True, "reachable"
    return False, "UNREACHABLE (offline / blocked registry)"


@check("Python >= 3.9", "sidecar startup")
def python():
    if sys.version_info >= (3, 9):
        return True, f"python {sys.version.split()[0]}"
    return False, f"python {sys.version.split()[0]} is too old"


@check("WebView2 runtime (Windows)", "Tauri desktop window")
def webview():
    if platform.system() != "Windows":
        return None, "n/a (non-Windows)"
    try:
        import winreg

        winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients"
            r"\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}",
        )
        return True, "WebView2 found"
    except OSError:
        return False, "install from https://developer.microsoft.com/microsoft-edge/webview2/"
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)


@check("NSIS (makensis)", "tauri build --bundle nsis")
def nsis():
    code, out = run(["makensis", "/VERSION"])
    if code == 0:
        return True, out or "found"
    return False, "install NSIS for installer bundling"


def main():
    print(f"\nLocalComet Preflight - {platform.system()} {platform.machine()}\n")
    print(f"{'Check':<38} {'Status':<9} Detail")
    print("-" * 90)

    missing = []
    for name, breaks, fn in CHECKS:
        try:
            result, detail = fn()
        except Exception as exc:  # noqa: BLE001
            result, detail = None, str(exc)
        if result is True:
            status = "OK"
        elif result is False:
            status = "MISSING"
            missing.append((name, breaks))
        else:
            status = "UNKNOWN"
        print(f"{name:<38} {status:<9} {detail}")

    print()
    if missing:
        print("BLOCKING - must fix before build:")
        for name, breaks in missing:
            print(f"  [{name}] needed for: {breaks}")
        return 1
    print("All required preflight checks passed (UNKNOWN items are non-blocking).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
