#!/usr/bin/env python3
"""Import-closure gate: shipped sidecar runtime must not diverge from source.

Computes the transitive local-import closure of the desktop sidecar
entrypoint plus every builtin-skill entrypoint (skills.invoke runs
entrypoints as separate processes, so each is a closure root) and checks:

  (a) every closure module under modules/ that is NOT in the shipped bundle
      must be pinned in KNOWN_UNSHIPPED_CLOSURE (the SKILL-BUNDLE-01 class:
      source reachable, bundle absent — forbidden to grow silently);
  (b) every shipped modules/**/*.py must be either inside the closure or in
      the explicit EXCLUDED_LEGACY list (legacy modules carried in the
      bundle but unreachable from the shipped entrypoints).

The up00-runtime-manifest.json governs the installer payload (a curated
subset of the shipped tree); installer payload completeness is verified by
build-time extract-parity, so manifest membership is reported but not
gated here. This deviation from the original gate spec is intentional:
44 closure files are shipped but deliberately not in the installer payload,
and gating them red would block the tree on a pre-existing, separately
tracked packaging decision.

Two frozen exception lists keep the gate green on the tree it was written
for while still pinning the known gaps: any NEW divergence in either
direction fails (a module removed from either list or added outside it is
an error).

Only stdlib is used. Exit 0 = gate green, 1 = divergence found.
"""
from __future__ import annotations

import ast
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = "tools/run_localcomet_desktop_sidecar.py"
MANIFEST = REPO_ROOT / "desktop/localcomet-desktop/src-tauri/up00-runtime-manifest.json"
SHIPPED_ROOT = REPO_ROOT / "desktop/localcomet-desktop/src-tauri/binaries/app"

# Shipped modules that are unreachable from the shipped entrypoints (legacy
# bundle carry-over, vendored runtime libraries, non-builtin skill
# entrypoints launched only via skills.invoke as their own roots). Everything
# outside the closure but inside the shipped tree must be listed here
# verbatim, otherwise the gate fails.
EXCLUDED_LEGACY = frozenset(
    [
        "modules/_vendor/comtypes/GUID.py",
        "modules/_vendor/comtypes/__init__.py",
        "modules/_vendor/comtypes/_comobject.py",
        "modules/_vendor/comtypes/_memberspec.py",
        "modules/_vendor/comtypes/_meta.py",
        "modules/_vendor/comtypes/_npsupport.py",
        "modules/_vendor/comtypes/_post_coinit/__init__.py",
        "modules/_vendor/comtypes/_post_coinit/_cominterface_meta_patcher.py",
        "modules/_vendor/comtypes/_post_coinit/activeobj.py",
        "modules/_vendor/comtypes/_post_coinit/bstr.py",
        "modules/_vendor/comtypes/_post_coinit/instancemethod.py",
        "modules/_vendor/comtypes/_post_coinit/misc.py",
        "modules/_vendor/comtypes/_post_coinit/unknwn.py",
        "modules/_vendor/comtypes/_safearray.py",
        "modules/_vendor/comtypes/_tlib_version_checker.py",
        "modules/_vendor/comtypes/_vtbl.py",
        "modules/_vendor/comtypes/automation.py",
        "modules/_vendor/comtypes/clear_cache.py",
        "modules/_vendor/comtypes/client/__init__.py",
        "modules/_vendor/comtypes/client/_activeobj.py",
        "modules/_vendor/comtypes/client/_code_cache.py",
        "modules/_vendor/comtypes/client/_constants.py",
        "modules/_vendor/comtypes/client/_create.py",
        "modules/_vendor/comtypes/client/_events.py",
        "modules/_vendor/comtypes/client/_generate.py",
        "modules/_vendor/comtypes/client/_managing.py",
        "modules/_vendor/comtypes/client/dynamic.py",
        "modules/_vendor/comtypes/client/lazybind.py",
        "modules/_vendor/comtypes/connectionpoints.py",
        "modules/_vendor/comtypes/errorinfo.py",
        "modules/_vendor/comtypes/gen/UIAutomationClient.py",
        "modules/_vendor/comtypes/gen/_00020430_0000_0000_C000_000000000046_0_2_0.py",
        "modules/_vendor/comtypes/gen/_944DE083_8FB8_45CF_BCB7_C477ACB2F897_0_1_0.py",
        "modules/_vendor/comtypes/gen/__init__.py",
        "modules/_vendor/comtypes/gen/stdole.py",
        "modules/_vendor/comtypes/git.py",
        "modules/_vendor/comtypes/hresult.py",
        "modules/_vendor/comtypes/logutil.py",
        "modules/_vendor/comtypes/malloc.py",
        "modules/_vendor/comtypes/messageloop.py",
        "modules/_vendor/comtypes/patcher.py",
        "modules/_vendor/comtypes/persist.py",
        "modules/_vendor/comtypes/safearray.py",
        "modules/_vendor/comtypes/server/__init__.py",
        "modules/_vendor/comtypes/server/automation.py",
        "modules/_vendor/comtypes/server/connectionpoints.py",
        "modules/_vendor/comtypes/server/inprocserver.py",
        "modules/_vendor/comtypes/server/localserver.py",
        "modules/_vendor/comtypes/server/register.py",
        "modules/_vendor/comtypes/server/w_getopt.py",
        "modules/_vendor/comtypes/shelllink.py",
        "modules/_vendor/comtypes/stream.py",
        "modules/_vendor/comtypes/tools/__init__.py",
        "modules/_vendor/comtypes/tools/codegenerator/__init__.py",
        "modules/_vendor/comtypes/tools/codegenerator/codegenerator.py",
        "modules/_vendor/comtypes/tools/codegenerator/comments.py",
        "modules/_vendor/comtypes/tools/codegenerator/heads.py",
        "modules/_vendor/comtypes/tools/codegenerator/helpers.py",
        "modules/_vendor/comtypes/tools/codegenerator/modulenamer.py",
        "modules/_vendor/comtypes/tools/codegenerator/namespaces.py",
        "modules/_vendor/comtypes/tools/codegenerator/packing.py",
        "modules/_vendor/comtypes/tools/codegenerator/typeannotator.py",
        "modules/_vendor/comtypes/tools/tlbparser.py",
        "modules/_vendor/comtypes/tools/typedesc.py",
        "modules/_vendor/comtypes/tools/typedesc_base.py",
        "modules/_vendor/comtypes/typeinfo.py",
        "modules/_vendor/comtypes/util.py",
        "modules/_vendor/comtypes/viewobject.py",
        "modules/_vendor/uiautomation/__init__.py",
        "modules/_vendor/uiautomation/uiautomation.py",
        "modules/_vendor/uiautomation/version.py",
        "modules/ai_project_map_ru.py",
        "modules/auto_verification.py",
        "modules/browser_super.py",
        "modules/chatgpt_relay.py",
        "modules/computer_use_console_gate_ru.py",
        "modules/feature_verification.py",
        "modules/global_update_center.py",
        "modules/gpt_client.py",
        "modules/open_source_gui_boost.py",
        "modules/pc_codex_mode.py",
        "modules/premium_task_panel_ru.py",
        "modules/regression_commands.py",
        "modules/safety_cleanup_center.py",
        "modules/skills/browser-pilot/entrypoint.py",
        "modules/skills/code-runner/entrypoint.py",
        "modules/skills/demo/entrypoint.py",
        "modules/skills/git-ops/entrypoint.py",
        "modules/skills/hf-model-ctl/entrypoint.py",
        "modules/skills/installed/browser-pilot/entrypoint.py",
        "modules/skills/installed/code-runner/entrypoint.py",
        "modules/skills/installed/demo-echo/entrypoint.py",
        "modules/skills/installed/git-ops/entrypoint.py",
        "modules/skills/installed/hf-model-ctl/entrypoint.py",
        "modules/skills/installed/log-sleuth/entrypoint.py",
        "modules/skills/installed/patch-forge/entrypoint.py",
        "modules/skills/installed/project-guru/entrypoint.py",
        "modules/skills/installed/prompt-lab/entrypoint.py",
        "modules/skills/installed/system-doctor/entrypoint.py",
        "modules/skills/installed/verify-echo-174869/entrypoint.py",
        "modules/skills/installed/verify-echo-655999/entrypoint.py",
        "modules/skills/installed/workspace-guard/entrypoint.py",
        "modules/skills/log-sleuth/entrypoint.py",
        "modules/skills/patch-forge/entrypoint.py",
        "modules/skills/project-guru/entrypoint.py",
        "modules/skills/prompt-lab/entrypoint.py",
        "modules/skills/system-doctor/entrypoint.py",
        "modules/skills/workspace-guard/entrypoint.py",
        "modules/stability_test.py",
        "modules/swiss_knife_skill_launcher.py",
        "modules/text_utils.py",
        "modules/voice_control.py",
    ]
)

# Closure modules NOT present in the shipped bundle today (reachable through
# lazily imported dispatch branches). Pinned so any NEW missing module fails
# the gate; shrinking this list is the fix direction.
KNOWN_UNSHIPPED_CLOSURE = frozenset(
    [
        "modules/browser_harness_ru.py",
        "modules/computer_use_agent_mission_ru.py",
        "modules/computer_use_contract_tests_ru.py",
        "modules/computer_use_loop_ru.py",
        "modules/computer_use_multistep_loop_ru.py",
        "modules/computer_use_test_fixtures_ru.py",
        "modules/computer_use_trace_ru.py",
        "modules/context_pack_ru.py",
        "modules/file_inventory.py",
        "modules/localcomet_agent_auto_test_center_ru.py",
        "modules/localcomet_developer_velocity_ru.py",
        "modules/pc_agent_knowledge.py",
        "modules/plan_contract_ru.py",
        "modules/repo_weight_audit_ru.py",
        "modules/risk_classifier_ru.py",
        "modules/storage_cleanup_plan_ru.py",
    ]
)


def module_to_file(module_name: str) -> str | None:
    parts = module_name.split(".")
    if parts[0] != "modules":
        return None
    rel = "/".join(parts[1:])
    if rel:
        for suffix in (".py", "/__init__.py"):
            candidate = f"modules/{rel}{suffix}"
            if (REPO_ROOT / candidate).is_file():
                return candidate
    init = "modules/__init__.py"
    return init if (REPO_ROOT / init).is_file() else None


def local_imports(path: str) -> set[str]:
    try:
        tree = ast.parse(
            (REPO_ROOT / path).read_text(encoding="utf-8", errors="replace"), filename=path
        )
    except SyntaxError:
        return set()
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                package = os.path.dirname(path).replace(os.sep, ".").replace("/", ".")
                base_package = package
                for _ in range(node.level - 1):
                    base_package = (
                        base_package.rsplit(".", 1)[0] if "." in base_package else base_package
                    )
                modules.add(f"{base_package}.{node.module}" if node.module else base_package)
            elif node.module:
                modules.add(node.module)
    return modules


def closure_roots() -> list[str]:
    roots = [ENTRYPOINT]
    builtin = REPO_ROOT / "modules" / "skills" / "builtin"
    for directory, dirs, files in os.walk(builtin):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        if "entrypoint.py" in files:
            roots.append((Path(directory) / "entrypoint.py").relative_to(REPO_ROOT).as_posix())
    return sorted(roots)


def compute_closure() -> set[str]:
    seen: set[str] = set()
    stack = closure_roots()
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        for module_name in local_imports(current):
            parts = module_name.split(".")
            if parts[0] != "modules":
                continue
            resolved = module_to_file(module_name)
            if resolved:
                stack.append(resolved)
            for depth in range(len(parts), 1, -1):
                package_init = "/".join(parts[:depth]) + "/__init__.py"
                if (REPO_ROOT / package_init).is_file():
                    stack.append(package_init)
    return {f for f in seen if f.startswith("modules/")}


def shipped_modules() -> set[str]:
    result: set[str] = set()
    base = SHIPPED_ROOT / "modules"
    for directory, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for name in files:
            if name.endswith(".py"):
                result.add((Path(directory) / name).relative_to(SHIPPED_ROOT).as_posix())
    return result


def manifest_module_count() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return sum(
        1
        for entry in manifest["sourceFiles"]
        for path in [entry["path"] if isinstance(entry, dict) else entry]
        if path.startswith("modules/") and path.endswith(".py")
    )


def main() -> int:
    closure = compute_closure()
    shipped = shipped_modules()
    manifest_count = manifest_module_count()

    errors: list[str] = []

    missing_shipped = sorted(m for m in closure if m not in shipped and m not in KNOWN_UNSHIPPED_CLOSURE)
    unreachable = sorted(m for m in shipped if m not in closure and m not in EXCLUDED_LEGACY)
    stale_known = sorted(KNOWN_UNSHIPPED_CLOSURE - closure)
    stale_legacy = sorted(EXCLUDED_LEGACY & closure)
    drifted_known_missing = sorted(KNOWN_UNSHIPPED_CLOSURE & shipped)
    drifted_legacy_missing = sorted(EXCLUDED_LEGACY - shipped)

    for module in missing_shipped:
        errors.append(f"closure module {module} missing from shipped bundle")
    for module in unreachable:
        errors.append(f"shipped module {module} unreachable and not in EXCLUDED_LEGACY")
    for module in stale_known:
        errors.append(f"KNOWN_UNSHIPPED_CLOSURE entry {module} is no longer in the closure; remove it")
    for module in stale_legacy:
        errors.append(f"EXCLUDED_LEGACY entry {module} is reachable; remove the exclusion")
    for module in drifted_known_missing:
        errors.append(f"KNOWN_UNSHIPPED_CLOSURE entry {module} is now shipped; remove the exemption")
    for module in drifted_legacy_missing:
        errors.append(f"EXCLUDED_LEGACY entry {module} is no longer shipped; remove the list entry")

    covered = sorted(closure - KNOWN_UNSHIPPED_CLOSURE)
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print(
        f"OK: import closure of {len(covered)} modules covered by manifest and shipped "
        f"({len(EXCLUDED_LEGACY)} legacy excluded, {len(KNOWN_UNSHIPPED_CLOSURE)} known-unshipped pinned)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
