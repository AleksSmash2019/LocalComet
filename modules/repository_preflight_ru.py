from __future__ import annotations

import ast
import json
import os
import re
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any


REPOSITORY_PREFLIGHT_VERSION = "v6.81.2"
MANIFEST_NAME = "localcomet_runtime_manifest.json"
REQUIRED_MANIFEST_KEYS = ("entrypoints", "runtime", "lazy_runtime", "tests", "tools")
PATH_CATEGORIES = (*REQUIRED_MANIFEST_KEYS,)
SECRET_PATTERNS = (
    ("openai_api_key", re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b")),
    ("github_token", re.compile(r"\bghp_[A-Za-z0-9_]{12,}\b")),
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("authorization_header", re.compile(r"\bAuthorization\s*:\s*(Bearer|Basic)\s+\S+", re.IGNORECASE)),
    ("bearer_token", re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{16,}\b", re.IGNORECASE)),
    (
        "secret_assignment",
        re.compile(
            r"(?i)\b(api[_-]?key|token|password|passwd|secret|client[_-]?secret)\b\s*[:=]\s*['\"]?[^'\"\s]{8,}"
        ),
    ),
)
MACHINE_PATH_PATTERNS = (
    ("windows_user_path", re.compile(r"[A-Za-z]:(?:\\\\|\\)Users(?:\\\\|\\)[^\\\s'\"]+")),
    ("windows_absolute_path", re.compile(r"[A-Za-z]:(?:\\\\|\\)[^\\\s'\"]+")),
    ("posix_user_path", re.compile(r"/Users/[^/\s'\"]+|/home/[^/\s'\"]+")),
)
LOCAL_PREFIXES = {"agents", "core", "modules", "next", "tools"}


def resolve_project_root(root: str | Path | None = None) -> Path:
    if root is not None:
        return Path(root).expanduser().resolve()
    for env_name in ("LOCALCOMET_ROOT", "LOCALCOMET_ROOT_DIR"):
        value = os.environ.get(env_name, "").strip()
        if value:
            return Path(value).expanduser().resolve()
    return Path(__file__).resolve().parents[1]


def _redact(text: Any, root: Path) -> str:
    value = str(text or "")
    for marker in {str(root), root.as_posix(), str(Path.home()), str(Path.home()).replace("\\", "/")}:
        if marker:
            value = value.replace(marker, "<PROJECT_ROOT>")
    return value


def _safe_rel_path(raw: str) -> tuple[str | None, str | None]:
    value = str(raw or "").replace("\\", "/").strip()
    if not value:
        return None, "empty_path"
    if PureWindowsPath(value).drive or value.startswith("/") or value.startswith("\\"):
        return None, "absolute_path"
    pure = PurePosixPath(value)
    if any(part in {"", ".", ".."} for part in pure.parts):
        return None, "traversal_path"
    return pure.as_posix(), None


def _resolve_under_root(root: Path, rel_path: str) -> bool:
    try:
        (root / rel_path).resolve().relative_to(root.resolve())
        return True
    except Exception:
        return False


def load_runtime_manifest(root: str | Path | None = None) -> dict[str, Any]:
    project_root = resolve_project_root(root)
    path = project_root / MANIFEST_NAME
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _manifest_paths(manifest: dict[str, Any]) -> list[tuple[str, str]]:
    paths: list[tuple[str, str]] = []
    for category in PATH_CATEGORIES:
        values = manifest.get(category, [])
        if isinstance(values, list):
            for item in values:
                paths.append((category, str(item)))
    return paths


def validate_manifest(root: str | Path, manifest: dict[str, Any]) -> dict[str, Any]:
    project_root = resolve_project_root(root)
    unsafe_paths: list[dict[str, str]] = []
    missing: list[dict[str, str]] = []
    warnings: list[str] = []
    present = bool(manifest)
    if not present:
        return {
            "present": False,
            "release": "",
            "runtime_count": 0,
            "lazy_runtime_count": 0,
            "unsafe_paths": [],
            "missing": [{"path": MANIFEST_NAME, "category": "manifest"}],
            "warnings": ["runtime_manifest_missing"],
        }

    for key in REQUIRED_MANIFEST_KEYS:
        values = manifest.get(key)
        if not isinstance(values, list):
            warnings.append(f"manifest_key_not_list:{key}")
            continue
        normalized = [str(item).replace("\\", "/") for item in values]
        if normalized != sorted(normalized, key=str.lower):
            warnings.append(f"manifest_list_not_sorted:{key}")
        if len(normalized) != len(set(normalized)):
            warnings.append(f"manifest_list_not_unique:{key}")

    required_categories = {"entrypoints", "runtime", "lazy_runtime", "tools", "tests"}
    for category, raw in _manifest_paths(manifest):
        rel, reason = _safe_rel_path(raw)
        if reason or rel is None:
            unsafe_paths.append({"path": raw, "category": category, "reason": str(reason)})
            continue
        if not _resolve_under_root(project_root, rel):
            unsafe_paths.append({"path": rel, "category": category, "reason": "outside_root"})
            continue
        if category in required_categories and not (project_root / rel).is_file():
            missing.append({"path": rel, "category": category})

    return {
        "present": True,
        "release": str(manifest.get("release", "")),
        "runtime_count": len(manifest.get("runtime", [])) if isinstance(manifest.get("runtime"), list) else 0,
        "lazy_runtime_count": len(manifest.get("lazy_runtime", [])) if isinstance(manifest.get("lazy_runtime"), list) else 0,
        "unsafe_paths": sorted(unsafe_paths, key=lambda item: (item["category"], item["path"])),
        "missing": sorted(missing, key=lambda item: (item["category"], item["path"])),
        "warnings": sorted(warnings),
    }


def _module_name_for_path(rel_path: str) -> str | None:
    if not rel_path.endswith(".py"):
        return None
    parts = rel_path[:-3].split("/")
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _local_module_exists(root: Path, imported: str) -> bool:
    parts = imported.split(".")
    for index in range(len(parts), 0, -1):
        rel = Path(*parts[:index])
        if (
            (root / rel).with_suffix(".py").is_file()
            or (root / rel / "__init__.py").is_file()
            or (root / rel).is_dir()
        ):
            return True
    return False


def _resolve_relative_import(module_name: str, level: int, imported: str) -> str:
    parts = module_name.split(".")
    base = parts[: max(0, len(parts) - level)]
    if imported:
        base.extend(imported.split("."))
    return ".".join(part for part in base if part)


def build_static_import_graph(root: str | Path, manifest: dict[str, Any]) -> dict[str, Any]:
    project_root = resolve_project_root(root)
    nodes: list[dict[str, str]] = []
    edges: list[dict[str, str]] = []
    unresolved: list[dict[str, str]] = []
    module_map: dict[str, str] = {}
    source_paths: list[tuple[str, str]] = []
    for category, raw in _manifest_paths(manifest):
        rel, reason = _safe_rel_path(raw)
        if reason or rel is None or not rel.endswith(".py"):
            continue
        path = project_root / rel
        if not path.is_file():
            continue
        module = _module_name_for_path(rel)
        if module:
            module_map[module] = rel
            source_paths.append((category, rel))

    for category, rel in sorted(source_paths, key=lambda item: item[1].lower()):
        path = project_root / rel
        module_name = _module_name_for_path(rel) or rel
        nodes.append({"path": rel, "module": module_name, "category": category})
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    imports.add(_resolve_relative_import(module_name, node.level, node.module or ""))
                elif node.module:
                    imports.add(node.module)
        for imported in sorted(imports, key=str.lower):
            head = imported.split(".", 1)[0]
            if head not in LOCAL_PREFIXES:
                continue
            target = None
            for candidate in sorted(module_map, key=len, reverse=True):
                if imported == candidate or imported.startswith(candidate + "."):
                    target = module_map[candidate]
                    break
            if target:
                edges.append({"from": rel, "to": target, "import": imported})
            elif not _local_module_exists(project_root, imported):
                unresolved.append({"from": rel, "import": imported, "reason": "local_module_missing"})
    return {
        "nodes": sorted(nodes, key=lambda item: item["path"].lower()),
        "edges": sorted(edges, key=lambda item: (item["from"].lower(), item["to"].lower(), item["import"].lower())),
        "unresolved_imports": sorted(unresolved, key=lambda item: (item["from"].lower(), item["import"].lower())),
    }


def _scan_text_markers(root: Path, rel_path: str, text: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    machine_paths: list[dict[str, Any]] = []
    secret_markers: list[dict[str, Any]] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        for category, pattern in MACHINE_PATH_PATTERNS:
            if pattern.search(line):
                machine_paths.append({"file": rel_path, "line": line_no, "category": category})
        for category, pattern in SECRET_PATTERNS:
            if pattern.search(line):
                secret_markers.append({"file": rel_path, "line": line_no, "category": category})
    return machine_paths, secret_markers


def _syntax_and_markers(root: Path, manifest: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    syntax_errors: list[dict[str, Any]] = []
    machine_paths: list[dict[str, Any]] = []
    secret_markers: list[dict[str, Any]] = []
    seen: set[str] = set()
    for _category, raw in _manifest_paths(manifest):
        rel, reason = _safe_rel_path(raw)
        if reason or rel is None or rel in seen:
            continue
        seen.add(rel)
        path = root / rel
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".py", ".pyw", ".json", ".md", ".txt", ".toml", ".yaml", ".yml"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        found_machine, found_secret = _scan_text_markers(root, rel, text)
        machine_paths.extend(found_machine)
        secret_markers.extend(found_secret)
        if path.suffix.lower() in {".py", ".pyw"}:
            try:
                compile(text, rel, "exec")
            except SyntaxError as exc:
                syntax_errors.append({"file": rel, "line": exc.lineno or 0, "category": "syntax_error"})
    return (
        sorted(syntax_errors, key=lambda item: (item["file"].lower(), item["line"])),
        sorted(machine_paths, key=lambda item: (item["file"].lower(), item["line"], item["category"])),
        sorted(secret_markers, key=lambda item: (item["file"].lower(), item["line"], item["category"])),
    )


def run_repository_preflight(root: str | Path | None = None) -> dict[str, Any]:
    project_root = resolve_project_root(root)
    warnings: list[str] = []
    try:
        manifest = load_runtime_manifest(project_root)
    except Exception as exc:
        manifest = {}
        warnings.append(f"manifest_parse_error:{type(exc).__name__}")
    manifest_validation = validate_manifest(project_root, manifest)
    warnings.extend(manifest_validation.get("warnings", []))
    syntax_errors, machine_paths, secret_markers = _syntax_and_markers(project_root, manifest)
    import_graph = build_static_import_graph(project_root, manifest)
    missing = manifest_validation.get("missing", [])
    unsafe_paths = manifest_validation.get("unsafe_paths", [])
    unresolved = import_graph.get("unresolved_imports", [])
    ok = not (missing or unsafe_paths or syntax_errors or unresolved)
    result = {
        "mode": "repository_preflight",
        "version": REPOSITORY_PREFLIGHT_VERSION,
        "ok": ok,
        "root": "<PROJECT_ROOT>",
        "manifest": {
            "present": bool(manifest_validation.get("present")),
            "release": manifest_validation.get("release", ""),
            "runtime_count": manifest_validation.get("runtime_count", 0),
            "lazy_runtime_count": manifest_validation.get("lazy_runtime_count", 0),
        },
        "missing": missing,
        "syntax_errors": syntax_errors,
        "unresolved_imports": unresolved,
        "unsafe_paths": unsafe_paths,
        "machine_paths": machine_paths,
        "secret_markers": secret_markers,
        "warnings": sorted(set(_redact(item, project_root) for item in warnings)),
        "summary": {
            "missing_count": len(missing),
            "syntax_error_count": len(syntax_errors),
            "unresolved_import_count": len(unresolved),
            "unsafe_path_count": len(unsafe_paths),
            "machine_path_count": len(machine_paths),
            "secret_marker_count": len(secret_markers),
            "manifest_warning_count": len(set(warnings)),
        },
    }
    return result
