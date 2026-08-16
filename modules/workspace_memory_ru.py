"""Bounded, workspace-isolated document and explicit-memory service.

This module deliberately stays in-memory for the selected MVP increment. It
reuses the existing WorkspacePolicy boundary and never exposes absolute paths
in retrieval or citation payloads.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path
from typing import Iterable

from modules.workspace_policy import WorkspacePolicyError, make_policy

MAX_DOCUMENT_BYTES = 1_000_000
MAX_CHUNK_CHARS = 1_200
MAX_QUERY_CHARS = 512
MAX_RESULTS = 20
ALLOWED_SUFFIXES = frozenset({".md", ".markdown", ".txt"})
TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)
HEADING_RE = re.compile(r"^#{1,6}[ \t]+(.+?)\s*$")


class DocumentState(str, Enum):
    REGISTERED = "registered"
    INDEXED = "indexed"
    FAILED = "failed"


class MemoryState(str, Enum):
    CANDIDATE = "candidate"
    USER_CONFIRMED = "user_confirmed"
    ACTIVE = "active"


@dataclass(frozen=True, slots=True)
class DocumentRecord:
    document_id: str
    workspace_id: str
    source_name: str
    source_sha256: str
    byte_size: int
    state: DocumentState
    chunk_ids: tuple[str, ...] = ()
    error_code: str | None = None
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class ChunkRecord:
    chunk_id: str
    document_id: str
    workspace_id: str
    source_sha256: str
    ordinal: int
    section: str
    parser_version: str
    text: str


@dataclass(frozen=True, slots=True)
class Citation:
    document_id: str
    source_sha256: str
    chunk_id: str
    ordinal: int
    section: str
    parser_version: str


@dataclass(frozen=True, slots=True)
class SearchHit:
    chunk: ChunkRecord
    score: int
    citation: Citation


@dataclass(frozen=True, slots=True)
class MemoryRecord:
    memory_id: str
    workspace_id: str
    content: str
    state: MemoryState
    source_chunk_ids: tuple[str, ...] = ()


class WorkspaceMemoryError(RuntimeError):
    """Stable, path-safe error for the workspace memory boundary."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _identifier(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 128:
        raise WorkspaceMemoryError("INVALID_IDENTIFIER", f"{field} is invalid")
    return value.strip()


def _tokens(value: str) -> tuple[str, ...]:
    return tuple(TOKEN_RE.findall(value.casefold()))


def _document_id(workspace_id: str, canonical_path: Path) -> str:
    material = f"{workspace_id}\0{canonical_path}".encode("utf-8")
    return "doc-" + hashlib.sha256(material).hexdigest()[:24]


def _chunk_id(document_id: str, source_sha256: str, ordinal: int) -> str:
    material = f"{document_id}\0{source_sha256}\0{ordinal}".encode("ascii")
    return "chunk-" + hashlib.sha256(material).hexdigest()[:24]


class WorkspaceMemoryStore:
    """A bounded, deterministic workspace document and memory store.

    Every public data operation requires both ``workspace_id`` and ``actor_id``.
    The store is scoped to exactly one workspace, so requests for another
    workspace fail closed instead of falling back globally.
    """

    def __init__(
        self,
        workspace_root: str | Path,
        workspace_id: str,
        owner_id: str,
        members: Iterable[str] = (),
    ) -> None:
        root = Path(workspace_root)
        if not root.exists() or not root.is_dir():
            raise WorkspaceMemoryError("WORKSPACE_NOT_FOUND", "workspace root is not a directory")
        self.workspace_root = root.resolve()
        self.workspace_id = _identifier(workspace_id, "workspace_id")
        self.owner_id = _identifier(owner_id, "owner_id")
        self.members = frozenset(_identifier(member, "member_id") for member in members)
        session_material = f"{self.workspace_id}\0{self.workspace_root}".encode("utf-8")
        session_id = hashlib.sha256(session_material).hexdigest()
        try:
            self._policy = make_policy(str(self.workspace_root), session_id)
        except (OSError, ValueError, WorkspacePolicyError) as exc:
            raise WorkspaceMemoryError("WORKSPACE_POLICY_INVALID", "workspace boundary is unsafe") from exc
        self._documents: dict[str, DocumentRecord] = {}
        self._chunks: dict[str, ChunkRecord] = {}
        self._chunk_tokens: dict[str, frozenset[str]] = {}
        self._index: dict[str, set[str]] = {}
        self._memories: dict[str, MemoryRecord] = {}
        self._memory_index: dict[str, set[str]] = {}
        self._memory_sequence = 0

    def _authorize(self, workspace_id: str, actor_id: str) -> None:
        requested = _identifier(workspace_id, "workspace_id")
        actor = _identifier(actor_id, "actor_id")
        if requested != self.workspace_id:
            raise WorkspaceMemoryError("WORKSPACE_MISMATCH", "workspace request does not match store")
        if actor != self.owner_id and actor not in self.members:
            raise WorkspaceMemoryError("MEMBERSHIP_REQUIRED", "actor is not a workspace member")

    def _safe_source(self, source_path: str | Path) -> Path:
        try:
            source = self._policy.validate_path(source_path)
        except (WorkspacePolicyError, ValueError, OSError) as exc:
            raise WorkspaceMemoryError("WORKSPACE_PATH_ESCAPE", "source path is outside workspace") from exc
        if source.is_symlink():
            raise WorkspaceMemoryError("WORKSPACE_REPARSE_POINT", "source reparse point is not allowed")
        if not source.exists():
            raise WorkspaceMemoryError("SOURCE_NOT_FOUND", "source file was not found")
        if not source.is_file():
            raise WorkspaceMemoryError("UNSUPPORTED_SOURCE_TYPE", "source is not a regular file")
        if source.suffix.casefold() not in ALLOWED_SUFFIXES:
            raise WorkspaceMemoryError("UNSUPPORTED_SOURCE_TYPE", "source type is not allowlisted")
        try:
            size = source.stat().st_size
        except OSError as exc:
            raise WorkspaceMemoryError("SOURCE_STAT_FAILED", "source metadata could not be read") from exc
        if size > MAX_DOCUMENT_BYTES:
            raise WorkspaceMemoryError("SOURCE_TOO_LARGE", "source exceeds the document size limit")
        return source

    def _remove_document_index(self, document_id: str) -> None:
        previous = self._documents.get(document_id)
        if previous is None:
            return
        for chunk_id in previous.chunk_ids:
            chunk = self._chunks.pop(chunk_id, None)
            self._chunk_tokens.pop(chunk_id, None)
            if chunk is None:
                continue
            for token in _tokens(chunk.text):
                ids = self._index.get(token)
                if ids is not None:
                    ids.discard(chunk_id)
                    if not ids:
                        self._index.pop(token, None)

    @staticmethod
    def _chunk_text(text: str) -> list[tuple[str, str]]:
        chunks: list[tuple[str, str]] = []
        section = "document"
        buffer: list[str] = []
        size = 0

        def flush() -> None:
            nonlocal buffer, size
            value = "\n".join(buffer).strip()
            if value:
                chunks.append((section, value))
            buffer = []
            size = 0

        for line in text.splitlines():
            heading = HEADING_RE.match(line.strip())
            if heading:
                if buffer:
                    flush()
                section = heading.group(1).strip()[:200]
            if size and size + len(line) + 1 > MAX_CHUNK_CHARS:
                flush()
            buffer.append(line)
            size += len(line) + 1
        flush()
        if not chunks:
            raise ValueError("document is empty")
        return chunks

    def ingest_document(
        self,
        *,
        workspace_id: str,
        actor_id: str,
        source_path: str | Path,
        parser_version: str = "text-v1",
    ) -> DocumentRecord:
        self._authorize(workspace_id, actor_id)
        parser = _identifier(parser_version, "parser_version")
        source = self._safe_source(source_path)
        try:
            raw = source.read_bytes()
        except OSError as exc:
            raise WorkspaceMemoryError("SOURCE_READ_FAILED", "source could not be read") from exc
        source_sha256 = hashlib.sha256(raw).hexdigest()
        document_id = _document_id(self.workspace_id, source)
        self._remove_document_index(document_id)
        registered = DocumentRecord(
            document_id=document_id,
            workspace_id=self.workspace_id,
            source_name=source.name,
            source_sha256=source_sha256,
            byte_size=len(raw),
            state=DocumentState.REGISTERED,
        )
        self._documents[document_id] = registered
        try:
            text = raw.decode("utf-8")
            chunk_texts = self._chunk_text(text)
            chunks: list[ChunkRecord] = []
            for ordinal, (section, chunk_text) in enumerate(chunk_texts):
                chunk = ChunkRecord(
                    chunk_id=_chunk_id(document_id, source_sha256, ordinal),
                    document_id=document_id,
                    workspace_id=self.workspace_id,
                    source_sha256=source_sha256,
                    ordinal=ordinal,
                    section=section,
                    parser_version=parser,
                    text=chunk_text,
                )
                chunks.append(chunk)
            for chunk in chunks:
                self._chunks[chunk.chunk_id] = chunk
                token_set = frozenset(_tokens(chunk.text))
                self._chunk_tokens[chunk.chunk_id] = token_set
                for token in token_set:
                    self._index.setdefault(token, set()).add(chunk.chunk_id)
            indexed = replace(registered, state=DocumentState.INDEXED, chunk_ids=tuple(chunk.chunk_id for chunk in chunks))
            self._documents[document_id] = indexed
            return indexed
        except (UnicodeDecodeError, OSError, ValueError) as exc:
            failed = replace(
                registered,
                state=DocumentState.FAILED,
                error_code="DOCUMENT_PARSE_OR_INDEX_FAILED",
                error_message=type(exc).__name__,
            )
            self._documents[document_id] = failed
            return failed

    def get_document(self, *, workspace_id: str, actor_id: str, document_id: str) -> DocumentRecord:
        self._authorize(workspace_id, actor_id)
        record = self._documents.get(_identifier(document_id, "document_id"))
        if record is None:
            raise WorkspaceMemoryError("DOCUMENT_NOT_FOUND", "document was not found")
        return record

    def search(
        self,
        *,
        workspace_id: str,
        actor_id: str,
        query: str,
        limit: int = 5,
    ) -> tuple[SearchHit, ...]:
        self._authorize(workspace_id, actor_id)
        if not isinstance(query, str) or not query.strip() or len(query) > MAX_QUERY_CHARS:
            raise WorkspaceMemoryError("QUERY_INVALID", "query is empty or too large")
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_RESULTS:
            raise WorkspaceMemoryError("RESULT_LIMIT_INVALID", "result limit is outside the allowed range")
        query_tokens = tuple(dict.fromkeys(_tokens(query)))
        candidate_ids: set[str] = set()
        for token in query_tokens:
            candidate_ids.update(self._index.get(token, set()))
        scored: list[tuple[int, ChunkRecord]] = []
        for chunk_id in candidate_ids:
            chunk = self._chunks.get(chunk_id)
            if chunk is None or chunk.workspace_id != self.workspace_id:
                continue
            score = sum(token in self._chunk_tokens.get(chunk_id, frozenset()) for token in query_tokens)
            if score:
                scored.append((score, chunk))
        scored.sort(key=lambda item: (-item[0], item[1].ordinal, item[1].chunk_id))
        return tuple(
            SearchHit(
                chunk=chunk,
                score=score,
                citation=Citation(
                    document_id=chunk.document_id,
                    source_sha256=chunk.source_sha256,
                    chunk_id=chunk.chunk_id,
                    ordinal=chunk.ordinal,
                    section=chunk.section,
                    parser_version=chunk.parser_version,
                ),
            )
            for score, chunk in scored[:limit]
        )

    def propose_memory(
        self,
        *,
        workspace_id: str,
        actor_id: str,
        content: str,
        source_chunk_ids: Iterable[str] = (),
    ) -> MemoryRecord:
        self._authorize(workspace_id, actor_id)
        if not isinstance(content, str) or not content.strip() or len(content) > MAX_QUERY_CHARS:
            raise WorkspaceMemoryError("MEMORY_CONTENT_INVALID", "memory content is empty or too large")
        source_ids = tuple(dict.fromkeys(_identifier(item, "chunk_id") for item in source_chunk_ids))
        for chunk_id in source_ids:
            chunk = self._chunks.get(chunk_id)
            if chunk is None or chunk.workspace_id != self.workspace_id:
                raise WorkspaceMemoryError("MEMORY_SOURCE_NOT_FOUND", "memory source chunk was not found")
        self._memory_sequence += 1
        material = f"{self.workspace_id}\0{self._memory_sequence}\0{content}".encode("utf-8")
        memory_id = "mem-" + hashlib.sha256(material).hexdigest()[:24]
        record = MemoryRecord(memory_id, self.workspace_id, content.strip(), MemoryState.CANDIDATE, source_ids)
        self._memories[memory_id] = record
        return record

    def get_memory(self, *, workspace_id: str, actor_id: str, memory_id: str) -> MemoryRecord:
        self._authorize(workspace_id, actor_id)
        record = self._memories.get(_identifier(memory_id, "memory_id"))
        if record is None:
            raise WorkspaceMemoryError("MEMORY_NOT_FOUND", "memory was not found")
        return record

    def confirm_memory(self, *, workspace_id: str, actor_id: str, memory_id: str) -> MemoryRecord:
        record = self.get_memory(workspace_id=workspace_id, actor_id=actor_id, memory_id=memory_id)
        if record.state is not MemoryState.CANDIDATE:
            raise WorkspaceMemoryError("MEMORY_STATE_INVALID", "only a candidate can be confirmed")
        updated = replace(record, state=MemoryState.USER_CONFIRMED)
        self._memories[record.memory_id] = updated
        return updated

    def activate_memory(self, *, workspace_id: str, actor_id: str, memory_id: str) -> MemoryRecord:
        record = self.get_memory(workspace_id=workspace_id, actor_id=actor_id, memory_id=memory_id)
        if record.state is not MemoryState.USER_CONFIRMED:
            raise WorkspaceMemoryError("MEMORY_STATE_INVALID", "memory requires explicit confirmation")
        updated = replace(record, state=MemoryState.ACTIVE)
        self._memories[record.memory_id] = updated
        for token in frozenset(_tokens(record.content)):
            self._memory_index.setdefault(token, set()).add(record.memory_id)
        return updated

    def delete_memory(self, *, workspace_id: str, actor_id: str, memory_id: str) -> dict[str, object]:
        record = self.get_memory(workspace_id=workspace_id, actor_id=actor_id, memory_id=memory_id)
        self._memories.pop(record.memory_id, None)
        for token in _tokens(record.content):
            ids = self._memory_index.get(token)
            if ids is not None:
                ids.discard(record.memory_id)
                if not ids:
                    self._memory_index.pop(token, None)
        verified = record.memory_id not in self._memories and all(
            record.memory_id not in ids for ids in self._memory_index.values()
        )
        if not verified:
            raise WorkspaceMemoryError("MEMORY_DELETE_UNVERIFIED", "memory deletion could not be verified")
        return {"memory_id": record.memory_id, "deleted": True, "verified": True}
