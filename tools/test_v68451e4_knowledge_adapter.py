"""Focused standard-library tests for the read-only KnowledgeAdapter prototype."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import hashlib
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest import mock


sys.dont_write_bytecode = True
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, os.fspath(PROJECT_ROOT))

from modules import knowledge_adapter_ru as adapter_module  # noqa: E402
from modules.knowledge_adapter_ru import KnowledgeAdapter  # noqa: E402
from modules.knowledge_contract_ru import (  # noqa: E402
    AdapterState,
    HARD_MAX_CONTEXT_CHARS,
    HARD_MAX_RESULTS,
    KnowledgeAdapterError,
    KnowledgeConfig,
    KnowledgeErrorCode,
    MAX_EXCERPT_CHARS,
    MAX_QUERY_CHARS,
    QueryIntent,
)
from tools import validate_localcomet_vault as vault_validator  # noqa: E402


MISSING = object()


class KnowledgeAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.vault = self.root / "Vault"
        self.project = self.root / "Project"
        self.vault.mkdir()
        self.project.mkdir()
        self.core_paths = self._write_core_vault()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def note_text(
        self,
        note_id: str,
        *,
        title: str,
        body: str,
        **overrides: object,
    ) -> str:
        metadata: dict[str, object] = {
            "id": note_id,
            "title": title,
            "type": "meta",
            "status": "active",
            "knowledge_layer": "operational",
            "evidence_class": "A",
            "authority": "architecture_decision",
            "updated": "2026-07-15",
            "last_reviewed": "2026-07-15",
            "canonical": False,
            "releases": [],
            "source_paths": [],
            "evidence_refs": [],
            "supersedes": [],
            "superseded_by": [],
            "aliases": [],
        }
        for key, value in overrides.items():
            if value is MISSING:
                metadata.pop(key, None)
            else:
                metadata[key] = value
        lines = ["---"]
        for key, value in metadata.items():
            if isinstance(value, list):
                if value:
                    lines.append(f"{key}:")
                    lines.extend(f"  - {json.dumps(item, ensure_ascii=False)}" for item in value)
                else:
                    lines.append(f"{key}: []")
            elif isinstance(value, bool):
                lines.append(f"{key}: {'true' if value else 'false'}")
            elif value is None:
                lines.append(f"{key}: null")
            else:
                lines.append(f"{key}: {value}")
        lines.extend(("---", body))
        return "\n".join(lines) + "\n"

    def write_note(
        self,
        filename: str,
        note_id: str,
        *,
        title: str,
        body: str,
        **overrides: object,
    ) -> Path:
        path = self.vault / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            self.note_text(note_id, title=title, body=body, **overrides),
            encoding="utf-8",
        )
        return path

    def _write_core_vault(self) -> dict[str, Path]:
        specs = [
            ("current-state", "canonical.current-state", "Current State", "canonical", "current", "current_source_truth", "A", "source"),
            ("version-matrix", "canonical.version-matrix", "Version Matrix", "canonical", "current", "current_source_truth", "A", "source"),
            ("product-vision", "vision.product", "Product Vision", "canonical", "active", "founder_intent", "C", "founder"),
            ("system-architecture", "canonical.system-architecture", "System Architecture", "canonical", "current", "current_source_truth", "A", "source"),
            ("source-map", "canonical.source-map", "Source Map", "canonical", "current", "operational", "A", "architecture_decision"),
            ("knowledge-schema", "meta.knowledge-schema", "Knowledge Schema", "meta", "current", "operational", "A", "architecture_decision"),
            ("security", "security.model", "Security Model", "security", "current", "current_source_truth", "A", "source"),
            ("roadmap", "roadmap.localcomet", "LocalComet Roadmap", "roadmap", "active", "roadmap", "C", "roadmap"),
            ("evidence", "evidence.index", "Evidence Index", "evidence", "current", "forensic_evidence", "B", "forensic_evidence"),
            ("incidents", "incident.index", "Incident Index", "incident", "current", "verified_history", "B", "forensic_evidence"),
        ]
        paths: dict[str, Path] = {}
        for index, spec in enumerate(specs):
            scope, note_id, title, note_type, status, layer, evidence, authority = spec
            next_scope = specs[(index + 1) % len(specs)][0]
            body = f"# {title}\n{title} LocalComet knowledge for {scope}.\n[[{next_scope}]]"
            paths[note_id] = self.write_note(
                f"{scope}.md",
                note_id,
                title=title,
                body=body,
                type=note_type,
                status=status,
                knowledge_layer=layer,
                evidence_class=evidence,
                authority=authority,
                canonical=True,
                canonical_scope=scope,
                aliases=[f"Alias {scope}"],
            )
        return paths

    def config(self, **overrides: object) -> KnowledgeConfig:
        values: dict[str, object] = {"vault_root": self.vault, "project_root": self.project}
        values.update(overrides)
        return KnowledgeConfig(**values)  # type: ignore[arg-type]

    def adapter(self, **config_overrides: object) -> KnowledgeAdapter:
        adapter = KnowledgeAdapter(self.config(**config_overrides))
        adapter.initialize()
        return adapter

    @staticmethod
    def assert_code(context: unittest.case._AssertRaisesContext, code: KnowledgeErrorCode) -> None:
        error = context.exception
        assert isinstance(error, KnowledgeAdapterError)
        if error.code is not code:
            raise AssertionError(f"expected {code.value}, got {error.code.value}")

    def add_extra(
        self,
        note_id: str,
        token: str,
        *,
        title: str | None = None,
        body: str | None = None,
        **overrides: object,
    ) -> Path:
        name = note_id.replace(".", "-")
        return self.write_note(
            f"extra/{name}.md",
            note_id,
            title=title or name,
            body=body or f"# {title or name}\n{token}\n[[current-state]]",
            **overrides,
        )

    def tree_snapshot(self, root: Path) -> list[tuple[str, int, int, str]]:
        rows = []
        for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
            if path.is_file():
                info = path.stat()
                rows.append(
                    (
                        path.relative_to(root).as_posix(),
                        info.st_size,
                        info.st_mtime_ns,
                        hashlib.sha256(path.read_bytes()).hexdigest(),
                    )
                )
        return rows

    # Core loading, validation gate, lookup, and refresh behavior.
    def test_01_valid_validated_vault_loads(self) -> None:
        adapter = self.adapter()
        self.assertEqual(adapter.status()["state"], AdapterState.READY.value)
        self.assertEqual(adapter.status()["indexed_note_count"], 10)

    def test_02_validation_failure_prevents_initial_build(self) -> None:
        (self.vault / "bad.md").write_text("# bad\n", encoding="utf-8")
        adapter = KnowledgeAdapter(self.config())
        with self.assertRaises(KnowledgeAdapterError) as raised:
            adapter.initialize()
        self.assert_code(raised, KnowledgeErrorCode.KNOWLEDGE_FRONTMATTER_INVALID)
        self.assertEqual(adapter.status()["state"], AdapterState.ERROR.value)

    def test_03_warnings_allow_degraded_usable_state(self) -> None:
        self.add_extra("note.lonely", "lonelytoken", body="# Lonely\nlonelytoken")
        adapter = self.adapter()
        self.assertEqual(adapter.status()["state"], AdapterState.DEGRADED.value)
        self.assertEqual(adapter.search("lonelytoken")["results"][0]["note_id"], "note.lonely")

    def test_04_stable_id_lookup_succeeds(self) -> None:
        result = self.adapter().note_get("canonical.current-state")
        self.assertEqual(result["note_id"], "canonical.current-state")

    def test_05_unknown_note_id_fails(self) -> None:
        with self.assertRaises(KnowledgeAdapterError) as raised:
            self.adapter().note_get("unknown.note")
        self.assert_code(raised, KnowledgeErrorCode.KNOWLEDGE_NOTE_NOT_FOUND)

    def test_06_arbitrary_path_cannot_replace_note_id(self) -> None:
        with self.assertRaises(KnowledgeAdapterError) as raised:
            self.adapter().note_get(r"C:\Windows\system.ini")
        self.assert_code(raised, KnowledgeErrorCode.KNOWLEDGE_NOTE_NOT_FOUND)
        self.assertNotIn("C:\\Windows", str(raised.exception))

    def test_07_note_metadata_is_preserved(self) -> None:
        metadata = self.adapter().note_get("security.model")["metadata"]
        self.assertEqual(metadata["knowledge_layer"], "current_source_truth")
        self.assertEqual(metadata["evidence_class"], "A")
        self.assertEqual(metadata["canonical_scope"], "security")

    def test_08_note_sha256_is_exact(self) -> None:
        expected = hashlib.sha256(self.core_paths["security.model"].read_bytes()).hexdigest()
        self.assertEqual(self.adapter().note_get("security.model")["note_sha256"], expected)

    def test_09_validator_revision_is_preserved(self) -> None:
        expected = vault_validator.validate_vault(self.vault, self.project).vault_revision
        self.assertEqual(self.adapter().status()["vault_revision"], expected)

    def test_10_unchanged_refresh_reports_false(self) -> None:
        adapter = self.adapter()
        self.assertFalse(adapter.refresh()["changed"])

    def test_11_changed_refresh_reports_true(self) -> None:
        adapter = self.adapter()
        self.add_extra("note.changed", "refreshchanged")
        self.assertTrue(adapter.refresh()["changed"])

    def test_12_failed_refresh_preserves_previous_index(self) -> None:
        adapter = self.adapter()
        previous = adapter.status()["vault_revision"]
        self.core_paths["canonical.current-state"].write_text("invalid\n", encoding="utf-8")
        with self.assertRaises(KnowledgeAdapterError) as raised:
            adapter.refresh()
        self.assert_code(raised, KnowledgeErrorCode.KNOWLEDGE_REFRESH_FAILED)
        self.assertEqual(adapter.status()["vault_revision"], previous)
        self.assertEqual(adapter.note_get("canonical.current-state")["note_id"], "canonical.current-state")

    # Lexical matching and deterministic intent ranking.
    def test_13_exact_id_search_ranks_first(self) -> None:
        result = self.adapter().search("canonical.current-state")
        self.assertEqual(result["results"][0]["note_id"], "canonical.current-state")

    def test_14_exact_title_search_ranks_first(self) -> None:
        result = self.adapter().search("System Architecture")
        self.assertEqual(result["results"][0]["note_id"], "canonical.system-architecture")

    def test_15_alias_match_works(self) -> None:
        result = self.adapter().search("Alias security")
        self.assertEqual(result["results"][0]["note_id"], "security.model")

    def test_16_heading_match_works(self) -> None:
        self.add_extra("note.heading", "unused", body="# Extra\n## Quantum Heading\ntext\n[[current-state]]")
        result = self.adapter().search("Quantum Heading")
        self.assertEqual(result["results"][0]["note_id"], "note.heading")

    def test_17_body_lexical_match_works(self) -> None:
        self.add_extra("note.body", "zephyrbodytoken")
        result = self.adapter().search("zephyrbodytoken")
        self.assertEqual(result["results"][0]["note_id"], "note.body")

    def test_18_search_ordering_is_deterministic(self) -> None:
        adapter = self.adapter()
        first = adapter.search("LocalComet", QueryIntent.ARCHITECTURE)
        second = adapter.search("LocalComet", QueryIntent.ARCHITECTURE)
        self.assertEqual(first, second)

    def _two_layer_notes(self, token: str) -> None:
        self.add_extra(
            "note.current",
            token,
            title="Current Candidate",
            knowledge_layer="current_source_truth",
            status="current",
            authority="source",
            evidence_class="A",
        )
        self.add_extra(
            "note.research",
            token,
            title="Research Candidate",
            type="research",
            status="research",
            knowledge_layer="research",
            authority="research",
            evidence_class="C",
        )

    def test_19_current_state_boosts_current_truth(self) -> None:
        self._two_layer_notes("sharedcurrenttoken")
        result = self.adapter().search("sharedcurrenttoken", QueryIntent.CURRENT_STATE)
        self.assertEqual(result["results"][0]["note_id"], "note.current")

    def test_20_history_boosts_release_history(self) -> None:
        self.add_extra("release.v1", "chronicleunique", type="release", status="historical", knowledge_layer="verified_history", authority="test", evidence_class="B", releases=["v1"])
        self.add_extra("note.operational", "chronicleunique")
        result = self.adapter().search("chronicleunique", QueryIntent.HISTORY)
        self.assertEqual(result["results"][0]["note_id"], "release.v1")

    def test_21_founder_intent_boosts_founder_note(self) -> None:
        self.add_extra("note.founder", "foundersignal", knowledge_layer="founder_intent", authority="founder", evidence_class="C")
        self.add_extra("note.other", "foundersignal")
        result = self.adapter().search("foundersignal", QueryIntent.FOUNDER_INTENT)
        self.assertEqual(result["results"][0]["note_id"], "note.founder")

    def test_22_roadmap_boosts_roadmap_note(self) -> None:
        self.add_extra("note.roadmap", "futuresignal", type="roadmap", knowledge_layer="roadmap", authority="roadmap", evidence_class="C")
        self.add_extra("note.other", "futuresignal")
        result = self.adapter().search("futuresignal", QueryIntent.ROADMAP)
        self.assertEqual(result["results"][0]["note_id"], "note.roadmap")

    def test_23_security_boosts_security_note(self) -> None:
        result = self.adapter().search("Security Model", QueryIntent.SECURITY)
        self.assertEqual(result["results"][0]["note_id"], "security.model")

    # Supersession and evidence-class policy.
    def test_24_superseded_excluded_by_default(self) -> None:
        self.add_extra("note.old", "olduniquetoken", status="superseded", knowledge_layer="verified_history", evidence_class="B", superseded_by=["canonical.current-state"])
        result = self.adapter().search("olduniquetoken")
        self.assertEqual(result["result_count"], 0)

    def test_25_superseded_can_be_included(self) -> None:
        self.add_extra("note.old", "olduniquetoken", status="superseded", knowledge_layer="verified_history", evidence_class="B", superseded_by=["canonical.current-state"])
        result = self.adapter().search("olduniquetoken", include_superseded=True)
        self.assertEqual(result["results"][0]["note_id"], "note.old")

    def _assert_low_evidence_excluded(self, evidence_class: str) -> None:
        note_id = f"note.evidence-{evidence_class.casefold()}"
        token = f"evidence{evidence_class.casefold()}token"
        self.add_extra(note_id, token, evidence_class=evidence_class)
        result = self.adapter().search(token, QueryIntent.CURRENT_STATE)
        self.assertNotIn(note_id, [item["note_id"] for item in result["results"]])

    def test_26_evidence_d_excluded_from_current_state(self) -> None:
        self._assert_low_evidence_excluded("D")

    def test_27_evidence_e_excluded_from_current_state(self) -> None:
        self._assert_low_evidence_excluded("E")

    def test_28_evidence_g_excluded_from_current_state(self) -> None:
        self._assert_low_evidence_excluded("G")

    def test_29_evidence_c_usable_for_founder_intent(self) -> None:
        self.add_extra("note.c-founder", "cevidencefounder", knowledge_layer="founder_intent", authority="founder", evidence_class="C")
        result = self.adapter().search("cevidencefounder", QueryIntent.FOUNDER_INTENT)
        self.assertEqual(result["results"][0]["note_id"], "note.c-founder")

    # Request bounds and excerpt construction.
    def test_30_empty_query_rejected(self) -> None:
        with self.assertRaises(KnowledgeAdapterError) as raised:
            self.adapter().search("  ")
        self.assert_code(raised, KnowledgeErrorCode.KNOWLEDGE_QUERY_EMPTY)

    def test_31_query_above_limit_rejected(self) -> None:
        with self.assertRaises(KnowledgeAdapterError) as raised:
            self.adapter().search("x" * (MAX_QUERY_CHARS + 1))
        self.assert_code(raised, KnowledgeErrorCode.KNOWLEDGE_QUERY_TOO_LARGE)

    def test_32_max_results_hard_limit_enforced(self) -> None:
        with self.assertRaises(KnowledgeAdapterError) as raised:
            self.adapter().search("LocalComet", max_results=HARD_MAX_RESULTS + 1)
        self.assert_code(raised, KnowledgeErrorCode.KNOWLEDGE_RESULT_LIMIT)

    def test_33_matched_excerpts_are_bounded(self) -> None:
        self.add_extra("note.largeexcerpt", "longtoken", body="# Long\nlongtoken " + ("x" * 5000) + "\n[[current-state]]")
        section = self.adapter().search("longtoken")["results"][0]["matched_sections"][0]
        self.assertLessEqual(len(section["excerpt"]), MAX_EXCERPT_CHARS)

    def test_34_matched_line_numbers_are_exact(self) -> None:
        path = self.add_extra("note.lines", "unused", body="# Lines\nalpha\n## Target\nlineexacttoken\nomega\n[[current-state]]")
        section = self.adapter().search("lineexacttoken")["results"][0]["matched_sections"][0]
        source_lines = path.read_text(encoding="utf-8").splitlines()
        selected = "\n".join(source_lines[section["line_start"] - 1 : section["line_end"]])
        self.assertEqual(section["excerpt"], selected)

    def test_35_note_get_content_is_bounded(self) -> None:
        result = self.adapter().note_get("canonical.current-state", max_chars=20)
        self.assertLessEqual(len(result["content"]), 20)
        self.assertTrue(result["truncated"])

    def test_36_context_preview_respects_limit(self) -> None:
        result = self.adapter().context_preview("LocalComet", max_context_chars=40)
        self.assertLessEqual(result["total_chars"], 40)

    def test_37_context_preview_sets_truncated(self) -> None:
        result = self.adapter().context_preview("LocalComet", max_context_chars=10)
        self.assertTrue(result["truncated"])
        self.assertIn("CONTEXT_TRUNCATED", result["warnings"])

    def test_38_context_source_provenance_is_complete(self) -> None:
        result = self.adapter().context_preview("System Architecture", QueryIntent.ARCHITECTURE)
        required = {"note_id", "title", "relative_path", "knowledge_layer", "evidence_class", "authority", "status", "canonical", "selected_sections", "note_sha256"}
        self.assertTrue(result["sources"])
        self.assertTrue(all(required <= set(source) for source in result["sources"]))

    def test_39_bundle_id_is_deterministic(self) -> None:
        adapter = self.adapter()
        first = adapter.context_preview("LocalComet", QueryIntent.ARCHITECTURE)
        second = adapter.context_preview("LocalComet", QueryIntent.ARCHITECTURE)
        self.assertEqual(first["bundle_id"], second["bundle_id"])

    def test_40_bundle_id_changes_with_selected_content(self) -> None:
        path = self.add_extra("note.bundle", "bundlecontenttoken", body="# Bundle\nbundlecontenttoken first\n[[current-state]]")
        adapter = self.adapter()
        first = adapter.context_preview("bundlecontenttoken")["bundle_id"]
        text = path.read_text(encoding="utf-8").replace("bundlecontenttoken first", "bundlecontenttoken second")
        path.write_text(text, encoding="utf-8")
        adapter.refresh()
        second = adapter.context_preview("bundlecontenttoken")["bundle_id"]
        self.assertNotEqual(first, second)

    # Negative capability, read-only, and filesystem-boundary guarantees.
    def test_41_no_model_call_surface_exists(self) -> None:
        source = (PROJECT_ROOT / "modules" / "knowledge_adapter_ru.py").read_text(encoding="utf-8")
        self.assertNotIn("local_model_gateway", source)
        self.assertNotIn("model_client", source)

    def test_42_no_network_occurs(self) -> None:
        with mock.patch.object(socket, "socket", side_effect=AssertionError("network attempted")):
            adapter = self.adapter()
            adapter.search("LocalComet")

    def test_43_no_filesystem_writes_occur(self) -> None:
        before_vault = self.tree_snapshot(self.vault)
        before_project = self.tree_snapshot(self.project)
        adapter = self.adapter()
        adapter.search("LocalComet")
        adapter.context_preview("LocalComet")
        self.assertEqual(before_vault, self.tree_snapshot(self.vault))
        self.assertEqual(before_project, self.tree_snapshot(self.project))

    def test_44_no_persistent_index_files_created(self) -> None:
        before = {path.relative_to(self.root).as_posix() for path in self.root.rglob("*")}
        self.adapter().search("LocalComet")
        after = {path.relative_to(self.root).as_posix() for path in self.root.rglob("*")}
        self.assertEqual(before, after)

    def test_45_no_vault_mutation_occurs(self) -> None:
        before = self.tree_snapshot(self.vault)
        self.adapter().refresh()
        self.assertEqual(before, self.tree_snapshot(self.vault))

    def test_46_reparse_boundary_is_mapped(self) -> None:
        adapter = KnowledgeAdapter(self.config())
        with mock.patch.object(
            adapter_module.vault_validator,
            "validate_vault",
            side_effect=vault_validator.ValidatorRuntimeError("reparse point"),
        ):
            with self.assertRaises(KnowledgeAdapterError) as raised:
                adapter.initialize()
        self.assert_code(raised, KnowledgeErrorCode.KNOWLEDGE_REPARSE_POINT)

    def test_47_only_markdown_notes_are_indexed(self) -> None:
        obsidian = self.vault / ".obsidian"
        obsidian.mkdir()
        (obsidian / "app.json").write_text("{}", encoding="utf-8")
        self.assertEqual(self.adapter().status()["indexed_note_count"], 10)

    def test_48_obsidian_json_is_not_knowledge(self) -> None:
        obsidian = self.vault / ".obsidian"
        obsidian.mkdir()
        (obsidian / "workspace.json").write_text('{"id":"fake.note"}', encoding="utf-8")
        adapter = self.adapter()
        with self.assertRaises(KnowledgeAdapterError):
            adapter.note_get("fake.note")

    # Relations, revision propagation, dispatch, and contract properties.
    def test_49_current_vs_historical_is_not_contradiction(self) -> None:
        self.add_extra("note.rel-current", "relationtoken", knowledge_layer="current_source_truth", status="current", authority="source")
        self.add_extra("note.rel-history", "relationtoken", type="release", status="historical", knowledge_layer="verified_history", authority="test", evidence_class="B", releases=["v1"])
        result = self.adapter().context_preview("relationtoken", QueryIntent.HISTORY, max_results=5)
        relation_types = {relation["type"] for relation in result["context_relations"]}
        self.assertIn("CURRENT_VS_HISTORICAL", relation_types)
        self.assertNotIn("CONTRADICTORY", relation_types)

    def test_50_every_retrieval_returns_revision(self) -> None:
        adapter = self.adapter()
        revision = adapter.status()["vault_revision"]
        self.assertEqual(adapter.search("LocalComet")["vault_revision"], revision)
        self.assertEqual(adapter.note_get("canonical.current-state")["vault_revision"], revision)
        self.assertEqual(adapter.context_preview("LocalComet")["vault_revision"], revision)

    def test_51_auto_intent_uses_lexical_heuristic(self) -> None:
        result = self.adapter().search("Каково текущее состояние?", QueryIntent.AUTO)
        self.assertEqual(result["resolved_intent"], QueryIntent.CURRENT_STATE.value)

    def test_52_dispatch_exposes_exact_operations(self) -> None:
        adapter = self.adapter()
        self.assertIn("state", adapter.dispatch("knowledge.status", {}))
        self.assertIn("results", adapter.dispatch("knowledge.search", {"query": "LocalComet"}))
        self.assertEqual(adapter.dispatch("knowledge.note.get", {"note_id": "security.model"})["note_id"], "security.model")
        self.assertIn("bundle_id", adapter.dispatch("knowledge.context.preview", {"query": "LocalComet"}))
        self.assertFalse(adapter.dispatch("knowledge.refresh", {})["changed"])

    def test_53_config_is_immutable(self) -> None:
        config = self.config()
        with self.assertRaises(FrozenInstanceError):
            config.max_notes = 5  # type: ignore[misc]

    def test_54_config_global_limit_is_validated(self) -> None:
        with self.assertRaises(ValueError):
            self.config(hard_max_results=HARD_MAX_RESULTS + 1)

    def test_55_note_get_hard_context_limit_enforced(self) -> None:
        with self.assertRaises(KnowledgeAdapterError) as raised:
            self.adapter().note_get("security.model", HARD_MAX_CONTEXT_CHARS + 1)
        self.assert_code(raised, KnowledgeErrorCode.KNOWLEDGE_CONTEXT_LIMIT)

    def test_56_preview_hard_context_limit_enforced(self) -> None:
        with self.assertRaises(KnowledgeAdapterError) as raised:
            self.adapter().context_preview("LocalComet", max_context_chars=HARD_MAX_CONTEXT_CHARS + 1)
        self.assert_code(raised, KnowledgeErrorCode.KNOWLEDGE_CONTEXT_LIMIT)

    def test_57_refresh_dispatch_does_not_accept_vault_override(self) -> None:
        adapter = self.adapter()
        result = adapter.dispatch("knowledge.refresh", {"vault_root": r"C:\other"})
        self.assertFalse(result["changed"])

    def test_58_status_reports_not_configured(self) -> None:
        self.assertEqual(KnowledgeAdapter(None).status()["state"], AdapterState.NOT_CONFIGURED.value)

    def test_59_error_contract_is_stable(self) -> None:
        error = KnowledgeAdapterError(KnowledgeErrorCode.KNOWLEDGE_QUERY_EMPTY, "empty")
        self.assertEqual(error.to_dict(), {"code": "KNOWLEDGE_QUERY_EMPTY", "message": "empty"})

    def test_60_results_do_not_expose_absolute_paths(self) -> None:
        response = self.adapter().search("LocalComet")
        self.assertNotIn(os.fspath(self.vault), json.dumps(response, ensure_ascii=False))

    def test_61_founder_relation_is_conservative(self) -> None:
        self.add_extra("note.impl", "dualrelation", knowledge_layer="current_source_truth", status="current", authority="source")
        self.add_extra("note.intent", "dualrelation", knowledge_layer="founder_intent", authority="founder", evidence_class="C")
        result = self.adapter().context_preview("dualrelation", QueryIntent.FOUNDER_INTENT)
        types = {relation["type"] for relation in result["context_relations"]}
        self.assertIn("FOUNDER_INTENT_VS_IMPLEMENTATION", types)

    def test_62_context_total_matches_selected_content(self) -> None:
        result = self.adapter().context_preview("LocalComet", max_context_chars=500)
        actual = sum(len(section["content"]) for source in result["sources"] for section in source["selected_sections"])
        self.assertEqual(result["total_chars"], actual)

    def test_63_scores_are_deterministic_integers(self) -> None:
        results = self.adapter().search("LocalComet")["results"]
        self.assertTrue(results)
        self.assertTrue(all(isinstance(item["score"], int) for item in results))

    def test_64_diagnostic_logging_omits_full_query(self) -> None:
        events: list[tuple[str, dict[str, object]]] = []
        adapter = KnowledgeAdapter(
            self.config(),
            diagnostic_logger=lambda event, fields: events.append((event, dict(fields))),
        )
        adapter.initialize()
        query = "privatequerytoken"
        adapter.search(query)
        self.assertTrue(events)
        self.assertTrue(all("query" not in fields for _event, fields in events))
        self.assertNotIn(query, json.dumps(events))

    def test_65_failed_initialization_retains_validator_status(self) -> None:
        (self.vault / "bad.md").write_text("# bad\n", encoding="utf-8")
        expected = vault_validator.validate_vault(self.vault, self.project)
        adapter = KnowledgeAdapter(self.config())
        with self.assertRaises(KnowledgeAdapterError):
            adapter.initialize()
        status = adapter.status()
        self.assertEqual(status["validation_status"], "FAIL")
        self.assertEqual(status["validation_error_count"], expected.error_count)
        self.assertEqual(status["validation_warning_count"], expected.warning_count)
        self.assertEqual(status["vault_revision"], expected.vault_revision)
        self.assertEqual(status["indexed_note_count"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
