"""Tool risk registry gate for LocalComet.

Introspects the REAL console-agent filesystem operations in modules/files.py
and verifies each is classified in security/invariants/tool_risk_levels.toml.

A "tool function" is any top-level function in modules/files.py whose body
calls safe_path() (the Projects/ confinement helper). safe_path() itself is
excluded because its body does not call safe_path().

A tool function is "mutating" if its body performs a filesystem mutation
(write_text, mkdir, unlink, rmtree, shutil.move/copy).

Rules enforced:
  1. Every tool function has a registry entry (implementation = "...::<fn>").
  2. Every mutating tool function has requires_approval = true.
  3. Every mutating tool function has risk_level in {guarded, dangerous}.
  4. Every registry entry has a valid risk_level.

Exit codes:
  0 - registry covers all real tool functions and rules hold
  1 - violation detected
  2 - could not read/parse inputs

Injection: add a new mutating function to modules/files.py that calls
safe_path() but is absent from the TOML -> this gate exits 1.
"""

import ast
import pathlib
import re
import sys

try:
    import tomllib
except ImportError:  # pragma: no cover
    print("FAIL: tomllib unavailable (Python >= 3.11 required)")
    sys.exit(2)

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
FILES_PY = REPO_ROOT / "modules" / "files.py"
TOOL_EXECUTION_PY = REPO_ROOT / "modules" / "tool_execution_ru.py"
REGISTRY = REPO_ROOT / "security" / "invariants" / "tool_risk_levels.toml"

VALID_RISK_LEVELS = {"read_only", "guarded", "dangerous"}
MUTATION_MARKERS = (
    "write_text",
    ".mkdir(",
    ".unlink(",
    "rmtree",
    "shutil.move",
    "shutil.copy",
)
EXECUTION_MUTATING_TOOLS = {"files.write", "files.create_folder", "files.delete"}


def parse_supported_tools(source: str) -> set[str]:
    """Extract the static SUPPORTED_TOOLS dispatch vocabulary from the sidecar."""
    tree = ast.parse(source)
    assignments = [
        node.value
        for node in tree.body
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        for target in (node.targets if isinstance(node, ast.Assign) else [node.target])
        if isinstance(target, ast.Name) and target.id == "SUPPORTED_TOOLS" and node.value is not None
    ]
    if len(assignments) != 1:
        raise ValueError("SUPPORTED_TOOLS must have exactly one top-level assignment")
    value = assignments[0]
    if not (
        isinstance(value, ast.Call)
        and isinstance(value.func, ast.Name)
        and value.func.id == "frozenset"
        and len(value.args) == 1
        and isinstance(value.args[0], (ast.Tuple, ast.List, ast.Set))
    ):
        raise ValueError("SUPPORTED_TOOLS must be a static frozenset literal")
    names: set[str] = set()
    for item in value.args[0].elts:
        if not isinstance(item, ast.Constant) or not isinstance(item.value, str):
            raise ValueError("SUPPORTED_TOOLS entries must be static strings")
        names.add(item.value)
    if not names:
        raise ValueError("SUPPORTED_TOOLS must not be empty")
    return names


def parse_top_level_functions(source: str) -> dict:
    """Return {function_name: body_text} for top-level defs."""
    functions = {}
    current_name = None
    current_body = []
    for line in source.split("\n"):
        match = re.match(r"^def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", line)
        if match:
            if current_name is not None:
                functions[current_name] = "\n".join(current_body)
            current_name = match.group(1)
            current_body = []
        elif current_name is not None:
            current_body.append(line)
    if current_name is not None:
        functions[current_name] = "\n".join(current_body)
    return functions


def main() -> int:
    if not FILES_PY.exists() or not TOOL_EXECUTION_PY.exists():
        print(f"FAIL: cannot find required tool source ({FILES_PY}, {TOOL_EXECUTION_PY})")
        return 2
    if not REGISTRY.exists():
        print(f"FAIL: cannot find {REGISTRY}")
        return 2

    source = FILES_PY.read_text(encoding="utf-8")
    functions = parse_top_level_functions(source)
    try:
        execution_tools = parse_supported_tools(TOOL_EXECUTION_PY.read_text(encoding="utf-8"))
    except (SyntaxError, ValueError) as exc:
        print(f"FAIL: cannot parse {TOOL_EXECUTION_PY}: {exc}")
        return 2

    tool_functions = {
        name: body
        for name, body in functions.items()
        if "safe_path(" in body
    }
    mutating_functions = {
        name
        for name, body in tool_functions.items()
        if any(marker in body for marker in MUTATION_MARKERS)
    }

    try:
        registry = tomllib.loads(REGISTRY.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        print(f"FAIL: registry is not valid TOML: {exc}")
        return 2

    tools = registry.get("tools", [])
    if not isinstance(tools, list) or not tools:
        print("FAIL: registry has no [[tools]] entries")
        return 1

    errors = []

    impl_to_entry = {}
    for entry in tools:
        name = entry.get("name")
        risk = entry.get("risk_level")
        impl = entry.get("implementation", "")
        requires = entry.get("requires_approval")
        if risk not in VALID_RISK_LEVELS:
            errors.append(f"INVALID_RISK_LEVEL: {name} -> {risk!r}")
        if not isinstance(requires, bool):
            errors.append(f"INVALID_REQUIRES_APPROVAL: {name} -> {requires!r}")
        fn = impl.split("::")[-1] if "::" in impl else None
        if fn:
            impl_to_entry[fn] = entry

    registry_by_name = {entry.get("name"): entry for entry in tools if isinstance(entry.get("name"), str)}
    for tool in sorted(execution_tools):
        entry = registry_by_name.get(tool)
        if entry is None:
            errors.append(f"UNCLASSIFIED_EXECUTION_TOOL: {tool} not in registry")
            continue
        if tool in EXECUTION_MUTATING_TOOLS:
            if entry.get("requires_approval") is not True:
                errors.append(f"EXECUTION_MUTATING_WITHOUT_APPROVAL: {tool}")
            if entry.get("risk_level") not in {"guarded", "dangerous"}:
                errors.append(f"EXECUTION_MUTATING_WRONG_RISK: {tool}")

    for fn in sorted(tool_functions):
        if fn not in impl_to_entry:
            kind = "mutating" if fn in mutating_functions else "read-only"
            errors.append(f"UNCLASSIFIED_TOOL: {fn} ({kind}) not in registry")
            continue
        entry = impl_to_entry[fn]
        if fn in mutating_functions:
            if entry.get("requires_approval") is not True:
                errors.append(
                    f"MUTATING_WITHOUT_APPROVAL: {fn} must have "
                    f"requires_approval = true"
                )
            if entry.get("risk_level") not in {"guarded", "dangerous"}:
                errors.append(
                    f"MUTATING_WRONG_RISK: {fn} must be guarded or dangerous, "
                    f"got {entry.get('risk_level')!r}"
                )

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print(
            f"\n{len(errors)} violation(s); "
            f"{len(tool_functions)} console tool function(s) introspected, "
            f"{len(mutating_functions)} mutating; {len(execution_tools)} sidecar tools checked"
        )
        return 1

    print(
        f"OK: {len(tool_functions)} console tool function(s) classified "
        f"({len(mutating_functions)} mutating, all requiring approval); "
        f"{len(execution_tools)} sidecar tools covered; {len(tools)} registry entries valid"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
