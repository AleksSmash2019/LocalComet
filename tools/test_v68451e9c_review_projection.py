"""Focused tests for the bounded e9b/e9c knowledge-review UI projection."""

from __future__ import annotations

import ast
import builtins
from dataclasses import FrozenInstanceError, fields, is_dataclass, replace
import difflib
import inspect
import json
from pathlib import Path
import socket
import subprocess
import sys
import textwrap
import types
import unittest
from unittest import mock

sys.dont_write_bytecode = True

import modules
from modules.knowledge_change_proposal_ru import ProposalOperation
from modules.knowledge_change_review_ru import (
    ConflictCode,
    ConflictFinding,
    FrozenCanonicalValue,
    KnowledgeChangeReviewArtifact,
    ReviewStatus,
)
import modules.knowledge_change_review_decision_ru as decision_contract
import modules.knowledge_review_ui_projection_ru as projection_contract
import tools.test_v68451e9b_knowledge_review as e9b_fixtures


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "modules" / "knowledge_review_ui_projection_ru.py"
TEST_PATH = Path(__file__).resolve()

PROPOSED_CONTENT_FIELDS = {
    "title",
    "body_text",
    "type",
    "status",
    "knowledge_layer",
    "evidence_class",
    "authority",
    "canonical",
    "canonical_scope",
    "aliases",
    "releases",
    "source_paths",
    "evidence_refs",
    "supersedes",
    "superseded_by",
    "updated",
    "last_reviewed",
    "verified_at",
}

DECISION_FIELDS = {
    "contract_version",
    "review_contract_version",
    "review_status",
    "proposal_id",
    "review_artifact_identity",
    "change_identity",
    "observed_vault_revision",
    "decision",
    "comment",
    "actor",
    "decision_identity",
    "hard_stop",
    "review_decision_only",
    "actor_metadata_evidence_only",
    "human_identity_authenticated",
    "grants_write_authority",
    "grants_vault_write_authority",
    "grants_persistence_authority",
    "grants_publication_authority",
    "grants_merge_authority",
    "grants_rebase_authority",
    "grants_execution_authority",
    "grants_policy_authority",
    "grants_model_gateway_authority",
    "grants_tauri_frontend_authority",
    "grants_automatic_approval_authority",
}

AUTHORITY_FIELDS = (
    "hard_stop",
    "review_decision_only",
    "actor_metadata_evidence_only",
    "human_identity_authenticated",
    "grants_write_authority",
    "grants_vault_write_authority",
    "grants_persistence_authority",
    "grants_publication_authority",
    "grants_merge_authority",
    "grants_rebase_authority",
    "grants_execution_authority",
    "grants_policy_authority",
    "grants_model_gateway_authority",
    "grants_tauri_frontend_authority",
    "grants_automatic_approval_authority",
)

CONSTRUCTION_COUNTS = {
    "e9a_proposal_instances": 0,
    "e9a_validation_results": 0,
    "e9b_review_artifacts": 0,
    "e9c_decisions": 0,
    "review_projection_calls": 0,
    "review_summary_projection_calls": 0,
    "decision_projection_calls": 0,
    "materialization_calls": 0,
    "canonical_calls": 0,
}
FAULT_RESULTS: list[dict[str, object]] = []
FAKE_DEPENDENCY_RESULTS: list[dict[str, object]] = []
SUBSTANCE_METRICS: dict[str, object] = {}


class DistinctBytes(bytes):
    """Valid UTF-8 bytes that model a distinct source representation."""

    def __eq__(self, other: object) -> bool:
        return False

    def __ne__(self, other: object) -> bool:
        return True


def _source_text() -> str:
    return MODULE_PATH.read_text(encoding="utf-8")


def _container_ids(value: object) -> set[int]:
    found: set[int] = set()
    if type(value) is dict:
        found.add(id(value))
        for key, child in value.items():
            found.update(_container_ids(key))
            found.update(_container_ids(child))
    elif type(value) is list:
        found.add(id(value))
        for child in value:
            found.update(_container_ids(child))
    return found


def _assert_standard_json_value(test: unittest.TestCase, value: object) -> None:
    value_type = type(value)
    test.assertIn(value_type, (dict, list, str, int, bool, type(None)))
    if value_type is dict:
        for key, child in value.items():
            test.assertIs(type(key), str)
            _assert_standard_json_value(test, child)
    elif value_type is list:
        for child in value:
            _assert_standard_json_value(test, child)


def _validation_mapping(node: dict[str, object]) -> dict[str, dict[str, object]]:
    if node["type_tag"] != "mapping":
        raise AssertionError("expected mapping projection")
    return {
        item["key"]: item["value"]
        for item in node["mapping_items"]
    }


def _clone_exact_review(
    artifact: KnowledgeChangeReviewArtifact,
    **changes: object,
) -> KnowledgeChangeReviewArtifact:
    return replace(artifact, **changes)


def _load_mutant(
    fault_name: str,
    needle: str,
    replacement: str,
) -> tuple[types.ModuleType, str]:
    source = _source_text()
    count = source.count(needle)
    if count != 1:
        raise AssertionError(f"{fault_name}: expected one mutation site, found {count}")
    mutated = source.replace(needle, replacement, 1)
    module_name = f"_localcomet_projection_mutant_{fault_name}"
    module = types.ModuleType(module_name)
    module.__file__ = f"<{module_name}>"
    sys.modules[module_name] = module
    try:
        exec(compile(mutated, module.__file__, "exec"), module.__dict__)
    except Exception:
        sys.modules.pop(module_name, None)
        raise
    return module, module_name


def _probe_incomplete_dependency(module_name: str) -> str:
    source = _source_text()
    attribute_name = module_name.rsplit(".", 1)[-1]
    original_module = sys.modules[module_name]
    original_attribute = getattr(modules, attribute_name)
    fake = types.ModuleType(module_name)
    probe_name = f"_projection_fake_probe_{attribute_name}"
    probe = types.ModuleType(probe_name)
    probe.__file__ = f"<{probe_name}>"
    sys.modules[module_name] = fake
    setattr(modules, attribute_name, fake)
    sys.modules[probe_name] = probe
    try:
        try:
            exec(compile(source, probe.__file__, "exec"), probe.__dict__)
        except ImportError:
            return "IMPORT_ERROR"
        return "UNEXPECTED_IMPORT_SUCCESS"
    finally:
        sys.modules[module_name] = original_module
        setattr(modules, attribute_name, original_attribute)
        sys.modules.pop(probe_name, None)


class ProjectionBehaviorTests(unittest.TestCase):
    api = projection_contract
    record_counts = True

    def _count(self, name: str, amount: int = 1) -> None:
        if self.record_counts:
            CONSTRUCTION_COUNTS[name] += amount

    def _record_review_construction(self) -> None:
        self._count("e9a_proposal_instances", 2)
        self._count("e9a_validation_results")
        self._count("e9b_review_artifacts")

    def setUp(self) -> None:
        self.helper = e9b_fixtures.KnowledgeReviewBehaviorTests()
        self.clear_create = self.helper.clear_create_artifact()
        self._record_review_construction()
        self.clear_update = self.helper.clear_update_artifact()
        self._record_review_construction()

        required_proposal = self.helper.make_proposal(body="required-after\n")
        required_result = self.helper.validate(required_proposal)
        required_current = self.helper.snapshot("required-before\n")
        self.review_required = self.helper.review(
            required_proposal,
            required_result,
            self.helper.state(current=required_current, baseline=None),
        )
        self._record_review_construction()

        blocked_proposal = self.helper.make_proposal(
            operation=ProposalOperation.CREATE_NEW,
            target=e9b_fixtures.OTHER_TARGET,
            body="blocked body\n",
        )
        blocked_result = self.helper.validate(
            blocked_proposal,
            stable_ids={e9b_fixtures.TARGET},
        )
        self.blocked = self.helper.review(
            blocked_proposal,
            blocked_result,
            self.helper.state(
                stable_ids={e9b_fixtures.TARGET, e9b_fixtures.OTHER_TARGET}
            ),
        )
        self._record_review_construction()
        self.actor = decision_contract.HumanReviewerMetadata(
            actor_identifier="human-reviewer-001",
            display_name="Local Reviewer",
            source="local-human-review",
        )

    def _review_projection(self, artifact: KnowledgeChangeReviewArtifact | None = None):
        self._count("review_projection_calls")
        return self.api.project_knowledge_change_review(artifact or self.clear_update)

    def _review_summary_projection(self, artifact: KnowledgeChangeReviewArtifact | None = None):
        self._count("review_summary_projection_calls")
        return self.api.project_knowledge_change_review_summary(artifact or self.clear_update)

    def _decision(self, artifact, *, value, comment="", actor=None):
        result = decision_contract.create_human_review_decision(
            artifact,
            expected_proposal_id=artifact.proposal_id,
            expected_review_artifact_identity=artifact.review_artifact_identity,
            expected_change_identity=artifact.change_identity,
            expected_observed_vault_revision=artifact.observed_vault_revision,
            current_observed_vault_revision=artifact.observed_vault_revision,
            decision=value,
            comment=comment,
            actor=actor or self.actor,
        )
        self._count("e9c_decisions")
        return result

    def _decision_projection(self, decision):
        self._count("decision_projection_calls")
        return self.api.project_human_review_decision(decision)

    def _materialize(self, projection):
        self._count("materialization_calls")
        return self.api.materialize_json_value(projection)

    def _canonical(self, projection):
        self._count("canonical_calls")
        return self.api.canonical_projection_json_bytes(projection)

    def _replace_source_paths(self, artifact, paths):
        snapshot = replace(artifact.proposed_content_snapshot, source_paths=tuple(paths))
        return _clone_exact_review(artifact, proposed_content_snapshot=snapshot)

    def _large_update(self):
        after = "".join(
            f"line-{index:04d} Протокол проекции и доказательство границы\n"
            for index in range(1_000)
        )
        artifact = self.helper.clear_update_artifact(before="old\n", after=after)
        self._record_review_construction()
        return artifact

    def test_001_projection_contract_and_kind_are_exact(self) -> None:
        review = self._review_projection(self.clear_create)
        decision = self._decision_projection(
            self._decision(
                self.clear_create,
                value=decision_contract.HumanReviewDecisionValue.APPROVE,
            )
        )
        self.assertEqual(review.projection_contract, "localcomet.knowledge-review-ui/1.0")
        self.assertEqual(review.kind.value, "KNOWLEDGE_CHANGE_REVIEW")
        self.assertEqual(decision.kind.value, "HUMAN_REVIEW_DECISION")

    def test_002_clear_create_new_projection_uses_real_e9b_artifact(self) -> None:
        projected = self._review_projection(self.clear_create)
        self.assertIs(type(projected), self.api.KnowledgeChangeReviewProjection)
        self.assertEqual(projected.status, "CLEAR")
        self.assertEqual(projected.operation, "CREATE_NEW")
        self.assertIsNone(projected.before_source_byte_hash)

    def test_003_clear_update_existing_projection_preserves_preimage_hashes(self) -> None:
        projected = self._review_projection(self.clear_update)
        self.assertEqual(projected.status, "CLEAR")
        self.assertEqual(projected.operation, "UPDATE_EXISTING")
        self.assertEqual(projected.before_source_byte_hash, self.clear_update.before_source_byte_hash)
        self.assertEqual(projected.before_text_raw_hash, self.clear_update.before_text_raw_hash)
        self.assertEqual(projected.before_semantic_text_hash, self.clear_update.before_semantic_text_hash)

    def test_004_review_required_projection_preserves_status_and_findings(self) -> None:
        projected = self._review_projection(self.review_required)
        self.assertEqual(projected.status, "REVIEW_REQUIRED")
        self.assertGreater(projected.findings.original_count, 0)
        self.assertEqual(
            [item.code for item in projected.findings.items],
            [item.code.value for item in self.review_required.findings],
        )

    def test_005_blocked_projection_preserves_status_without_change_identity(self) -> None:
        projected = self._review_projection(self.blocked)
        self.assertEqual(projected.status, "BLOCKED")
        self.assertIsNone(projected.change_identity)
        self.assertEqual(projected.review_artifact_identity, self.blocked.review_artifact_identity)

    def test_006_metadata_only_empty_diff_is_present_not_absent(self) -> None:
        artifact = self.helper.metadata_only_artifact(title="Metadata-only title")
        self._record_review_construction()
        self.assertEqual(artifact.deterministic_text_diff, "")
        projected = self._review_projection(artifact)
        self.assertIsNotNone(projected.diff)
        self.assertTrue(projected.diff.full_diff_present)
        self.assertEqual(projected.diff.full_diff_utf8_bytes, 0)
        self.assertEqual(projected.diff.preview.preview_text, "")
        self.assertEqual(projected.diff.full_diff_hash, artifact.deterministic_text_diff_hash)

    def test_007_line_ending_only_representation_delta_is_complete(self) -> None:
        artifact = self.helper.clear_update_artifact(before="same\r\n", after="same\n")
        self._record_review_construction()
        projected = self._review_projection(artifact)
        delta = projected.representation_delta
        self.assertIsNotNone(delta)
        self.assertEqual(delta.before_line_endings.crlf_count, 1)
        self.assertEqual(delta.after_line_endings.lf_count, 1)
        self.assertTrue(delta.raw_text_changed_semantic_equal)

    def test_008_terminal_newline_only_delta_is_preserved(self) -> None:
        artifact = self.helper.clear_update_artifact(before="same", after="same\n")
        self._record_review_construction()
        projected = self._review_projection(artifact)
        self.assertTrue(projected.representation_delta.terminal_newline_changed)
        self.assertFalse(projected.representation_delta.before_line_endings.terminal_newline)
        self.assertTrue(projected.representation_delta.after_line_endings.terminal_newline)

    def test_009_source_bytes_changed_text_identical_is_authentic_and_visible(self) -> None:
        proposal = self.helper.make_proposal(body="same\n")
        validation = self.helper.validate(proposal)
        baseline = self.helper.snapshot("same\n")
        current = replace(baseline, source_bytes=DistinctBytes(baseline.source_bytes))
        artifact = self.helper.review(
            proposal,
            validation,
            self.helper.state(current=current, baseline=baseline),
        )
        self._record_review_construction()
        self.assertIn(
            ConflictCode.TARGET_SOURCE_BYTES_CHANGED_TEXT_IDENTICAL,
            {finding.code for finding in artifact.findings},
        )
        projected = self._review_projection(artifact)
        self.assertFalse(projected.representation_delta.after_source_bytes_known)
        self.assertEqual(
            projected.representation_delta.source_bytes_changed_text_identical,
            artifact.representation_delta.source_bytes_changed_text_identical,
        )
        self.assertIn(
            "TARGET_SOURCE_BYTES_CHANGED_TEXT_IDENTICAL",
            [item.code for item in projected.findings.items],
        )

    def test_010_all_18_proposed_content_fields_are_materialized(self) -> None:
        value = self._materialize(self._review_projection(self.clear_update))
        proposed = value["proposed_content_snapshot"]
        self.assertEqual(set(proposed), PROPOSED_CONTENT_FIELDS)
        self.assertEqual(len(proposed), 18)
        self.assertIs(type(proposed["body_text"]), dict)

    def test_011_proposed_scalar_metadata_is_exact(self) -> None:
        source = self.clear_update.proposed_content_snapshot
        projected = self._review_projection(self.clear_update).proposed_content_snapshot
        for name in (
            "title", "type", "status", "knowledge_layer", "evidence_class",
            "authority", "canonical", "canonical_scope", "updated",
            "last_reviewed", "verified_at",
        ):
            self.assertEqual(getattr(projected, name), getattr(source, name), name)

    def test_012_body_preview_preserves_exact_hashes_and_original_byte_count(self) -> None:
        projected = self._review_projection(self.clear_update).proposed_content_snapshot.body_text
        source = self.clear_update.proposed_content_snapshot.body_text
        self.assertEqual(projected.raw_text_hash, self.clear_update.proposed_text_raw_hash)
        self.assertEqual(projected.semantic_text_hash, self.clear_update.proposed_semantic_text_hash)
        self.assertEqual(projected.original_utf8_bytes, len(source.encode("utf-8")))
        self.assertTrue(projected.is_preview)

    def test_013_large_body_preview_has_truthful_truncation_flag(self) -> None:
        artifact = self.helper.clear_create_artifact(body="ж" * 10_000)
        self._record_review_construction()
        body = self._review_projection(artifact).proposed_content_snapshot.body_text
        self.assertTrue(body.truncated)
        self.assertLessEqual(body.preview_utf8_bytes, self.api.MAX_BODY_PREVIEW_BYTES)
        self.assertGreater(body.original_utf8_bytes, body.preview_utf8_bytes)

    def test_014_body_preview_enforces_line_bound(self) -> None:
        artifact = self.helper.clear_create_artifact(
            body="".join(f"body-{index}\n" for index in range(260))
        )
        self._record_review_construction()
        body = self._review_projection(artifact).proposed_content_snapshot.body_text
        self.assertTrue(body.truncated)
        self.assertLessEqual(body.preview_line_count, self.api.MAX_BODY_PREVIEW_LINES)
        self.assertEqual(body.original_line_count, 260)

    def test_015_bounded_metadata_collection_reports_original_count(self) -> None:
        aliases = tuple(f"alias-{index:03d}" for index in range(129))
        snapshot = replace(self.clear_create.proposed_content_snapshot, aliases=aliases)
        artifact = _clone_exact_review(self.clear_create, proposed_content_snapshot=snapshot)
        collection = self._review_projection(artifact).proposed_content_snapshot.aliases
        self.assertTrue(collection.truncated)
        self.assertEqual(collection.original_count, 129)
        self.assertEqual(len(collection.items), self.api.MAX_METADATA_COLLECTION_ITEMS)

    def test_016_every_collection_is_new_and_preserves_source_order(self) -> None:
        source = self.clear_update.proposed_content_snapshot
        projected = self._review_projection(self.clear_update).proposed_content_snapshot
        for name in (
            "aliases", "releases", "source_paths", "evidence_refs",
            "supersedes", "superseded_by",
        ):
            collection = getattr(projected, name)
            self.assertEqual(collection.items, getattr(source, name), name)
            self.assertEqual(collection.original_count, len(getattr(source, name)), name)
            self.assertFalse(collection.truncated, name)

    def test_017_validation_snapshot_retains_mapping_and_sequence_type_tags(self) -> None:
        materialized = self._materialize(self._review_projection(self.clear_create))
        root = materialized["validation_snapshot"]["value"]
        entries = _validation_mapping(root)
        self.assertEqual(root["type_tag"], "mapping")
        self.assertEqual(entries["findings"]["type_tag"], "sequence")
        self.assertEqual(entries["provenance_summary"]["type_tag"], "mapping")

    def test_018_validation_scalar_types_are_not_collapsed(self) -> None:
        materialized = self._materialize(self._review_projection(self.clear_create))
        entries = _validation_mapping(materialized["validation_snapshot"]["value"])
        self.assertEqual(entries["evidence_reference_count"]["type_tag"], "int")
        self.assertIs(type(entries["evidence_reference_count"]["scalar_value"]), int)
        self.assertEqual(entries["proposal_id"]["type_tag"], "string")

    def test_019_validation_projection_has_explicit_non_truncated_flag(self) -> None:
        projected = self._review_projection(self.clear_create).validation_snapshot
        self.assertFalse(projected.truncated)
        self.assertIs(type(projected.value), self.api.ValidationValueProjection)

    def test_020_source_validation_findings_do_not_invent_messages(self) -> None:
        projected = self._review_projection(self.clear_create).source_validation_findings
        self.assertEqual(
            [(item.code, item.severity) for item in projected.items],
            list(self.clear_create.source_validation_findings),
        )
        materialized = self._materialize(self._review_projection(self.clear_create))
        self.assertTrue(
            all(set(item) == {"code", "severity"}
                for item in materialized["source_validation_findings"]["items"])
        )

    def test_021_review_finding_order_messages_and_details_are_exact(self) -> None:
        projected = self._review_projection(self.review_required).findings
        self.assertEqual(projected.original_count, len(self.review_required.findings))
        for source, target in zip(self.review_required.findings, projected.items, strict=True):
            self.assertEqual(target.code, source.code.value)
            self.assertEqual(target.severity, source.severity.value)
            self.assertEqual(target.message.preview_text, source.message)
            self.assertEqual(
                [(detail.key, detail.value) for detail in target.details.items],
                list(source.details),
            )
            self.assertEqual(target.details.original_count, len(source.details))
            self.assertFalse(target.details.truncated)

    def test_022_review_finding_collection_truncation_is_explicit(self) -> None:
        finding = self.review_required.findings[0]
        artifact = _clone_exact_review(self.review_required, findings=(finding,) * 17)
        projected = self._review_projection(artifact).findings
        self.assertTrue(projected.truncated)
        self.assertEqual(projected.original_count, 17)
        self.assertEqual(len(projected.items), self.api.MAX_PROJECTED_FINDINGS)

    def test_023_all_before_and_proposed_hashes_are_unshortened(self) -> None:
        projected = self._review_projection(self.clear_update)
        for name in (
            "before_source_byte_hash", "before_text_raw_hash",
            "before_semantic_text_hash", "proposed_text_raw_hash",
            "proposed_semantic_text_hash",
        ):
            self.assertEqual(getattr(projected, name), getattr(self.clear_update, name))
            self.assertEqual(len(getattr(projected, name)), 71)

    def test_024_diff_projection_preserves_full_hash_and_original_byte_count(self) -> None:
        projected = self._review_projection(self.clear_update).diff
        self.assertTrue(projected.full_diff_present)
        self.assertEqual(projected.full_diff_hash, self.clear_update.deterministic_text_diff_hash)
        self.assertEqual(
            projected.full_diff_utf8_bytes,
            len(self.clear_update.deterministic_text_diff.encode("utf-8")),
        )

    def test_025_diff_preview_is_never_labeled_as_full_diff(self) -> None:
        projected = self._review_projection(self.clear_update).diff
        self.assertFalse(projected.preview_is_full_diff)
        self.assertIs(projected.preview_truncated, projected.preview.truncated)
        self.assertTrue(projected.preview.is_preview)
        self.assertNotEqual(projected.preview.preview_text, self.clear_update.deterministic_text_diff)

    def test_026_large_diff_preview_is_bounded_and_truncated(self) -> None:
        artifact = self._large_update()
        projected = self._review_projection(artifact).diff
        self.assertTrue(projected.preview.truncated)
        self.assertLessEqual(projected.preview.preview_utf8_bytes, self.api.MAX_DIFF_PREVIEW_BYTES)
        self.assertLessEqual(projected.preview.preview_line_count, self.api.MAX_DIFF_PREVIEW_LINES)

    def test_027_full_deterministic_diff_text_is_not_a_materialized_field(self) -> None:
        materialized = self._materialize(self._review_projection(self.clear_update))
        self.assertNotIn("deterministic_text_diff", materialized)
        self.assertNotIn("full_diff", materialized["diff"])
        self.assertIn("preview", materialized["diff"])

    def test_028_full_representation_delta_is_materialized(self) -> None:
        materialized = self._materialize(self._review_projection(self.clear_update))
        delta = materialized["representation_delta"]
        self.assertIsNotNone(delta)
        self.assertEqual(
            set(delta),
            {
                "before_present", "after_present", "before_line_endings",
                "after_line_endings", "terminal_newline_changed",
                "after_source_bytes_known", "source_bytes_changed_text_identical",
                "raw_text_changed_semantic_equal", "semantic_content_changed", "identity",
            },
        )
        self.assertEqual(delta["identity"], self.clear_update.representation_delta.identity)

    def test_029_human_preview_reports_original_size_and_preview_semantics(self) -> None:
        projected = self._review_projection(self.clear_update).human_review_preview
        self.assertTrue(projected.is_preview)
        self.assertEqual(
            projected.original_utf8_bytes,
            len(self.clear_update.human_review_preview.encode("utf-8")),
        )
        self.assertLessEqual(projected.preview_utf8_bytes, self.api.MAX_HUMAN_PREVIEW_BYTES)

    def test_030_large_human_preview_truncation_is_truthful(self) -> None:
        artifact = self._large_update()
        source_bytes = len(artifact.human_review_preview.encode("utf-8"))
        projected = self._review_projection(artifact).human_review_preview
        self.assertGreater(source_bytes, self.api.MAX_HUMAN_PREVIEW_BYTES)
        self.assertTrue(projected.truncated)
        self.assertLess(projected.preview_utf8_bytes, projected.original_utf8_bytes)

    def test_031_exact_review_identity_is_never_shortened(self) -> None:
        projected = self._review_projection(self.clear_update)
        self.assertEqual(projected.review_artifact_identity, self.clear_update.review_artifact_identity)
        self.assertEqual(len(projected.review_artifact_identity), len("kreview:") + 64)
        self.assertEqual(projected.change_identity, self.clear_update.change_identity)

    def test_032_blocked_diff_delta_and_change_material_are_exact_none(self) -> None:
        materialized = self._materialize(self._review_projection(self.blocked))
        self.assertIsNone(materialized["diff"])
        self.assertIsNone(materialized["representation_delta"])
        self.assertIsNone(materialized["change_identity"])
        self.assertIsNone(self.blocked.deterministic_text_diff_hash)

    def test_033_blocked_projection_still_preserves_proposed_hashes(self) -> None:
        projected = self._review_projection(self.blocked)
        self.assertEqual(projected.proposed_text_raw_hash, self.blocked.proposed_text_raw_hash)
        self.assertEqual(projected.proposed_semantic_text_hash, self.blocked.proposed_semantic_text_hash)
        self.assertIsNotNone(projected.proposed_content_snapshot.body_text)

    def test_034_approve_decision_projection_preserves_real_e9c_fields(self) -> None:
        decision = self._decision(
            self.clear_create,
            value=decision_contract.HumanReviewDecisionValue.APPROVE,
        )
        projected = self._decision_projection(decision)
        self.assertEqual(projected.decision, "APPROVE")
        self.assertEqual(projected.change_identity, self.clear_create.change_identity)
        self.assertEqual(projected.decision_identity, decision.decision_identity)

    def test_035_blocked_reject_preserves_none_change_identity(self) -> None:
        decision = self._decision(
            self.blocked,
            value=decision_contract.HumanReviewDecisionValue.REJECT,
            comment="Отклонено: конфликт stable ID",
        )
        projected = self._decision_projection(decision)
        self.assertEqual(projected.review_status, "BLOCKED")
        self.assertEqual(projected.decision, "REJECT")
        self.assertIsNone(projected.change_identity)

    def test_036_request_changes_preserves_exact_unicode_comment(self) -> None:
        comment = "Нужны изменения — проверить Café и 東京 🚀\nСтрока 2"
        decision = self._decision(
            self.review_required,
            value=decision_contract.HumanReviewDecisionValue.REQUEST_CHANGES,
            comment=comment,
        )
        projected = self._decision_projection(decision)
        self.assertEqual(projected.decision, "REQUEST_CHANGES")
        self.assertEqual(projected.comment, comment)
        self.assertEqual(self._materialize(projected)["comment"], comment)

    def test_037_every_authority_flag_is_preserved_exactly(self) -> None:
        decision = self._decision(
            self.clear_create,
            value=decision_contract.HumanReviewDecisionValue.APPROVE,
        )
        projected = self._decision_projection(decision)
        for name in AUTHORITY_FIELDS:
            self.assertIs(getattr(projected, name), getattr(decision, name), name)
        self.assertTrue(projected.hard_stop)
        self.assertTrue(projected.review_decision_only)
        self.assertTrue(projected.actor_metadata_evidence_only)
        self.assertFalse(any(getattr(projected, name) for name in AUTHORITY_FIELDS[3:]))

    def test_038_all_26_decision_fields_are_materialized(self) -> None:
        decision = self._decision(
            self.clear_create,
            value=decision_contract.HumanReviewDecisionValue.REJECT,
        )
        materialized = self._materialize(self._decision_projection(decision))
        self.assertEqual(set(materialized) - {"projection_contract", "kind"}, DECISION_FIELDS)
        self.assertEqual(len(materialized), 28)
        self.assertEqual(set(materialized["actor"]), {"actor_identifier", "display_name", "source"})

    def test_039_actor_metadata_is_exact_unicode_evidence(self) -> None:
        actor = decision_contract.HumanReviewerMetadata(
            actor_identifier="reviewer-ёж-東京",
            display_name="Ревьюер Élodie",
            source="локальный-интерфейс",
        )
        decision = self._decision(
            self.clear_create,
            value=decision_contract.HumanReviewDecisionValue.REJECT,
            actor=actor,
        )
        projected = self._decision_projection(decision)
        self.assertEqual(projected.actor.actor_identifier, actor.actor_identifier)
        self.assertEqual(projected.actor.display_name, actor.display_name)
        self.assertEqual(projected.actor.source, actor.source)

    def test_040_decision_and_binding_identities_are_exact(self) -> None:
        decision = self._decision(
            self.review_required,
            value=decision_contract.HumanReviewDecisionValue.REJECT,
            comment="exact",
        )
        projected = self._decision_projection(decision)
        for name in (
            "proposal_id", "review_artifact_identity", "change_identity",
            "observed_vault_revision", "decision_identity",
        ):
            self.assertEqual(getattr(projected, name), getattr(decision, name), name)

    def test_041_projection_records_are_frozen_slotted_and_tuple_only(self) -> None:
        projected = self._review_projection(self.clear_update)
        self.assertFalse(hasattr(projected, "__dict__"))
        with self.assertRaises(FrozenInstanceError):
            projected.status = "BLOCKED"

        def walk(value):
            if is_dataclass(value) and not isinstance(value, type):
                self.assertFalse(hasattr(value, "__dict__"), type(value).__name__)
                for item in fields(value):
                    walk(getattr(value, item.name))
            elif type(value) is tuple:
                for child in value:
                    walk(child)
            else:
                self.assertNotIn(type(value), (dict, list, set, bytearray))

        walk(projected)

    def test_042_materialized_projection_contains_only_standard_json_values(self) -> None:
        review_value = self._materialize(self._review_projection(self.clear_update))
        decision_value = self._materialize(
            self._decision_projection(
                self._decision(
                    self.clear_create,
                    value=decision_contract.HumanReviewDecisionValue.APPROVE,
                )
            )
        )
        _assert_standard_json_value(self, review_value)
        _assert_standard_json_value(self, decision_value)

    def test_043_json_round_trip_preserves_materialized_value(self) -> None:
        projected = self._review_projection(self.clear_update)
        materialized = self._materialize(projected)
        decoded = json.loads(self._canonical(projected).decode("utf-8"))
        self.assertEqual(decoded, materialized)
        self.assertIs(type(decoded), dict)

    def test_044_materializations_have_disjoint_containers_and_mutation_isolation(self) -> None:
        projected = self._review_projection(self.clear_update)
        first = self._materialize(projected)
        second = self._materialize(projected)
        self.assertTrue(_container_ids(first).isdisjoint(_container_ids(second)))
        first["proposed_content_snapshot"]["aliases"]["items"].append("MUTATED")
        third = self._materialize(projected)
        self.assertEqual(second, third)
        self.assertNotIn("MUTATED", third["proposed_content_snapshot"]["aliases"]["items"])

    def test_045_wrong_root_types_and_dict_inputs_are_typed_rejections(self) -> None:
        with self.assertRaises(self.api.ProjectionRejected) as review_error:
            self.api.project_knowledge_change_review({"artifact": self.clear_update})
        self.assertIs(review_error.exception.code, self.api.ProjectionRejectionCode.WRONG_REVIEW_ARTIFACT_TYPE)
        with self.assertRaises(self.api.ProjectionRejected) as decision_error:
            self.api.project_human_review_decision(object())
        self.assertIs(decision_error.exception.code, self.api.ProjectionRejectionCode.WRONG_DECISION_TYPE)
        with self.assertRaises(self.api.ProjectionRejected) as json_error:
            self.api.materialize_json_value({"projection": "fake"})
        self.assertIs(json_error.exception.code, self.api.ProjectionRejectionCode.WRONG_PROJECTION_TYPE)

    def test_046_posix_absolute_and_windows_absolute_paths_are_rejected(self) -> None:
        for path in ("/etc/localcomet.md", r"C:\vault\note.md", r"\\server\share\note.md"):
            with self.subTest(path=path):
                artifact = self._replace_source_paths(self.clear_create, (path,))
                with self.assertRaises(self.api.ProjectionRejected) as captured:
                    self._review_projection(artifact)
                self.assertIs(captured.exception.code, self.api.ProjectionRejectionCode.UNSAFE_SOURCE_PATH)

    def test_047_windows_drive_relative_path_is_rejected(self) -> None:
        artifact = self._replace_source_paths(self.clear_create, ("C:foo.md",))
        with self.assertRaises(self.api.ProjectionRejected) as captured:
            self._review_projection(artifact)
        self.assertIs(captured.exception.code, self.api.ProjectionRejectionCode.UNSAFE_SOURCE_PATH)

    def test_048_rooted_traversal_nul_and_overlength_paths_are_rejected(self) -> None:
        cases = (
            r"\rooted\note.md",
            "notes/../secret.md",
            "notes/bad\x00name.md",
            "a" * (self.api.MAX_SOURCE_PATH_CHARS + 1),
        )
        for path in cases:
            with self.subTest(path=repr(path)):
                artifact = self._replace_source_paths(self.clear_create, (path,))
                with self.assertRaises(self.api.ProjectionRejected):
                    self._review_projection(artifact)

    def test_049_unsafe_path_cannot_hide_after_collection_truncation(self) -> None:
        paths = tuple(
            f"notes/safe-{index:03d}.md"
            for index in range(self.api.MAX_METADATA_COLLECTION_ITEMS)
        ) + ("C:hidden-after-bound.md",)
        artifact = self._replace_source_paths(self.clear_create, paths)
        with self.assertRaises(self.api.ProjectionRejected) as captured:
            self._review_projection(artifact)
        self.assertIs(captured.exception.code, self.api.ProjectionRejectionCode.UNSAFE_SOURCE_PATH)

    def test_050_safe_relative_posix_windows_and_dotted_paths_are_exact(self) -> None:
        paths = ("notes/current.md", r"notes\windows-relative.md", ".hidden/review.md")
        artifact = self._replace_source_paths(self.clear_create, paths)
        projected = self._review_projection(artifact)
        self.assertEqual(projected.proposed_content_snapshot.source_paths.items, paths)
        self.assertFalse(projected.proposed_content_snapshot.source_paths.truncated)

    def test_051_total_projection_byte_bound_is_enforced_at_canonical_boundary(self) -> None:
        projected = self._review_projection(self.clear_update)
        with mock.patch.object(self.api, "MAX_TOTAL_JSON_BYTES", 1):
            with self.assertRaises(self.api.ProjectionRejected) as captured:
                self._canonical(projected)
        self.assertIs(
            captured.exception.code,
            self.api.ProjectionRejectionCode.PROJECTION_JSON_LIMIT_EXCEEDED,
        )

    def test_052_canonical_bytes_are_repeatable_and_match_independent_oracle(self) -> None:
        projected = self._review_projection(self.clear_update)
        first = self._canonical(projected)
        second = self._canonical(projected)
        self.assertEqual(first, second)
        oracle = json.dumps(
            self._materialize(projected),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        self.assertEqual(first, oracle)
        self.assertLessEqual(len(first), self.api.MAX_TOTAL_JSON_BYTES)

    def test_053_governed_review_and_decision_changes_change_canonical_bytes(self) -> None:
        before = self._canonical(self._review_projection(self.clear_update))
        after_artifact = self.helper.clear_update_artifact(before="old\n", after="different\n")
        self._record_review_construction()
        after = self._canonical(self._review_projection(after_artifact))
        self.assertNotEqual(before, after)
        reject = self._decision(
            self.clear_create,
            value=decision_contract.HumanReviewDecisionValue.REJECT,
        )
        approve = self._decision(
            self.clear_create,
            value=decision_contract.HumanReviewDecisionValue.APPROVE,
        )
        self.assertNotEqual(
            self._canonical(self._decision_projection(reject)),
            self._canonical(self._decision_projection(approve)),
        )

    def test_054_static_module_has_no_side_effect_or_integration_runtime(self) -> None:
        tree = ast.parse(_source_text())
        allowed_import_roots = {
            "__future__", "dataclasses", "enum", "json", "pathlib", "re", "typing", "modules"
        }
        imports = []
        banned_calls = {
            "open", "write", "write_text", "write_bytes", "unlink", "mkdir", "makedirs",
            "rename", "connect", "urlopen", "request", "run",
            "Popen", "system", "invoke", "emit",
        }
        calls = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module.split(".", 1)[0])
            elif isinstance(node, ast.Call):
                name = node.func.attr if isinstance(node.func, ast.Attribute) else (
                    node.func.id if isinstance(node.func, ast.Name) else ""
                )
                if name in banned_calls:
                    calls.append(name)
        self.assertEqual(sorted(set(imports) - allowed_import_roots), [])
        self.assertEqual(calls, [])
        self.assertNotIn("__import__", _source_text())

    def test_055_runtime_projection_performs_no_io_network_subprocess_or_frontend_action(self) -> None:
        with (
            mock.patch.object(builtins, "open", side_effect=AssertionError("open forbidden")),
            mock.patch.object(Path, "open", side_effect=AssertionError("Path.open forbidden")),
            mock.patch.object(Path, "write_text", side_effect=AssertionError("write forbidden")),
            mock.patch.object(Path, "write_bytes", side_effect=AssertionError("write forbidden")),
            mock.patch.object(socket, "socket", side_effect=AssertionError("network forbidden")),
            mock.patch.object(subprocess, "Popen", side_effect=AssertionError("subprocess forbidden")),
        ):
            review = self._review_projection(self.clear_update)
            decision = self._decision_projection(
                self._decision(
                    self.clear_create,
                    value=decision_contract.HumanReviewDecisionValue.REJECT,
                )
            )
            self._canonical(review)
            self._canonical(decision)

    def test_056_incomplete_fake_e9b_dependency_fails_static_import(self) -> None:
        result = _probe_incomplete_dependency("modules.knowledge_change_review_ru")
        FAKE_DEPENDENCY_RESULTS.append({"dependency": "e9b", "result": result})
        self.assertEqual(result, "IMPORT_ERROR")

    def test_057_incomplete_fake_e9c_dependency_fails_static_import(self) -> None:
        result = _probe_incomplete_dependency("modules.knowledge_change_review_decision_ru")
        FAKE_DEPENDENCY_RESULTS.append({"dependency": "e9c", "result": result})
        self.assertEqual(result, "IMPORT_ERROR")

    def test_058_all_ten_in_memory_faults_are_detected(self) -> None:
        faults = (
            (
                "01_omitted_proposed_field",
                "            for field in fields(value)\n",
                "            for field in fields(value)\n"
                "            if not (type(value) is ProposedContentProjection and field.name == \"verified_at\")\n",
                "test_010_all_18_proposed_content_fields_are_materialized",
            ),
            (
                "02_shortened_identity",
                "        review_artifact_identity=artifact.review_artifact_identity,\n",
                "        review_artifact_identity=artifact.review_artifact_identity[:-1],\n",
                "test_031_exact_review_identity_is_never_shortened",
            ),
            (
                "03_blocked_material_exposed",
                "        diff=diff,\n",
                "        diff=diff if artifact.status is not ReviewStatus.BLOCKED else \"EXPOSED\",\n",
                "test_032_blocked_diff_delta_and_change_material_are_exact_none",
            ),
            (
                "04_representation_omitted",
                "        representation_delta=representation,\n",
                "        representation_delta=None,\n",
                "test_028_full_representation_delta_is_materialized",
            ),
            (
                "05_preview_labeled_full",
                "        preview_is_full_diff=False,\n",
                "        preview_is_full_diff=True,\n",
                "test_025_diff_preview_is_never_labeled_as_full_diff",
            ),
            (
                "06_truncation_flag_disabled",
                "        truncated=body_preview.truncated,\n",
                "        truncated=False,\n",
                "test_013_large_body_preview_has_truthful_truncation_flag",
            ),
            (
                "07_windows_drive_relative_accepted",
                "        or bool(windows.drive)\n",
                "        or (bool(windows.drive) and not re.match(r\"^[A-Za-z]:[^\\\\/]\", value))\n",
                "test_047_windows_drive_relative_path_is_rejected",
            ),
            (
                "08_output_bound_disabled",
                "    if len(encoded) > MAX_TOTAL_JSON_BYTES:\n",
                "    if False and len(encoded) > MAX_TOTAL_JSON_BYTES:\n",
                "test_051_total_projection_byte_bound_is_enforced_at_canonical_boundary",
            ),
            (
                "09_json_aliases_internal_list",
                "            return [\n"
                "                _materialize(item, active=active, budget=budget)\n"
                "                for item in value\n"
                "            ]\n",
                "            global _FAULT_SHARED_LIST\n"
                "            if \"_FAULT_SHARED_LIST\" not in globals():\n"
                "                _FAULT_SHARED_LIST = [\n"
                "                    _materialize(item, active=active, budget=budget)\n"
                "                    for item in value\n"
                "                ]\n"
                "            return _FAULT_SHARED_LIST\n",
                "test_044_materializations_have_disjoint_containers_and_mutation_isolation",
            ),
            (
                "10_canonical_nondeterministic",
                "    return _canonical_json_value_bytes(materialized)\n",
                "    global _FAULT_CANONICAL_COUNTER\n"
                "    _FAULT_CANONICAL_COUNTER = globals().get(\"_FAULT_CANONICAL_COUNTER\", 0) + 1\n"
                "    return (\n"
                "        _canonical_json_value_bytes(materialized)\n"
                "        + str(_FAULT_CANONICAL_COUNTER).encode(\"ascii\")\n"
                "    )\n",
                "test_052_canonical_bytes_are_repeatable_and_match_independent_oracle",
            ),
        )
        observed = []
        for name, needle, replacement, test_name in faults:
            mutant, module_name = _load_mutant(name, needle, replacement)
            try:
                case = type(self)(test_name)
                case.api = mutant
                case.record_counts = False
                result = unittest.TestResult()
                case.run(result)
                entry = {
                    "fault": name,
                    "test": test_name,
                    "tests_run": result.testsRun,
                    "failures": len(result.failures),
                    "errors": len(result.errors),
                }
                observed.append(entry)
                self.assertEqual(entry["tests_run"], 1, name)
                self.assertEqual(entry["failures"], 1, name)
                self.assertEqual(entry["errors"], 0, name)
            finally:
                sys.modules.pop(module_name, None)
        FAULT_RESULTS[:] = observed
        self.assertEqual(len(observed), 10)

    def test_059_focused_suite_substance_gate(self) -> None:
        methods = {
            name: member
            for name, member in type(self).__dict__.items()
            if inspect.isfunction(member) and (name.startswith("test_") or name.startswith("_"))
        }
        public_names = {
            "project_knowledge_change_review",
            "project_knowledge_change_review_summary",
            "project_human_review_decision",
            "materialize_json_value",
            "canonical_projection_json_bytes",
        }
        call_graph: dict[str, set[str]] = {}
        direct_public: set[str] = set()
        normalized_bodies: dict[str, str] = {}
        assertion_patterns: dict[str, tuple[str, ...]] = {}
        for name, member in methods.items():
            try:
                source = inspect.getsource(member)
            except OSError:
                continue
            tree = ast.parse(textwrap.dedent(source))
            called = set()
            assertions = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    called.add(node.func.attr)
                    if node.func.attr.startswith("assert"):
                        assertions.append(node.func.attr)
                    if node.func.attr in public_names:
                        direct_public.add(name)
            call_graph[name] = called
            if name.startswith("test_"):
                function = tree.body[0]
                function.name = "normalized"
                normalized_bodies[name] = ast.dump(function, include_attributes=False)
                assertion_patterns[name] = tuple(assertions)

        memo: dict[str, bool] = {}

        def reaches_public(name: str, active: set[str]) -> bool:
            if name in memo:
                return memo[name]
            if name in direct_public:
                memo[name] = True
                return True
            if name in active:
                return False
            result = any(
                called in methods and reaches_public(called, active | {name})
                for called in call_graph.get(name, set())
            )
            memo[name] = result
            return result

        tests = sorted(name for name in normalized_bodies)
        reached = sorted(name for name in tests if reaches_public(name, set()))
        duplicate_groups = []
        for index, left in enumerate(tests):
            group = [
                right for right in tests[index + 1:]
                if normalized_bodies[left] == normalized_bodies[right]
            ]
            if group:
                duplicate_groups.append([left, *group])
        near_duplicate_pairs = []
        for index, left in enumerate(tests):
            for right in tests[index + 1:]:
                left_body = normalized_bodies[left]
                right_body = normalized_bodies[right]
                larger = max(len(left_body), len(right_body))
                if larger and abs(len(left_body) - len(right_body)) / larger > 0.01:
                    continue
                matcher = difflib.SequenceMatcher(
                    None,
                    left_body,
                    right_body,
                    autojunk=False,
                )
                if matcher.quick_ratio() < 0.995:
                    continue
                ratio = matcher.ratio()
                if ratio >= 0.995:
                    near_duplicate_pairs.append((left, right, round(ratio, 6)))
        reach_ratio = len(reached) / len(tests)
        SUBSTANCE_METRICS.update(
            {
                "test_methods": len(tests),
                "public_api_reaching_methods": len(reached),
                "public_api_reach_ratio": round(reach_ratio, 6),
                "unique_behavioral_scenarios": len(
                    [
                        name for name in tests
                        if not name.startswith(("test_054_", "test_056_", "test_057_", "test_058_", "test_059_"))
                    ]
                ),
                "exact_duplicate_groups": duplicate_groups,
                "near_duplicate_pairs_at_0_995": near_duplicate_pairs,
                "distinct_assertion_patterns": len(set(assertion_patterns.values())),
            }
        )
        self.assertGreaterEqual(len(tests), 50)
        self.assertGreaterEqual(reach_ratio, 0.80)
        self.assertEqual(duplicate_groups, [])
        self.assertLessEqual(len(near_duplicate_pairs), 2)
        self.assertGreaterEqual(len(set(assertion_patterns.values())), 12)

    def test_060_validation_depth_nodes_mapping_sequence_key_and_string_bounds(self) -> None:
        null = FrozenCanonicalValue("null")
        deep = null
        for _ in range(self.api.MAX_VALIDATION_DEPTH + 1):
            deep = FrozenCanonicalValue("sequence", sequence_items=(deep,))
        mapping = FrozenCanonicalValue(
            "mapping",
            mapping_items=tuple(
                (f"key-{index:03d}", null)
                for index in range(self.api.MAX_VALIDATION_MAPPING_ITEMS + 1)
            ),
        )
        sequence = FrozenCanonicalValue(
            "sequence",
            sequence_items=(null,) * (self.api.MAX_VALIDATION_SEQUENCE_ITEMS + 1),
        )
        branch = FrozenCanonicalValue(
            "sequence",
            sequence_items=(null,) * self.api.MAX_VALIDATION_SEQUENCE_ITEMS,
        )
        node_heavy = FrozenCanonicalValue(
            "sequence",
            sequence_items=(branch,) * 9,
        )
        long_key = FrozenCanonicalValue(
            "mapping",
            mapping_items=(("k" * (self.api.MAX_VALIDATION_KEY_CHARS + 1), null),),
        )
        long_string = FrozenCanonicalValue(
            "string",
            "s" * (self.api.MAX_VALIDATION_STRING_CHARS + 1),
        )
        large_integer = FrozenCanonicalValue(
            "int",
            self.api.MAX_SAFE_JSON_INTEGER + 1,
        )
        cases = (
            (deep, self.api.ProjectionRejectionCode.VALIDATION_DEPTH_EXCEEDED),
            (mapping, self.api.ProjectionRejectionCode.VALIDATION_MAPPING_LIMIT_EXCEEDED),
            (sequence, self.api.ProjectionRejectionCode.VALIDATION_SEQUENCE_LIMIT_EXCEEDED),
            (node_heavy, self.api.ProjectionRejectionCode.VALIDATION_NODE_LIMIT_EXCEEDED),
            (long_key, self.api.ProjectionRejectionCode.STRING_LIMIT_EXCEEDED),
            (long_string, self.api.ProjectionRejectionCode.STRING_LIMIT_EXCEEDED),
            (large_integer, self.api.ProjectionRejectionCode.INVALID_VALIDATION_VALUE),
        )
        for snapshot, expected_code in cases:
            with self.subTest(code=expected_code.value):
                artifact = _clone_exact_review(
                    self.clear_create,
                    validation_snapshot=snapshot,
                )
                with self.assertRaises(self.api.ProjectionRejected) as captured:
                    self._review_projection(artifact)
                self.assertIs(captured.exception.code, expected_code)

    def test_061_general_string_and_source_body_bounds_fail_closed(self) -> None:
        oversized_title = replace(
            self.clear_create.proposed_content_snapshot,
            title="t" * (self.api.MAX_GENERAL_STRING_CHARS + 1),
        )
        title_artifact = _clone_exact_review(
            self.clear_create,
            proposed_content_snapshot=oversized_title,
        )
        with self.assertRaises(self.api.ProjectionRejected) as title_error:
            self._review_projection(title_artifact)
        self.assertIs(title_error.exception.code, self.api.ProjectionRejectionCode.STRING_LIMIT_EXCEEDED)

        oversized_body = replace(
            self.clear_create.proposed_content_snapshot,
            body_text="b" * (self.api.MAX_SOURCE_BODY_BYTES + 1),
        )
        body_artifact = _clone_exact_review(
            self.clear_create,
            proposed_content_snapshot=oversized_body,
        )
        with self.assertRaises(self.api.ProjectionRejected) as body_error:
            self._review_projection(body_artifact)
        self.assertIs(body_error.exception.code, self.api.ProjectionRejectionCode.STRING_LIMIT_EXCEEDED)

    def test_062_finding_detail_source_bound_fails_closed(self) -> None:
        source = self.review_required.findings[0]
        finding = object.__new__(ConflictFinding)
        object.__setattr__(finding, "code", source.code)
        object.__setattr__(finding, "severity", source.severity)
        object.__setattr__(finding, "message", source.message)
        object.__setattr__(
            finding,
            "details",
            tuple((f"key-{index:03d}", "value") for index in range(257)),
        )
        artifact = _clone_exact_review(self.review_required, findings=(finding,))
        with self.assertRaises(self.api.ProjectionRejected) as captured:
            self._review_projection(artifact)
        self.assertIs(captured.exception.code, self.api.ProjectionRejectionCode.COLLECTION_LIMIT_EXCEEDED)

    def test_063_same_shape_but_unbound_decision_identity_is_rejected(self) -> None:
        decision = self._decision(
            self.clear_create,
            value=decision_contract.HumanReviewDecisionValue.REJECT,
            comment="identity-bound",
        )
        clone = object.__new__(decision_contract.HumanReviewDecision)
        for item in fields(decision_contract.HumanReviewDecision):
            value = getattr(decision, item.name)
            if item.name == "decision_identity":
                value = "kdecision:" + "0" * 64
            object.__setattr__(clone, item.name, value)
        with self.assertRaises(self.api.ProjectionRejected) as captured:
            self._decision_projection(clone)
        self.assertIs(captured.exception.code, self.api.ProjectionRejectionCode.INVALID_DECISION_ARTIFACT)

    def test_064_empty_and_dot_only_source_paths_are_rejected(self) -> None:
        for path in ("", ".", "./", ".\\"):
            with self.subTest(path=repr(path)):
                artifact = self._replace_source_paths(self.clear_create, (path,))
                with self.assertRaises(self.api.ProjectionRejected) as captured:
                    self._review_projection(artifact)
                self.assertIs(captured.exception.code, self.api.ProjectionRejectionCode.UNSAFE_SOURCE_PATH)

    def test_065_exact_review_identity_contract_and_binding_fields_are_preserved(self) -> None:
        projected = self._review_projection(self.clear_update)
        for name in (
            "contract_version", "proposal_id", "proposal_content_hash", "operation",
            "target_stable_id", "expected_vault_revision", "observed_vault_revision",
            "validation_outcome", "stable_id_set_hash", "change_identity",
            "review_artifact_identity",
        ):
            source_value = getattr(self.clear_update, name)
            expected = source_value.value if hasattr(source_value, "value") else source_value
            self.assertEqual(getattr(projected, name), expected, name)

    def test_066_every_representation_field_and_line_profile_value_is_exact(self) -> None:
        source = self.clear_update.representation_delta
        projected = self._review_projection(self.clear_update).representation_delta
        for name in (
            "before_present", "after_present", "terminal_newline_changed",
            "after_source_bytes_known", "source_bytes_changed_text_identical",
            "raw_text_changed_semantic_equal", "semantic_content_changed", "identity",
        ):
            self.assertEqual(getattr(projected, name), getattr(source, name), name)
        for profile_name in ("before_line_endings", "after_line_endings"):
            source_profile = getattr(source, profile_name)
            projected_profile = getattr(projected, profile_name)
            for name in ("crlf_count", "lf_count", "cr_count", "terminal_newline"):
                self.assertEqual(
                    getattr(projected_profile, name),
                    getattr(source_profile, name),
                    f"{profile_name}.{name}",
                )

    def test_067_all_projection_records_are_runtime_frozen(self) -> None:
        review = self._review_projection(self.clear_update)
        decision = self._decision_projection(
            self._decision(
                self.clear_create,
                value=decision_contract.HumanReviewDecisionValue.REJECT,
            )
        )

        def assert_frozen_tree(value):
            if is_dataclass(value) and not isinstance(value, type):
                self.assertTrue(type(value).__dataclass_params__.frozen, type(value).__name__)
                self.assertFalse(hasattr(value, "__dict__"), type(value).__name__)
                for item in fields(value):
                    assert_frozen_tree(getattr(value, item.name))
            elif type(value) is tuple:
                for child in value:
                    assert_frozen_tree(child)

        assert_frozen_tree(review)
        assert_frozen_tree(decision)
        with self.assertRaises(FrozenInstanceError):
            review.proposed_content_snapshot.title = "mutated"
        with self.assertRaises(FrozenInstanceError):
            decision.actor.display_name = "mutated"

    def test_068_real_finding_message_is_bounded_by_bytes_and_lines(self) -> None:
        source = self.review_required.findings[0]
        byte_heavy = ConflictFinding(
            code=source.code,
            severity=source.severity,
            message="🚀" * 800,
            details=source.details,
        )
        line_heavy = ConflictFinding(
            code=source.code,
            severity=source.severity,
            message="строка\n" * 100,
            details=source.details,
        )
        for finding, bound_name in (
            (byte_heavy, "bytes"),
            (line_heavy, "lines"),
        ):
            with self.subTest(bound=bound_name):
                artifact = _clone_exact_review(self.review_required, findings=(finding,))
                message = self._review_projection(artifact).findings.items[0].message
                self.assertTrue(message.truncated)
                self.assertLessEqual(message.preview_utf8_bytes, self.api.MAX_FINDING_MESSAGE_BYTES)
                self.assertLessEqual(message.preview_line_count, self.api.MAX_FINDING_MESSAGE_LINES)

    def test_069_exact_root_type_rejects_review_and_decision_subclasses(self) -> None:
        class ReviewSubclass(KnowledgeChangeReviewArtifact):
            pass

        review_subclass = object.__new__(ReviewSubclass)
        for item in fields(KnowledgeChangeReviewArtifact):
            object.__setattr__(review_subclass, item.name, getattr(self.clear_update, item.name))
        with self.assertRaises(self.api.ProjectionRejected) as review_error:
            self.api.project_knowledge_change_review(review_subclass)
        self.assertIs(review_error.exception.code, self.api.ProjectionRejectionCode.WRONG_REVIEW_ARTIFACT_TYPE)

        decision = self._decision(
            self.clear_create,
            value=decision_contract.HumanReviewDecisionValue.REJECT,
        )

        class DecisionSubclass(decision_contract.HumanReviewDecision):
            pass

        decision_subclass = object.__new__(DecisionSubclass)
        for item in fields(decision_contract.HumanReviewDecision):
            object.__setattr__(decision_subclass, item.name, getattr(decision, item.name))
        with self.assertRaises(self.api.ProjectionRejected) as decision_error:
            self.api.project_human_review_decision(decision_subclass)
        self.assertIs(decision_error.exception.code, self.api.ProjectionRejectionCode.WRONG_DECISION_TYPE)

    def test_070_manual_projection_injection_is_rejected_before_json_escape(self) -> None:
        projected = self._review_projection(self.clear_update)
        mutable_injection = replace(projected, status=["CLEAR"])
        with self.assertRaises(self.api.ProjectionRejected) as mutable_error:
            self.api.materialize_json_value(mutable_injection)
        self.assertIs(mutable_error.exception.code, self.api.ProjectionRejectionCode.SERIALIZATION_FAILED)

        delta = replace(
            projected.representation_delta,
            before_present=self.api.MAX_SAFE_JSON_INTEGER + 1,
        )
        integer_injection = replace(projected, representation_delta=delta)
        with self.assertRaises(self.api.ProjectionRejected) as integer_error:
            self.api.materialize_json_value(integer_injection)
        self.assertIs(integer_error.exception.code, self.api.ProjectionRejectionCode.SERIALIZATION_FAILED)

    def test_071_stable_id_and_windows_normalized_traversal_are_rejected(self) -> None:
        invalid_target = _clone_exact_review(
            self.clear_update,
            target_stable_id=r"C:\secret\note.md",
        )
        with self.assertRaises(self.api.ProjectionRejected) as stable_id_error:
            self._review_projection(invalid_target)
        self.assertIs(stable_id_error.exception.code, self.api.ProjectionRejectionCode.INVALID_REVIEW_ARTIFACT)

        traversal = self._replace_source_paths(
            self.clear_create,
            ("notes/.. /secret.md",),
        )
        with self.assertRaises(self.api.ProjectionRejected) as traversal_error:
            self._review_projection(traversal)
        self.assertIs(traversal_error.exception.code, self.api.ProjectionRejectionCode.UNSAFE_SOURCE_PATH)

    def test_072_summary_projection_has_exact_bounded_queue_fields(self) -> None:
        summary = self._review_summary_projection(self.review_required)
        value = self._materialize(summary)
        self.assertIs(type(summary), self.api.KnowledgeChangeReviewSummaryProjection)
        self.assertEqual(
            set(value),
            {
                "projection_contract",
                "kind",
                "contract_version",
                "status",
                "blocked",
                "proposal_id",
                "target_stable_id",
                "operation",
                "expected_vault_revision",
                "observed_vault_revision",
                "review_artifact_identity",
                "change_identity",
                "finding_count",
                "normal_change_material_present",
                "detail_projection_truncated",
            },
        )
        self.assertEqual(value["projection_contract"], self.api.PROJECTION_CONTRACT_VERSION)
        self.assertEqual(value["kind"], "KNOWLEDGE_CHANGE_REVIEW_SUMMARY")
        self.assertEqual(value["finding_count"], len(self.review_required.findings))
        self.assertNotIn("body_text", value)
        self.assertNotIn("validation_snapshot", value)
        self.assertNotIn("human_review_preview", value)
        self.assertNotIn("findings", value)

    def test_073_summary_is_derived_by_calling_the_accepted_full_projector(self) -> None:
        original = self.api.project_knowledge_change_review
        with mock.patch.object(
            self.api,
            "project_knowledge_change_review",
            wraps=original,
        ) as full_projector:
            summary = self._review_summary_projection(self.clear_update)
        full_projector.assert_called_once_with(self.clear_update)
        self.assertEqual(summary.review_artifact_identity, self.clear_update.review_artifact_identity)
        self.assertTrue(summary.normal_change_material_present)

    def test_074_blocked_summary_preserves_absence_without_authority_fields(self) -> None:
        summary = self._review_summary_projection(self.blocked)
        value = self._materialize(summary)
        self.assertEqual(summary.status, "BLOCKED")
        self.assertTrue(summary.blocked)
        self.assertIsNone(summary.change_identity)
        self.assertFalse(summary.normal_change_material_present)
        serialized = json.dumps(value, sort_keys=True)
        for forbidden in (
            "decision_identity",
            "grants_write_authority",
            "human_identity_authenticated",
            "human_review_preview",
            "validation_snapshot",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_075_summary_truncation_fact_is_truthful_and_canonical(self) -> None:
        artifact = self._large_update()
        summary = self._review_summary_projection(artifact)
        first = self._canonical(summary)
        second = self._canonical(summary)
        self.assertTrue(summary.detail_projection_truncated)
        self.assertEqual(first, second)
        self.assertLessEqual(len(first), self.api.MAX_TOTAL_JSON_BYTES)
        self.assertEqual(json.loads(first.decode("utf-8")), self._materialize(summary))

    def test_076_summary_is_frozen_fresh_and_rejects_wrong_source_type(self) -> None:
        summary = self._review_summary_projection(self.clear_create)
        self.assertFalse(hasattr(summary, "__dict__"))
        with self.assertRaises(FrozenInstanceError):
            summary.status = "BLOCKED"
        first = self._materialize(summary)
        second = self._materialize(summary)
        self.assertTrue(_container_ids(first).isdisjoint(_container_ids(second)))
        first["status"] = "MUTATED"
        self.assertEqual(second["status"], "CLEAR")
        with self.assertRaises(self.api.ProjectionRejected) as captured:
            self.api.project_knowledge_change_review_summary({"artifact": self.clear_create})
        self.assertIs(
            captured.exception.code,
            self.api.ProjectionRejectionCode.WRONG_REVIEW_ARTIFACT_TYPE,
        )


def _run() -> int:
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ProjectionBehaviorTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    evidence = {
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "successful": result.wasSuccessful(),
        "construction_counts": CONSTRUCTION_COUNTS,
        "fake_dependency_results": sorted(
            FAKE_DEPENDENCY_RESULTS,
            key=lambda item: str(item["dependency"]),
        ),
        "fault_results": FAULT_RESULTS,
        "substance_metrics": SUBSTANCE_METRICS,
    }
    print("PROJECTION_EVIDENCE_JSON=" + json.dumps(evidence, sort_keys=True, ensure_ascii=False))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(_run())
