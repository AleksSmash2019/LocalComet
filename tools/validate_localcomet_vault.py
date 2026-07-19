"""Deterministic, dependency-free, read-only validator for LocalComet Vault v2."""

from __future__ import annotations

import argparse
import datetime as _datetime
import hashlib
import json
import math
import os
from pathlib import Path, PureWindowsPath
import re
import stat
import sys
import unicodedata
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable


sys.dont_write_bytecode = True

MAX_NOTES = 2000
MAX_NOTE_BYTES = 1_048_576
MAX_TOTAL_SCAN_BYTES = 67_108_864
MAX_AUXILIARY_BYTES = 1_048_576
MAX_CANVAS_NODES = 512
MAX_CANVAS_EDGES = 1024
MAX_CANVAS_TEXT_CHARS = 65_536

DECLARED_CANVAS_ASSETS = frozenset(
    {"00 Канон/LocalComet — Архитектурная карта.canvas"}
)
HUB_PATH_PREFIXES = ("00 Канон/", "01 Архитектура/", "03 Решения/")
COMPONENT_PATH_PREFIXES = ("01 Архитектура/",)
DRAFT_PATH_PREFIXES = ("01 Архитектура/",)

REQUIRED_FIELDS = (
    "id",
    "type",
    "status",
    "knowledge_layer",
    "evidence_class",
    "authority",
    "updated",
    "last_reviewed",
)
LIST_FIELDS = {
    "releases",
    "source_paths",
    "evidence_refs",
    "supersedes",
    "superseded_by",
    "aliases",
    "tags",
}
ENUMS = {
    "type": {
        "canonical", "architecture", "release", "adr", "runbook", "incident",
        "roadmap", "security", "research", "prompt", "session", "evidence", "meta",
        "hub", "component",
    },
    "status": {
        "current", "active", "accepted", "planned", "research", "resolved",
        "historical", "superseded", "evidence-limited", "draft",
    },
    "knowledge_layer": {
        "current_source_truth", "verified_history", "founder_intent", "operational",
        "research", "roadmap", "forensic_evidence", "session_snapshot",
    },
    "evidence_class": {"A", "B", "C", "D", "E", "G"},
    "authority": {
        "source", "runtime", "test", "forensic_evidence", "founder",
        "architecture_decision", "research", "roadmap", "session",
    },
}
REQUIRED_CANONICAL_SCOPES = {
    "current-state",
    "version-matrix",
    "product-vision",
    "system-architecture",
    "source-map",
    "knowledge-schema",
    "security",
    "roadmap",
    "evidence",
    "incidents",
}
FORBIDDEN_EXTENSIONS = {
    ".exe", ".dll", ".bat", ".cmd", ".ps1", ".com", ".scr", ".msi",
    ".zip", ".7z", ".rar", ".tar", ".gz", ".db", ".sqlite", ".sqlite3",
    ".py", ".pyw", ".js", ".mjs", ".cjs", ".ts", ".sh", ".bash", ".zsh",
    ".vbs", ".jar",
}
FORBIDDEN_AUXILIARY_PREFIXES = (
    b"MZ",
    b"\x7fELF",
    b"PK\x03\x04",
    b"7z\xbc\xaf\x27\x1c",
    b"Rar!\x1a\x07",
    b"\x1f\x8b",
    b"SQLite format 3\x00",
    b"#!",
)
LINK_BENEFIT_TYPES = {
    "canonical", "architecture", "adr", "runbook", "incident", "roadmap",
    "security", "research", "evidence", "hub",
}

ID_RE = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")
EVIDENCE_ID_RE = re.compile(r"^EV-[0-9]{3,}$")
ISO_DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):(?:[ ](.*))?$")
LIST_ITEM_RE = re.compile(r"^  -[ ](.+)$")
HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.+?)\s*$")
WIKI_LINK_RE = re.compile(r"!?\[\[([^\[\]\r\n]+)\]\]")
URL_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")


class ValidatorRuntimeError(RuntimeError):
    """The validator could not safely establish or read its configured roots."""


class FrontmatterError(ValueError):
    def __init__(self, message: str, line: int) -> None:
        super().__init__(message)
        self.line = line


@dataclass(frozen=True)
class Issue:
    severity: str
    code: str
    message: str
    file: str = ""
    line: int = 0
    finding_type: str = ""
    redacted: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {key: value for key, value in asdict(self).items() if value not in ("", 0)}


@dataclass
class Note:
    path: Path
    relative_path: str
    raw_bytes: bytes
    text: str
    metadata: dict[str, Any]
    body_lines: list[tuple[int, str]]
    headings: set[str] = field(default_factory=set)
    title: str = ""
    note_id: str = ""
    aliases: list[str] = field(default_factory=list)


@dataclass
class ValidationResult:
    status: str
    vault_root: str
    project_root: str
    vault_revision: str
    markdown_note_count: int
    markdown_total_bytes: int
    obsidian_json_count: int
    obsidian_auxiliary_count: int
    obsidian_auxiliary_total_bytes: int
    obsidian_auxiliary_files: list[dict[str, Any]]
    stable_id_count: int
    canonical_scope_count: int
    wiki_link_count: int
    resolved_wiki_link_count: int
    broken_link_count: int
    ambiguous_link_count: int
    alias_collision_count: int
    evidence_record_count: int
    unresolved_evidence_ref_count: int
    canonical_ownership_conflict_count: int
    supersession_cycle_count: int
    missing_source_path_count: int
    unexpected_file_count: int
    binary_or_forbidden_file_count: int
    secret_finding_count: int
    error_count: int
    warning_count: int
    errors: list[dict[str, Any]]
    warnings: list[dict[str, Any]]
    read_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _normal(value: str) -> str:
    return unicodedata.normalize("NFC", value)


def _lookup_key(value: str) -> str:
    return _normal(value).casefold()


def _relative_posix(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _is_path_within(path: Path, root: Path) -> bool:
    try:
        return os.path.commonpath((os.fspath(path), os.fspath(root))) == os.fspath(root)
    except (ValueError, OSError):
        return False


def _stat_is_reparse(info: os.stat_result) -> bool:
    marker = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(getattr(info, "st_file_attributes", 0) & marker)


def is_reparse_point(path: os.PathLike[str] | str) -> bool:
    """Return True for a symlink or Windows reparse point without following it."""
    info = os.lstat(path)
    return stat.S_ISLNK(info.st_mode) or _stat_is_reparse(info)


def _path_components(path: Path) -> Iterable[Path]:
    absolute = Path(os.path.abspath(os.fspath(path)))
    anchor = Path(absolute.anchor)
    current = anchor
    if absolute == anchor:
        yield anchor
        return
    for part in absolute.parts[1:]:
        current = current / part
        yield current


def _safe_root(configured: os.PathLike[str] | str, label: str) -> Path:
    path = Path(os.path.abspath(os.fspath(configured)))
    try:
        for component in _path_components(path):
            if is_reparse_point(component):
                raise ValidatorRuntimeError(f"{label} contains a symlink or reparse point: {component}")
        if not path.exists() or not path.is_dir():
            raise ValidatorRuntimeError(f"{label} does not exist or is not a directory: {path}")
        resolved = path.resolve(strict=True)
    except ValidatorRuntimeError:
        raise
    except OSError as exc:
        raise ValidatorRuntimeError(f"cannot inspect {label}: {path}: {exc}") from exc
    return resolved


def _entry_is_link_or_reparse(entry: os.DirEntry[str], info: os.stat_result) -> bool:
    return entry.is_symlink() or stat.S_ISLNK(info.st_mode) or _stat_is_reparse(info)


def _inspect_auxiliary_file(
    candidate: Path,
    info: os.stat_result,
    relative: str,
) -> tuple[dict[str, Any], list[Issue], bool]:
    record: dict[str, Any] = {
        "relative_path": _normal(relative),
        "size": info.st_size,
        "sha256": None,
        "category": "obsidian_auxiliary",
    }
    issues: list[Issue] = []
    if info.st_size > MAX_AUXILIARY_BYTES:
        issues.append(
            Issue(
                "error",
                "AUXILIARY_SIZE_LIMIT",
                f"Obsidian auxiliary file size {info.st_size} exceeds limit {MAX_AUXILIARY_BYTES}",
                relative,
            )
        )
        return record, issues, False
    try:
        raw = candidate.read_bytes()
    except OSError as exc:
        raise ValidatorRuntimeError(f"cannot read Obsidian auxiliary file {relative}: {exc}") from exc
    if len(raw) != info.st_size:
        raise ValidatorRuntimeError(f"Obsidian auxiliary file changed during validation: {relative}")
    record["sha256"] = hashlib.sha256(raw).hexdigest()
    if any(raw.startswith(prefix) for prefix in FORBIDDEN_AUXILIARY_PREFIXES):
        issues.append(
            Issue(
                "error",
                "AUXILIARY_FORBIDDEN_CONTENT",
                "Obsidian auxiliary file contains executable, archive, or database content",
                relative,
            )
        )
        return record, issues, True
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        issues.append(
            Issue(
                "error",
                "AUXILIARY_BINARY_CONTENT",
                "Obsidian auxiliary file must be bounded UTF-8 text",
                relative,
            )
        )
        return record, issues, True
    issues.extend(_scan_secret_text(text, relative))
    return record, issues, False


def _json_object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _bounded_canvas_number(value: Any, *, positive: bool = False) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    if not math.isfinite(value) or abs(value) > 10_000_000:
        return False
    return not positive or value > 0


def _canvas_file_reference_problem(path_value: Any, vault_root: Path) -> str | None:
    if not isinstance(path_value, str) or not 1 <= len(path_value) <= 512:
        return "file node reference must be a bounded string"
    if URL_RE.match(path_value):
        return "URL file references are forbidden"
    windows = PureWindowsPath(path_value)
    if windows.is_absolute() or windows.drive or path_value.startswith(("/", "\\")):
        return "absolute, drive-qualified, or UNC file references are forbidden"
    if "\\" in path_value:
        return "Canvas file references must use forward slashes"
    parts = path_value.split("/")
    if any(part in ("", ".", "..") for part in parts):
        return "Canvas file reference traversal is forbidden"
    if Path(path_value).suffix.casefold() != ".md":
        return "Canvas file nodes may reference Markdown notes only"
    candidate = vault_root.joinpath(*parts)
    current = vault_root
    try:
        for part in parts:
            current = current / part
            if current.exists() and is_reparse_point(current):
                return "Canvas file reference crosses a symlink or reparse point"
        if not candidate.exists() or not candidate.is_file():
            return "Canvas file reference does not resolve to a Vault note"
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        return f"Canvas file reference inspection failed: {exc}"
    if not _is_path_within(resolved, vault_root):
        return "Canvas file reference resolves outside the Vault"
    return None


def _canvas_node_problem(node: Any, vault_root: Path) -> str | None:
    if not isinstance(node, dict):
        return "Canvas node must be an object"
    node_type = node.get("type")
    common = {"id", "type", "x", "y", "width", "height", "color"}
    allowed_by_type = {
        "group": common | {"label"},
        "file": common | {"file"},
        "text": common | {"text"},
    }
    required_by_type = {
        "group": {"id", "type", "x", "y", "width", "height", "label"},
        "file": {"id", "type", "x", "y", "width", "height", "file"},
        "text": {"id", "type", "x", "y", "width", "height", "text"},
    }
    if node_type not in allowed_by_type:
        return "Canvas node type must be group, file, or text"
    if not required_by_type[node_type].issubset(node) or not set(node).issubset(allowed_by_type[node_type]):
        return f"Canvas {node_type} node has missing or unknown fields"
    node_id = node.get("id")
    if not isinstance(node_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", node_id):
        return "Canvas node id is invalid"
    if not _bounded_canvas_number(node.get("x")) or not _bounded_canvas_number(node.get("y")):
        return "Canvas node coordinates are invalid"
    if not _bounded_canvas_number(node.get("width"), positive=True) or not _bounded_canvas_number(node.get("height"), positive=True):
        return "Canvas node dimensions are invalid"
    color = node.get("color")
    if color is not None and (not isinstance(color, str) or not 1 <= len(color) <= 64):
        return "Canvas node color is invalid"
    if node_type == "group":
        label = node.get("label")
        if not isinstance(label, str) or not 1 <= len(label) <= 512:
            return "Canvas group label is invalid"
    elif node_type == "file":
        return _canvas_file_reference_problem(node.get("file"), vault_root)
    else:
        text = node.get("text")
        if not isinstance(text, str) or not 1 <= len(text) <= MAX_CANVAS_TEXT_CHARS:
            return "Canvas text node content is invalid"
        if re.search(r"(?i)\b(?:https?|file)://", text):
            return "Canvas text nodes may not declare external URL references"
    return None


def _canvas_edge_problem(edge: Any, node_ids: set[str]) -> str | None:
    if not isinstance(edge, dict):
        return "Canvas edge must be an object"
    allowed = {
        "id", "fromNode", "fromSide", "fromEnd", "toNode", "toSide",
        "toEnd", "color", "label",
    }
    if not {"id", "fromNode", "toNode"}.issubset(edge) or not set(edge).issubset(allowed):
        return "Canvas edge has missing or unknown fields"
    for field_name in ("id", "fromNode", "toNode"):
        value = edge.get(field_name)
        if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value):
            return f"Canvas edge {field_name} is invalid"
    if edge["fromNode"] not in node_ids or edge["toNode"] not in node_ids:
        return "Canvas edge references an unknown node"
    if edge["fromNode"] == edge["toNode"]:
        return "Canvas self-edges are forbidden"
    for field_name in ("fromSide", "toSide"):
        if field_name in edge and edge[field_name] not in {"top", "right", "bottom", "left"}:
            return f"Canvas edge {field_name} is invalid"
    for field_name in ("fromEnd", "toEnd"):
        if field_name in edge and edge[field_name] not in {"none", "arrow"}:
            return f"Canvas edge {field_name} is invalid"
    for field_name, limit in (("color", 64), ("label", 512)):
        if field_name in edge and (
            not isinstance(edge[field_name], str) or not 1 <= len(edge[field_name]) <= limit
        ):
            return f"Canvas edge {field_name} is invalid"
    return None


def _inspect_canvas_file(
    candidate: Path,
    info: os.stat_result,
    relative: str,
    vault_root: Path,
) -> tuple[dict[str, Any], list[Issue], bool]:
    record: dict[str, Any] = {
        "relative_path": _normal(relative),
        "size": info.st_size,
        "sha256": None,
        "category": "obsidian_canvas",
    }
    issues: list[Issue] = []
    if info.st_size > MAX_AUXILIARY_BYTES:
        issues.append(Issue("error", "AUXILIARY_SIZE_LIMIT", f"Canvas size {info.st_size} exceeds limit {MAX_AUXILIARY_BYTES}", relative))
        return record, issues, False
    try:
        raw = candidate.read_bytes()
    except OSError as exc:
        raise ValidatorRuntimeError(f"cannot read Canvas file {relative}: {exc}") from exc
    if len(raw) != info.st_size:
        raise ValidatorRuntimeError(f"Canvas file changed during validation: {relative}")
    record["sha256"] = hashlib.sha256(raw).hexdigest()
    if any(raw.startswith(prefix) for prefix in FORBIDDEN_AUXILIARY_PREFIXES):
        issues.append(Issue("error", "AUXILIARY_FORBIDDEN_CONTENT", "Canvas contains executable, archive, or database content", relative))
        return record, issues, True
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        issues.append(Issue("error", "AUXILIARY_BINARY_CONTENT", "Canvas must be bounded UTF-8 JSON", relative))
        return record, issues, True
    issues.extend(_scan_secret_text(text, relative))
    try:
        payload = json.loads(
            text,
            object_pairs_hook=_json_object_without_duplicates,
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f"invalid JSON number: {value}")),
        )
    except (json.JSONDecodeError, ValueError) as exc:
        issues.append(Issue("error", "CANVAS_JSON_INVALID", f"Canvas JSON is invalid: {exc}", relative))
        return record, issues, False
    if not isinstance(payload, dict) or set(payload) != {"nodes", "edges"}:
        issues.append(Issue("error", "CANVAS_STRUCTURE_INVALID", "Canvas root must contain exactly nodes and edges arrays", relative))
        return record, issues, False
    nodes = payload["nodes"]
    edges = payload["edges"]
    if not isinstance(nodes, list) or not isinstance(edges, list) or not nodes:
        issues.append(Issue("error", "CANVAS_STRUCTURE_INVALID", "Canvas nodes must be a non-empty array and edges must be an array", relative))
        return record, issues, False
    if len(nodes) > MAX_CANVAS_NODES or len(edges) > MAX_CANVAS_EDGES:
        issues.append(Issue("error", "CANVAS_STRUCTURE_INVALID", "Canvas node or edge count exceeds the bounded policy", relative))
        return record, issues, False
    node_ids: set[str] = set()
    hard_stop_present = False
    for index, node in enumerate(nodes):
        problem = _canvas_node_problem(node, vault_root)
        if problem:
            issues.append(Issue("error", "CANVAS_NODE_INVALID", f"Canvas node {index}: {problem}", relative))
            continue
        node_id = node["id"]
        if node_id in node_ids:
            issues.append(Issue("error", "CANVAS_NODE_INVALID", f"Canvas node {index}: duplicate node id", relative))
        node_ids.add(node_id)
        if node.get("type") == "text" and "HARD STOP" in node.get("text", "") and "NO AUTOMATIC VAULT WRITE" in node.get("text", ""):
            hard_stop_present = True
    edge_ids: set[str] = set()
    for index, edge in enumerate(edges):
        problem = _canvas_edge_problem(edge, node_ids)
        if problem:
            issues.append(Issue("error", "CANVAS_EDGE_INVALID", f"Canvas edge {index}: {problem}", relative))
            continue
        edge_id = edge["id"]
        if edge_id in edge_ids:
            issues.append(Issue("error", "CANVAS_EDGE_INVALID", f"Canvas edge {index}: duplicate edge id", relative))
        edge_ids.add(edge_id)
    if not hard_stop_present:
        issues.append(Issue("error", "CANVAS_BOUNDARY_MISSING", "Declared architecture Canvas must retain the no-write HARD STOP boundary", relative))
    return record, issues, False


def _discover_files_detailed(
    vault_root: Path,
) -> tuple[
    list[tuple[Path, os.stat_result]],
    int,
    list[dict[str, Any]],
    list[Issue],
    int,
    int,
]:
    notes: list[tuple[Path, os.stat_result]] = []
    obsidian_json_count = 0
    auxiliary_files: list[dict[str, Any]] = []
    issues: list[Issue] = []
    unexpected_count = 0
    forbidden_count = 0

    def walk(directory: Path) -> None:
        nonlocal obsidian_json_count, unexpected_count, forbidden_count
        try:
            entries = sorted(os.scandir(directory), key=lambda item: _lookup_key(item.name))
        except OSError as exc:
            raise ValidatorRuntimeError(f"cannot enumerate Vault directory {directory}: {exc}") from exc
        try:
            for entry in entries:
                candidate = Path(entry.path)
                try:
                    info = entry.stat(follow_symlinks=False)
                except OSError as exc:
                    raise ValidatorRuntimeError(f"cannot inspect Vault entry {candidate}: {exc}") from exc
                relative = _relative_posix(candidate, vault_root)
                if _entry_is_link_or_reparse(entry, info):
                    issues.append(Issue("error", "REPARSE_POINT", "symlink or reparse point is forbidden", relative))
                    continue
                if stat.S_ISDIR(info.st_mode):
                    walk(candidate)
                    continue
                if not stat.S_ISREG(info.st_mode):
                    issues.append(Issue("error", "NON_REGULAR_FILE", "non-regular Vault entry is forbidden", relative))
                    continue
                resolved = candidate.resolve(strict=True)
                if not _is_path_within(resolved, vault_root):
                    issues.append(Issue("error", "PATH_ESCAPE", "Vault file resolves outside the configured root", relative))
                    continue
                in_obsidian = bool(Path(relative).parts and Path(relative).parts[0] == ".obsidian")
                suffix = candidate.suffix.casefold()
                if in_obsidian and suffix == ".json":
                    obsidian_json_count += 1
                elif not in_obsidian and suffix == ".md":
                    notes.append((candidate, info))
                elif suffix == ".base":
                    record, auxiliary_issues, forbidden_content = _inspect_auxiliary_file(
                        candidate,
                        info,
                        relative,
                    )
                    auxiliary_files.append(record)
                    issues.extend(auxiliary_issues)
                    if forbidden_content:
                        forbidden_count += 1
                elif suffix == ".canvas" and _normal(relative) in DECLARED_CANVAS_ASSETS:
                    record, auxiliary_issues, forbidden_content = _inspect_canvas_file(
                        candidate,
                        info,
                        relative,
                        vault_root,
                    )
                    auxiliary_files.append(record)
                    issues.extend(auxiliary_issues)
                    if forbidden_content:
                        forbidden_count += 1
                else:
                    unexpected_count += 1
                    if suffix in FORBIDDEN_EXTENSIONS:
                        forbidden_count += 1
                        issues.append(Issue("error", "FORBIDDEN_FILE", f"forbidden Vault file extension: {suffix}", relative))
                    else:
                        issues.append(Issue("error", "UNEXPECTED_FILE", "unexpected regular file outside the Vault file policy", relative))
        finally:
            for entry in entries:
                del entry

    walk(vault_root)
    notes.sort(key=lambda item: _lookup_key(_relative_posix(item[0], vault_root)))
    auxiliary_files.sort(key=lambda item: _normal(item["relative_path"]))
    return (
        notes,
        obsidian_json_count,
        auxiliary_files,
        issues,
        unexpected_count,
        forbidden_count,
    )


def _discover_files(
    vault_root: Path,
) -> tuple[list[tuple[Path, os.stat_result]], int, list[Issue], int, int]:
    """Compatibility wrapper used by the read-only KnowledgeAdapter."""
    notes, json_count, _auxiliary, issues, unexpected, forbidden = (
        _discover_files_detailed(vault_root)
    )
    return notes, json_count, issues, unexpected, forbidden


def _parse_scalar(value: str, line_number: int) -> Any:
    if value == "[]":
        return []
    if value == "true":
        return True
    if value == "false":
        return False
    if value == "null":
        return None
    if not value:
        raise FrontmatterError("empty scalar is unsupported; use [] for an empty list", line_number)
    if value.startswith('"'):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise FrontmatterError(f"invalid quoted string: {exc.msg}", line_number) from exc
        if not isinstance(parsed, str):
            raise FrontmatterError("quoted frontmatter values must be strings", line_number)
        return parsed
    if value.startswith("'"):
        if len(value) < 2 or not value.endswith("'"):
            raise FrontmatterError("invalid single-quoted string", line_number)
        return value[1:-1].replace("''", "'")
    if value[0] in "[{&*!>|%@`" or value.endswith(":") or " #" in value or "\t" in value:
        raise FrontmatterError("unsupported YAML-like scalar syntax", line_number)
    return value


def parse_frontmatter(text: str) -> tuple[dict[str, Any], list[tuple[int, str]]]:
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise FrontmatterError("missing opening frontmatter delimiter", 1)
    closing = next((index for index in range(1, len(lines)) if lines[index] == "---"), None)
    if closing is None:
        raise FrontmatterError("missing closing frontmatter delimiter", 1)
    metadata: dict[str, Any] = {}
    index = 1
    while index < closing:
        line = lines[index]
        line_number = index + 1
        if not line.strip():
            index += 1
            continue
        if "\t" in line:
            raise FrontmatterError("tabs are unsupported in frontmatter", line_number)
        match = KEY_RE.fullmatch(line)
        if not match:
            raise FrontmatterError("unsupported frontmatter syntax", line_number)
        key, raw_value = match.group(1), match.group(2)
        if key in metadata:
            raise FrontmatterError(f"duplicate frontmatter key: {key}", line_number)
        if raw_value is None or raw_value == "":
            values: list[str] = []
            index += 1
            while index < closing:
                item_match = LIST_ITEM_RE.fullmatch(lines[index])
                if not item_match:
                    break
                item = _parse_scalar(item_match.group(1), index + 1)
                if not isinstance(item, str):
                    raise FrontmatterError("block list items must be scalar strings", index + 1)
                values.append(item)
                index += 1
            if not values:
                raise FrontmatterError(f"empty block list for {key}; use []", line_number)
            metadata[key] = values
            continue
        metadata[key] = _parse_scalar(raw_value, line_number)
        index += 1
    body = [(line_number + 1, line) for line_number, line in enumerate(lines[closing + 1 :], closing + 1)]
    return metadata, body


def _outside_fences(lines: list[tuple[int, str]]) -> Iterable[tuple[int, str]]:
    fence: str | None = None
    for line_number, line in lines:
        marker_match = re.match(r"^[ ]{0,3}(`{3,}|~{3,})", line)
        if marker_match:
            marker = marker_match.group(1)
            if fence is None:
                fence = marker[0]
            elif marker[0] == fence:
                fence = None
            continue
        if fence is None:
            yield line_number, line


def _extract_headings(note: Note) -> None:
    headings: set[str] = set()
    first_h1 = ""
    for _line_number, line in _outside_fences(note.body_lines):
        match = HEADING_RE.match(line)
        if not match:
            continue
        heading = re.sub(r"[ \t]+#+[ \t]*$", "", match.group(2)).strip()
        if heading:
            headings.add(_lookup_key(heading))
            if len(match.group(1)) == 1 and not first_h1:
                first_h1 = heading
    note.headings = headings
    configured_title = note.metadata.get("title")
    note.title = configured_title if isinstance(configured_title, str) else first_h1


def _issue(issues: list[Issue], severity: str, code: str, message: str, note: Note | None = None, line: int = 0) -> None:
    issues.append(Issue(severity, code, message, note.relative_path if note else "", line))


def _validate_date(value: Any) -> bool:
    if not isinstance(value, str) or not ISO_DATE_RE.fullmatch(value):
        return False
    try:
        _datetime.date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _validate_timestamp(value: Any) -> bool:
    if _validate_date(value):
        return True
    if not isinstance(value, str):
        return False
    try:
        _datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return "T" in value


def _validate_note_schema(note: Note, issues: list[Issue]) -> None:
    metadata = note.metadata
    for field_name in REQUIRED_FIELDS:
        if field_name not in metadata:
            _issue(issues, "error", "MISSING_REQUIRED_FIELD", f"missing required field: {field_name}", note)
    for field_name, allowed in ENUMS.items():
        value = metadata.get(field_name)
        if field_name in metadata and (not isinstance(value, str) or value not in allowed):
            _issue(issues, "error", "INVALID_ENUM", f"invalid {field_name}: {value!r}", note)
    for field_name in LIST_FIELDS:
        if field_name not in metadata:
            continue
        value = metadata[field_name]
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            _issue(issues, "error", "INVALID_FIELD_TYPE", f"{field_name} must be a list of strings", note)
    canonical = metadata.get("canonical", False)
    if not isinstance(canonical, bool):
        _issue(issues, "error", "INVALID_CANONICAL_TYPE", "canonical must be a boolean", note)
    for field_name in ("updated", "last_reviewed"):
        if field_name in metadata and not _validate_date(metadata[field_name]):
            _issue(issues, "error", "INVALID_DATE", f"{field_name} must be a valid YYYY-MM-DD date", note)
    if "verified_at" in metadata and not _validate_timestamp(metadata["verified_at"]):
        _issue(issues, "error", "INVALID_TIMESTAMP", "verified_at must be an ISO date or ISO-8601 timestamp", note)
    note_id = metadata.get("id")
    if isinstance(note_id, str):
        note.note_id = note_id
        if not ID_RE.fullmatch(note_id):
            _issue(issues, "error", "INVALID_STABLE_ID", f"invalid stable ID: {note_id!r}", note)
    elif "id" in metadata:
        _issue(issues, "error", "INVALID_STABLE_ID", "stable ID must be a string", note)
    aliases = metadata.get("aliases", [])
    if isinstance(aliases, list) and all(isinstance(value, str) for value in aliases):
        note.aliases = aliases

    status = metadata.get("status")
    layer = metadata.get("knowledge_layer")
    note_type = metadata.get("type")
    if layer == "current_source_truth" and status in {"planned", "superseded"}:
        _issue(issues, "error", "CURRENT_TRUTH_STATUS", f"current source truth cannot be {status}", note)
    if canonical is True and status == "superseded":
        _issue(issues, "error", "SUPERSEDED_CANONICAL", "canonical note cannot be superseded", note)
    if status == "superseded" and not metadata.get("superseded_by"):
        _issue(issues, "error", "SUPERSEDED_WITHOUT_SUCCESSOR", "superseded note requires superseded_by", note)
    if layer == "founder_intent" and metadata.get("authority") != "founder":
        _issue(issues, "warning", "FOUNDER_INTENT_AUTHORITY", "founder_intent normally uses authority: founder", note)
    if note_type == "release" and not metadata.get("releases"):
        if not (isinstance(note_id, str) and re.fullmatch(r"release[._-]v?[0-9]+(?:[._-][0-9]+)*(?:[a-z][0-9]*)?", note_id)):
            _issue(issues, "error", "RELEASE_IDENTIFIER_MISSING", "release note requires releases or a release-compatible stable ID", note)
    if note_type == "hub":
        tags = metadata.get("tags", [])
        if not note.relative_path.startswith(HUB_PATH_PREFIXES) or not isinstance(tags, list) or "hub" not in tags:
            _issue(
                issues,
                "error",
                "HUB_ROLE_BOUNDARY",
                "hub is reserved for tagged navigation entry points under Canon, Architecture, or Decisions",
                note,
            )
    if note_type == "component":
        component_contract = (
            note.relative_path.startswith(COMPONENT_PATH_PREFIXES)
            and canonical is False
            and layer == "current_source_truth"
            and metadata.get("evidence_class") == "A"
            and metadata.get("authority") == "source"
            and bool(metadata.get("source_paths"))
        )
        if not component_contract:
            _issue(
                issues,
                "error",
                "COMPONENT_ROLE_BOUNDARY",
                "component is reserved for source-grounded, non-canonical software component notes under Architecture",
                note,
            )
    if status == "draft":
        draft_contract = (
            note.relative_path.startswith(DRAFT_PATH_PREFIXES)
            and canonical is False
            and layer == "founder_intent"
            and metadata.get("evidence_class") == "C"
            and metadata.get("authority") in {"founder", "architecture_decision"}
        )
        if not draft_contract:
            _issue(
                issues,
                "error",
                "DRAFT_AUTHORITY_BOUNDARY",
                "draft is non-canonical founder intent under Architecture and grants no current-source authority",
                note,
            )


def _validate_source_path(path_value: str, project_root: Path) -> tuple[Path | None, str | None]:
    if URL_RE.match(path_value):
        return None, "URL source path is forbidden"
    windows = PureWindowsPath(path_value)
    if windows.is_absolute() or windows.drive or path_value.startswith(("/", "\\")):
        return None, "absolute, drive-qualified, or UNC source path is forbidden"
    components = [part for part in re.split(r"[\\/]", path_value) if part not in ("", ".")]
    if not components or any(part == ".." for part in components):
        return None, "source path traversal is forbidden"
    candidate = project_root.joinpath(*components)
    current = project_root
    try:
        for component in components:
            current = current / component
            if current.exists() and is_reparse_point(current):
                return None, "source path traverses a symlink or reparse point"
        resolved = candidate.resolve(strict=False)
    except OSError as exc:
        return None, f"source path inspection failed: {exc}"
    if not _is_path_within(resolved, project_root):
        return None, "source path resolves outside project root"
    return candidate, None


def _redact(value: str) -> str:
    if len(value) <= 8:
        return "[REDACTED]"
    return f"{value[:4]}…{value[-4:]}"


def _looks_placeholder(value: str) -> bool:
    lowered = value.casefold()
    return any(marker in lowered for marker in ("placeholder", "redacted", "example", "changeme", "your_", "your-", "xxxx", "<", ">", "..."))


def _scan_secret_text(text: str, relative_path: str) -> list[Issue]:
    findings: list[Issue] = []
    prefix_re = re.compile(
        r"\b(sk-(?:live-)?[A-Za-z0-9]{20,}|gh[pousr]_[A-Za-z0-9]{30,}|"
        r"xox[baprs]-[A-Za-z0-9-]{20,}|AKIA[0-9A-Z]{16})\b"
    )
    assignment_re = re.compile(
        r"(?i)\b(api[ _-]?key|access[ _-]?token|token|secret|password|passwd|client_secret)"
        r"\s*[:=]\s*[\"']?([A-Za-z0-9_./+\-=]{20,})"
    )
    for line_number, line in enumerate(text.splitlines(), 1):
        if "-----BEGIN " in line and "PRIVATE KEY-----" in line:
            findings.append(Issue("error", "SECRET_FINDING", "high-confidence secret pattern", relative_path, line_number, "PEM_PRIVATE_KEY", "-----BEGIN … PRIVATE KEY-----"))
        for match in prefix_re.finditer(line):
            value = match.group(1)
            if not _looks_placeholder(value):
                findings.append(Issue("error", "SECRET_FINDING", "high-confidence secret pattern", relative_path, line_number, "LIVE_TOKEN_PREFIX", _redact(value)))
        for match in assignment_re.finditer(line):
            value = match.group(2)
            if re.fullmatch(r"[0-9a-fA-F]{64}", value) or _looks_placeholder(value):
                continue
            findings.append(Issue("error", "SECRET_FINDING", "high-confidence credential assignment", relative_path, line_number, "CREDENTIAL_ASSIGNMENT", _redact(value)))
    unique: dict[tuple[Any, ...], Issue] = {}
    for finding in findings:
        unique[(finding.file, finding.line, finding.finding_type, finding.redacted)] = finding
    return list(unique.values())


def _scan_secrets(note: Note) -> list[Issue]:
    return _scan_secret_text(note.text, note.relative_path)


def _compute_revision(notes: list[Note]) -> str:
    canonical = hashlib.sha256()
    for note in sorted(notes, key=lambda item: _normal(item.relative_path)):
        canonical.update(_normal(note.relative_path).encode("utf-8"))
        canonical.update(b"\0")
        canonical.update(hashlib.sha256(note.raw_bytes).hexdigest().encode("ascii"))
        canonical.update(b"\0")
    return f"sha256:{canonical.hexdigest()}"


def _cycle_count(edges: dict[str, set[str]]) -> int:
    state: dict[str, int] = {}
    stack: list[str] = []
    cycle_keys: set[tuple[str, ...]] = set()

    def visit(node: str) -> None:
        state[node] = 1
        stack.append(node)
        for target in sorted(edges.get(node, set())):
            if state.get(target, 0) == 0:
                visit(target)
            elif state.get(target) == 1:
                start = stack.index(target)
                cycle = stack[start:]
                rotations = [tuple(cycle[index:] + cycle[:index]) for index in range(len(cycle))]
                cycle_keys.add(min(rotations))
        stack.pop()
        state[node] = 2

    for node in sorted(edges):
        if state.get(node, 0) == 0:
            visit(node)
    return len(cycle_keys)


def _result(
    *, vault_root: Path, project_root: Path, notes: list[Note], markdown_note_count: int,
    markdown_total_bytes: int, obsidian_json_count: int,
    obsidian_auxiliary_files: list[dict[str, Any]], issues: list[Issue],
    canonical_scope_count: int, wiki_count: int, resolved_count: int, broken_count: int,
    ambiguous_count: int, alias_collision_count: int, evidence_count: int,
    unresolved_evidence_count: int, ownership_conflicts: int, cycle_count: int,
    missing_source_count: int, unexpected_count: int, forbidden_count: int,
    secret_count: int,
) -> ValidationResult:
    issues.sort(key=lambda item: (_lookup_key(item.file), item.line, item.severity, item.code, item.message))
    errors = [issue.to_dict() for issue in issues if issue.severity == "error"]
    warnings = [issue.to_dict() for issue in issues if issue.severity == "warning"]
    status = "FAIL" if errors else ("PASS_WITH_WARNINGS" if warnings else "PASS")
    stable_ids = {note.note_id for note in notes if note.note_id and ID_RE.fullmatch(note.note_id)}
    return ValidationResult(
        status=status,
        vault_root=os.fspath(vault_root),
        project_root=os.fspath(project_root),
        vault_revision=_compute_revision(notes),
        markdown_note_count=markdown_note_count,
        markdown_total_bytes=markdown_total_bytes,
        obsidian_json_count=obsidian_json_count,
        obsidian_auxiliary_count=len(obsidian_auxiliary_files),
        obsidian_auxiliary_total_bytes=sum(
            int(item["size"]) for item in obsidian_auxiliary_files
        ),
        obsidian_auxiliary_files=obsidian_auxiliary_files,
        stable_id_count=len(stable_ids),
        canonical_scope_count=canonical_scope_count,
        wiki_link_count=wiki_count,
        resolved_wiki_link_count=resolved_count,
        broken_link_count=broken_count,
        ambiguous_link_count=ambiguous_count,
        alias_collision_count=alias_collision_count,
        evidence_record_count=evidence_count,
        unresolved_evidence_ref_count=unresolved_evidence_count,
        canonical_ownership_conflict_count=ownership_conflicts,
        supersession_cycle_count=cycle_count,
        missing_source_path_count=missing_source_count,
        unexpected_file_count=unexpected_count,
        binary_or_forbidden_file_count=forbidden_count,
        secret_finding_count=secret_count,
        error_count=len(errors),
        warning_count=len(warnings),
        errors=errors,
        warnings=warnings,
    )


def validate_vault(
    vault: os.PathLike[str] | str,
    project: os.PathLike[str] | str,
    *,
    require_canonical_scopes: bool = True,
    max_notes: int = MAX_NOTES,
    max_note_bytes: int = MAX_NOTE_BYTES,
    max_total_scan_bytes: int = MAX_TOTAL_SCAN_BYTES,
) -> ValidationResult:
    """Validate without writing to the Vault or project tree."""
    vault_root = _safe_root(vault, "Vault root")
    project_root = _safe_root(project, "project root")
    (
        discovered,
        obsidian_json_count,
        obsidian_auxiliary_files,
        issues,
        unexpected_count,
        forbidden_count,
    ) = _discover_files_detailed(vault_root)
    markdown_note_count = len(discovered)
    markdown_total_bytes = sum(info.st_size for _path, info in discovered)
    if markdown_note_count > max_notes:
        issues.append(Issue("error", "NOTE_COUNT_LIMIT", f"Markdown note count {markdown_note_count} exceeds limit {max_notes}"))
    if markdown_total_bytes > max_total_scan_bytes:
        issues.append(Issue("error", "TOTAL_SCAN_LIMIT", f"Markdown bytes {markdown_total_bytes} exceed limit {max_total_scan_bytes}"))

    notes: list[Note] = []
    for path, info in discovered:
        relative = _relative_posix(path, vault_root)
        if info.st_size > max_note_bytes:
            issues.append(Issue("error", "NOTE_SIZE_LIMIT", f"note size {info.st_size} exceeds limit {max_note_bytes}", relative))
            continue
        try:
            raw_bytes = path.read_bytes()
            if len(raw_bytes) != info.st_size:
                raise ValidatorRuntimeError(f"Vault note changed during validation: {relative}")
            text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            issues.append(Issue("error", "INVALID_UTF8", f"note is not valid UTF-8: {exc}", relative))
            continue
        except OSError as exc:
            raise ValidatorRuntimeError(f"cannot read Vault note {relative}: {exc}") from exc
        try:
            metadata, body_lines = parse_frontmatter(text)
        except FrontmatterError as exc:
            issues.append(Issue("error", "FRONTMATTER_ERROR", str(exc), relative, exc.line))
            continue
        note = Note(path, relative, raw_bytes, text, metadata, body_lines)
        _extract_headings(note)
        _validate_note_schema(note, issues)
        issues.extend(_scan_secrets(note))
        notes.append(note)

    by_id: dict[str, list[Note]] = {}
    normalized_ids: dict[str, list[Note]] = {}
    for note in notes:
        if not note.note_id:
            continue
        by_id.setdefault(note.note_id, []).append(note)
        normalized_ids.setdefault(_lookup_key(note.note_id), []).append(note)
    for note_id, owners in sorted(by_id.items()):
        if len(owners) > 1:
            for note in owners:
                _issue(issues, "error", "DUPLICATE_STABLE_ID", f"duplicate stable ID: {note_id}", note)
    for normalized_id, owners in sorted(normalized_ids.items()):
        raw_values = {note.note_id for note in owners}
        if len(owners) > 1 and (len(raw_values) > 1 or len(by_id.get(next(iter(raw_values)), [])) > 1):
            for note in owners:
                _issue(issues, "error", "NORMALIZED_DUPLICATE_ID", f"normalized/case duplicate stable ID: {normalized_id}", note)

    canonical_owners: dict[str, list[Note]] = {}
    for note in notes:
        canonical = note.metadata.get("canonical", False)
        scope = note.metadata.get("canonical_scope")
        if canonical is True:
            if not isinstance(scope, str) or not scope:
                _issue(issues, "error", "CANONICAL_SCOPE_MISSING", "canonical note requires canonical_scope", note)
            else:
                canonical_owners.setdefault(scope, []).append(note)
    ownership_conflicts = 0
    for scope, owners in sorted(canonical_owners.items()):
        if len(owners) > 1:
            ownership_conflicts += 1
            for note in owners:
                _issue(issues, "error", "CANONICAL_SCOPE_CONFLICT", f"multiple canonical owners for scope: {scope}", note)
    if require_canonical_scopes:
        for scope in sorted(REQUIRED_CANONICAL_SCOPES - set(canonical_owners)):
            issues.append(Issue("error", "MISSING_CANONICAL_SCOPE", f"missing canonical scope: {scope}"))

    missing_source_count = 0
    for note in notes:
        paths = note.metadata.get("source_paths", [])
        if not isinstance(paths, list):
            continue
        for source_path in paths:
            if not isinstance(source_path, str):
                continue
            candidate, problem = _validate_source_path(source_path, project_root)
            if problem:
                _issue(issues, "error", "INVALID_SOURCE_PATH", f"{source_path!r}: {problem}", note)
                continue
            assert candidate is not None
            if not candidate.exists():
                if note.metadata.get("knowledge_layer") == "current_source_truth":
                    missing_source_count += 1
                    _issue(issues, "error", "MISSING_CURRENT_SOURCE", f"current source path does not exist: {source_path}", note)
                elif not note.metadata.get("evidence_refs"):
                    _issue(issues, "error", "MISSING_HISTORICAL_SOURCE", f"missing historical source path lacks evidence_refs: {source_path}", note)

    evidence_records: dict[str, list[tuple[Note, int]]] = {}
    for note in notes:
        for line_number, line in _outside_fences(note.body_lines):
            heading = HEADING_RE.match(line)
            if not heading:
                continue
            heading_text = heading.group(2).strip()
            match = re.match(r"^(EV-[0-9]{3,})(?:\b|\s|—|-)", heading_text)
            if match:
                evidence_records.setdefault(match.group(1), []).append((note, line_number))
            elif heading_text.startswith("EV-"):
                _issue(issues, "error", "MALFORMED_EVIDENCE_ID", "malformed evidence record ID", note, line_number)
    for evidence_id, records in sorted(evidence_records.items()):
        if len(records) > 1:
            for note, line_number in records:
                _issue(issues, "error", "DUPLICATE_EVIDENCE_ID", f"duplicate evidence record ID: {evidence_id}", note, line_number)
    unresolved_evidence_count = 0
    for note in notes:
        references = note.metadata.get("evidence_refs", [])
        if not isinstance(references, list):
            continue
        for reference in references:
            if not isinstance(reference, str) or not EVIDENCE_ID_RE.fullmatch(reference):
                unresolved_evidence_count += 1
                _issue(issues, "error", "MALFORMED_EVIDENCE_REF", f"malformed evidence reference: {reference!r}", note)
            elif reference not in evidence_records:
                unresolved_evidence_count += 1
                _issue(issues, "error", "UNRESOLVED_EVIDENCE_REF", f"unresolved evidence reference: {reference}", note)

    id_to_note = {note.note_id: note for note in notes if note.note_id and len(by_id.get(note.note_id, [])) == 1}
    edges: dict[str, set[str]] = {note_id: set() for note_id in id_to_note}
    for note_id, note in id_to_note.items():
        supersedes = note.metadata.get("supersedes", [])
        superseded_by = note.metadata.get("superseded_by", [])
        for relation_name, references in (("supersedes", supersedes), ("superseded_by", superseded_by)):
            if not isinstance(references, list):
                continue
            for reference in references:
                if not isinstance(reference, str) or not ID_RE.fullmatch(reference):
                    _issue(issues, "error", "MALFORMED_SUPERSESSION_REF", f"malformed {relation_name} reference: {reference!r}", note)
                    continue
                if reference == note_id:
                    _issue(issues, "error", "SELF_SUPERSESSION", "self-supersession is forbidden", note)
                    continue
                if reference not in id_to_note:
                    _issue(issues, "error", "UNRESOLVED_SUPERSESSION_REF", f"unresolved {relation_name} reference: {reference}", note)
                    continue
                if relation_name == "supersedes":
                    edges[note_id].add(reference)
                    reciprocal = id_to_note[reference].metadata.get("superseded_by", [])
                    if reciprocal and note_id not in reciprocal:
                        _issue(issues, "error", "INCONSISTENT_SUPERSESSION", f"{reference} explicitly names a different superseded_by relation", note)
                else:
                    edges[reference].add(note_id)
                    reciprocal = id_to_note[reference].metadata.get("supersedes", [])
                    if reciprocal and note_id not in reciprocal:
                        _issue(issues, "error", "INCONSISTENT_SUPERSESSION", f"{reference} explicitly names a different supersedes relation", note)
    cycle_count = _cycle_count(edges)
    if cycle_count:
        issues.append(Issue("error", "SUPERSESSION_CYCLE", f"supersession graph contains {cycle_count} cycle(s)"))

    path_index: dict[str, list[Note]] = {}
    label_index: dict[str, list[Note]] = {}
    label_raw: dict[str, set[str]] = {}
    for note in notes:
        without_suffix = note.relative_path[:-3] if note.relative_path.casefold().endswith(".md") else note.relative_path
        path_index.setdefault(_lookup_key(without_suffix), []).append(note)
        labels = [Path(note.relative_path).stem]
        if note.title:
            labels.append(note.title)
        labels.extend(note.aliases)
        seen_in_note: set[str] = set()
        for label in labels:
            key = _lookup_key(label.strip())
            if not key or key in seen_in_note:
                continue
            seen_in_note.add(key)
            label_index.setdefault(key, []).append(note)
            label_raw.setdefault(key, set()).add(label)
    alias_collision_count = 0
    for key, owners in sorted(label_index.items()):
        unique_owners = {note.relative_path: note for note in owners}
        if len(unique_owners) > 1:
            alias_collision_count += 1
            raw = ", ".join(sorted(label_raw[key], key=_lookup_key))
            for note in unique_owners.values():
                _issue(issues, "error", "ALIAS_TITLE_COLLISION", f"ambiguous title/basename/alias after NFC and case normalization: {raw}", note)

    wiki_count = 0
    resolved_count = 0
    broken_count = 0
    ambiguous_count = 0
    incoming: dict[str, set[str]] = {note.relative_path: set() for note in notes}
    outgoing: dict[str, set[str]] = {note.relative_path: set() for note in notes}
    for note in notes:
        for line_number, line in _outside_fences(note.body_lines):
            for match in WIKI_LINK_RE.finditer(line):
                wiki_count += 1
                content = match.group(1)
                target_part = content.split("|", 1)[0].strip()
                target_text, separator, heading_text = target_part.partition("#")
                target_text = target_text.strip().replace("\\", "/")
                heading_text = heading_text.strip() if separator else ""
                if not target_text:
                    candidates = [note] if separator else []
                else:
                    parts = target_text.split("/")
                    unsafe = URL_RE.match(target_text) or target_text.startswith("/") or PureWindowsPath(target_text).drive or any(part in ("", ".", "..") for part in parts)
                    if unsafe:
                        candidates = []
                    elif "/" in target_text:
                        normalized_target = target_text[:-3] if target_text.casefold().endswith(".md") else target_text
                        candidates = path_index.get(_lookup_key(normalized_target), [])
                    else:
                        plain_target = target_text[:-3] if target_text.casefold().endswith(".md") else target_text
                        candidates = label_index.get(_lookup_key(plain_target), [])
                unique_candidates = {candidate.relative_path: candidate for candidate in candidates}
                if not unique_candidates:
                    broken_count += 1
                    _issue(issues, "error", "BROKEN_WIKI_LINK", f"unresolved wiki link target: {target_text or target_part}", note, line_number)
                elif len(unique_candidates) > 1:
                    ambiguous_count += 1
                    _issue(issues, "error", "AMBIGUOUS_WIKI_LINK", f"ambiguous wiki link target: {target_text}", note, line_number)
                else:
                    target_note = next(iter(unique_candidates.values()))
                    resolved_count += 1
                    outgoing[note.relative_path].add(target_note.relative_path)
                    incoming[target_note.relative_path].add(note.relative_path)
                    if heading_text and _lookup_key(heading_text) not in target_note.headings:
                        _issue(issues, "warning", "MISSING_HEADING_FRAGMENT", f"wiki link heading not found: {heading_text}", note, line_number)

    for note in notes:
        if not incoming[note.relative_path]:
            code = "CANONICAL_NO_INCOMING" if note.metadata.get("canonical") is True else "NO_INCOMING_LINKS"
            _issue(issues, "warning", code, "note has no incoming wiki links", note)
        if note.metadata.get("type") in LINK_BENEFIT_TYPES and not outgoing[note.relative_path]:
            _issue(issues, "warning", "NO_OUTGOING_LINKS", "note type normally benefits from outgoing wiki links", note)
    hub_threshold = max(50, int(len(notes) * 0.60))
    for relative, targets in outgoing.items():
        if len(targets) > hub_threshold:
            note = next(item for item in notes if item.relative_path == relative)
            _issue(issues, "warning", "EXTREME_NAVIGATION_HUB", f"navigation note links to {len(targets)} distinct notes", note)

    secret_count = sum(1 for issue in issues if issue.code == "SECRET_FINDING")
    return _result(
        vault_root=vault_root,
        project_root=project_root,
        notes=notes,
        markdown_note_count=markdown_note_count,
        markdown_total_bytes=markdown_total_bytes,
        obsidian_json_count=obsidian_json_count,
        obsidian_auxiliary_files=obsidian_auxiliary_files,
        issues=issues,
        canonical_scope_count=len(canonical_owners),
        wiki_count=wiki_count,
        resolved_count=resolved_count,
        broken_count=broken_count,
        ambiguous_count=ambiguous_count,
        alias_collision_count=alias_collision_count,
        evidence_count=len(evidence_records),
        unresolved_evidence_count=unresolved_evidence_count,
        ownership_conflicts=ownership_conflicts,
        cycle_count=cycle_count,
        missing_source_count=missing_source_count,
        unexpected_count=unexpected_count,
        forbidden_count=forbidden_count,
        secret_count=secret_count,
    )


def _human_report(result: ValidationResult) -> str:
    evidence_status = "PASS" if result.unresolved_evidence_ref_count == 0 else "FAIL"
    supersession_status = "PASS" if result.supersession_cycle_count == 0 else "FAIL"
    source_status = "PASS" if result.missing_source_path_count == 0 else "FAIL"
    return "\n".join(
        (
            "LocalComet Vault Validation",
            "",
            f"Status:\n{result.status}",
            "",
            f"Vault:\n{result.vault_root}",
            "",
            f"Vault revision:\n{result.vault_revision}",
            "",
            f"Markdown notes:\n{result.markdown_note_count}",
            "",
            f"Stable IDs:\n{result.stable_id_count}",
            "",
            f"Canonical scopes:\n{result.canonical_scope_count}",
            "",
            f"Obsidian auxiliary files:\n{result.obsidian_auxiliary_count}",
            "",
            f"Wiki links:\n{result.resolved_wiki_link_count} resolved\n{result.broken_link_count} broken\n{result.ambiguous_link_count} ambiguous",
            "",
            f"Evidence references:\n{evidence_status}",
            "",
            f"Supersession graph:\n{supersession_status}",
            "",
            f"Source paths:\n{source_status}",
            "",
            f"Unexpected files:\n{result.unexpected_file_count}",
            "",
            f"Secret findings:\n{result.secret_finding_count}",
            "",
            f"Errors:\n{result.error_count}",
            "",
            f"Warnings:\n{result.warning_count}",
            "",
            "Read only:\nYES",
        )
    )


def _runtime_payload(vault: str, project: str, exc: BaseException) -> dict[str, Any]:
    return {
        "status": "FAIL",
        "vault_root": os.path.abspath(vault),
        "project_root": os.path.abspath(project),
        "error_count": 1,
        "warning_count": 0,
        "errors": [{"severity": "error", "code": "RUNTIME_FAILURE", "message": str(exc)}],
        "warnings": [],
        "read_only": True,
    }


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--json", action="store_true", dest="json_output")
    parser.add_argument("--fail-on-warnings", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = validate_vault(args.vault, args.project)
    except Exception as exc:  # Boundary: runtime failures use the exact CLI code 2.
        if args.json_output:
            print(json.dumps(_runtime_payload(args.vault, args.project, exc), ensure_ascii=False, sort_keys=True))
        else:
            print(f"LocalComet Vault Validation\n\nStatus:\nRUNTIME FAILURE\n\nError:\n{exc}\n\nRead only:\nYES")
        return 2
    if args.json_output:
        print(json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True))
    else:
        print(_human_report(result))
    if result.status == "FAIL" or (args.fail_on_warnings and result.warning_count):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
