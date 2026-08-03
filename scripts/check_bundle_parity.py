"""Bundle parity gate for the LocalComet desktop sidecar.

Verifies that every Python module shipped with the sidecar matches the
repository source byte-for-byte (SHA-256). Two locations are checked:

  1. BUILD SOURCE: desktop/localcomet-desktop/src-tauri/binaries/app/modules
     (tauri.conf.json bundles binaries/app/ -> app/; this is what a build packs).
  2. DEPLOYED RUNTIME: %LOCALAPPDATA%\\LocalComet\\DevRuntime\\cargo-target\\debug\\
     app\\modules (the running sidecar; override with LOCALCOMET_BUNDLE_MODULES).

A stale bundle (repo != shipped) is the root cause of Bug #1
(request_model_turn_reserved -> invalid_payload): the running sidecar loaded an
outdated local_model_gateway_ru.py whose conversation key set lagged the Rust
bridge, and the build-source copy under binaries/app/ had drifted from repo
modules/ as well. This gate fails when any shipped module diverges from source,
verifying the rebuild and preventing a recurrence (critical once ADR-013 adds
modules/tool_execution_ru.py to the sidecar).

Each shipped location is a curated subset of repo modules (the production path).
The required subset is versioned below: every listed module must be present in
every available shipped location and byte-identical to its repository counterpart.
This catches both directions of drift: stale shipped bytes and an accidentally
omitted shipped module.

Exit codes:
  0 - all present shipped locations match source (absent locations -> SKIP)
  1 - one or more shipped modules diverge (STALE) or are missing in repo
  2 - environment error (repo modules dir missing)
"""

import hashlib
import os
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
REPO_MODULES = REPO_ROOT / "modules"
BUILD_SOURCE_MODULES = (
    REPO_ROOT
    / "desktop"
    / "localcomet-desktop"
    / "src-tauri"
    / "binaries"
    / "app"
    / "modules"
)

# The exact Python subset loaded by the desktop sidecar. Keep this list in sync
# with the bundle assembly step; do not infer it from an already-drifted bundle.
REQUIRED_SIDECAR_MODULES = frozenset(
    {
        "desktop_control_plane_ru.py",
        "desktop_ipc_contract_ru.py",
        "desktop_sidecar_runtime_ru.py",
        "knowledge_adapter_ru.py",
        "knowledge_change_proposal_ru.py",
        "knowledge_change_review_decision_ru.py",
        "knowledge_change_review_ru.py",
        "knowledge_contract_ru.py",
        "knowledge_injection_ru.py",
        "knowledge_review_ui_projection_ru.py",
        "local_model_gateway_ru.py",
        "tool_execution_ru.py",
        "workspace_policy.py",
    }
)


def deployed_modules() -> pathlib.Path | None:
    override = os.environ.get("LOCALCOMET_BUNDLE_MODULES")
    if override:
        return pathlib.Path(override)
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        return None
    return (
        pathlib.Path(base)
        / "LocalComet"
        / "DevRuntime"
        / "cargo-target"
        / "debug"
        / "app"
        / "modules"
    )


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_location(label: str, location: pathlib.Path) -> tuple[int, list[str], list[str], list[str]]:
    """Return matched, stale, missing-in-repo, and missing-in-shipped names."""
    shipped = {module.name: module for module in location.glob("*.py")}
    stale: list[str] = []
    missing_in_repo: list[str] = []
    missing_in_shipped = sorted(REQUIRED_SIDECAR_MODULES - shipped.keys())
    matched = 0
    for name, module in sorted(shipped.items()):
        source = REPO_MODULES / name
        if not source.is_file():
            missing_in_repo.append(name)
        elif sha256(module) != sha256(source):
            stale.append(name)
        else:
            matched += 1
    for name in stale:
        print(f"FAIL: [{label}] STALE (hash mismatch): {name}")
    for name in missing_in_repo:
        print(f"FAIL: [{label}] MISSING_IN_REPO: {name}")
    for name in missing_in_shipped:
        print(f"FAIL: [{label}] MISSING_IN_SHIPPED: {name}")
    return matched, stale, missing_in_repo, missing_in_shipped


def main() -> int:
    if not REPO_MODULES.is_dir():
        print(f"FAIL: repo modules dir missing: {REPO_MODULES}")
        return 2

    targets: list[tuple[str, pathlib.Path]] = [("build-source", BUILD_SOURCE_MODULES)]
    deployed = deployed_modules()
    if deployed is not None:
        targets.append(("deployed", deployed))

    checked = 0
    total_matched = 0
    total_stale = 0
    total_missing_in_repo = 0
    total_missing_in_shipped = 0
    for label, location in targets:
        if not location.is_dir():
            print(f"SKIP: [{label}] shipped modules not found: {location}")
            continue
        checked += 1
        matched, stale, missing_in_repo, missing_in_shipped = check_location(label, location)
        total_matched += matched
        total_stale += len(stale)
        total_missing_in_repo += len(missing_in_repo)
        total_missing_in_shipped += len(missing_in_shipped)

    if checked == 0:
        print("SKIP: no shipped sidecar module locations found on this machine")
        return 0

    if total_stale or total_missing_in_repo or total_missing_in_shipped:
        print(
            f"\n{checked} location(s) checked: {total_matched} match, "
            f"{total_stale} stale, {total_missing_in_repo} missing in repo, "
            f"{total_missing_in_shipped} missing in shipped"
        )
        print("Shipped sidecar is out of sync with source; refresh the bundle.")
        return 1

    print(
        f"OK: {total_matched} shipped module(s) match source across "
        f"{checked} location(s) (bundle parity holds)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
