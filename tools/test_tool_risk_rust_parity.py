#!/usr/bin/env python
"""Parity check: Rust risk_level_for_tool mirror vs tool_risk_levels.toml.

The Rust approval boundary (approval_commands.rs::risk_level_for_tool) decides
whether a tool.call requires an approval token. It MUST stay in sync with
security/invariants/tool_risk_levels.toml (the source of truth). This test
cross-checks the Rust mirror against the TOML so a one-sided edit is caught
(closes the ADR-013 review finding that the Rust mirror was previously unchecked
by any gate; check_tool_risk_registry.py only covers the Python registry).

B3F extension: verifies REGISTERED_MODEL_TOOLS (Rust closed model-tool registry)
against Python TOOL_REGISTRY, SUPPORTED_TOOLS, and tool_risk_levels.toml.
"""
from __future__ import annotations

import ast
import pathlib
import re
import sys
import tomllib

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
TOML_PATH = REPO_ROOT / "security" / "invariants" / "tool_risk_levels.toml"
RUST_PATH = (
    REPO_ROOT / "desktop" / "localcomet-desktop" / "src-tauri" / "src" / "approval_commands.rs"
)
CONTROL_PLANE_PATH = (
    REPO_ROOT / "desktop" / "localcomet-desktop" / "src-tauri" / "src" / "control_plane.rs"
)
PYTHON_GATEWAY_PATH = REPO_ROOT / "modules" / "local_model_gateway_ru.py"
PYTHON_EXECUTION_PATH = REPO_ROOT / "modules" / "tool_execution_ru.py"

ARM_RE = re.compile(
    r'((?:"[^"]+"\s*\|\s*)*"[^"]+")\s*=>\s*'
    r'(?:RiskLevel::(?P<bare>ReadOnly|Guarded|Dangerous)'
    r'|Ok\(\s*RiskLevel::(?P<wrapped>ReadOnly|Guarded|Dangerous)\s*\))'
)

PERMISSIVE_FALLBACK_RE = re.compile(
    r'_\s*=>\s*(?:Ok\(\s*)?RiskLevel::(ReadOnly|Guarded|Dangerous)'
)

FAIL_CLOSED_FALLBACK_RE = re.compile(
    r'_\s*=>\s*Err\(\s*BridgeError::new\(\s*"unknown_tool"'
)


def rust_classification(text: str) -> dict[str, set[str]]:
    fn = re.search(r"fn risk_level_for_tool.*?\{(.*?)\n\}", text, re.DOTALL)
    if not fn:
        raise AssertionError("risk_level_for_tool not found in approval_commands.rs")
    body = fn.group(1)
    result: dict[str, set[str]] = {"Dangerous": set(), "Guarded": set(), "ReadOnly": set()}
    seen_names: list[str] = []
    for arm in ARM_RE.finditer(body):
        names = re.findall(r'"([^"]+)"', arm.group(1))
        variant = arm.group("bare") or arm.group("wrapped")
        for name in names:
            if name in seen_names:
                raise AssertionError(f"duplicate tool in risk_level_for_tool: {name}")
            seen_names.append(name)
        result.setdefault(variant, set()).update(names)
    if PERMISSIVE_FALLBACK_RE.search(body):
        raise AssertionError(
            "risk_level_for_tool has permissive fallback (_ => RiskLevel/Ok(RiskLevel))"
        )
    if not FAIL_CLOSED_FALLBACK_RE.search(body):
        raise AssertionError(
            'risk_level_for_tool missing fail-closed fallback (_ => Err(BridgeError::new("unknown_tool"...))'
        )
    return result


MODEL_REGISTRY_RE = re.compile(
    r"^(?:pub(?:\(crate\))?\s+)?(?:const|static)\s+REGISTERED_MODEL_TOOLS\s*:\s*&\[&str\]\s*=\s*&\[(.*?)\]",
    re.DOTALL | re.MULTILINE,
)


def extract_rust_model_registry(text: str) -> list[str] | None:
    stripped = re.sub(r'#\[cfg\(test\)\]\s*(?:const|static)\s+\w+[^;]*;', '', text)
    production = stripped.split("#[cfg(test)]")[0]
    matches = list(MODEL_REGISTRY_RE.finditer(production))
    if not matches:
        return None
    if len(matches) > 1:
        raise AssertionError(
            f"ambiguous: {len(matches)} REGISTERED_MODEL_TOOLS declarations found"
        )
    return re.findall(r'"([^"]+)"', matches[0].group(1))


def _find_top_level_assign(tree: ast.Module, name: str) -> ast.expr:
    found: list[ast.expr] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    found.append(node.value)
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == name and node.value:
                found.append(node.value)
    if not found:
        raise AssertionError(f"{name}: top-level assignment not found")
    if len(found) > 1:
        raise AssertionError(f"{name}: ambiguous — {len(found)} top-level assignments")
    return found[0]


def extract_python_tool_registry(source: str) -> list[str]:
    tree = ast.parse(source)
    value = _find_top_level_assign(tree, "TOOL_REGISTRY")
    if not isinstance(value, ast.Dict):
        raise AssertionError("TOOL_REGISTRY: value is not a static dict literal")
    keys: list[str] = []
    for key in value.keys:
        if not isinstance(key, ast.Constant) or not isinstance(key.value, str):
            raise AssertionError("TOOL_REGISTRY: non-string or dynamic key found")
        keys.append(key.value)
    return keys


def extract_supported_tools(source: str) -> list[str]:
    tree = ast.parse(source)
    value = _find_top_level_assign(tree, "SUPPORTED_TOOLS")
    if not isinstance(value, ast.Call):
        raise AssertionError("SUPPORTED_TOOLS: expected frozenset(...) call")
    if not isinstance(value.func, ast.Name) or value.func.id != "frozenset":
        raise AssertionError("SUPPORTED_TOOLS: not a frozenset() call")
    if len(value.args) != 1:
        raise AssertionError("SUPPORTED_TOOLS: frozenset must have exactly one argument")
    inner = value.args[0]
    if not isinstance(inner, (ast.Tuple, ast.List, ast.Set)):
        raise AssertionError("SUPPORTED_TOOLS: inner literal must be tuple/list/set")
    names: list[str] = []
    for elt in inner.elts:
        if not isinstance(elt, ast.Constant) or not isinstance(elt.value, str):
            raise AssertionError("SUPPORTED_TOOLS: non-string or dynamic element")
        names.append(elt.value)
    return names


def check_model_tool_registry() -> list[str]:
    errors: list[str] = []

    rust_source = CONTROL_PLANE_PATH.read_text(encoding="utf-8")
    rust_tools = extract_rust_model_registry(rust_source)
    if rust_tools is None:
        errors.append(
            "B3F-R1: Rust closed model-tool registry REGISTERED_MODEL_TOOLS "
            "is missing from control_plane.rs production section"
        )
        return errors

    if len(rust_tools) != len(set(rust_tools)):
        errors.append(f"B3F: Rust REGISTERED_MODEL_TOOLS contains duplicates: {rust_tools}")

    python_source = PYTHON_GATEWAY_PATH.read_text(encoding="utf-8")
    python_tools = extract_python_tool_registry(python_source)
    python_set = set(python_tools)
    rust_set = set(rust_tools)

    if len(python_tools) != len(python_set):
        errors.append(f"B3F: Python TOOL_REGISTRY contains duplicates: {python_tools}")

    if rust_set != python_set:
        errors.append(
            f"B3F-R2: Rust/Python model-tool parity mismatch: "
            f"rust_only={sorted(rust_set - python_set)} "
            f"python_only={sorted(python_set - rust_set)}"
        )

    if len(rust_tools) != 5:
        errors.append(
            f"B3F: Rust REGISTERED_MODEL_TOOLS cardinality is {len(rust_tools)}, expected 5"
        )

    with TOML_PATH.open("rb") as handle:
        data = tomllib.load(handle)
    risk_names = {tool["name"] for tool in data.get("tools", [])}
    missing_risk = rust_set - risk_names
    if missing_risk:
        errors.append(
            f"B3F-R3: Rust model tools missing from tool_risk_levels.toml: {sorted(missing_risk)}"
        )

    execution_source = PYTHON_EXECUTION_PATH.read_text(encoding="utf-8")
    execution_names = set(extract_supported_tools(execution_source))
    missing_execution = rust_set - execution_names
    if missing_execution:
        errors.append(
            f"B3F-R4: Rust model tools missing from execution dispatch: {sorted(missing_execution)}"
        )

    return errors


def parser_self_tests() -> list[str]:
    errors: list[str] = []

    nested_fixture = '''
TOOL_REGISTRY: dict[str, dict[str, Any]] = {
    "files.read": {
        "type": "function",
        "properties": {"path": {"type": "string"}},
        "required": ["path"]
    },
    "files.list": {"type": "function"}
}
'''
    keys = extract_python_tool_registry(nested_fixture)
    if keys != ["files.read", "files.list"]:
        errors.append(f"PARSER-T1: nested fixture extracted {keys}, expected only top-level keys")

    comment_fixture = '''
# TOOL_REGISTRY = {"evil.tool": {}}
TOOL_REGISTRY: dict[str, dict[str, Any]] = {
    "files.read": {}
}
'''
    keys2 = extract_python_tool_registry(comment_fixture)
    if "evil.tool" in keys2:
        errors.append("PARSER-T2: comment satisfied parser")

    supported_fixture = '''
SUPPORTED_TOOLS = frozenset(
    ("files.read", "files.list", "files.write")
)
'''
    st = extract_supported_tools(supported_fixture)
    if st != ["files.read", "files.list", "files.write"]:
        errors.append(f"PARSER-T6: SUPPORTED_TOOLS extracted {st}")

    rust_comment = '''
// const REGISTERED_MODEL_TOOLS: &[&str] = &["evil.tool"];
pub(crate) const REGISTERED_MODEL_TOOLS: &[&str] = &[
    "files.read",
];
'''
    rust_names = extract_rust_model_registry(rust_comment)
    if rust_names is None or "evil.tool" in rust_names:
        errors.append("PARSER-T7: Rust comment satisfied parser")

    rust_missing = "fn main() {}"
    if extract_rust_model_registry(rust_missing) is not None:
        errors.append("PARSER-T10: missing registry not detected")

    rust_dup = '''
pub(crate) const REGISTERED_MODEL_TOOLS: &[&str] = &[
    "files.read",
    "files.read",
];
'''
    dup_names = extract_rust_model_registry(rust_dup)
    if dup_names is not None and len(dup_names) != len(set(dup_names)):
        pass
    else:
        errors.append("PARSER-T9: duplicate not detectable")

    string_literal_fixture = '''
payload = "TOOL_REGISTRY = {'evil.tool': {}}"
'''
    try:
        extract_python_tool_registry(string_literal_fixture)
        errors.append("PARSER-T3: string literal satisfied parser (should fail)")
    except AssertionError:
        pass

    duplicate_assign_fixture = '''
TOOL_REGISTRY = {
    "files.read": {}
}

TOOL_REGISTRY = {
    "evil.tool": {}
}
'''
    try:
        extract_python_tool_registry(duplicate_assign_fixture)
        errors.append("PARSER-T4: duplicate assignments accepted (should fail)")
    except AssertionError as exc:
        if "ambiguous" not in str(exc).lower():
            errors.append(f"PARSER-T4: wrong error for duplicate: {exc}")

    dynamic_fixture = '''
TOOL_REGISTRY = build_registry()
'''
    try:
        extract_python_tool_registry(dynamic_fixture)
        errors.append("PARSER-T5: dynamic expression accepted (should fail)")
    except AssertionError as exc:
        if "not a static dict" not in str(exc).lower():
            errors.append(f"PARSER-T5: wrong error for dynamic: {exc}")

    rust_cfg_test_only = '''
#[cfg(test)]
mod tests {
    pub(crate) const REGISTERED_MODEL_TOOLS: &[&str] = &[
        "evil.tool",
    ];
}
'''
    cfg_result = extract_rust_model_registry(rust_cfg_test_only)
    if cfg_result is not None:
        errors.append("PARSER-T8a: cfg(test)-only registry treated as production")

    rust_cfg_test_with_production = '''
#[cfg(test)]
const REGISTERED_MODEL_TOOLS: &[&str] = &[
    "evil.tool",
];

pub(crate) const REGISTERED_MODEL_TOOLS: &[&str] = &[
    "files.read",
    "files.list",
    "files.write",
    "files.create_folder",
    "files.delete",
];

#[cfg(test)]
mod tests {}
'''
    cfg_prod_result = extract_rust_model_registry(rust_cfg_test_with_production)
    if cfg_prod_result is None:
        errors.append("PARSER-T8b: production registry not found alongside cfg(test)")
    elif "evil.tool" in cfg_prod_result:
        errors.append("PARSER-T8b: cfg(test) registry leaked into production extraction")
    elif cfg_prod_result != ["files.read", "files.list", "files.write", "files.create_folder", "files.delete"]:
        errors.append(f"PARSER-T8b: wrong extraction: {cfg_prod_result}")

    return errors


def main() -> int:
    with TOML_PATH.open("rb") as handle:
        data = tomllib.load(handle)
    tools = data.get("tools", [])
    toml_by_level: dict[str, set[str]] = {"dangerous": set(), "guarded": set(), "read_only": set()}
    for tool in tools:
        toml_by_level.setdefault(tool["risk_level"], set()).add(tool["name"])

    rust = rust_classification(RUST_PATH.read_text(encoding="utf-8"))

    errors = []
    if rust["Dangerous"] != toml_by_level["dangerous"]:
        errors.append(
            f"Dangerous mismatch: rust={sorted(rust['Dangerous'])} "
            f"toml={sorted(toml_by_level['dangerous'])}"
        )
    if rust["Guarded"] != toml_by_level["guarded"]:
        errors.append(
            f"Guarded mismatch: rust={sorted(rust['Guarded'])} "
            f"toml={sorted(toml_by_level['guarded'])}"
        )
    read_only_in_mutating = toml_by_level["read_only"] & (rust["Dangerous"] | rust["Guarded"])
    if read_only_in_mutating:
        errors.append(f"read_only tools classified as mutating in Rust: {sorted(read_only_in_mutating)}")

    errors.extend(parser_self_tests())
    errors.extend(check_model_tool_registry())

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print(f"OK: Rust risk_level_for_tool matches tool_risk_levels.toml ({len(tools)} tools)")
    print("OK: Rust REGISTERED_MODEL_TOOLS matches Python TOOL_REGISTRY (5 tools)")
    print("OK: R4 execution coverage confirmed via SUPPORTED_TOOLS")
    print("OK: parser self-tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
