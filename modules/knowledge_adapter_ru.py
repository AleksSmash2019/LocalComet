"""Read-only, deterministic, in-memory LocalComet KnowledgeAdapter prototype."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import stat
import sys
import threading
import time
import unicodedata
from types import MappingProxyType
from typing import Any, Callable, Mapping

from modules.knowledge_contract_ru import (
    AdapterState,
    HARD_MAX_CONTEXT_CHARS,
    HARD_MAX_RESULTS,
    KnowledgeAdapterError,
    KnowledgeConfig,
    KnowledgeErrorCode,
    KnowledgeNote,
    MatchedSection,
    MAX_EXCERPT_CHARS,
    MAX_MATCHED_SECTIONS,
    MAX_QUERY_CHARS,
    NoteHeading,
    QueryIntent,
)
from tools import validate_localcomet_vault as vault_validator


sys.dont_write_bytecode = True

DiagnosticLogger = Callable[[str, Mapping[str, Any]], None]
TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)
HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.+?)\s*$")


@dataclass(frozen=True, slots=True)
class _KnowledgeIndex:
    notes: tuple[KnowledgeNote, ...]
    by_id: Mapping[str, KnowledgeNote]
    vault_revision: str
    canonical_scope_count: int
    validation_status: str
    validation_error_count: int
    validation_warning_count: int


def _nfc(value: str) -> str:
    return unicodedata.normalize("NFC", value)


def _normalize(value: str) -> str:
    return " ".join(_nfc(value).casefold().split())


def _tokens(value: str) -> tuple[str, ...]:
    return tuple(TOKEN_RE.findall(_normalize(value)))


def _list_of_strings(metadata: Mapping[str, Any], name: str) -> tuple[str, ...]:
    value = metadata.get(name, [])
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise KnowledgeAdapterError(
            KnowledgeErrorCode.KNOWLEDGE_FRONTMATTER_INVALID,
            f"Validated note has an invalid {name} field.",
        )
    return tuple(value)


def _safe_error_from_validation(result: Any) -> KnowledgeAdapterError:
    codes = {item.get("code") for item in result.errors}
    if "NOTE_SIZE_LIMIT" in codes:
        code = KnowledgeErrorCode.KNOWLEDGE_NOTE_TOO_LARGE
    elif "TOTAL_SCAN_LIMIT" in codes:
        code = KnowledgeErrorCode.KNOWLEDGE_VAULT_TOO_LARGE
    elif "NOTE_COUNT_LIMIT" in codes:
        code = KnowledgeErrorCode.KNOWLEDGE_TOO_MANY_NOTES
    elif "FRONTMATTER_ERROR" in codes:
        code = KnowledgeErrorCode.KNOWLEDGE_FRONTMATTER_INVALID
    elif codes & {"DUPLICATE_STABLE_ID", "NORMALIZED_DUPLICATE_ID"}:
        code = KnowledgeErrorCode.KNOWLEDGE_DUPLICATE_ID
    elif "CANONICAL_SCOPE_CONFLICT" in codes:
        code = KnowledgeErrorCode.KNOWLEDGE_CANONICAL_CONFLICT
    elif codes & {"REPARSE_POINT", "NON_REGULAR_FILE"}:
        code = KnowledgeErrorCode.KNOWLEDGE_REPARSE_POINT
    elif "PATH_ESCAPE" in codes:
        code = KnowledgeErrorCode.KNOWLEDGE_PATH_ESCAPE
    else:
        code = KnowledgeErrorCode.KNOWLEDGE_VALIDATION_FAILED
    return KnowledgeAdapterError(
        code,
        "Knowledge Vault validation failed.",
        details={"validation_error_count": result.error_count},
    )


def _runtime_error(error: BaseException) -> KnowledgeAdapterError:
    message = str(error).casefold()
    if "reparse" in message or "symlink" in message or "junction" in message:
        code = KnowledgeErrorCode.KNOWLEDGE_REPARSE_POINT
        safe_message = "Knowledge Vault contains an unsafe reparse boundary."
    elif "outside" in message or "escape" in message:
        code = KnowledgeErrorCode.KNOWLEDGE_PATH_ESCAPE
        safe_message = "Knowledge Vault path boundary is unsafe."
    elif "does not exist" in message or "not a directory" in message:
        code = KnowledgeErrorCode.KNOWLEDGE_VAULT_NOT_FOUND
        safe_message = "Configured Knowledge Vault was not found."
    else:
        code = KnowledgeErrorCode.KNOWLEDGE_INTERNAL_ERROR
        safe_message = "Knowledge Vault could not be read safely."
    return KnowledgeAdapterError(code, safe_message)


class KnowledgeAdapter:
    """Validated, read-only knowledge retrieval with process-memory state only."""

    def __init__(
        self,
        config: KnowledgeConfig | None,
        *,
        diagnostic_logger: DiagnosticLogger | None = None,
    ) -> None:
        self._config = config
        self._logger = diagnostic_logger
        self._index: _KnowledgeIndex | None = None
        self._last_validation: dict[str, Any] | None = None
        self._state = AdapterState.NOT_CONFIGURED if config is None else AdapterState.NOT_CONFIGURED
        self._last_error_code: str | None = None
        self._lock = threading.RLock()

    def _log(self, event: str, **fields: Any) -> None:
        if self._logger is not None:
            bounded = {key: value for key, value in fields.items() if key != "query"}
            self._logger(event, MappingProxyType(bounded))

    def _require_config(self) -> KnowledgeConfig:
        if self._config is None:
            raise KnowledgeAdapterError(
                KnowledgeErrorCode.KNOWLEDGE_NOT_CONFIGURED,
                "KnowledgeAdapter is not configured.",
            )
        return self._config

    def _require_index(self) -> _KnowledgeIndex:
        if self._index is None:
            raise KnowledgeAdapterError(
                KnowledgeErrorCode.KNOWLEDGE_NOT_CONFIGURED,
                "Knowledge index is not initialized.",
            )
        return self._index

    def status(self) -> dict[str, Any]:
        with self._lock:
            index = self._index
            observed = self._last_validation or {}
            return {
                "state": self._state.value,
                "vault_revision": index.vault_revision if index else observed.get("vault_revision"),
                "note_count": len(index.notes) if index else observed.get("note_count", 0),
                "indexed_note_count": len(index.notes) if index else 0,
                "canonical_scope_count": (
                    index.canonical_scope_count
                    if index
                    else observed.get("canonical_scope_count", 0)
                ),
                "validation_status": (
                    index.validation_status if index else observed.get("status")
                ),
                "validation_error_count": (
                    index.validation_error_count
                    if index
                    else observed.get("error_count", 0)
                ),
                "validation_warning_count": (
                    index.validation_warning_count
                    if index
                    else observed.get("warning_count", 0)
                ),
                "read_only": True,
                "last_refresh_revision": index.vault_revision if index else None,
                "observed_vault_revision": observed.get("vault_revision"),
                "last_validation_status": observed.get("status"),
                "last_validation_error_count": observed.get("error_count", 0),
                "last_validation_warning_count": observed.get("warning_count", 0),
                "last_error_code": self._last_error_code,
            }

    def initialize(self) -> dict[str, Any]:
        return self.refresh()

    def refresh(self) -> dict[str, Any]:
        config = self._require_config()
        with self._lock:
            previous = self._index
            previous_state = self._state
            previous_revision = previous.vault_revision if previous else None
            self._state = AdapterState.SCANNING
            self._last_error_code = None
            started = time.monotonic()
            self._log("scan_started")
            try:
                candidate = self._build_index(config)
            except KnowledgeAdapterError as exc:
                self._last_error_code = exc.code.value
                if previous is not None:
                    self._index = previous
                    self._state = previous_state
                    self._log("scan_failed", error_code=exc.code.value)
                    raise KnowledgeAdapterError(
                        KnowledgeErrorCode.KNOWLEDGE_REFRESH_FAILED,
                        "Knowledge refresh failed; the previous validated index remains active.",
                        details={
                            "cause_code": exc.code.value,
                            "previous_revision": previous_revision,
                        },
                    ) from exc
                self._state = AdapterState.ERROR
                self._log("scan_failed", error_code=exc.code.value)
                raise
            except Exception as exc:
                mapped = _runtime_error(exc)
                self._last_error_code = mapped.code.value
                if previous is not None:
                    self._index = previous
                    self._state = previous_state
                    self._log("scan_failed", error_code=mapped.code.value)
                    raise KnowledgeAdapterError(
                        KnowledgeErrorCode.KNOWLEDGE_REFRESH_FAILED,
                        "Knowledge refresh failed; the previous validated index remains active.",
                        details={
                            "cause_code": mapped.code.value,
                            "previous_revision": previous_revision,
                        },
                    ) from exc
                self._state = AdapterState.ERROR
                self._log("scan_failed", error_code=mapped.code.value)
                raise mapped from exc
            self._index = candidate
            self._state = (
                AdapterState.DEGRADED
                if candidate.validation_warning_count
                else AdapterState.READY
            )
            duration_ms = int((time.monotonic() - started) * 1000)
            self._log(
                "scan_completed",
                note_count=len(candidate.notes),
                duration_ms=duration_ms,
                vault_revision=candidate.vault_revision,
            )
            return {
                "state": self._state.value,
                "previous_revision": previous_revision,
                "current_revision": candidate.vault_revision,
                "note_count": len(candidate.notes),
                "changed": previous_revision != candidate.vault_revision,
                "validation_warning_count": candidate.validation_warning_count,
            }

    def _build_index(self, config: KnowledgeConfig) -> _KnowledgeIndex:
        try:
            validation = vault_validator.validate_vault(
                config.vault_root,
                config.project_root,
                max_notes=config.max_notes,
                max_note_bytes=config.max_note_bytes,
                max_total_scan_bytes=config.max_total_scan_bytes,
            )
        except vault_validator.ValidatorRuntimeError as exc:
            raise _runtime_error(exc) from exc
        self._last_validation = {
            "status": validation.status,
            "vault_revision": validation.vault_revision,
            "note_count": validation.markdown_note_count,
            "canonical_scope_count": validation.canonical_scope_count,
            "error_count": validation.error_count,
            "warning_count": validation.warning_count,
        }
        if validation.status == "FAIL" or validation.error_count:
            raise _safe_error_from_validation(validation)
        try:
            vault_root = vault_validator._safe_root(config.vault_root, "Vault root")
            discovered, _obsidian_count, discovery_issues, _unexpected, _forbidden = (
                vault_validator._discover_files(vault_root)
            )
        except vault_validator.ValidatorRuntimeError as exc:
            raise _runtime_error(exc) from exc
        if any(issue.severity == "error" for issue in discovery_issues):
            raise KnowledgeAdapterError(
                KnowledgeErrorCode.KNOWLEDGE_PATH_ESCAPE,
                "Knowledge Vault discovery crossed an unsafe boundary.",
            )
        if len(discovered) != validation.markdown_note_count:
            raise KnowledgeAdapterError(
                KnowledgeErrorCode.KNOWLEDGE_INTERNAL_ERROR,
                "Knowledge Vault changed during index construction.",
            )
        notes: list[KnowledgeNote] = []
        for path, info in discovered:
            notes.append(self._read_note(path, info, vault_root, config))
        notes.sort(key=lambda note: (_nfc(note.note_id), _nfc(note.relative_path)))
        by_id = {note.note_id: note for note in notes}
        if len(by_id) != len(notes):
            raise KnowledgeAdapterError(
                KnowledgeErrorCode.KNOWLEDGE_DUPLICATE_ID,
                "Knowledge Vault contains duplicate stable IDs.",
            )
        return _KnowledgeIndex(
            notes=tuple(notes),
            by_id=MappingProxyType(by_id),
            vault_revision=validation.vault_revision,
            canonical_scope_count=validation.canonical_scope_count,
            validation_status=validation.status,
            validation_error_count=validation.error_count,
            validation_warning_count=validation.warning_count,
        )

    def _read_note(
        self,
        path: Path,
        info: os.stat_result,
        vault_root: Path,
        config: KnowledgeConfig,
    ) -> KnowledgeNote:
        relative = path.relative_to(vault_root).as_posix()
        if path.suffix.casefold() != ".md" or not stat.S_ISREG(info.st_mode):
            raise KnowledgeAdapterError(
                KnowledgeErrorCode.KNOWLEDGE_PATH_ESCAPE,
                "Knowledge index encountered an invalid note entry.",
            )
        if info.st_size > config.max_note_bytes:
            raise KnowledgeAdapterError(
                KnowledgeErrorCode.KNOWLEDGE_NOTE_TOO_LARGE,
                "Knowledge note exceeds the configured size limit.",
            )
        resolved = path.resolve(strict=True)
        if not vault_validator._is_path_within(resolved, vault_root):
            raise KnowledgeAdapterError(
                KnowledgeErrorCode.KNOWLEDGE_PATH_ESCAPE,
                "Knowledge note resolves outside the configured Vault.",
            )
        if vault_validator.is_reparse_point(path):
            raise KnowledgeAdapterError(
                KnowledgeErrorCode.KNOWLEDGE_REPARSE_POINT,
                "Knowledge note crosses an unsafe reparse boundary.",
            )
        raw = path.read_bytes()
        if len(raw) != info.st_size:
            raise KnowledgeAdapterError(
                KnowledgeErrorCode.KNOWLEDGE_INTERNAL_ERROR,
                "Knowledge note changed during index construction.",
            )
        try:
            text = raw.decode("utf-8")
            metadata, body_lines = vault_validator.parse_frontmatter(text)
        except (UnicodeDecodeError, vault_validator.FrontmatterError) as exc:
            raise KnowledgeAdapterError(
                KnowledgeErrorCode.KNOWLEDGE_FRONTMATTER_INVALID,
                "Knowledge note frontmatter is invalid.",
            ) from exc
        text_lines = tuple(text.splitlines())
        headings = self._headings(body_lines, len(text_lines))
        configured_title = metadata.get("title")
        title = configured_title if isinstance(configured_title, str) and configured_title else ""
        if not title:
            title = next((heading.title for heading in headings if heading.level == 1), path.stem)
        body_start_line = body_lines[0][0] if body_lines else len(text_lines) + 1
        body_text = "\n".join(line for _line_number, line in body_lines)
        return KnowledgeNote(
            note_id=str(metadata["id"]),
            title=title,
            relative_path=relative,
            type=str(metadata["type"]),
            status=str(metadata["status"]),
            knowledge_layer=str(metadata["knowledge_layer"]),
            evidence_class=str(metadata["evidence_class"]),
            authority=str(metadata["authority"]),
            canonical=metadata.get("canonical", False) is True,
            canonical_scope=(
                str(metadata["canonical_scope"])
                if isinstance(metadata.get("canonical_scope"), str)
                else None
            ),
            aliases=_list_of_strings(metadata, "aliases"),
            releases=_list_of_strings(metadata, "releases"),
            source_paths=_list_of_strings(metadata, "source_paths"),
            evidence_refs=_list_of_strings(metadata, "evidence_refs"),
            supersedes=_list_of_strings(metadata, "supersedes"),
            superseded_by=_list_of_strings(metadata, "superseded_by"),
            updated=str(metadata["updated"]),
            last_reviewed=str(metadata["last_reviewed"]),
            verified_at=(
                str(metadata["verified_at"])
                if isinstance(metadata.get("verified_at"), str)
                else None
            ),
            headings=headings,
            body_text=body_text,
            text_lines=text_lines,
            body_start_line=body_start_line,
            note_sha256=hashlib.sha256(raw).hexdigest(),
            file_size=len(raw),
        )

    @staticmethod
    def _headings(
        body_lines: list[tuple[int, str]],
        total_lines: int,
    ) -> tuple[NoteHeading, ...]:
        raw_headings: list[tuple[str, int, int]] = []
        for line_number, line in vault_validator._outside_fences(body_lines):
            match = HEADING_RE.match(line)
            if match:
                title = re.sub(r"[ \t]+#+[ \t]*$", "", match.group(2)).strip()
                raw_headings.append((title, len(match.group(1)), line_number))
        headings = []
        for index, (title, level, line_start) in enumerate(raw_headings):
            line_end = raw_headings[index + 1][2] - 1 if index + 1 < len(raw_headings) else total_lines
            headings.append(NoteHeading(title, level, line_start, max(line_start, line_end)))
        return tuple(headings)

    @staticmethod
    def resolve_intent(query: str, intent: QueryIntent | str) -> QueryIntent:
        try:
            requested = intent if isinstance(intent, QueryIntent) else QueryIntent(str(intent).upper())
        except ValueError as exc:
            raise KnowledgeAdapterError(
                KnowledgeErrorCode.KNOWLEDGE_INTERNAL_ERROR,
                "Unknown knowledge query intent.",
            ) from exc
        if requested is not QueryIntent.AUTO:
            return requested
        normalized = _normalize(query)
        hints: tuple[tuple[QueryIntent, tuple[str, ...]], ...] = (
            (QueryIntent.CURRENT_STATE, ("current", "сейчас", "текущ", "работает")),
            (QueryIntent.ARCHITECTURE, ("architecture", "архитектур", "почему устроено")),
            (QueryIntent.SECURITY, ("security", "безопасност")),
            (QueryIntent.HISTORY, ("history", "истори", "релиз", "раньше")),
            (QueryIntent.FOUNDER_INTENT, ("vision", "цель", "видение", "founder intent")),
            (QueryIntent.ROADMAP, ("roadmap", "план", "дальше", "будет")),
            (QueryIntent.RESEARCH, ("research", "исследован")),
            (QueryIntent.INCIDENT, ("incident", "ошибк", "инцидент", "сломалось")),
            (QueryIntent.OPERATIONAL, ("runbook", "инструкц", "диагностик", "запуск")),
        )
        matches = [resolved for resolved, words in hints if any(word in normalized for word in words)]
        return matches[0] if len(matches) == 1 else QueryIntent.AUTO

    def _validated_query(self, query: Any) -> tuple[str, str, tuple[str, ...]]:
        if not isinstance(query, str) or not _normalize(query):
            raise KnowledgeAdapterError(
                KnowledgeErrorCode.KNOWLEDGE_QUERY_EMPTY,
                "Knowledge query must be a non-empty string.",
            )
        if len(query) > MAX_QUERY_CHARS:
            raise KnowledgeAdapterError(
                KnowledgeErrorCode.KNOWLEDGE_QUERY_TOO_LARGE,
                "Knowledge query exceeds the hard character limit.",
            )
        normalized = _normalize(query)
        return query, normalized, _tokens(normalized)

    def _result_limit(self, value: Any) -> int:
        config = self._require_config()
        limit = config.default_max_results if value is None else value
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= config.hard_max_results:
            raise KnowledgeAdapterError(
                KnowledgeErrorCode.KNOWLEDGE_RESULT_LIMIT,
                "max_results is outside the configured bounds.",
            )
        return limit

    @staticmethod
    def _lexical_score(note: KnowledgeNote, normalized: str, query_tokens: tuple[str, ...]) -> int:
        score = 0
        if normalized == _normalize(note.note_id):
            score += 100_000
        if normalized == _normalize(note.title):
            score += 80_000
        if any(normalized == _normalize(alias) for alias in note.aliases):
            score += 70_000
        title_tokens = set(_tokens(note.title))
        heading_tokens = set(_tokens(" ".join(heading.title for heading in note.headings)))
        body_tokens = set(_tokens(note.body_text))
        query_set = set(query_tokens)
        score += len(query_set & title_tokens) * 1_000
        score += len(query_set & heading_tokens) * 500
        score += len(query_set & body_tokens) * 20
        return score

    @staticmethod
    def _intent_boost(note: KnowledgeNote, intent: QueryIntent) -> int:
        boost = 0
        if intent is QueryIntent.CURRENT_STATE:
            boost += 8_000 if note.note_id == "canonical.current-state" else 0
            boost += 6_000 if note.note_id == "canonical.version-matrix" else 0
            boost += 2_500 if note.knowledge_layer == "current_source_truth" else 0
            boost += 700 if note.evidence_class == "A" else 0
            boost += 500 if note.status == "current" else 0
            boost -= 1_500 if note.knowledge_layer in {"research", "roadmap", "session_snapshot"} else 0
            boost -= 1_000 if note.type == "release" or note.status == "historical" else 0
        elif intent is QueryIntent.FOUNDER_INTENT:
            boost += 8_000 if note.note_id == "vision.product" else 0
            boost += 3_000 if note.knowledge_layer == "founder_intent" else 0
            boost += 700 if note.authority == "founder" else 0
        elif intent is QueryIntent.ROADMAP:
            boost += 8_000 if note.note_id == "roadmap.localcomet" else 0
            boost += 3_000 if note.knowledge_layer == "roadmap" else 0
            boost += 600 if note.knowledge_layer == "founder_intent" else 0
        elif intent is QueryIntent.HISTORY:
            boost += 3_000 if note.type in {"release", "incident"} else 0
            boost += 2_000 if note.knowledge_layer == "verified_history" else 0
            boost += 800 if note.knowledge_layer == "forensic_evidence" else 0
        elif intent is QueryIntent.SECURITY:
            boost += 8_000 if note.canonical_scope == "security" else 0
            boost += 3_000 if note.type == "security" else 0
            boost += 1_500 if note.type == "adr" and "security" in _normalize(note.body_text) else 0
            boost += 800 if note.knowledge_layer == "current_source_truth" else 0
        elif intent is QueryIntent.ARCHITECTURE:
            boost += 8_000 if note.note_id == "canonical.system-architecture" else 0
            boost += 3_000 if note.type == "architecture" else 0
            boost += 2_000 if note.type == "adr" else 0
            boost += 800 if note.knowledge_layer == "current_source_truth" else 0
        elif intent is QueryIntent.OPERATIONAL:
            boost += 4_000 if note.type == "runbook" else 0
            boost += 2_000 if note.knowledge_layer == "operational" else 0
        elif intent is QueryIntent.INCIDENT:
            boost += 8_000 if note.note_id == "incident.index" else 0
            boost += 3_500 if note.type == "incident" else 0
            boost += 1_500 if note.knowledge_layer == "verified_history" else 0
        elif intent is QueryIntent.RESEARCH:
            boost += 4_000 if note.type == "research" else 0
            boost += 2_500 if note.knowledge_layer == "research" else 0
        return boost

    def search(
        self,
        query: str,
        intent: QueryIntent | str = QueryIntent.AUTO,
        max_results: int | None = None,
        include_superseded: bool = False,
    ) -> dict[str, Any]:
        with self._lock:
            index = self._require_index()
            original, normalized, query_tokens = self._validated_query(query)
            resolved = self.resolve_intent(original, intent)
            limit = self._result_limit(max_results)
            if not isinstance(include_superseded, bool):
                raise KnowledgeAdapterError(
                    KnowledgeErrorCode.KNOWLEDGE_INTERNAL_ERROR,
                    "include_superseded must be boolean.",
                )
            ranked: list[tuple[int, KnowledgeNote]] = []
            for note in index.notes:
                if note.status == "superseded" and not include_superseded:
                    continue
                if resolved is QueryIntent.CURRENT_STATE and note.evidence_class in {"D", "E", "G"}:
                    continue
                lexical = self._lexical_score(note, normalized, query_tokens)
                if lexical <= 0:
                    continue
                ranked.append((lexical + self._intent_boost(note, resolved), note))
            ranked.sort(key=lambda item: (-item[0], _nfc(item[1].note_id), _nfc(item[1].relative_path)))
            results = [
                self._search_result(note, score, query_tokens)
                for score, note in ranked[:limit]
            ]
            self._log("search_completed", resolved_intent=resolved.value, result_count=len(results))
            return {
                "query": original,
                "resolved_intent": resolved.value,
                "vault_revision": index.vault_revision,
                "result_count": len(results),
                "results": results,
            }

    def _search_result(
        self,
        note: KnowledgeNote,
        score: int,
        query_tokens: tuple[str, ...],
    ) -> dict[str, Any]:
        result = {
            "note_id": note.note_id,
            "title": note.title,
            "relative_path": note.relative_path,
            "type": note.type,
            "status": note.status,
            "knowledge_layer": note.knowledge_layer,
            "evidence_class": note.evidence_class,
            "authority": note.authority,
            "canonical": note.canonical,
            "score": score,
            "matched_sections": [
                section.to_dict() for section in self._matched_sections(note, query_tokens)
            ],
            "note_sha256": note.note_sha256,
        }
        if note.canonical_scope is not None:
            result["canonical_scope"] = note.canonical_scope
        return result

    @staticmethod
    def _heading_for_line(note: KnowledgeNote, line_number: int) -> NoteHeading | None:
        containing = [
            heading
            for heading in note.headings
            if heading.line_start <= line_number <= heading.line_end
        ]
        return containing[-1] if containing else None

    def _matched_sections(
        self,
        note: KnowledgeNote,
        query_tokens: tuple[str, ...],
    ) -> tuple[MatchedSection, ...]:
        matches: list[int] = []
        query_set = set(query_tokens)
        for line_number in range(note.body_start_line, len(note.text_lines) + 1):
            line_tokens = set(_tokens(note.text_lines[line_number - 1]))
            if query_set & line_tokens:
                matches.append(line_number)
        if not matches and note.headings:
            matches.append(note.headings[0].line_start)
        sections: list[MatchedSection] = []
        used_ranges: set[tuple[int, int]] = set()
        for line_number in matches:
            heading = self._heading_for_line(note, line_number)
            section_start = heading.line_start if heading else max(note.body_start_line, line_number - 1)
            section_end = min(
                heading.line_end if heading else len(note.text_lines),
                line_number + 2,
            )
            section_start = max(section_start, line_number - 2, note.body_start_line)
            key = (section_start, section_end)
            if key in used_ranges:
                continue
            used_ranges.add(key)
            excerpt = "\n".join(note.text_lines[section_start - 1 : section_end])
            if len(excerpt) > MAX_EXCERPT_CHARS:
                excerpt = excerpt[: MAX_EXCERPT_CHARS - 1] + "…"
            sections.append(
                MatchedSection(
                    heading=heading.title if heading else "",
                    line_start=section_start,
                    line_end=section_end,
                    excerpt=excerpt,
                )
            )
            if len(sections) >= MAX_MATCHED_SECTIONS:
                break
        return tuple(sections)

    def note_get(self, note_id: str, max_chars: int | None = None) -> dict[str, Any]:
        with self._lock:
            index = self._require_index()
            if not isinstance(note_id, str) or not vault_validator.ID_RE.fullmatch(note_id):
                raise KnowledgeAdapterError(
                    KnowledgeErrorCode.KNOWLEDGE_NOTE_NOT_FOUND,
                    "Knowledge note was not found by stable ID.",
                )
            note = index.by_id.get(note_id)
            if note is None:
                raise KnowledgeAdapterError(
                    KnowledgeErrorCode.KNOWLEDGE_NOTE_NOT_FOUND,
                    "Knowledge note was not found by stable ID.",
                )
            limit = self._context_limit(max_chars)
            truncated = len(note.body_text) > limit
            return {
                "note_id": note.note_id,
                "title": note.title,
                "relative_path": note.relative_path,
                "metadata": note.metadata_dict(),
                "content": note.body_text[:limit],
                "truncated": truncated,
                "note_sha256": note.note_sha256,
                "vault_revision": index.vault_revision,
            }

    def _context_limit(self, value: Any) -> int:
        config = self._require_config()
        limit = config.default_context_chars if value is None else value
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= config.hard_max_context_chars:
            raise KnowledgeAdapterError(
                KnowledgeErrorCode.KNOWLEDGE_CONTEXT_LIMIT,
                "Context character limit is outside the configured bounds.",
            )
        return limit

    def context_preview(
        self,
        query: str,
        intent: QueryIntent | str = QueryIntent.AUTO,
        max_context_chars: int | None = None,
        max_results: int | None = None,
        include_superseded: bool = False,
    ) -> dict[str, Any]:
        with self._lock:
            index = self._require_index()
            limit = self._context_limit(max_context_chars)
            search_response = self.search(
                query,
                intent,
                max_results=max_results,
                include_superseded=include_superseded,
            )
            sources: list[dict[str, Any]] = []
            total_chars = 0
            truncated = False
            bundle_parts: list[bytes] = [
                index.vault_revision.encode("utf-8"),
                _normalize(query).encode("utf-8"),
                search_response["resolved_intent"].encode("ascii"),
            ]
            for result in search_response["results"]:
                note = index.by_id[result["note_id"]]
                selected_sections: list[dict[str, Any]] = []
                for section in result["matched_sections"]:
                    content = section["excerpt"]
                    remaining = limit - total_chars
                    if remaining <= 0:
                        truncated = True
                        break
                    if len(content) > remaining:
                        content = content[:remaining]
                        truncated = True
                    selected = {
                        "heading": section["heading"],
                        "line_start": section["line_start"],
                        "line_end": section["line_end"],
                        "content": content,
                    }
                    selected_sections.append(selected)
                    total_chars += len(content)
                    bundle_parts.extend(
                        (
                            note.note_id.encode("utf-8"),
                            f"{selected['line_start']}:{selected['line_end']}".encode("ascii"),
                            hashlib.sha256(content.encode("utf-8")).hexdigest().encode("ascii"),
                        )
                    )
                    if len(content) < len(section["excerpt"]):
                        break
                if selected_sections:
                    sources.append(
                        {
                            "note_id": note.note_id,
                            "title": note.title,
                            "relative_path": note.relative_path,
                            "knowledge_layer": note.knowledge_layer,
                            "evidence_class": note.evidence_class,
                            "authority": note.authority,
                            "status": note.status,
                            "canonical": note.canonical,
                            "selected_sections": selected_sections,
                            "note_sha256": note.note_sha256,
                        }
                    )
                if total_chars >= limit:
                    if any(
                        candidate["note_id"] != result["note_id"]
                        for candidate in search_response["results"]
                        if candidate not in search_response["results"][: len(sources)]
                    ):
                        truncated = True
                    break
            digest = hashlib.sha256()
            for part in bundle_parts:
                digest.update(part)
                digest.update(b"\0")
            warnings = []
            if index.validation_warning_count:
                warnings.append(f"VALIDATION_WARNINGS:{index.validation_warning_count}")
            if truncated:
                warnings.append("CONTEXT_TRUNCATED")
            response = {
                "bundle_id": "kb:" + digest.hexdigest(),
                "vault_revision": index.vault_revision,
                "query": query,
                "resolved_intent": search_response["resolved_intent"],
                "total_chars": total_chars,
                "truncated": truncated,
                "sources": sources,
                "context_relations": self._relations(sources, index),
                "warnings": warnings,
            }
            self._log(
                "context_preview_completed",
                resolved_intent=search_response["resolved_intent"],
                result_count=len(sources),
                context_character_count=total_chars,
            )
            return response

    @staticmethod
    def _relations(sources: list[dict[str, Any]], index: _KnowledgeIndex) -> list[dict[str, Any]]:
        relations: list[dict[str, Any]] = []
        current = [source["note_id"] for source in sources if source["knowledge_layer"] == "current_source_truth"]
        historical = [
            source["note_id"]
            for source in sources
            if source["knowledge_layer"] in {"verified_history", "forensic_evidence", "session_snapshot"}
        ]
        founders = [source["note_id"] for source in sources if source["knowledge_layer"] == "founder_intent"]
        research = [source["note_id"] for source in sources if source["knowledge_layer"] == "research"]
        if current and historical:
            relations.append({"type": "CURRENT_VS_HISTORICAL", "note_ids": [current[0], historical[0]]})
        if current and founders:
            relations.append({"type": "FOUNDER_INTENT_VS_IMPLEMENTATION", "note_ids": [founders[0], current[0]]})
        if current and research:
            relations.append({"type": "RESEARCH_VS_CURRENT", "note_ids": [research[0], current[0]]})
        for source in sources:
            note = index.by_id[source["note_id"]]
            if note.status == "superseded" and note.superseded_by:
                relations.append({"type": "SUPERSEDED", "note_ids": [note.note_id, note.superseded_by[0]]})
        return relations

    def dispatch(self, operation: str, request: Mapping[str, Any] | None = None) -> dict[str, Any]:
        payload = dict(request or {})
        if operation == "knowledge.status":
            return self.status()
        if operation == "knowledge.refresh":
            return self.refresh()
        if operation == "knowledge.search":
            return self.search(
                payload.get("query"),
                payload.get("intent", QueryIntent.AUTO.value),
                payload.get("max_results"),
                payload.get("include_superseded", False),
            )
        if operation == "knowledge.note.get":
            return self.note_get(payload.get("note_id"), payload.get("max_chars"))
        if operation == "knowledge.context.preview":
            return self.context_preview(
                payload.get("query"),
                payload.get("intent", QueryIntent.AUTO.value),
                payload.get("max_context_chars"),
                payload.get("max_results"),
                payload.get("include_superseded", False),
            )
        raise KnowledgeAdapterError(
            KnowledgeErrorCode.KNOWLEDGE_INTERNAL_ERROR,
            "Unknown knowledge operation.",
        )


__all__ = [
    "KnowledgeAdapter",
    "KnowledgeAdapterError",
    "KnowledgeConfig",
    "KnowledgeErrorCode",
    "QueryIntent",
]
