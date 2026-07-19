"""Immutable contracts for the read-only LocalComet KnowledgeAdapter prototype."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import os
from pathlib import Path
from pathlib import PurePosixPath, PureWindowsPath
import re
from types import MappingProxyType
from typing import Any, Mapping


MAX_NOTES = 2000
MAX_NOTE_BYTES = 1_048_576
MAX_TOTAL_SCAN_BYTES = 67_108_864
DEFAULT_MAX_RESULTS = 8
HARD_MAX_RESULTS = 20
DEFAULT_CONTEXT_CHARS = 24_000
HARD_MAX_CONTEXT_CHARS = 48_000
MAX_QUERY_CHARS = 4096
MAX_MATCHED_SECTIONS = 3
MAX_EXCERPT_CHARS = 1200


class AdapterState(str, Enum):
    NOT_CONFIGURED = "NOT_CONFIGURED"
    SCANNING = "SCANNING"
    READY = "READY"
    DEGRADED = "DEGRADED"
    ERROR = "ERROR"


class QueryIntent(str, Enum):
    AUTO = "AUTO"
    CURRENT_STATE = "CURRENT_STATE"
    ARCHITECTURE = "ARCHITECTURE"
    SECURITY = "SECURITY"
    HISTORY = "HISTORY"
    FOUNDER_INTENT = "FOUNDER_INTENT"
    ROADMAP = "ROADMAP"
    RESEARCH = "RESEARCH"
    OPERATIONAL = "OPERATIONAL"
    INCIDENT = "INCIDENT"


class KnowledgeContextState(str, Enum):
    NOT_REQUESTED = "NOT_REQUESTED"
    REQUESTED = "REQUESTED"
    RETRIEVING = "RETRIEVING"
    READY = "READY"
    FAILED = "FAILED"


class KnowledgeErrorCode(str, Enum):
    KNOWLEDGE_NOT_CONFIGURED = "KNOWLEDGE_NOT_CONFIGURED"
    KNOWLEDGE_VAULT_NOT_FOUND = "KNOWLEDGE_VAULT_NOT_FOUND"
    KNOWLEDGE_PATH_ESCAPE = "KNOWLEDGE_PATH_ESCAPE"
    KNOWLEDGE_REPARSE_POINT = "KNOWLEDGE_REPARSE_POINT"
    KNOWLEDGE_NOTE_TOO_LARGE = "KNOWLEDGE_NOTE_TOO_LARGE"
    KNOWLEDGE_VAULT_TOO_LARGE = "KNOWLEDGE_VAULT_TOO_LARGE"
    KNOWLEDGE_TOO_MANY_NOTES = "KNOWLEDGE_TOO_MANY_NOTES"
    KNOWLEDGE_VALIDATION_FAILED = "KNOWLEDGE_VALIDATION_FAILED"
    KNOWLEDGE_FRONTMATTER_INVALID = "KNOWLEDGE_FRONTMATTER_INVALID"
    KNOWLEDGE_DUPLICATE_ID = "KNOWLEDGE_DUPLICATE_ID"
    KNOWLEDGE_CANONICAL_CONFLICT = "KNOWLEDGE_CANONICAL_CONFLICT"
    KNOWLEDGE_NOTE_NOT_FOUND = "KNOWLEDGE_NOTE_NOT_FOUND"
    KNOWLEDGE_QUERY_EMPTY = "KNOWLEDGE_QUERY_EMPTY"
    KNOWLEDGE_QUERY_TOO_LARGE = "KNOWLEDGE_QUERY_TOO_LARGE"
    KNOWLEDGE_RESULT_LIMIT = "KNOWLEDGE_RESULT_LIMIT"
    KNOWLEDGE_CONTEXT_LIMIT = "KNOWLEDGE_CONTEXT_LIMIT"
    KNOWLEDGE_REFRESH_FAILED = "KNOWLEDGE_REFRESH_FAILED"
    KNOWLEDGE_INTERNAL_ERROR = "KNOWLEDGE_INTERNAL_ERROR"


class KnowledgeAdapterError(RuntimeError):
    """Stable, path-safe adapter error suitable for a future IPC boundary."""

    def __init__(
        self,
        code: KnowledgeErrorCode,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = dict(details or {})

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"code": self.code.value, "message": self.message}
        if self.details:
            result["details"] = dict(self.details)
        return result


_OPAQUE_REQUEST_ID_RE = re.compile(r"^[^\s]{1,128}$")
_ERROR_CODE_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,127}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_VAULT_REVISION_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_BUNDLE_ID_RE = re.compile(r"^kb:[0-9a-f]{64}$")
_ABSOLUTE_PATH_RE = re.compile(
    r"(?i)(?:[A-Z]:[\\/]|\\\\[^\\/\s]+[\\/][^\\/\s]+|/(?:home|Users)/[^/\s]+/)"
)
_SOURCE_PROVENANCE_FIELDS = (
    "note_id",
    "relative_path",
    "knowledge_layer",
    "evidence_class",
    "authority",
    "status",
    "canonical",
    "selected_sections",
    "note_sha256",
)


def _contains_absolute_path(value: object) -> bool:
    if isinstance(value, str):
        return bool(_ABSOLUTE_PATH_RE.search(value))
    if isinstance(value, Mapping):
        return any(_contains_absolute_path(key) or _contains_absolute_path(child) for key, child in value.items())
    if isinstance(value, (list, tuple)):
        return any(_contains_absolute_path(child) for child in value)
    return False


def _freeze(value: object) -> object:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(child) for key, child in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(child) for child in value)
    return value


def _thaw(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _thaw(child) for key, child in value.items()}
    if isinstance(value, tuple):
        return [_thaw(child) for child in value]
    return value


@dataclass(frozen=True, slots=True)
class KnowledgeContextError:
    code: str
    safe_message: str

    def __post_init__(self) -> None:
        if not isinstance(self.code, str) or not _ERROR_CODE_RE.fullmatch(self.code):
            raise ValueError("knowledge context error code is invalid")
        if not isinstance(self.safe_message, str) or not 1 <= len(self.safe_message) <= 512:
            raise ValueError("knowledge context safe message is invalid")
        if _contains_absolute_path(self.safe_message):
            raise ValueError("knowledge context safe message contains an absolute path")

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "safe_message": self.safe_message}


@dataclass(frozen=True, slots=True)
class KnowledgeContextRequest:
    request_id: str
    query: str
    intent: QueryIntent
    max_context_chars: int = DEFAULT_CONTEXT_CHARS
    max_results: int = DEFAULT_MAX_RESULTS
    include_superseded: bool = False
    turn_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.request_id, str) or not _OPAQUE_REQUEST_ID_RE.fullmatch(self.request_id):
            raise ValueError("request_id must be a bounded opaque identity")
        if not isinstance(self.query, str) or not self.query.strip():
            raise ValueError("query must be a non-empty string")
        if len(self.query) > MAX_QUERY_CHARS:
            raise ValueError("query exceeds the hard character limit")
        if not isinstance(self.intent, QueryIntent):
            try:
                object.__setattr__(self, "intent", QueryIntent(self.intent))
            except (TypeError, ValueError) as exc:
                raise ValueError("intent is not a supported KnowledgeAdapter intent") from exc
        _bounded_integer("max_context_chars", self.max_context_chars, 1, HARD_MAX_CONTEXT_CHARS)
        _bounded_integer("max_results", self.max_results, 1, HARD_MAX_RESULTS)
        if not isinstance(self.include_superseded, bool):
            raise ValueError("include_superseded must be a boolean")
        if self.turn_id is not None and (
            not isinstance(self.turn_id, str) or not _OPAQUE_REQUEST_ID_RE.fullmatch(self.turn_id)
        ):
            raise ValueError("turn_id must be a bounded opaque identity when supplied")

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "query": self.query,
            "intent": self.intent.value,
            "max_context_chars": self.max_context_chars,
            "max_results": self.max_results,
            "include_superseded": self.include_superseded,
            "turn_id": self.turn_id,
        }


@dataclass(frozen=True, slots=True)
class KnowledgeContextResult:
    request_id: str
    state: KnowledgeContextState
    turn_id: str | None = None
    vault_revision: str = ""
    bundle_id: str | None = None
    resolved_intent: QueryIntent | None = None
    source_count: int = 0
    total_chars: int = 0
    truncated: bool = False
    sources: tuple[Mapping[str, Any], ...] = ()
    context_relations: tuple[Mapping[str, Any], ...] = ()
    warnings: tuple[str, ...] = ()
    error: KnowledgeContextError | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.request_id, str) or not _OPAQUE_REQUEST_ID_RE.fullmatch(self.request_id):
            raise ValueError("result request_id is invalid")
        if not isinstance(self.state, KnowledgeContextState):
            try:
                object.__setattr__(self, "state", KnowledgeContextState(self.state))
            except (TypeError, ValueError) as exc:
                raise ValueError("knowledge context state is invalid") from exc
        if self.turn_id is not None and (
            not isinstance(self.turn_id, str) or not _OPAQUE_REQUEST_ID_RE.fullmatch(self.turn_id)
        ):
            raise ValueError("result turn_id is invalid")
        if isinstance(self.source_count, bool) or not isinstance(self.source_count, int) or self.source_count < 0:
            raise ValueError("source_count must be a non-negative integer")
        if isinstance(self.total_chars, bool) or not isinstance(self.total_chars, int) or self.total_chars < 0:
            raise ValueError("total_chars must be a non-negative integer")
        if self.source_count > HARD_MAX_RESULTS:
            raise ValueError("source_count exceeds the adapter hard result limit")
        if self.total_chars > HARD_MAX_CONTEXT_CHARS:
            raise ValueError("total_chars exceeds the adapter hard context limit")
        if not isinstance(self.truncated, bool):
            raise ValueError("truncated must be a boolean")
        if not isinstance(self.sources, tuple):
            object.__setattr__(self, "sources", tuple(self.sources))
        if not isinstance(self.context_relations, tuple):
            object.__setattr__(self, "context_relations", tuple(self.context_relations))
        if not isinstance(self.warnings, tuple):
            object.__setattr__(self, "warnings", tuple(self.warnings))
        self._validate_state_contract()
        frozen_sources = tuple(_freeze(source) for source in self.sources)
        frozen_relations = tuple(_freeze(relation) for relation in self.context_relations)
        object.__setattr__(self, "sources", frozen_sources)
        object.__setattr__(self, "context_relations", frozen_relations)

    def _validate_state_contract(self) -> None:
        if len(self.warnings) > 64:
            raise ValueError("knowledge context warning count exceeds the bounded contract")
        if any(not isinstance(warning, str) or len(warning) > 256 for warning in self.warnings):
            raise ValueError("knowledge context warnings are invalid")
        if self.state is KnowledgeContextState.READY:
            if not _VAULT_REVISION_RE.fullmatch(self.vault_revision):
                raise ValueError("READY result requires a valid Vault revision")
            if not isinstance(self.bundle_id, str) or not _BUNDLE_ID_RE.fullmatch(self.bundle_id):
                raise ValueError("READY result requires a valid adapter bundle_id")
            if not isinstance(self.resolved_intent, QueryIntent):
                try:
                    object.__setattr__(self, "resolved_intent", QueryIntent(self.resolved_intent))
                except (TypeError, ValueError) as exc:
                    raise ValueError("READY result requires a valid resolved intent") from exc
            if self.error is not None:
                raise ValueError("READY result cannot contain an error")
            if len(self.context_relations) > HARD_MAX_RESULTS * 2:
                raise ValueError("knowledge context relation count exceeds the bounded contract")
            if any(not isinstance(relation, Mapping) for relation in self.context_relations):
                raise ValueError("knowledge context relations must be objects")
            self._validate_sources()
            if _contains_absolute_path((self.sources, self.context_relations, self.warnings)):
                raise ValueError("READY result contains an absolute filesystem path")
            return
        if self.state is KnowledgeContextState.FAILED:
            if not isinstance(self.error, KnowledgeContextError):
                raise ValueError("FAILED result requires a structured error")
            if (
                self.vault_revision
                or self.bundle_id is not None
                or self.resolved_intent is not None
                or self.sources
                or self.context_relations
                or self.source_count
                or self.total_chars
                or self.truncated
            ):
                raise ValueError("FAILED result cannot contain successful context content")
            return
        if (
            self.vault_revision
            or self.error is not None
            or self.bundle_id is not None
            or self.resolved_intent is not None
            or self.sources
            or self.context_relations
            or self.source_count
            or self.total_chars
            or self.truncated
            or self.warnings
        ):
            raise ValueError("non-terminal knowledge context state contains terminal data")

    def _validate_sources(self) -> None:
        if self.source_count != len(self.sources):
            raise ValueError("source_count does not match sources")
        measured_chars = 0
        for source in self.sources:
            if not isinstance(source, Mapping):
                raise ValueError("knowledge source must be an object")
            missing = [name for name in _SOURCE_PROVENANCE_FIELDS if name not in source]
            if missing:
                raise ValueError("knowledge source provenance is incomplete")
            if not isinstance(source["note_id"], str) or not source["note_id"]:
                raise ValueError("knowledge source note_id is invalid")
            for field_name in ("knowledge_layer", "evidence_class", "authority", "status"):
                if not isinstance(source[field_name], str) or not source[field_name]:
                    raise ValueError("knowledge source provenance field is invalid")
            relative_path = source["relative_path"]
            if not isinstance(relative_path, str) or not relative_path:
                raise ValueError("knowledge source relative_path is invalid")
            if PurePosixPath(relative_path).is_absolute() or PureWindowsPath(relative_path).is_absolute():
                raise ValueError("knowledge source path must remain relative")
            if not isinstance(source["canonical"], bool):
                raise ValueError("knowledge source canonical flag is invalid")
            if not isinstance(source["note_sha256"], str) or not _SHA256_RE.fullmatch(source["note_sha256"]):
                raise ValueError("knowledge source hash is invalid")
            sections = source["selected_sections"]
            if not isinstance(sections, (list, tuple)):
                raise ValueError("knowledge source sections are invalid")
            for section in sections:
                if not isinstance(section, Mapping) or not isinstance(section.get("content"), str):
                    raise ValueError("knowledge source section content is invalid")
                measured_chars += len(section["content"])
        if measured_chars != self.total_chars:
            raise ValueError("total_chars does not match selected source content")

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "turn_id": self.turn_id,
            "state": self.state.value,
            "vault_revision": self.vault_revision,
            "bundle_id": self.bundle_id,
            "resolved_intent": self.resolved_intent.value if self.resolved_intent else None,
            "source_count": self.source_count,
            "total_chars": self.total_chars,
            "truncated": self.truncated,
            "sources": _thaw(self.sources),
            "context_relations": _thaw(self.context_relations),
            "warnings": list(self.warnings),
            "error": self.error.to_dict() if self.error else None,
        }


def _bounded_integer(name: str, value: int, lower: int, upper: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not lower <= value <= upper:
        raise ValueError(f"{name} must be an integer between {lower} and {upper}")


@dataclass(frozen=True, slots=True)
class KnowledgeConfig:
    vault_root: Path
    project_root: Path
    max_notes: int = MAX_NOTES
    max_note_bytes: int = MAX_NOTE_BYTES
    max_total_scan_bytes: int = MAX_TOTAL_SCAN_BYTES
    default_max_results: int = DEFAULT_MAX_RESULTS
    hard_max_results: int = HARD_MAX_RESULTS
    default_context_chars: int = DEFAULT_CONTEXT_CHARS
    hard_max_context_chars: int = HARD_MAX_CONTEXT_CHARS

    def __post_init__(self) -> None:
        object.__setattr__(self, "vault_root", Path(os.fspath(self.vault_root)))
        object.__setattr__(self, "project_root", Path(os.fspath(self.project_root)))
        _bounded_integer("max_notes", self.max_notes, 1, MAX_NOTES)
        _bounded_integer("max_note_bytes", self.max_note_bytes, 1, MAX_NOTE_BYTES)
        _bounded_integer("max_total_scan_bytes", self.max_total_scan_bytes, 1, MAX_TOTAL_SCAN_BYTES)
        _bounded_integer("hard_max_results", self.hard_max_results, 1, HARD_MAX_RESULTS)
        _bounded_integer("default_max_results", self.default_max_results, 1, self.hard_max_results)
        _bounded_integer("hard_max_context_chars", self.hard_max_context_chars, 1, HARD_MAX_CONTEXT_CHARS)
        _bounded_integer(
            "default_context_chars",
            self.default_context_chars,
            1,
            self.hard_max_context_chars,
        )


@dataclass(frozen=True, slots=True)
class NoteHeading:
    title: str
    level: int
    line_start: int
    line_end: int


@dataclass(frozen=True, slots=True)
class KnowledgeNote:
    note_id: str
    title: str
    relative_path: str
    type: str
    status: str
    knowledge_layer: str
    evidence_class: str
    authority: str
    canonical: bool
    canonical_scope: str | None
    aliases: tuple[str, ...]
    releases: tuple[str, ...]
    source_paths: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    supersedes: tuple[str, ...]
    superseded_by: tuple[str, ...]
    updated: str
    last_reviewed: str
    verified_at: str | None
    headings: tuple[NoteHeading, ...]
    body_text: str
    text_lines: tuple[str, ...]
    body_start_line: int
    note_sha256: str
    file_size: int

    def metadata_dict(self) -> dict[str, Any]:
        return {
            "id": self.note_id,
            "title": self.title,
            "type": self.type,
            "status": self.status,
            "knowledge_layer": self.knowledge_layer,
            "evidence_class": self.evidence_class,
            "authority": self.authority,
            "canonical": self.canonical,
            "canonical_scope": self.canonical_scope,
            "aliases": list(self.aliases),
            "releases": list(self.releases),
            "source_paths": list(self.source_paths),
            "evidence_refs": list(self.evidence_refs),
            "supersedes": list(self.supersedes),
            "superseded_by": list(self.superseded_by),
            "updated": self.updated,
            "last_reviewed": self.last_reviewed,
            "verified_at": self.verified_at,
            "headings": [
                {
                    "title": heading.title,
                    "level": heading.level,
                    "line_start": heading.line_start,
                    "line_end": heading.line_end,
                }
                for heading in self.headings
            ],
            "file_size": self.file_size,
        }


@dataclass(frozen=True, slots=True)
class MatchedSection:
    heading: str
    line_start: int
    line_end: int
    excerpt: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "heading": self.heading,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "excerpt": self.excerpt,
        }
