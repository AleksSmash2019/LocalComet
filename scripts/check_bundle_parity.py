"""Bundle parity gate for the LocalComet desktop sidecar.

Verifies that every Python module shipped with the sidecar matches the
repository source byte-for-byte (SHA-256). Two locations are checked:

  1. BUILD SOURCE: desktop/localcomet-desktop/src-tauri/binaries/app/modules
     (tauri.conf.json bundles binaries/app/ -> app/; this is what a build packs).
  2. DEPLOYED RUNTIME: %LOCALAPPDATA%\\LocalCometDev\\workspace\\modules
     (the running sidecar; override with LOCALCOMET_BUNDLE_MODULES).

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
  0 - all required shipped locations match source
  1 - one or more shipped modules diverge (STALE) or are missing in repo
  2 - environment error (a required source or deployed location is missing)
"""

import hashlib
import os
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
REPO_MODULES = REPO_ROOT / "modules"
VENDOR_RELATIVE = pathlib.Path("_vendor")
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
REQUIRED_SKILL_FILES = frozenset(
    {
        "__init__.py",
        "registry.json",
        "skills_archive.py",
        "skills_contract.py",
        "skills_invoker.py",
        "skills_manager.py",
        "code-runner/entrypoint.py",
        "git-ops/entrypoint.py",
        "hf-model-ctl/entrypoint.py",
        "log-sleuth/entrypoint.py",
        "patch-forge/entrypoint.py",
        "system-doctor/entrypoint.py",
        "installed/browser-pilot/entrypoint.py",
        "installed/code-runner/entrypoint.py",
        "installed/demo-echo/entrypoint.py",
        "installed/git-ops/entrypoint.py",
        "installed/hf-model-ctl/entrypoint.py",
        "installed/log-sleuth/entrypoint.py",
        "installed/patch-forge/entrypoint.py",
        "installed/project-guru/entrypoint.py",
        "installed/prompt-lab/entrypoint.py",
        "installed/system-doctor/entrypoint.py",
        "installed/verify-echo-174869/entrypoint.py",
        "installed/verify-echo-655999/entrypoint.py",
        "installed/workspace-guard/entrypoint.py",
    }
)


REQUIRED_SIDECAR_MODULES = frozenset(
    {
        "computer_use_real_actions_ru.py",
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
        "pc_agent_actions.py",
        "tool_execution_ru.py",
        "workspace_policy.py",
    }
)


# Builtin skills are trusted, bundled and auto-seeded into every runtime by
# SkillsManager.ensure_builtins(). Their file set is DISCOVERED from repo source
# rather than hardcoded: a hardcoded list silently passed while the
# `computer-use` skill was missing from the shipped bundle entirely, so
# "открой <приложение>" had no workflow to compile in a packaged install.
# Discovery makes an omitted builtin skill a gate failure by construction.
_BUILTIN_MANIFEST_FILES = ("skill.json", "entrypoint.py", "workflow.json")


def discover_builtin_skill_files() -> frozenset[str]:
    """Every builtin skill file that must reach each shipped location."""
    builtin_root = REPO_MODULES / "skills" / "builtin"
    discovered: set[str] = set()
    if not builtin_root.is_dir():
        return frozenset()
    for skill_dir in sorted(builtin_root.iterdir(), key=lambda p: p.name.casefold()):
        if not skill_dir.is_dir() or not (skill_dir / "skill.json").is_file():
            continue
        for name in _BUILTIN_MANIFEST_FILES:
            if (skill_dir / name).is_file():
                discovered.add(f"builtin/{skill_dir.name}/{name}")
    return frozenset(discovered)


def check_skill_location(label: str, modules_location: pathlib.Path) -> tuple[int, list[str], list[str], list[str]]:
    source_root = REPO_MODULES / "skills"
    shipped_root = modules_location / "skills"
    stale: list[str] = []
    missing_in_repo: list[str] = []
    missing_in_shipped: list[str] = []
    matched = 0
    required = REQUIRED_SKILL_FILES | discover_builtin_skill_files()
    for relative in sorted(required, key=str.casefold):
        source = source_root / pathlib.Path(relative)
        shipped = shipped_root / pathlib.Path(relative)
        if not source.is_file():
            missing_in_repo.append(relative)
        elif not shipped.is_file():
            missing_in_shipped.append(relative)
        elif sha256(source) != sha256(shipped):
            stale.append(relative)
        else:
            matched += 1
    for relative in stale:
        print(f"FAIL: [{label}] STALE skill file: {relative}")
    for relative in missing_in_repo:
        print(f"FAIL: [{label}] MISSING skill file in repo: {relative}")
    for relative in missing_in_shipped:
        print(f"FAIL: [{label}] MISSING skill file in shipped runtime: {relative}")
    return matched, stale, missing_in_repo, missing_in_shipped


def deployed_modules() -> pathlib.Path | None:
    """Return the modules directory used by the supported LocalComet runtime.

    The normal launcher uses %LOCALAPPDATA%\\LocalCometDev\\workspace as its
    runtime workspace. The old LocalComet\\DevRuntime tree is intentionally not
    accepted here: checking it can produce a green result for a stale runtime.
    Tests and explicitly isolated runs may provide LOCALCOMET_BUNDLE_MODULES.
    """
    override = os.environ.get("LOCALCOMET_BUNDLE_MODULES")
    if override:
        return pathlib.Path(override)
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        return None
    return pathlib.Path(base) / "LocalCometDev" / "workspace" / "modules"


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_vendor_location(label: str, location: pathlib.Path) -> tuple[int, list[str], list[str]]:
    """Check every shipped file in the approved third-party vendor tree."""
    source_root = REPO_MODULES / VENDOR_RELATIVE
    shipped_root = location / VENDOR_RELATIVE
    source_files = {
        path.relative_to(source_root): path
        for path in source_root.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    } if source_root.is_dir() else {}
    shipped_files = {
        path.relative_to(shipped_root): path
        for path in shipped_root.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    } if shipped_root.is_dir() else {}
    stale: list[str] = []
    missing: list[str] = []
    matched = 0
    for relative, source in sorted(source_files.items(), key=lambda item: str(item[0]).casefold()):
        shipped = shipped_files.get(relative)
        display = str(VENDOR_RELATIVE / relative)
        if shipped is None:
            missing.append(display)
        elif sha256(source) != sha256(shipped):
            stale.append(display)
        else:
            matched += 1
    for relative in sorted(set(shipped_files) - set(source_files), key=str.casefold):
        stale.append(str(VENDOR_RELATIVE / relative))
    for relative in stale:
        print(f"FAIL: [{label}] STALE vendor file: {relative}")
    for relative in missing:
        print(f"FAIL: [{label}] MISSING vendor file: {relative}")
    return matched, stale, missing


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
    if deployed is None:
        print("FAIL: LOCALAPPDATA is not set; supported deployed runtime cannot be resolved")
        return 2
    targets.append(("deployed", deployed))

    checked = 0
    missing_locations: list[tuple[str, pathlib.Path]] = []
    total_matched = 0
    total_stale = 0
    total_missing_in_repo = 0
    total_missing_in_shipped = 0
    for label, location in targets:
        if not location.is_dir():
            print(f"FAIL: [{label}] required shipped modules not found: {location}")
            missing_locations.append((label, location))
            continue
        checked += 1
        matched, stale, missing_in_repo, missing_in_shipped = check_location(label, location)
        skill_matched, skill_stale, skill_missing_in_repo, skill_missing_in_shipped = check_skill_location(label, location)
        vendor_matched, vendor_stale, vendor_missing = check_vendor_location(label, location)
        total_matched += matched + skill_matched + vendor_matched
        total_stale += len(stale) + len(skill_stale) + len(vendor_stale)
        total_missing_in_repo += len(missing_in_repo) + len(skill_missing_in_repo)
        total_missing_in_shipped += len(missing_in_shipped) + len(skill_missing_in_shipped) + len(vendor_missing)

    if missing_locations:
        print(
            "Required shipped module location(s) are missing; parity cannot be "
            "considered green: "
            + ", ".join(label for label, _location in missing_locations)
        )
        return 2

    if checked == 0:
        print("FAIL: no required shipped sidecar module locations found")
        return 2

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
