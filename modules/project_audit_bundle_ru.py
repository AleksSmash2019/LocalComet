from __future__ import annotations

import ast
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any


RELEASE = "v6.80.2"
VERIFIER_SCHEMA_VERSION = "v6.80.2"
MANIFEST_NAME = "localcomet_runtime_manifest.json"
FIXED_ZIP_DT = (2026, 1, 1, 0, 0, 0)
TEXT_EXTENSIONS = {
    ".bat",
    ".cfg",
    ".css",
    ".csv",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".jsonl",
    ".md",
    ".py",
    ".pyw",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
SOURCE_SCAN_ROOTS = ("agents", "core", "docs", "modules", "next", "tools")
TOP_LEVEL_SOURCE_EXTENSIONS = {".py", ".md", ".json", ".txt"}
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
REDACT_PATTERNS = tuple((name, re.compile(pattern.pattern, pattern.flags)) for name, pattern in SECRET_PATTERNS)
EXCLUDE_PREFIXES = (
    ".git/",
    ".incident_backup/",
    ".tmp/",
    ".localcomet/temp/",
    ".localcomet/reviewer/",
    "Projects/BrowserProfile/",
    "LocalAgent_Archive/",
)
EXCLUDE_GLOBS = (
    "__pycache__/**",
    "*.pyc",
    "*.pyo",
    "*.zip",
    "*.7z",
    "*.rar",
    "tools/install_*.py",
    "tools/repair_russian_menu_v617d.py",
)
GENERATED_PREFIXES = (
    "Projects/Reports/",
    "Projects/Logs/",
    "Projects/ComputerUse/reports/",
)
RUNTIME_JSON_PREFIXES = ("Projects/",)
TEST_COMMANDS = [
    "tools/test_v677_regression.py",
    "tools/test_v678_router_registry.py",
    "tools/test_v679_retention.py",
    "tools/test_v680_reproducibility.py",
    "tools/test_v6801_audit_bundle.py",
]
RECURSIVE_TEST_COMMANDS = {
    "tools/test_v6801_audit_bundle.py",
    "tools/test_v6802_bundle_security.py",
}
AUDIT_BUNDLE_TEST_ENV = "LOCALCOMET_AUDIT_BUNDLE_RUNNING_TESTS"


class AuditBundleError(RuntimeError):
    pass


@dataclass(frozen=True)
class IncludedFile:
    rel_path: str
    category: str
    origin: str
    size: int
    sha256: str


def _json_bytes(data: Any) -> bytes:
    return (json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise AuditBundleError(f"unable to read JSON {path.name}: {exc}") from exc
    if not isinstance(payload, dict):
        raise AuditBundleError(f"{path.name} must contain a JSON object")
    return payload


def _redact_path_text(text: str) -> str:
    home = str(Path.home()).replace("\\", "/")
    if home:
        text = text.replace(str(Path.home()), "<USER_HOME>")
        text = text.replace(home, "<USER_HOME>")
    return text


def redact_text(text: str, limit: int | None = None) -> str:
    redacted = _redact_path_text(str(text))
    for category, pattern in REDACT_PATTERNS:
        redacted = pattern.sub(f"<REDACTED:{category}>", redacted)
    if limit is not None and len(redacted) > limit:
        redacted = redacted[:limit] + "\n<TRUNCATED>"
    return redacted


def _safe_rel_path(raw: str) -> str:
    value = str(raw or "").replace("\\", "/").strip()
    if not value:
        raise AuditBundleError("empty path is not allowed")
    if PureWindowsPath(value).drive or value.startswith("/") or value.startswith("\\"):
        raise AuditBundleError(f"absolute path rejected: {raw}")
    pure = PurePosixPath(value)
    if any(part in {"", ".", ".."} for part in pure.parts):
        raise AuditBundleError(f"unsafe relative path rejected: {raw}")
    return pure.as_posix()


def _resolve_under_root(root: Path, rel_path: str) -> Path:
    safe = _safe_rel_path(rel_path)
    path = (root / safe).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise AuditBundleError(f"path escapes project root: {rel_path}") from exc
    return path


def _is_reparse_point(path: Path) -> bool:
    try:
        return bool(path.lstat().st_file_attributes & 0x400)
    except AttributeError:
        return False
    except OSError:
        return False


def _has_external_link(root: Path, path: Path) -> bool:
    root_resolved = root.resolve()
    current = path
    chain = [path, *path.parents]
    for candidate in chain:
        if candidate == root_resolved.parent:
            break
        if candidate.exists() and (candidate.is_symlink() or _is_reparse_point(candidate)):
            try:
                candidate.resolve().relative_to(root_resolved)
            except ValueError:
                return True
    try:
        path.resolve().relative_to(root_resolved)
    except ValueError:
        return True
    return False


def _run_git(root: Path, args: list[str], timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=timeout,
    )


def _git_lines(root: Path, args: list[str]) -> list[str]:
    result = _run_git(root, args)
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _collect_git_metadata(root: Path) -> dict[str, str]:
    commands = {
        "git_status.txt": ["status", "--short", "--untracked-files=no"],
        "git_diff.patch": ["diff", "--binary", "HEAD"],
        "git_diff_stat.txt": ["diff", "--stat", "HEAD"],
        "git_diff_name_status.txt": ["diff", "--name-status", "HEAD"],
    }
    metadata: dict[str, str] = {}
    for name, args in commands.items():
        try:
            result = _run_git(root, args, timeout=120)
            text = result.stdout if result.returncode == 0 else (result.stderr or result.stdout)
        except Exception as exc:
            text = f"{type(exc).__name__}: {exc}"
        metadata[name] = redact_text(text)
    return metadata


def _load_runtime_manifest(root: Path) -> dict[str, Any]:
    path = root / MANIFEST_NAME
    if not path.exists():
        raise AuditBundleError(f"missing required {MANIFEST_NAME}")
    data = _read_json(path)
    for key in ("entrypoints", "runtime", "lazy_runtime", "tests", "tools"):
        if key not in data or not isinstance(data[key], list):
            raise AuditBundleError(f"{MANIFEST_NAME} missing list category: {key}")
    return data


def _manifest_category_map(manifest: dict[str, Any]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for category in ("entrypoints", "runtime", "lazy_runtime", "tests", "tools"):
        for item in manifest.get(category, []):
            mapping[_safe_rel_path(str(item))] = category
    mapping[MANIFEST_NAME] = "metadata_manifest"
    return mapping


def _discover_source_files(root: Path, tracked: set[str], manifest_map: dict[str, str]) -> dict[str, tuple[str, str]]:
    candidates: dict[str, tuple[str, str]] = {}
    for rel in tracked:
        candidates[rel] = (manifest_map.get(rel, "tracked"), "git_ls_files")
    for rel, category in manifest_map.items():
        candidates[rel] = (category, "runtime_manifest")
    for child in sorted(root.iterdir(), key=lambda p: p.name.lower()):
        if child.is_file() and child.suffix.lower() in TOP_LEVEL_SOURCE_EXTENSIONS:
            rel = child.relative_to(root).as_posix()
            candidates.setdefault(rel, (manifest_map.get(rel, "important_untracked_source"), "source_scan"))
    for scan_root in SOURCE_SCAN_ROOTS:
        base = root / scan_root
        if not base.exists() or not base.is_dir():
            continue
        for path in sorted(base.rglob("*"), key=lambda p: p.as_posix().lower()):
            if not path.is_file():
                continue
            if path.suffix.lower() not in TEXT_EXTENSIONS:
                continue
            rel = path.relative_to(root).as_posix()
            candidates.setdefault(rel, (manifest_map.get(rel, "important_untracked_source"), "source_scan"))
    return candidates


def _matches_any(path: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


def _exclude_reason(rel_path: str, include_generated: bool) -> str | None:
    lower = rel_path.lower()
    if any(rel_path.startswith(prefix) for prefix in EXCLUDE_PREFIXES):
        return "excluded_private_or_runtime_prefix"
    if _matches_any(rel_path, EXCLUDE_GLOBS):
        return "excluded_generated_or_archive_pattern"
    if not include_generated and any(rel_path.startswith(prefix) for prefix in GENERATED_PREFIXES):
        return "excluded_generated_report"
    if lower.endswith((".json", ".jsonl")) and any(rel_path.startswith(prefix) for prefix in RUNTIME_JSON_PREFIXES):
        return "excluded_projects_runtime_json"
    return None


def _scan_secrets(path: Path) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    data = path.read_bytes()
    text = data.decode("utf-8", errors="ignore")
    for line_no, line in enumerate(text.splitlines(), start=1):
        for category, pattern in SECRET_PATTERNS:
            if pattern.search(line):
                findings.append({"line": line_no, "category": category})
    return findings


def scan_text_for_secret_markers(text: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for line_no, line in enumerate(str(text).splitlines(), start=1):
        for category, pattern in SECRET_PATTERNS:
            if pattern.search(line):
                findings.append({"line": line_no, "category": category})
    return findings


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _collect_files(
    root: Path,
    include_generated: bool,
    max_file_size_mb: float,
    blocked_output_paths: set[str] | None = None,
) -> tuple[list[IncludedFile], dict[str, str], list[dict[str, Any]], list[dict[str, Any]], list[str], dict[str, int]]:
    manifest = _load_runtime_manifest(root)
    manifest_map = _manifest_category_map(manifest)
    tracked = {_safe_rel_path(path) for path in _git_lines(root, ["ls-files"])}
    cached = sorted(_git_lines(root, ["diff", "--cached", "--name-only"]))
    candidates = _discover_source_files(root, tracked, manifest_map)
    included: list[IncludedFile] = []
    hashes: dict[str, str] = {}
    excluded: list[dict[str, Any]] = []
    secret_findings: list[dict[str, Any]] = []
    categories: dict[str, int] = {}
    seen: set[str] = set()
    max_bytes = int(max_file_size_mb * 1024 * 1024)
    blocked_output_paths = blocked_output_paths or set()

    for rel_path in sorted(candidates, key=str.lower):
        try:
            safe_rel = _safe_rel_path(rel_path)
            if safe_rel in blocked_output_paths:
                excluded.append({"path": safe_rel, "reason": "output_archive_not_included"})
                continue
            if safe_rel in seen:
                excluded.append({"path": safe_rel, "reason": "duplicate_candidate"})
                continue
            seen.add(safe_rel)
            path = root / safe_rel
            if not path.exists():
                excluded.append({"path": safe_rel, "reason": "missing"})
                continue
            if not path.is_file():
                excluded.append({"path": safe_rel, "reason": "not_a_file"})
                continue
            if _has_external_link(root, path):
                excluded.append({"path": safe_rel, "reason": "external_symlink_or_junction"})
                continue
            path = _resolve_under_root(root, safe_rel)
            reason = _exclude_reason(safe_rel, include_generated)
            if reason:
                excluded.append({"path": safe_rel, "reason": reason})
                continue
            size = path.stat().st_size
            if size > max_bytes:
                excluded.append({"path": safe_rel, "reason": "over_size_limit", "size": size})
                continue
            findings = _scan_secrets(path)
            if findings:
                for finding in findings:
                    secret_findings.append(
                        {"file": safe_rel, "line": finding["line"], "category": finding["category"]}
                    )
                excluded.append({"path": safe_rel, "reason": "secret_marker_detected"})
                continue
            digest = _sha256(path)
            category, origin = candidates[rel_path]
            included.append(IncludedFile(safe_rel, category, origin, size, digest))
            hashes[safe_rel] = digest
            categories[category] = categories.get(category, 0) + 1
        except AuditBundleError as exc:
            excluded.append({"path": str(rel_path), "reason": "path_security_rejected", "detail": str(exc)})
    if cached:
        excluded.append({"path": "<git-index>", "reason": "staged_files_present", "count": len(cached)})
    return included, hashes, excluded, secret_findings, sorted(tracked, key=str.lower), categories


def _module_name_for_path(path: str) -> str | None:
    if not path.endswith(".py"):
        return None
    parts = path[:-3].split("/")
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _build_import_graph(root: Path, included: list[IncludedFile], category_map: dict[str, str]) -> dict[str, Any]:
    module_to_path = {
        module: item.rel_path
        for item in included
        for module in [_module_name_for_path(item.rel_path)]
        if module
    }
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, str]] = []
    unresolved: list[dict[str, str]] = []
    for item in sorted(included, key=lambda f: f.rel_path.lower()):
        if not item.rel_path.endswith(".py"):
            continue
        node_module = _module_name_for_path(item.rel_path) or item.rel_path
        nodes.append(
            {
                "path": item.rel_path,
                "module": node_module,
                "category": category_map.get(item.rel_path, item.category),
                "entrypoint": category_map.get(item.rel_path) == "entrypoints",
            }
        )
        try:
            tree = ast.parse((root / item.rel_path).read_text(encoding="utf-8", errors="ignore"))
        except Exception as exc:
            unresolved.append({"from": item.rel_path, "import": "<parse_error>", "reason": type(exc).__name__})
            continue
        imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    imports.add("." * node.level + (node.module or ""))
                elif node.module:
                    imports.add(node.module)
        for imported in sorted(imports):
            target = None
            if imported.startswith("."):
                unresolved.append({"from": item.rel_path, "import": imported, "reason": "relative_import"})
                continue
            parts = imported.split(".")
            for index in range(len(parts), 0, -1):
                candidate = ".".join(parts[:index])
                if candidate in module_to_path:
                    target = module_to_path[candidate]
                    break
            if target:
                edges.append({"from": item.rel_path, "to": target, "import": imported})
            elif parts[0] in {"agents", "core", "modules", "next", "tools"}:
                unresolved.append({"from": item.rel_path, "import": imported, "reason": "local_module_not_included"})
    return {
        "nodes": sorted(nodes, key=lambda n: n["path"].lower()),
        "edges": sorted(edges, key=lambda e: (e["from"].lower(), e["to"].lower(), e["import"].lower())),
        "unresolved_local_imports": sorted(
            unresolved, key=lambda e: (e["from"].lower(), e["import"].lower(), e["reason"].lower())
        ),
    }


def _collect_versions(root: Path, included_paths: set[str]) -> dict[str, Any]:
    targets = [
        "LocalComet_Control_Panel.py",
        "modules/development_safety_orchestrator_ru.py",
        "modules/reviewer_bridge_ru.py",
        "modules/screenshot_retention_dry_run_ru.py",
        "modules/screenshot_retention_policy_config_ru.py",
        "modules/storage_cleanup_plan_ru.py",
        MANIFEST_NAME,
    ]
    versions: dict[str, Any] = {"release": RELEASE, "markers": {}}
    version_re = re.compile(r"(?m)^([A-Z0-9_]*VERSION[A-Z0-9_]*)\s*=\s*['\"]([^'\"]+)['\"]")
    bridge_re = re.compile(r"(v\d+\.\d+(?:\.\d+)?[a-z]?)")
    for rel in targets:
        if rel not in included_paths and rel != MANIFEST_NAME:
            continue
        path = root / rel
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        markers: dict[str, str] = {match.group(1): match.group(2) for match in version_re.finditer(text)}
        found = sorted(set(bridge_re.findall(text)))
        versions["markers"][rel] = {"assignments": markers, "version_mentions": found[:40]}
    return versions


def _run_tests(root: Path, skip_tests: bool) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    if skip_tests:
        return {"skipped": True, "results": results, "summary": {"pass": 0, "fail": 0, "skipped": len(TEST_COMMANDS)}}
    for rel in TEST_COMMANDS:
        path = root / rel
        if rel in RECURSIVE_TEST_COMMANDS or os.environ.get(AUDIT_BUNDLE_TEST_ENV):
            results.append(
                {
                    "command": f"{sys.executable} {rel}",
                    "exit_code": None,
                    "duration_seconds": 0,
                    "status": "SKIP",
                    "reason": "recursive_bundle_test_skipped",
                }
            )
            continue
        if not path.exists():
            results.append({"command": f"{sys.executable} {rel}", "exit_code": None, "duration_seconds": 0, "status": "SKIP"})
            continue
        start = time.perf_counter()
        env = dict(os.environ)
        env[AUDIT_BUNDLE_TEST_ENV] = "1"
        completed = subprocess.run(
            [sys.executable, rel],
            cwd=str(root),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
            check=False,
        )
        elapsed = time.perf_counter() - start
        results.append(
            {
                "command": f"{sys.executable} {rel}",
                "exit_code": completed.returncode,
                "duration_seconds": round(elapsed, 3),
                "status": "PASS" if completed.returncode == 0 else "FAIL",
                "stdout": redact_text(completed.stdout, 12000),
                "stderr": redact_text(completed.stderr, 12000),
            }
        )
    passed = sum(1 for item in results if item["status"] == "PASS")
    failed = sum(1 for item in results if item["status"] == "FAIL")
    skipped = sum(1 for item in results if item["status"] == "SKIP")
    return {"skipped": False, "results": results, "summary": {"pass": passed, "fail": failed, "skipped": skipped}}


def _health(test_results: dict[str, Any], excluded: list[dict[str, Any]], secret_findings: list[dict[str, Any]]) -> str:
    if test_results["summary"]["fail"]:
        return "FAIL"
    if secret_findings or any(item["reason"] == "staged_files_present" for item in excluded):
        return "PASS_WITH_WARNINGS"
    return "PASS"


def _load_previous_hashes(path: Path) -> dict[str, str]:
    if not path.exists():
        raise AuditBundleError(f"compare path does not exist: {path}")
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path, "r") as zipf:
            names = zipf.namelist()
            manifest_names = [name for name in names if name.endswith("/metadata/bundle_manifest.json")]
            if len(manifest_names) != 1:
                raise AuditBundleError("compare zip must contain exactly one metadata/bundle_manifest.json")
            for name in names:
                pure = PurePosixPath(name)
                if name.startswith("/") or any(part in {"", ".", ".."} for part in pure.parts):
                    raise AuditBundleError("compare zip contains malformed path")
            data = json.loads(zipf.read(manifest_names[0]).decode("utf-8"))
    else:
        data = _read_json(path)
    files = data.get("files")
    if not isinstance(files, list):
        raise AuditBundleError("previous manifest missing files list")
    hashes: dict[str, str] = {}
    for item in files:
        rel = _safe_rel_path(str(item.get("path", "")))
        digest = str(item.get("sha256", ""))
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise AuditBundleError("previous manifest contains malformed sha256")
        hashes[rel] = digest
    return hashes


def _compare_hashes(previous: dict[str, str], current: dict[str, str]) -> dict[str, list[str]]:
    prev_keys = set(previous)
    current_keys = set(current)
    return {
        "added": sorted(current_keys - prev_keys, key=str.lower),
        "removed": sorted(prev_keys - current_keys, key=str.lower),
        "modified": sorted(
            (path for path in (prev_keys & current_keys) if previous[path] != current[path]),
            key=str.lower,
        ),
        "unchanged": sorted(
            (path for path in (prev_keys & current_keys) if previous[path] == current[path]),
            key=str.lower,
        ),
    }


def _bundle_manifest(
    root: Path,
    included: list[IncludedFile],
    hashes: dict[str, str],
    categories: dict[str, int],
    excluded: list[dict[str, Any]],
    health: str,
    deterministic: bool,
) -> dict[str, Any]:
    return {
        "release": RELEASE,
        "schema_version": VERIFIER_SCHEMA_VERSION,
        "bundle_id_scope": "source_manifest_excludes_test_timing",
        "project": "LocalComet / LocalAgent",
        "root": "<PROJECT_ROOT>",
        "deterministic": deterministic,
        "bundle_health": health,
        "source_file_count": len(included),
        "categories": dict(sorted(categories.items())),
        "excluded_count": len(excluded),
        "files": [
            {
                "path": item.rel_path,
                "category": item.category,
                "origin": item.origin,
                "size": item.size,
                "sha256": item.sha256,
            }
            for item in sorted(included, key=lambda f: f.rel_path.lower())
        ],
        "hash_algorithm": "sha256",
        "file_hashes_sha256": hashes,
    }


def _build_integrity_record(
    bundle_id: str,
    entries: dict[str, bytes],
    manifest_out: dict[str, Any],
) -> dict[str, Any]:
    return {
        "mode": "audit_bundle_integrity",
        "version": VERIFIER_SCHEMA_VERSION,
        "bundle_id": bundle_id,
        "entry_count": len(entries) + 1,
        "uncompressed_size": sum(len(payload) for payload in entries.values()),
        "hash_algorithm": "sha256",
        "manifest_sha256": hashlib.sha256(_json_bytes(manifest_out)).hexdigest(),
        "entry_sha256": {
            path: hashlib.sha256(payload).hexdigest()
            for path, payload in sorted(entries.items(), key=lambda item: item[0].lower())
        },
    }


def _metadata_secret_findings(entries: dict[str, bytes]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for path, payload in sorted(entries.items(), key=lambda item: item[0].lower()):
        if not path.startswith("metadata/") and path != "README_AUDIT.md":
            continue
        text = payload.decode("utf-8", errors="ignore")
        for finding in scan_text_for_secret_markers(text):
            findings.append({"file": path, "line": finding["line"], "category": finding["category"]})
    return findings


def _readme(bundle_id: str, health: str, categories: dict[str, int], excluded: list[dict[str, Any]], tests: dict[str, Any]) -> str:
    excluded_reasons: dict[str, int] = {}
    for item in excluded:
        excluded_reasons[item["reason"]] = excluded_reasons.get(item["reason"], 0) + 1
    return "\n".join(
        [
            f"# LocalComet Audit Bundle {RELEASE}",
            "",
            f"- Bundle ID: {bundle_id}",
            f"- Bundle health: {health}",
            "- Source bytes: `source/` contains exact working-tree bytes for included files.",
            "- Local paths: user profile paths are redacted in metadata where practical.",
            "",
            "## Included Categories",
            json.dumps(categories, ensure_ascii=False, sort_keys=True),
            "",
            "## Excluded Categories",
            json.dumps(excluded_reasons, ensure_ascii=False, sort_keys=True),
            "",
            "## Git State",
            "See `metadata/git_status.txt`, `metadata/git_diff.patch`, and related files.",
            "",
            "## Test Summary",
            json.dumps(tests.get("summary", {}), ensure_ascii=False, sort_keys=True),
            "",
            "## Reviewer Notes",
            "Start with `metadata/bundle_manifest.json`, verify `metadata/file_hashes_sha256.json`, then inspect `source/`.",
            "Secret-like files are excluded by default and only marker categories are recorded.",
            "",
        ]
    )


def _default_output_path(bundle_id: str) -> Path:
    return Path(tempfile.gettempdir()) / f"LocalComet_Audit_Bundle_{bundle_id}.zip"


def _resolve_output(output: Path | None, bundle_id: str) -> Path:
    if output is None:
        return _default_output_path(bundle_id)
    output = output.expanduser()
    if output.suffix.lower() == ".zip":
        return output
    return output / f"LocalComet_Audit_Bundle_{bundle_id}.zip"


def _blocked_output_paths(root: Path, output: Path | None) -> set[str]:
    if output is None:
        return set()
    candidate = output.expanduser()
    paths = [candidate]
    if candidate.suffix.lower() != ".zip":
        paths.append(candidate / "placeholder.zip")
    blocked: set[str] = set()
    for path in paths:
        try:
            resolved = path.resolve()
            rel = resolved.relative_to(root)
        except ValueError:
            continue
        blocked.add(rel.as_posix())
    return blocked


def _ensure_output_not_scanned(root: Path, output: Path | None) -> None:
    if output is None:
        return
    candidate = output.expanduser().resolve()
    try:
        rel = candidate.relative_to(root)
    except ValueError:
        return
    if candidate.suffix.lower() != ".zip":
        raise AuditBundleError(f"output directory must be outside project root: {rel.as_posix()}")


def _write_zip(zip_path: Path, bundle_root: str, entries: dict[str, bytes], deterministic: bool) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    compression = zipfile.ZIP_DEFLATED
    with zipfile.ZipFile(zip_path, "w", compression=compression) as zipf:
        for name in sorted(entries, key=str.lower):
            info = zipfile.ZipInfo(f"{bundle_root}/{name}")
            if deterministic:
                info.date_time = FIXED_ZIP_DT
            info.compress_type = compression
            zipf.writestr(info, entries[name])


def create_audit_bundle(
    root: Path,
    output: Path | None = None,
    skip_tests: bool = False,
    max_file_size_mb: float = 5.0,
    include_generated: bool = False,
    deterministic: bool = False,
    compare: Path | None = None,
) -> dict[str, Any]:
    root = root.expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise AuditBundleError(f"root is not a directory: {root}")
    _ensure_output_not_scanned(root, output)
    manifest = _load_runtime_manifest(root)
    category_map = _manifest_category_map(manifest)
    blocked_outputs = _blocked_output_paths(root, output)
    included, hashes, excluded, secrets, tracked, categories = _collect_files(
        root,
        include_generated,
        max_file_size_mb,
        blocked_outputs,
    )
    import_graph = _build_import_graph(root, included, category_map)
    versions = _collect_versions(root, {item.rel_path for item in included})
    tests = _run_tests(root, skip_tests)
    health = _health(tests, excluded, secrets)
    git_metadata = _collect_git_metadata(root)
    included_untracked = [
        item.rel_path
        for item in included
        if item.origin in {"runtime_manifest", "source_scan"} and item.rel_path not in set(tracked)
    ]
    comparison = None
    if compare is not None:
        comparison = _compare_hashes(_load_previous_hashes(compare.expanduser()), hashes)

    base_manifest = _bundle_manifest(root, included, hashes, categories, excluded, health, deterministic)
    base_manifest["bundle_id"] = None
    bundle_id = hashlib.sha256(_json_bytes(base_manifest)).hexdigest()[:16]
    manifest_out = dict(base_manifest)
    manifest_out["bundle_id"] = bundle_id
    manifest_out["bundle_name"] = f"LocalComet_Audit_Bundle_{bundle_id}"
    if not deterministic:
        manifest_out["created_at_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    zip_path = _resolve_output(output, bundle_id).resolve()
    if zip_path.exists() and zip_path.is_dir():
        raise AuditBundleError(f"output zip path is a directory: {zip_path}")

    entries: dict[str, bytes] = {}
    for item in included:
        entries[f"source/{item.rel_path}"] = (root / item.rel_path).read_bytes()
    metadata = {
        "metadata/localcomet_runtime_manifest.json": _json_bytes(manifest),
        "metadata/bundle_manifest.json": _json_bytes(manifest_out),
        "metadata/file_hashes_sha256.json": _json_bytes(hashes),
        "metadata/tracked_files.txt": ("\n".join(tracked) + "\n").encode("utf-8"),
        "metadata/included_untracked_sources.txt": ("\n".join(sorted(included_untracked, key=str.lower)) + "\n").encode("utf-8"),
        "metadata/excluded_paths.json": _json_bytes(excluded),
        "metadata/import_graph.json": _json_bytes(import_graph),
        "metadata/versions.json": _json_bytes(versions),
        "metadata/test_results.json": _json_bytes(tests),
        "metadata/secret_findings.json": _json_bytes(secrets),
    }
    for name, text in git_metadata.items():
        metadata[f"metadata/{name}"] = text.encode("utf-8")
    if comparison is not None:
        metadata["metadata/bundle_comparison.json"] = _json_bytes(comparison)
    entries.update(metadata)
    entries["README_AUDIT.md"] = _readme(bundle_id, health, categories, excluded, tests).encode("utf-8")
    metadata_findings = _metadata_secret_findings(entries)
    if metadata_findings:
        safe_findings = [
            {"file": item["file"], "line": item["line"], "category": item["category"]}
            for item in metadata_findings
        ]
        entries["metadata/metadata_secret_findings.json"] = _json_bytes(safe_findings)
        manifest_out["metadata_secret_findings_count"] = len(safe_findings)
        entries["metadata/bundle_manifest.json"] = _json_bytes(manifest_out)
    integrity = _build_integrity_record(bundle_id, entries, manifest_out)
    entries["metadata/bundle_integrity.json"] = _json_bytes(integrity)

    bundle_root = f"LocalComet_Audit_Bundle_{bundle_id}"
    _write_zip(zip_path, bundle_root, entries, deterministic)
    with zipfile.ZipFile(zip_path, "r") as zipf:
        zipf.testzip()
    return {
        "zip_path": zip_path,
        "bundle_id": bundle_id,
        "bundle_health": health,
        "bundle_manifest": manifest_out,
        "included_counts": categories,
        "excluded": excluded,
        "secret_findings": secrets,
        "test_results": tests,
        "comparison": comparison,
        "zip_size": zip_path.stat().st_size,
    }
