"""Focused behavioral tests for v6.84.5.1e9c Human Review Decision."""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, fields
import difflib
import hashlib
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import types
import unittest
from unittest import mock

sys.dont_write_bytecode = True

from modules.knowledge_change_proposal_ru import (
    CONTRACT_VERSION as E9A_CONTRACT_VERSION,
    CanonicalLocationHint,
    KnowledgeChangeProposal,
    ProposalOperation,
    ProposalValidator,
    ProposerMetadata,
    ProposedNoteContent,
    Provenance,
    ValidationResult,
    compute_proposal_instance_id,
)
from modules.knowledge_change_review_ru import (
    CONTRACT_VERSION as E9B_CONTRACT_VERSION,
    CurrentKnowledgeState,
    KnowledgeChangeReviewArtifact,
    ReviewStatus,
    analyze_review,
    create_trusted_target_snapshot,
)
import modules.knowledge_change_review_decision_ru as decision_contract


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "modules" / "knowledge_change_review_decision_ru.py"
TEST_PATH = Path(__file__).resolve()
REV_A = "sha256:" + "a" * 64
REV_B = "sha256:" + "b" * 64
TARGET = "canonical.current-state"
CLEAR_TARGET = "test.e9c-clear"
BLOCKED_TARGET = "test.e9c-blocked"


def _source_text() -> str:
    return MODULE_PATH.read_text(encoding="utf-8")


def _clone_review(
    artifact: KnowledgeChangeReviewArtifact,
    **changes: object,
) -> KnowledgeChangeReviewArtifact:
    clone = object.__new__(KnowledgeChangeReviewArtifact)
    for item in fields(KnowledgeChangeReviewArtifact):
        object.__setattr__(clone, item.name, changes.get(item.name, getattr(artifact, item.name)))
    return clone


class HumanReviewDecisionBehaviorTests(unittest.TestCase):
    api = decision_contract
    record_counts = True
    counters = {
        "proposer_metadata": 0,
        "provenance": 0,
        "proposed_content": 0,
        "knowledge_change_proposals": 0,
        "proposal_validators": 0,
        "validation_results": 0,
        "trusted_target_snapshots": 0,
        "current_knowledge_states": 0,
        "knowledge_change_review_artifacts": 0,
        "human_review_decisions": 0,
    }
    fault_results: tuple[dict[str, object], ...] = ()

    def _count(self, name: str, amount: int = 1) -> None:
        if self.record_counts:
            type(self).counters[name] += amount

    def _make_proposal(
        self,
        *,
        operation: ProposalOperation,
        target: str,
        revision: str,
        body: str,
    ) -> KnowledgeChangeProposal:
        proposer = ProposerMetadata(
            agent_type="focused-test",
            agent_instance_id="e9c-instance",
            model_identifier="none",
            source_workflow="e9c-human-review",
        )
        self._count("proposer_metadata")
        provenance = Provenance(
            reason="Exercise the exact e9c review-decision boundary",
            source_observation="real e9a/e9b in-memory artifact",
            related_stable_ids=(target,),
            workflow_origin="focused-test",
        )
        self._count("provenance")
        content = ProposedNoteContent(
            title="Decision Contract Fixture",
            body_text=body,
            type="project_state",
            status="proposed",
            knowledge_layer="canonical",
            evidence_class="A",
            authority="repository",
            canonical=operation is ProposalOperation.UPDATE_EXISTING,
            canonical_scope="current-state" if operation is ProposalOperation.UPDATE_EXISTING else None,
            aliases=("decision-fixture",),
            releases=("v6.84.5.1e9c",),
            source_paths=("modules/knowledge_change_review_decision_ru.py",),
            evidence_refs=("E9C-FOCUSED",),
            updated="2026-07-16",
            last_reviewed="2026-07-16",
        )
        self._count("proposed_content")
        hint = (
            CanonicalLocationHint(relative_path=f"tests/{target}.md")
            if operation is ProposalOperation.CREATE_NEW
            else None
        )
        temporary = KnowledgeChangeProposal(
            proposal_id="kprop:" + "0" * 64,
            contract_version=E9A_CONTRACT_VERSION,
            operation=operation,
            target_stable_id=target,
            expected_vault_revision=revision,
            proposer=proposer,
            provenance=provenance,
            proposed_content=content,
            canonical_location_hint=hint,
        )
        proposal = KnowledgeChangeProposal(
            proposal_id=compute_proposal_instance_id(temporary),
            contract_version=E9A_CONTRACT_VERSION,
            operation=operation,
            target_stable_id=target,
            expected_vault_revision=revision,
            proposer=proposer,
            provenance=provenance,
            proposed_content=content,
            canonical_location_hint=hint,
        )
        self._count("knowledge_change_proposals", 2)
        return proposal

    def _build_review(
        self,
        status: ReviewStatus,
        *,
        revision: str = REV_A,
    ) -> tuple[
        KnowledgeChangeProposal,
        ValidationResult,
        CurrentKnowledgeState,
        KnowledgeChangeReviewArtifact,
    ]:
        if status is ReviewStatus.CLEAR:
            operation = ProposalOperation.CREATE_NEW
            target = CLEAR_TARGET
            validator_ids = {TARGET}
            state_ids = {TARGET}
            current = None
        elif status is ReviewStatus.REVIEW_REQUIRED:
            operation = ProposalOperation.UPDATE_EXISTING
            target = TARGET
            validator_ids = {TARGET}
            state_ids = {TARGET}
            current = create_trusted_target_snapshot(
                source_bytes=b"before\n",
                source_relative_path="canonical/current-state.md",
                target_stable_id=TARGET,
                captured_vault_revision=revision,
            )
            self._count("trusted_target_snapshots")
        elif status is ReviewStatus.BLOCKED:
            operation = ProposalOperation.CREATE_NEW
            target = BLOCKED_TARGET
            validator_ids = {TARGET}
            state_ids = {TARGET, BLOCKED_TARGET}
            current = None
        else:
            raise AssertionError("unsupported fixture status")

        proposal = self._make_proposal(
            operation=operation,
            target=target,
            revision=revision,
            body=f"after-{status.value}\n",
        )
        validator = ProposalValidator(revision, validator_ids)
        self._count("proposal_validators")
        validation = validator.validate(proposal)
        self._count("validation_results")
        state = CurrentKnowledgeState(
            observed_vault_revision=revision,
            current_stable_ids=state_ids,
            current_target=current,
            baseline_target=None,
        )
        self._count("current_knowledge_states")
        artifact = analyze_review(proposal, validation, state)
        self._count("knowledge_change_review_artifacts")
        if artifact.status is not status:
            raise AssertionError(f"fixture status mismatch: {artifact.status} != {status}")
        return proposal, validation, state, artifact

    def setUp(self) -> None:
        self.actor = self.api.HumanReviewerMetadata(
            actor_identifier="human-reviewer-001",
            display_name="Local Reviewer",
            source="local-human-review",
        )
        self.clear_inputs = self._build_review(ReviewStatus.CLEAR)
        self.required_inputs = self._build_review(ReviewStatus.REVIEW_REQUIRED)
        self.blocked_inputs = self._build_review(ReviewStatus.BLOCKED)
        self.clear = self.clear_inputs[-1]
        self.required = self.required_inputs[-1]
        self.blocked = self.blocked_inputs[-1]

    def _decision_kwargs(
        self,
        artifact: KnowledgeChangeReviewArtifact,
        **overrides: object,
    ) -> dict[str, object]:
        values: dict[str, object] = {
            "expected_proposal_id": artifact.proposal_id,
            "expected_review_artifact_identity": artifact.review_artifact_identity,
            "expected_change_identity": artifact.change_identity,
            "expected_observed_vault_revision": artifact.observed_vault_revision,
            "current_observed_vault_revision": artifact.observed_vault_revision,
            "decision": self.api.HumanReviewDecisionValue.REJECT,
            "comment": "",
            "actor": self.actor,
        }
        values.update(overrides)
        return values

    def decide(
        self,
        artifact: KnowledgeChangeReviewArtifact,
        **overrides: object,
    ):
        result = self.api.create_human_review_decision(
            artifact,
            **self._decision_kwargs(artifact, **overrides),
        )
        if self.record_counts and self.api is decision_contract:
            type(self).counters["human_review_decisions"] += 1
        return result

    def assert_rejection(self, expected_code, callback) -> None:
        with self.assertRaises(self.api.HumanReviewDecisionRejected) as captured:
            callback()
        self.assertIs(captured.exception.code, expected_code)
        self.assertEqual(str(captured.exception), expected_code.value)

    def _independent_identity(self, decision, *, domain: str | None = None) -> str:
        semantics = {
            "hard_stop": decision.hard_stop,
            "review_decision_only": decision.review_decision_only,
            "actor_metadata_evidence_only": decision.actor_metadata_evidence_only,
            "human_identity_authenticated": decision.human_identity_authenticated,
            "grants_write_authority": decision.grants_write_authority,
            "grants_vault_write_authority": decision.grants_vault_write_authority,
            "grants_persistence_authority": decision.grants_persistence_authority,
            "grants_publication_authority": decision.grants_publication_authority,
            "grants_merge_authority": decision.grants_merge_authority,
            "grants_rebase_authority": decision.grants_rebase_authority,
            "grants_execution_authority": decision.grants_execution_authority,
            "grants_policy_authority": decision.grants_policy_authority,
            "grants_model_gateway_authority": decision.grants_model_gateway_authority,
            "grants_tauri_frontend_authority": decision.grants_tauri_frontend_authority,
            "grants_automatic_approval_authority": decision.grants_automatic_approval_authority,
        }
        payload = {
            "decision_contract_version": decision.contract_version,
            "review_contract_version": decision.review_contract_version,
            "review_status": decision.review_status.value,
            "proposal_id": decision.proposal_id,
            "review_artifact_identity": decision.review_artifact_identity,
            "change_identity": decision.change_identity,
            "observed_vault_revision": decision.observed_vault_revision,
            "decision": decision.decision.value,
            "comment": decision.comment,
            "actor": {
                "actor_identifier": decision.actor.actor_identifier,
                "display_name": decision.actor.display_name,
                "source": decision.actor.source,
            },
            "semantics": semantics,
        }
        envelope = {
            "domain": domain or self.api.IDENTITY_DOMAIN,
            "version": self.api.IDENTITY_VERSION,
            "payload": payload,
        }
        canonical = json.dumps(
            envelope,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return "kdecision:" + hashlib.sha256(canonical).hexdigest()

    def test_001_static_real_e9b_import_and_public_contract(self) -> None:
        decision = self.decide(self.clear)
        self.assertEqual(self.api.REVIEW_CONTRACT_VERSION, E9B_CONTRACT_VERSION)
        self.assertIs(self.api.KnowledgeChangeReviewArtifact, KnowledgeChangeReviewArtifact)
        self.assertEqual(decision.contract_version, "localcomet.knowledge-change-review-decision/1.0")

    def test_002_clear_approve_accepts_empty_comment(self) -> None:
        decision = self.decide(
            self.clear,
            decision=self.api.HumanReviewDecisionValue.APPROVE,
            comment="",
        )
        self.assertIs(decision.decision, self.api.HumanReviewDecisionValue.APPROVE)
        self.assertIsNotNone(decision.change_identity)
        self.assertEqual(decision.comment, "")

    def test_003_clear_reject_accepts_exact_string_value(self) -> None:
        decision = self.decide(self.clear, decision="REJECT", comment="not selected")
        self.assertIs(decision.decision, self.api.HumanReviewDecisionValue.REJECT)
        self.assertEqual(decision.review_status, ReviewStatus.CLEAR)
        self.assertEqual(decision.comment, "not selected")

    def test_004_clear_request_changes_accepts_comment(self) -> None:
        decision = self.decide(
            self.clear,
            decision=self.api.HumanReviewDecisionValue.REQUEST_CHANGES,
            comment="Please add evidence.",
        )
        self.assertEqual(decision.decision.value, "REQUEST_CHANGES")
        self.assertEqual(decision.proposal_id, self.clear.proposal_id)

    def test_005_review_required_approve_is_allowed_with_change_identity(self) -> None:
        decision = self.decide(self.required, decision="APPROVE")
        self.assertEqual(decision.review_status, ReviewStatus.REVIEW_REQUIRED)
        self.assertTrue(decision.change_identity.startswith("kchange:"))

    def test_006_review_required_reject_is_allowed(self) -> None:
        decision = self.decide(self.required, decision="REJECT", comment="reviewed")
        self.assertEqual(decision.decision.value, "REJECT")
        self.assertEqual(decision.review_artifact_identity, self.required.review_artifact_identity)

    def test_007_review_required_request_changes_is_allowed(self) -> None:
        decision = self.decide(
            self.required,
            decision="REQUEST_CHANGES",
            comment="Resolve the missing historical baseline.",
        )
        self.assertEqual(decision.comment, "Resolve the missing historical baseline.")
        self.assertEqual(decision.observed_vault_revision, REV_A)

    def test_008_blocked_approve_is_forbidden(self) -> None:
        self.assert_rejection(
            self.api.HumanReviewDecisionRejectionCode.BLOCKED_APPROVAL_FORBIDDEN,
            lambda: self.decide(self.blocked, decision="APPROVE"),
        )
        self.assertIsNone(self.blocked.change_identity)

    def test_009_blocked_reject_is_allowed_when_fresh_and_exact(self) -> None:
        decision = self.decide(self.blocked, decision="REJECT", comment="blocked")
        self.assertEqual(decision.review_status, ReviewStatus.BLOCKED)
        self.assertIsNone(decision.change_identity)
        self.assertTrue(decision.hard_stop)

    def test_010_blocked_request_changes_is_allowed_when_fresh_and_exact(self) -> None:
        decision = self.decide(
            self.blocked,
            decision="REQUEST_CHANGES",
            comment="Remove the stable-ID collision.",
        )
        self.assertIsNone(decision.change_identity)
        self.assertEqual(decision.decision.value, "REQUEST_CHANGES")

    def test_011_approve_requires_non_null_change_identity(self) -> None:
        without_change = _clone_review(self.clear, change_identity=None)
        self.assert_rejection(
            self.api.HumanReviewDecisionRejectionCode.APPROVAL_REQUIRES_CHANGE_IDENTITY,
            lambda: self.decide(without_change, decision="APPROVE"),
        )
        self.assertIsNone(without_change.change_identity)

    def test_012_exact_proposal_id_binding_rejects_mismatch(self) -> None:
        self.assert_rejection(
            self.api.HumanReviewDecisionRejectionCode.PROPOSAL_ID_MISMATCH,
            lambda: self.decide(
                self.clear,
                expected_proposal_id="kprop:" + "f" * 64,
            ),
        )
        self.assertNotEqual(self.clear.proposal_id, "kprop:" + "f" * 64)

    def test_013_bindings_for_artifact_a_are_rejected_for_artifact_b(self) -> None:
        values = self._decision_kwargs(self.clear)
        self.assert_rejection(
            self.api.HumanReviewDecisionRejectionCode.PROPOSAL_ID_MISMATCH,
            lambda: self.api.create_human_review_decision(self.required, **values),
        )
        self.assertNotEqual(self.clear.review_artifact_identity, self.required.review_artifact_identity)

    def test_014_review_artifact_identity_mismatch_is_rejected(self) -> None:
        self.assert_rejection(
            self.api.HumanReviewDecisionRejectionCode.REVIEW_ARTIFACT_IDENTITY_MISMATCH,
            lambda: self.decide(
                self.clear,
                expected_review_artifact_identity="kreview:" + "e" * 64,
            ),
        )
        self.assertTrue(self.clear.review_artifact_identity.startswith("kreview:"))

    def test_015_change_identity_mismatch_is_rejected(self) -> None:
        self.assert_rejection(
            self.api.HumanReviewDecisionRejectionCode.CHANGE_IDENTITY_MISMATCH,
            lambda: self.decide(
                self.clear,
                expected_change_identity="kchange:" + "d" * 64,
            ),
        )
        self.assertNotEqual(self.clear.change_identity, "kchange:" + "d" * 64)

    def test_016_exact_none_change_identity_binding_is_preserved(self) -> None:
        decision = self.decide(
            self.blocked,
            expected_change_identity=None,
            decision="REJECT",
        )
        self.assertIsNone(decision.change_identity)
        self.assertIsNone(self.blocked.change_identity)

    def test_017_non_none_expectation_for_none_change_identity_is_rejected(self) -> None:
        self.assert_rejection(
            self.api.HumanReviewDecisionRejectionCode.CHANGE_IDENTITY_MISMATCH,
            lambda: self.decide(
                self.blocked,
                expected_change_identity="kchange:" + "c" * 64,
                decision="REJECT",
            ),
        )
        self.assertEqual(self.blocked.status, ReviewStatus.BLOCKED)

    def test_018_expected_observed_revision_mismatch_is_rejected(self) -> None:
        self.assert_rejection(
            self.api.HumanReviewDecisionRejectionCode.OBSERVED_VAULT_REVISION_MISMATCH,
            lambda: self.decide(self.clear, expected_observed_vault_revision=REV_B),
        )
        self.assertEqual(self.clear.observed_vault_revision, REV_A)

    def test_019_current_observed_revision_drift_is_rejected(self) -> None:
        self.assert_rejection(
            self.api.HumanReviewDecisionRejectionCode.STALE_CURRENT_VAULT_REVISION,
            lambda: self.decide(self.clear, current_observed_vault_revision=REV_B),
        )
        self.assertNotEqual(REV_A, REV_B)

    def test_020_unsupported_review_contract_is_rejected(self) -> None:
        unsupported = _clone_review(self.clear, contract_version="unsupported/9")
        self.assert_rejection(
            self.api.HumanReviewDecisionRejectionCode.UNSUPPORTED_REVIEW_CONTRACT,
            lambda: self.decide(unsupported),
        )
        self.assertIs(type(unsupported), KnowledgeChangeReviewArtifact)

    def test_021_wrong_review_artifact_type_is_rejected(self) -> None:
        values = self._decision_kwargs(self.clear)
        self.assert_rejection(
            self.api.HumanReviewDecisionRejectionCode.WRONG_REVIEW_ARTIFACT_TYPE,
            lambda: self.api.create_human_review_decision({}, **values),
        )
        self.assertNotIsInstance({}, KnowledgeChangeReviewArtifact)

    def test_022_unsupported_decision_is_exact_and_case_sensitive(self) -> None:
        self.assert_rejection(
            self.api.HumanReviewDecisionRejectionCode.UNSUPPORTED_DECISION,
            lambda: self.decide(self.clear, decision="approve"),
        )
        self.assertNotIn("approve", tuple(item.value for item in self.api.HumanReviewDecisionValue))

    def test_023_request_changes_empty_comment_is_rejected(self) -> None:
        self.assert_rejection(
            self.api.HumanReviewDecisionRejectionCode.COMMENT_REQUIRED,
            lambda: self.decide(self.clear, decision="REQUEST_CHANGES", comment=""),
        )
        self.assertEqual("".strip(), "")

    def test_024_request_changes_whitespace_comment_is_rejected_without_rewrite(self) -> None:
        raw = " \t\n "
        self.assert_rejection(
            self.api.HumanReviewDecisionRejectionCode.COMMENT_REQUIRED,
            lambda: self.decide(self.clear, decision="REQUEST_CHANGES", comment=raw),
        )
        self.assertEqual(raw, " \t\n ")

    def test_025_comment_character_bound_is_enforced(self) -> None:
        raw = "x" * (self.api.MAX_COMMENT_CHARS + 1)
        self.assert_rejection(
            self.api.HumanReviewDecisionRejectionCode.COMMENT_CHARACTER_LIMIT_EXCEEDED,
            lambda: self.decide(self.clear, decision="REJECT", comment=raw),
        )
        self.assertEqual(len(raw), 2_001)

    def test_026_comment_utf8_byte_bound_is_enforced_independently(self) -> None:
        raw = "🚀" * ((self.api.MAX_COMMENT_UTF8_BYTES // 4) + 1)
        self.assertLess(len(raw), self.api.MAX_COMMENT_CHARS)
        self.assert_rejection(
            self.api.HumanReviewDecisionRejectionCode.COMMENT_UTF8_BYTE_LIMIT_EXCEEDED,
            lambda: self.decide(self.clear, decision="REJECT", comment=raw),
        )
        self.assertGreater(len(raw.encode("utf-8")), self.api.MAX_COMMENT_UTF8_BYTES)
        self.assert_rejection(
            self.api.HumanReviewDecisionRejectionCode.COMMENT_UTF8_ENCODING_INVALID,
            lambda: self.decide(self.clear, decision="REJECT", comment="\ud800"),
        )

    def test_027_unicode_comment_is_preserved_exactly(self) -> None:
        raw = "  Нужны доказательства — café 中文 🚀  "
        decision = self.decide(self.clear, decision="REQUEST_CHANGES", comment=raw)
        self.assertEqual(decision.comment, raw)
        self.assertEqual(decision.comment.encode("utf-8"), raw.encode("utf-8"))
        self.assertTrue(decision.comment.startswith("  "))

    def test_028_comment_exact_bytes_participate_in_identity(self) -> None:
        composed = self.decide(self.clear, decision="REJECT", comment="é")
        decomposed = self.decide(self.clear, decision="REJECT", comment="e\u0301")
        self.assertNotEqual(composed.comment.encode("utf-8"), decomposed.comment.encode("utf-8"))
        self.assertNotEqual(composed.decision_identity, decomposed.decision_identity)

    def test_029_actor_identifier_bound_and_type_are_enforced(self) -> None:
        with self.assertRaises(ValueError):
            self.api.HumanReviewerMetadata(
                actor_identifier="x" * (self.api.MAX_ACTOR_IDENTIFIER_CHARS + 1),
                display_name="Reviewer",
                source="local",
            )
        with self.assertRaisesRegex(ValueError, "exact string"):
            self.api.HumanReviewerMetadata(
                actor_identifier=7,
                display_name="Reviewer",
                source="local",
            )
        byte_overflow = "🚀" * (self.api.MAX_ACTOR_IDENTIFIER_UTF8_BYTES // 4 + 1)
        self.assertLessEqual(len(byte_overflow), self.api.MAX_ACTOR_IDENTIFIER_CHARS)
        with self.assertRaisesRegex(ValueError, "UTF-8 bytes"):
            self.api.HumanReviewerMetadata(byte_overflow, "Reviewer", "local")
        decision = self.decide(self.clear)
        self.assertEqual(decision.actor.actor_identifier, "human-reviewer-001")

    def test_030_actor_display_name_bound_is_enforced(self) -> None:
        with self.assertRaisesRegex(ValueError, "display_name"):
            self.api.HumanReviewerMetadata(
                actor_identifier="reviewer",
                display_name="x" * (self.api.MAX_ACTOR_DISPLAY_NAME_CHARS + 1),
                source="local",
            )
        byte_overflow = "🚀" * (self.api.MAX_ACTOR_DISPLAY_NAME_UTF8_BYTES // 4 + 1)
        self.assertLessEqual(len(byte_overflow), self.api.MAX_ACTOR_DISPLAY_NAME_CHARS)
        with self.assertRaisesRegex(ValueError, "UTF-8 bytes"):
            self.api.HumanReviewerMetadata("reviewer", byte_overflow, "local")
        decision = self.decide(self.required)
        self.assertEqual(decision.actor.display_name, "Local Reviewer")

    def test_031_actor_source_bound_and_required_content_are_enforced(self) -> None:
        with self.assertRaises(ValueError):
            self.api.HumanReviewerMetadata("reviewer", "Reviewer", " " * 3)
        with self.assertRaises(ValueError):
            self.api.HumanReviewerMetadata(
                "reviewer",
                "Reviewer",
                "s" * (self.api.MAX_ACTOR_SOURCE_CHARS + 1),
            )
        byte_overflow = "🚀" * (self.api.MAX_ACTOR_SOURCE_UTF8_BYTES // 4 + 1)
        self.assertLessEqual(len(byte_overflow), self.api.MAX_ACTOR_SOURCE_CHARS)
        with self.assertRaisesRegex(ValueError, "UTF-8 bytes"):
            self.api.HumanReviewerMetadata("reviewer", "Reviewer", byte_overflow)
        self.assertEqual(self.decide(self.clear).actor.source, "local-human-review")

    def test_032_actor_metadata_participates_in_identity(self) -> None:
        first = self.decide(self.clear, decision="REJECT")
        other_actor = self.api.HumanReviewerMetadata(
            "human-reviewer-002",
            "Local Reviewer",
            "local-human-review",
        )
        second = self.decide(self.clear, decision="REJECT", actor=other_actor)
        self.assertNotEqual(first.actor.actor_identifier, second.actor.actor_identifier)
        self.assertNotEqual(first.decision_identity, second.decision_identity)

    def test_033_actor_is_evidence_only_and_cannot_grant_authority(self) -> None:
        claimant = self.api.HumanReviewerMetadata(
            "administrator",
            "Claims Authority",
            "claims-publication-and-execution-authority",
        )
        decision = self.decide(self.clear, decision="APPROVE", actor=claimant)
        self.assertTrue(decision.actor_metadata_evidence_only)
        self.assertFalse(decision.human_identity_authenticated)
        self.assertFalse(any(
            getattr(decision, name)
            for name in (
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
        ))

    def test_034_identity_is_deterministic_for_identical_input(self) -> None:
        first = self.decide(self.clear, decision="APPROVE", comment="same")
        second = self.decide(self.clear, decision="APPROVE", comment="same")
        self.assertEqual(first, second)
        self.assertEqual(first.decision_identity, second.decision_identity)
        self.assertRegex(first.decision_identity, r"^kdecision:[0-9a-f]{64}$")

    def test_035_identity_uses_independent_canonical_domain_separation_oracle(self) -> None:
        decision = self.decide(self.clear, decision="REJECT", comment="Космос")
        expected = self._independent_identity(decision)
        other_domain = self._independent_identity(decision, domain="OTHER_DOMAIN")
        self.assertEqual(decision.decision_identity, expected)
        self.assertNotEqual(decision.decision_identity, other_domain)

    def test_036_every_variable_governed_input_changes_identity(self) -> None:
        baseline = self.decide(self.clear, decision="APPROVE", comment="")
        boundary = self.api._authority_boundary_values()
        inputs = {
            "contract_version": baseline.contract_version,
            "review_contract_version": baseline.review_contract_version,
            "review_status": baseline.review_status,
            "proposal_id": baseline.proposal_id,
            "review_artifact_identity": baseline.review_artifact_identity,
            "change_identity": baseline.change_identity,
            "observed_vault_revision": baseline.observed_vault_revision,
            "decision": baseline.decision,
            "comment": baseline.comment,
            "actor": baseline.actor,
            "boundary": boundary,
        }

        def identity(**changes: object) -> str:
            governed = dict(inputs)
            governed.update(changes)
            return self.api._compute_decision_identity(**governed)

        self.assertEqual(identity(), baseline.decision_identity)
        variants = {
            "decision_contract_version": identity(contract_version="other-decision-contract"),
            "review_contract_version": identity(review_contract_version="other-review-contract"),
            "review_status": identity(review_status=ReviewStatus.REVIEW_REQUIRED),
            "proposal_id": identity(proposal_id="kprop:" + "f" * 64),
            "review_artifact_identity": identity(
                review_artifact_identity="kreview:" + "f" * 64
            ),
            "change_identity": identity(change_identity="kchange:" + "f" * 64),
            "observed_vault_revision": identity(
                observed_vault_revision="sha256:" + "f" * 64
            ),
            "decision": identity(decision=self.api.HumanReviewDecisionValue.REJECT),
            "comment": identity(comment="comment"),
            "actor_identifier": identity(
                actor=self.api.HumanReviewerMetadata(
                    "other-reviewer",
                    baseline.actor.display_name,
                    baseline.actor.source,
                )
            ),
            "actor_display_name": identity(
                actor=self.api.HumanReviewerMetadata(
                    baseline.actor.actor_identifier,
                    "Other Reviewer",
                    baseline.actor.source,
                )
            ),
            "actor_source": identity(
                actor=self.api.HumanReviewerMetadata(
                    baseline.actor.actor_identifier,
                    baseline.actor.display_name,
                    "other-source",
                )
            ),
        }
        for index, (name, value) in enumerate(boundary):
            changed_boundary = tuple(
                (item_name, not item_value if item_index == index else item_value)
                for item_index, (item_name, item_value) in enumerate(boundary)
            )
            variants[f"semantics.{name}"] = identity(boundary=changed_boundary)

        unchanged_fields = tuple(
            name
            for name, changed_identity in variants.items()
            if changed_identity == baseline.decision_identity
        )
        self.assertEqual(unchanged_fields, ())
        self.assertEqual(len(set(variants.values())), len(variants))

    def test_037_returned_artifact_is_frozen_and_has_no_mutable_collections(self) -> None:
        decision = self.decide(self.clear)
        with self.assertRaises(FrozenInstanceError):
            decision.comment = "mutated"
        stored_values = tuple(getattr(decision, item.name) for item in fields(decision))
        self.assertFalse(any(isinstance(value, (dict, list, set, bytearray)) for value in stored_values))

    def test_038_actor_metadata_is_frozen(self) -> None:
        decision = self.decide(self.clear)
        with self.assertRaises(FrozenInstanceError):
            decision.actor.source = "changed"
        self.assertEqual(decision.actor, self.actor)
        self.assertIs(type(decision.actor), self.api.HumanReviewerMetadata)

    def test_039_caller_owned_inputs_are_not_mutated(self) -> None:
        artifact_before = repr(self.clear)
        actor_before = repr(self.actor)
        raw_comment = "  exact caller text  "
        decision = self.decide(self.clear, decision="REJECT", comment=raw_comment)
        self.assertEqual(repr(self.clear), artifact_before)
        self.assertEqual(repr(self.actor), actor_before)
        self.assertEqual(decision.comment, raw_comment)

    def test_040_identity_ignores_ambient_time_environment_and_paths(self) -> None:
        first = self.decide(self.clear, decision="REJECT", comment="ambient-free")
        with mock.patch.dict(os.environ, {"HOSTNAME": "different", "LANG": "xx_YY"}, clear=True):
            second = self.decide(self.clear, decision="REJECT", comment="ambient-free")
        source_tree = ast.parse(_source_text())
        imported = {
            alias.name.split(".")[0]
            for node in ast.walk(source_tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertEqual(first.decision_identity, second.decision_identity)
        self.assertTrue({"os", "pathlib", "time", "datetime", "random", "uuid"}.isdisjoint(imported))

    def test_041_module_has_no_filesystem_write_runtime(self) -> None:
        tree = ast.parse(_source_text())
        forbidden_calls = {"open", "write_text", "write_bytes", "mkdir", "unlink", "rename", "replace"}
        called = {
            node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, (ast.Attribute, ast.Name))
        }
        with mock.patch("builtins.open", side_effect=AssertionError("write path")):
            decision = self.decide(self.clear)
        self.assertTrue(forbidden_calls.isdisjoint(called))
        self.assertTrue(decision.hard_stop)

    def test_042_module_has_no_persistence_registry_database_or_consumer_api(self) -> None:
        decision = self.decide(self.required, decision="REJECT")
        tree = ast.parse(_source_text())
        imported = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        exported = set(self.api.__all__)
        self.assertTrue({"sqlite3", "shelve", "dbm", "pickle"}.isdisjoint(imported))
        self.assertTrue({"apply", "publish", "persist", "execute", "registry", "store"}.isdisjoint(exported))
        self.assertTrue(decision.review_decision_only)

    def test_043_module_has_no_network_model_tauri_or_frontend_coupling(self) -> None:
        tree = ast.parse(_source_text())
        imported = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        with mock.patch.object(socket, "socket", side_effect=AssertionError("network")):
            decision = self.decide(self.clear)
        forbidden = {
            "socket",
            "urllib",
            "http",
            "requests",
            "browser",
            "openai",
            "tauri",
            "frontend",
            "model_gateway",
        }
        self.assertTrue(forbidden.isdisjoint(imported))
        self.assertFalse(decision.grants_model_gateway_authority)
        self.assertFalse(decision.grants_tauri_frontend_authority)

    def test_044_module_has_no_subprocess_or_shell_runtime(self) -> None:
        with (
            mock.patch.object(subprocess, "run", side_effect=AssertionError("subprocess")),
            mock.patch.object(os, "system", side_effect=AssertionError("shell")),
        ):
            decision = self.decide(self.clear, decision="REJECT")
        imported = {
            alias.name.split(".")[0]
            for node in ast.walk(ast.parse(_source_text()))
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        self.assertNotIn("subprocess", imported)
        self.assertFalse(decision.grants_execution_authority)

    def test_045_e9a_and_e9b_inputs_are_not_mutated(self) -> None:
        proposal, validation, state, artifact = self.clear_inputs
        before = (repr(proposal), repr(validation), repr(state), repr(artifact))
        decision = self.decide(artifact, decision="APPROVE", comment="reviewed")
        after = (repr(proposal), repr(validation), repr(state), repr(artifact))
        self.assertEqual(before, after)
        self.assertEqual(decision.review_artifact_identity, artifact.review_artifact_identity)

    def test_046_hard_stop_and_no_authority_invariants_are_explicit(self) -> None:
        decision = self.decide(self.clear, decision="APPROVE")
        self.assertIs(decision.hard_stop, True)
        self.assertIs(decision.review_decision_only, True)
        self.assertIs(decision.actor_metadata_evidence_only, True)
        self.assertIs(decision.human_identity_authenticated, False)
        self.assertFalse(decision.grants_write_authority)
        self.assertFalse(decision.grants_vault_write_authority)
        self.assertFalse(decision.grants_persistence_authority)
        self.assertFalse(decision.grants_publication_authority)
        self.assertFalse(decision.grants_merge_authority)
        self.assertFalse(decision.grants_rebase_authority)
        self.assertFalse(decision.grants_execution_authority)
        self.assertFalse(decision.grants_policy_authority)
        self.assertFalse(decision.grants_model_gateway_authority)
        self.assertFalse(decision.grants_tauri_frontend_authority)
        self.assertFalse(decision.grants_automatic_approval_authority)

    def test_047_exact_comment_character_and_utf8_boundaries_are_accepted(self) -> None:
        char_boundary = self.decide(
            self.clear,
            decision="REJECT",
            comment="x" * self.api.MAX_COMMENT_CHARS,
        )
        byte_text = "🚀" * (self.api.MAX_COMMENT_UTF8_BYTES // 4)
        byte_boundary = self.decide(self.clear, decision="REJECT", comment=byte_text)
        self.assertEqual(len(char_boundary.comment), self.api.MAX_COMMENT_CHARS)
        self.assertEqual(len(byte_boundary.comment.encode("utf-8")), self.api.MAX_COMMENT_UTF8_BYTES)

    def test_048_binding_values_require_exact_types_and_formats(self) -> None:
        cases = (
            {"expected_proposal_id": True},
            {"expected_review_artifact_identity": "kreview:bad"},
            {"expected_change_identity": 7},
            {"expected_observed_vault_revision": "SHA256:" + "a" * 64},
            {"current_observed_vault_revision": None},
        )
        for overrides in cases:
            with self.subTest(overrides=overrides):
                self.assert_rejection(
                    self.api.HumanReviewDecisionRejectionCode.INVALID_BINDING_VALUE,
                    lambda values=overrides: self.decide(self.clear, **values),
                )
        self.assertEqual(len(cases), 5)

    def test_049_actor_argument_requires_exact_metadata_type(self) -> None:
        values = self._decision_kwargs(self.clear, actor={"actor_identifier": "fake"})
        self.assert_rejection(
            self.api.HumanReviewDecisionRejectionCode.ACTOR_TYPE_INVALID,
            lambda: self.api.create_human_review_decision(self.clear, **values),
        )
        self.assertIs(type(self.actor), self.api.HumanReviewerMetadata)

    def test_050_malformed_real_type_artifact_field_is_rejected(self) -> None:
        malformed = _clone_review(self.clear, status="CLEAR")
        self.assert_rejection(
            self.api.HumanReviewDecisionRejectionCode.INVALID_REVIEW_ARTIFACT,
            lambda: self.decide(malformed),
        )
        self.assertIs(type(malformed), KnowledgeChangeReviewArtifact)

    def test_051_typed_rejection_is_deterministic_and_validation_order_is_fixed(self) -> None:
        observed = []
        for _ in range(2):
            try:
                self.decide(
                    self.clear,
                    expected_proposal_id="kprop:" + "f" * 64,
                    expected_review_artifact_identity="kreview:" + "f" * 64,
                )
            except self.api.HumanReviewDecisionRejected as exc:
                observed.append((exc.code, str(exc)))
        self.assertEqual(observed[0], observed[1])
        self.assertEqual(observed[0][0], self.api.HumanReviewDecisionRejectionCode.PROPOSAL_ID_MISMATCH)

    def test_052_incomplete_fake_e9b_dependency_fails_static_import(self) -> None:
        self.assertTrue(incomplete_e9b_dependency_fails())
        decision = self.decide(self.clear)
        self.assertEqual(decision.review_contract_version, E9B_CONTRACT_VERSION)

    def test_053_all_eight_deliberate_faults_are_detected(self) -> None:
        original = self.decide(self.clear)
        results = run_deliberate_fault_checks()
        type(self).fault_results = results
        self.assertEqual(len(results), 8)
        self.assertTrue(all(item["detected"] for item in results))
        self.assertTrue(original.hard_stop)

    def test_054_focused_suite_substance_gate(self) -> None:
        decision = self.decide(self.clear)
        metrics = focused_test_substance_metrics()
        self.assertGreaterEqual(metrics["api_percentage"], 80.0)
        self.assertEqual(metrics["exact_duplicate_method_count"], 0)
        self.assertEqual(metrics["unique_behavioral_scenarios"], metrics["total_test_methods"])
        self.assertGreater(metrics["unique_assertion_pattern_count"], 10)
        self.assertTrue(decision.review_decision_only)

    def test_055_public_artifact_constructor_enforces_lifecycle_invariants(self) -> None:
        baseline = self.decide(self.clear, decision="APPROVE")

        def construct(
            review_status: ReviewStatus,
            change_identity: str | None,
        ) -> None:
            values = {item.name: getattr(baseline, item.name) for item in fields(baseline)}
            boundary = self.api._authority_boundary_values()
            values.update({
                "review_status": review_status,
                "change_identity": change_identity,
                "decision": self.api.HumanReviewDecisionValue.APPROVE,
                "decision_identity": self.api._compute_decision_identity(
                    contract_version=baseline.contract_version,
                    review_contract_version=baseline.review_contract_version,
                    review_status=review_status,
                    proposal_id=baseline.proposal_id,
                    review_artifact_identity=baseline.review_artifact_identity,
                    change_identity=change_identity,
                    observed_vault_revision=baseline.observed_vault_revision,
                    decision=self.api.HumanReviewDecisionValue.APPROVE,
                    comment=baseline.comment,
                    actor=baseline.actor,
                    boundary=boundary,
                ),
            })
            self.api.HumanReviewDecision(**values)

        with self.assertRaisesRegex(ValueError, "BLOCKED_APPROVAL_FORBIDDEN"):
            construct(ReviewStatus.BLOCKED, None)
        with self.assertRaisesRegex(ValueError, "APPROVAL_REQUIRES_CHANGE_IDENTITY"):
            construct(ReviewStatus.CLEAR, None)


def incomplete_e9b_dependency_fails() -> bool:
    dependency_name = "modules.knowledge_change_review_ru"
    probe_name = "modules._e9c_incomplete_dependency_probe"
    source = _source_text()
    fake = types.ModuleType(dependency_name)
    original_dependency = sys.modules.get(dependency_name)
    import modules as modules_package

    had_attribute = hasattr(modules_package, "knowledge_change_review_ru")
    original_attribute = getattr(modules_package, "knowledge_change_review_ru", None)
    probe = types.ModuleType(probe_name)
    probe.__file__ = os.fspath(MODULE_PATH)
    probe.__package__ = "modules"
    sys.modules[dependency_name] = fake
    setattr(modules_package, "knowledge_change_review_ru", fake)
    sys.modules[probe_name] = probe
    failed = False
    try:
        exec(compile(source, f"<{probe_name}>", "exec"), probe.__dict__)
    except ImportError:
        failed = True
    finally:
        sys.modules.pop(probe_name, None)
        if original_dependency is None:
            sys.modules.pop(dependency_name, None)
        else:
            sys.modules[dependency_name] = original_dependency
        if had_attribute:
            setattr(modules_package, "knowledge_change_review_ru", original_attribute)
        elif hasattr(modules_package, "knowledge_change_review_ru"):
            delattr(modules_package, "knowledge_change_review_ru")
    return failed


def _load_mutant(
    name: str,
    replacements: tuple[tuple[str, str], ...],
):
    source = _source_text()
    for old, new in replacements:
        count = source.count(old)
        if count != 1:
            raise AssertionError(f"fault replacement for {name!r} matched {count} times: {old!r}")
        source = source.replace(old, new, 1)
    module_name = f"modules._e9c_fault_{name}"
    mutant = types.ModuleType(module_name)
    mutant.__file__ = os.fspath(MODULE_PATH)
    mutant.__package__ = "modules"
    sys.modules[module_name] = mutant
    try:
        exec(compile(source, f"<{module_name}>", "exec"), mutant.__dict__)
    except Exception:
        sys.modules.pop(module_name, None)
        raise
    return mutant


def run_deliberate_fault_checks() -> tuple[dict[str, object], ...]:
    faults = (
        (
            "exact_review_binding_disabled",
            ((
                "if expected_review_artifact_identity != review_artifact.review_artifact_identity:",
                "if False:",
            ),),
            "test_014_review_artifact_identity_mismatch_is_rejected",
        ),
        (
            "blocked_approve_allowed",
            (
                (
                    "if review_status is ReviewStatus.BLOCKED and decision is HumanReviewDecisionValue.APPROVE:",
                    "if False:",
                ),
                (
                    "if decision is HumanReviewDecisionValue.APPROVE and change_identity is None:",
                    "if decision is HumanReviewDecisionValue.APPROVE and change_identity is None and review_status is not ReviewStatus.BLOCKED:",
                ),
            ),
            "test_008_blocked_approve_is_forbidden",
        ),
        (
            "current_revision_ignored",
            ((
                "if current_observed_vault_revision != review_artifact.observed_vault_revision:",
                "if False:",
            ),),
            "test_019_current_observed_revision_drift_is_rejected",
        ),
        (
            "request_changes_comment_requirement_disabled",
            ((
                "if decision is HumanReviewDecisionValue.REQUEST_CHANGES and not comment.strip():",
                "if False:",
            ),),
            "test_023_request_changes_empty_comment_is_rejected",
        ),
        (
            "constant_decision_identity",
            ((
                "return DECISION_ID_PREFIX + hashlib.sha256(_canonical_json_bytes(envelope)).hexdigest()",
                "return DECISION_ID_PREFIX + '0' * 64",
            ),),
            "test_036_every_variable_governed_input_changes_identity",
        ),
        (
            "comment_removed_from_identity",
            (("\"comment\": comment,", "\"comment\": '',"),),
            "test_028_comment_exact_bytes_participate_in_identity",
        ),
        (
            "actor_removed_from_identity",
            ((
                "\"actor\": _actor_identity_payload(actor),",
                "\"actor\": {'actor_identifier':'','display_name':'','source':''},",
            ),),
            "test_032_actor_metadata_participates_in_identity",
        ),
        (
            "hard_stop_no_authority_invariant_disabled",
            (
                ("HARD_STOP: Final[bool] = True", "HARD_STOP: Final[bool] = False"),
                (
                    "GRANTS_WRITE_AUTHORITY: Final[bool] = False",
                    "GRANTS_WRITE_AUTHORITY: Final[bool] = True",
                ),
            ),
            "test_046_hard_stop_and_no_authority_invariants_are_explicit",
        ),
    )
    results: list[dict[str, object]] = []
    for name, replacements, test_name in faults:
        mutant = _load_mutant(name, replacements)
        case = HumanReviewDecisionBehaviorTests(test_name)
        case.api = mutant
        case.record_counts = False
        result = unittest.TestResult()
        try:
            case.run(result)
        finally:
            sys.modules.pop(mutant.__name__, None)
        detected = len(result.failures) == 1 and len(result.errors) == 0
        results.append({
            "fault": name,
            "relevant_test": test_name,
            "detected": detected,
            "failure_count": len(result.failures),
            "error_count": len(result.errors),
        })
    return tuple(results)


def focused_test_substance_metrics() -> dict[str, object]:
    tree = ast.parse(TEST_PATH.read_text(encoding="utf-8"))
    class_node = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "HumanReviewDecisionBehaviorTests"
    )
    methods = {
        node.name: node
        for node in class_node.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    tests = {name: node for name, node in methods.items() if name.startswith("test_")}
    calls: dict[str, set[str]] = {}
    direct_api: set[str] = set()
    for name, node in methods.items():
        self_calls = {
            call.func.attr
            for call in ast.walk(node)
            if isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and (
                isinstance(call.func.value, ast.Name) and call.func.value.id == "self"
                or isinstance(call.func.value, ast.Attribute)
            )
        }
        calls[name] = self_calls & set(methods)
        if any(
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and call.func.attr == "create_human_review_decision"
            for call in ast.walk(node)
        ):
            direct_api.add(name)

    def reaches_api(name: str, active: frozenset[str] = frozenset()) -> bool:
        if name in direct_api:
            return True
        if name in active:
            return False
        return any(reaches_api(child, active | {name}) for child in calls[name])

    api_methods = tuple(sorted(name for name in tests if reaches_api(name)))
    normalized = {
        name: ast.dump(ast.Module(body=node.body, type_ignores=[]), include_attributes=False)
        for name, node in tests.items()
    }
    by_body: dict[str, list[str]] = {}
    for name, body in normalized.items():
        by_body.setdefault(body, []).append(name)
    exact_duplicates = tuple(
        tuple(names)
        for names in by_body.values()
        if len(names) > 1
    )
    near_duplicates = []
    test_names = sorted(tests)
    for index, left in enumerate(test_names):
        for right in test_names[index + 1:]:
            ratio = difflib.SequenceMatcher(None, normalized[left], normalized[right]).ratio()
            if ratio >= 0.985:
                near_duplicates.append((left, right, round(ratio, 4)))
    assertion_patterns = set()
    for node in tests.values():
        pattern = tuple(
            call.func.attr
            for call in ast.walk(node)
            if isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and call.func.attr.startswith("assert")
        )
        assertion_patterns.add(pattern)
    total = len(tests)
    api_count = len(api_methods)
    return {
        "total_test_methods": total,
        "api_calling_methods": api_count,
        "api_percentage": round((api_count * 100.0 / total) if total else 0.0, 2),
        "unique_behavioral_scenarios": total - sum(len(group) - 1 for group in exact_duplicates),
        "exact_duplicate_method_count": sum(len(group) - 1 for group in exact_duplicates),
        "exact_duplicate_groups": exact_duplicates,
        "near_duplicate_count": len(near_duplicates),
        "near_duplicate_pairs": tuple(near_duplicates),
        "unique_assertion_pattern_count": len(assertion_patterns),
    }


def main() -> None:
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(HumanReviewDecisionBehaviorTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    metrics = focused_test_substance_metrics()
    e9a_count_keys = (
        "proposer_metadata",
        "provenance",
        "proposed_content",
        "knowledge_change_proposals",
        "proposal_validators",
        "validation_results",
    )
    output = {
        "metrics": metrics,
        "construction_counts": dict(HumanReviewDecisionBehaviorTests.counters),
        "real_e9a_object_constructions": sum(
            HumanReviewDecisionBehaviorTests.counters[key] for key in e9a_count_keys
        ),
        "real_e9b_artifact_constructions": HumanReviewDecisionBehaviorTests.counters[
            "knowledge_change_review_artifacts"
        ],
        "human_review_decision_constructions": HumanReviewDecisionBehaviorTests.counters[
            "human_review_decisions"
        ],
        "fault_results": HumanReviewDecisionBehaviorTests.fault_results,
        "fake_incomplete_e9b_import_failed": incomplete_e9b_dependency_fails(),
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
    }
    print("E9C_FOCUSED_EVIDENCE=" + json.dumps(output, ensure_ascii=False, sort_keys=True))
    if not result.wasSuccessful():
        raise SystemExit(1)


if __name__ == "__main__":
    main()
