"""Focused behavioral tests for LocalComet v6.84.5.1e9b Knowledge Review Layer."""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, fields, replace
import hashlib
import inspect
from pathlib import Path
import unittest

from modules.knowledge_change_proposal_ru import (
    CONTRACT_VERSION as E9A_CONTRACT_VERSION,
    CanonicalLocationHint,
    EvidenceReference,
    KnowledgeChangeProposal,
    ProposalOperation,
    ProposalValidator,
    ProposerMetadata,
    ProposedNoteContent,
    Provenance,
    ValidationFinding,
    ValidationOutcome,
    ValidationResult,
    compute_proposal_content_hash,
    compute_proposal_instance_id,
    create_proposal_from_untrusted,
)
from modules.knowledge_change_review_ru import (
    CONTRACT_VERSION,
    E9A_API_BINDINGS,
    MAX_PREVIEW_BYTES,
    MAX_PREVIEW_LINES,
    MAX_PROPOSED_CONTENT_BYTES,
    MAX_PATH_LENGTH,
    MAX_VALIDATION_KEY_LENGTH,
    MAX_VALIDATION_MAPPING_ENTRIES,
    MAX_VALIDATION_SEQUENCE_ENTRIES,
    MAX_VALIDATION_SNAPSHOT_DEPTH,
    MAX_VALIDATION_SNAPSHOT_NODES,
    MAX_VALIDATION_STRING_LENGTH,
    MAX_SOURCE_BYTES,
    MAX_STABLE_IDS,
    TRUNCATION_MARKER,
    ConflictCode,
    ConflictSeverity,
    CurrentKnowledgeState,
    FrozenCanonicalValue,
    KnowledgeChangeReviewArtifact,
    ProposedContentSnapshot,
    ReviewStatus,
    TrustedTargetSnapshot,
    analyze_review,
    compute_semantic_text_hash,
    compute_source_byte_hash,
    compute_text_raw_hash,
    create_trusted_target_snapshot,
    semantic_normalize_v1,
)


REV_A = "sha256:" + "a" * 64
REV_B = "sha256:" + "b" * 64
REV_C = "sha256:" + "c" * 64
TARGET = "canonical.current-state"
OTHER_TARGET = "architecture.knowledge-layer"


class KnowledgeReviewBehaviorTests(unittest.TestCase):
    proposal_constructions = 0
    validation_result_constructions = 0
    validator_constructions = 0
    proposer_constructions = 0
    provenance_constructions = 0
    content_constructions = 0
    api_calls = 0

    def make_proposal(
        self,
        *,
        operation: ProposalOperation = ProposalOperation.UPDATE_EXISTING,
        target: str = TARGET,
        expected_revision: str = REV_A,
        body: str = "new body\n",
        reason: str = "review test",
        evidence_count: int = 1,
        content_overrides: dict[str, object] | None = None,
    ) -> KnowledgeChangeProposal:
        proposer = ProposerMetadata(
            agent_type="test-agent",
            agent_instance_id="instance-1",
            model_identifier="none",
            source_workflow="e9b-focused-tests",
        )
        type(self).proposer_constructions += 1
        references = tuple(
            EvidenceReference(reference=f"EV-{index:03d}", description=f"evidence {index}")
            for index in range(evidence_count)
        )
        provenance = Provenance(
            reason=reason,
            source_observation="observed source",
            related_stable_ids=(target,),
            evidence_references=references,
            workflow_origin="focused-test",
        )
        type(self).provenance_constructions += 1
        content_values: dict[str, object] = {
            "title": "Current State",
            "body_text": body,
            "type": "project_state",
            "status": "accepted",
            "knowledge_layer": "canonical",
            "evidence_class": "A",
            "authority": "repository",
            "canonical": True,
            "canonical_scope": "current-state",
            "aliases": ("state",),
            "releases": ("v6.84.5.1e9b",),
            "source_paths": ("modules/example.py",),
            "evidence_refs": ("EV-000",),
            "supersedes": (),
            "superseded_by": (),
            "updated": "2026-07-16",
            "last_reviewed": "2026-07-16",
            "verified_at": None,
        }
        if content_overrides:
            content_values.update(content_overrides)
        content = ProposedNoteContent(**content_values)
        type(self).content_constructions += 1
        hint = (
            CanonicalLocationHint(
                relative_path="canonical/current-state.md",
                parent_stable_id=None,
            )
            if operation is ProposalOperation.CREATE_NEW
            else None
        )
        temporary = KnowledgeChangeProposal(
            proposal_id="kprop:" + "0" * 64,
            contract_version=E9A_CONTRACT_VERSION,
            operation=operation,
            target_stable_id=target,
            expected_vault_revision=expected_revision,
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
            expected_vault_revision=expected_revision,
            proposer=proposer,
            provenance=provenance,
            proposed_content=content,
            canonical_location_hint=hint,
        )
        type(self).proposal_constructions += 2
        return proposal

    def validate(
        self,
        proposal: KnowledgeChangeProposal,
        *,
        vault_revision: str = REV_A,
        stable_ids: frozenset[str] | set[str] = frozenset({TARGET}),
    ) -> ValidationResult:
        validator = ProposalValidator(
            vault_revision=vault_revision,
            stable_ids=stable_ids,
        )
        type(self).validator_constructions += 1
        result = validator.validate(proposal)
        type(self).validation_result_constructions += 1
        return result

    def snapshot(
        self,
        text: str,
        *,
        stable_id: str = TARGET,
        revision: str = REV_A,
        path: str = "canonical/current-state.md",
    ) -> TrustedTargetSnapshot:
        return create_trusted_target_snapshot(
            source_bytes=text.encode("utf-8"),
            source_relative_path=path,
            target_stable_id=stable_id,
            captured_vault_revision=revision,
        )

    def state(
        self,
        *,
        revision: str = REV_A,
        stable_ids: frozenset[str] | set[str] = frozenset({TARGET}),
        current: TrustedTargetSnapshot | None = None,
        baseline: TrustedTargetSnapshot | None = None,
    ) -> CurrentKnowledgeState:
        return CurrentKnowledgeState(
            observed_vault_revision=revision,
            current_stable_ids=frozenset(stable_ids),
            current_target=current,
            baseline_target=baseline,
        )

    def review(
        self,
        proposal: KnowledgeChangeProposal,
        result: ValidationResult,
        state: CurrentKnowledgeState,
    ) -> KnowledgeChangeReviewArtifact:
        type(self).api_calls += 1
        return analyze_review(proposal, result, state)

    def tamper_result(self, result: ValidationResult, **changes: object) -> ValidationResult:
        clone = object.__new__(ValidationResult)
        for item in fields(ValidationResult):
            object.__setattr__(
                clone,
                item.name,
                changes.get(item.name, getattr(result, item.name)),
            )
        type(self).validation_result_constructions += 1
        return clone

    def clear_create_artifact(self, body: str = "created\n") -> KnowledgeChangeReviewArtifact:
        proposal = self.make_proposal(
            operation=ProposalOperation.CREATE_NEW,
            target=OTHER_TARGET,
            body=body,
        )
        result = self.validate(proposal, stable_ids={TARGET})
        return self.review(
            proposal,
            result,
            self.state(stable_ids={TARGET}),
        )

    def clear_update_artifact(
        self,
        *,
        before: str = "old\n",
        after: str = "new\n",
    ) -> KnowledgeChangeReviewArtifact:
        proposal = self.make_proposal(body=after)
        result = self.validate(proposal)
        current = self.snapshot(before)
        baseline = self.snapshot(before)
        return self.review(
            proposal,
            result,
            self.state(current=current, baseline=baseline),
        )

    def metadata_only_artifact(
        self,
        **content_overrides: object,
    ) -> KnowledgeChangeReviewArtifact:
        proposal = self.make_proposal(
            body="same body\n",
            content_overrides=content_overrides,
        )
        result = self.validate(proposal)
        current = self.snapshot("same body\n")
        return self.review(
            proposal,
            result,
            self.state(current=current, baseline=current),
        )

    def result_with_provenance_summary(
        self,
        summary: object,
    ) -> tuple[KnowledgeChangeProposal, ValidationResult, CurrentKnowledgeState]:
        proposal = self.make_proposal(
            operation=ProposalOperation.CREATE_NEW,
            target=OTHER_TARGET,
        )
        result = self.validate(proposal, stable_ids={TARGET})
        tampered = self.tamper_result(result, provenance_summary=summary)
        return proposal, tampered, self.state(stable_ids={TARGET})

    def assert_no_unproven_equality_findings(
        self,
        artifact: KnowledgeChangeReviewArtifact,
    ) -> None:
        codes = {finding.code for finding in artifact.findings}
        self.assertNotIn(ConflictCode.PROPOSED_CONTENT_ALREADY_IDENTICAL, codes)
        self.assertNotIn(ConflictCode.PROPOSED_CONTENT_SEMANTICALLY_EQUIVALENT, codes)

    def assert_no_normal_change_material(
        self,
        artifact: KnowledgeChangeReviewArtifact,
    ) -> None:
        self.assertIsNone(artifact.deterministic_text_diff)
        self.assertIsNone(artifact.deterministic_text_diff_hash)
        self.assertIsNone(artifact.representation_delta)
        self.assertIsNone(artifact.change_identity)

    def review_with_invalid_current_path(
        self,
        path: str,
    ) -> KnowledgeChangeReviewArtifact:
        proposal = self.make_proposal(body="after\n")
        result = self.validate(proposal)
        valid = self.snapshot("before\n")
        invalid = replace(valid, source_relative_path=path)
        return self.review(
            proposal,
            result,
            self.state(current=invalid, baseline=valid),
        )

    def test_001_static_e9a_import_compatibility_uses_real_symbols(self) -> None:
        proposal = self.make_proposal(
            operation=ProposalOperation.CREATE_NEW,
            target=OTHER_TARGET,
        )
        result = self.validate(proposal, stable_ids={TARGET})
        artifact = self.review(proposal, result, self.state(stable_ids={TARGET}))
        self.assertIs(E9A_API_BINDINGS["KnowledgeChangeProposal"], KnowledgeChangeProposal)
        self.assertIs(E9A_API_BINDINGS["ValidationResult"], ValidationResult)
        self.assertEqual(artifact.contract_version, "localcomet.knowledge-change-review/1.0")

    def test_002_factory_instance_id_caveat_is_not_used_for_binding(self) -> None:
        proposal = create_proposal_from_untrusted(
            operation="CREATE_NEW",
            target_stable_id=OTHER_TARGET,
            expected_vault_revision=REV_A,
            proposer={"agent_type": "test"},
            provenance={"reason": "factory caveat"},
            proposed_content={
                "title": "New",
                "body_text": "body\n",
                "type": "note",
                "status": "draft",
                "knowledge_layer": "project",
                "evidence_class": "C",
                "authority": "user",
            },
            canonical_location_hint={"relative_path": "notes/new.md"},
        )
        result = self.validate(proposal, stable_ids={TARGET})
        artifact = self.review(proposal, result, self.state(stable_ids={TARGET}))
        self.assertNotEqual(compute_proposal_instance_id(proposal), proposal.proposal_id)
        self.assertEqual(artifact.proposal_id, proposal.proposal_id)
        self.assertNotIn(
            ConflictCode.VALIDATION_RESULT_PROPOSAL_MISMATCH,
            {item.code for item in artifact.findings},
        )

    def test_003_exact_proposal_result_binding_accepts_matching_result(self) -> None:
        artifact = self.clear_create_artifact()
        self.assertEqual(artifact.status, ReviewStatus.CLEAR)
        self.assertEqual(artifact.findings, ())
        self.assertIsNotNone(artifact.change_identity)

    def test_004_proposal_a_result_is_rejected_for_proposal_b(self) -> None:
        proposal_a = self.make_proposal(
            operation=ProposalOperation.CREATE_NEW,
            target=OTHER_TARGET,
            body="A\n",
        )
        proposal_b = self.make_proposal(
            operation=ProposalOperation.CREATE_NEW,
            target=OTHER_TARGET,
            body="B\n",
        )
        result_a = self.validate(proposal_a, stable_ids={TARGET})
        artifact = self.review(proposal_b, result_a, self.state(stable_ids={TARGET}))
        self.assertEqual(artifact.status, ReviewStatus.BLOCKED)
        self.assertEqual(
            artifact.findings[0].code,
            ConflictCode.VALIDATION_RESULT_PROPOSAL_MISMATCH,
        )
        self.assertIsNone(artifact.deterministic_text_diff)

    def test_005_content_hash_mismatch_is_blocking(self) -> None:
        proposal = self.make_proposal(
            operation=ProposalOperation.CREATE_NEW,
            target=OTHER_TARGET,
        )
        result = self.validate(proposal, stable_ids={TARGET})
        tampered = self.tamper_result(
            result,
            proposal_content_hash="sha256:" + "0" * 64,
        )
        artifact = self.review(proposal, tampered, self.state(stable_ids={TARGET}))
        detail = dict(artifact.findings[0].details)
        self.assertIn("proposal_content_hash", detail["mismatched_fields"])
        self.assertIsNone(artifact.change_identity)

    def test_006_contract_version_mismatch_is_detected_at_trust_boundary(self) -> None:
        proposal = self.make_proposal(
            operation=ProposalOperation.CREATE_NEW,
            target=OTHER_TARGET,
        )
        result = self.validate(proposal, stable_ids=set())
        malformed = self.tamper_result(result, contract_version="wrong/9")
        artifact = self.review(proposal, malformed, self.state(stable_ids=set()))
        self.assertEqual(artifact.status, ReviewStatus.BLOCKED)
        self.assertIn(
            "contract_version",
            dict(artifact.findings[0].details)["mismatched_fields"],
        )

    def test_007_operation_type_and_value_mismatch_is_detected(self) -> None:
        proposal = self.make_proposal(
            operation=ProposalOperation.CREATE_NEW,
            target=OTHER_TARGET,
        )
        result = self.validate(proposal, stable_ids=set())
        malformed = self.tamper_result(result, operation=ProposalOperation.CREATE_NEW)
        artifact = self.review(proposal, malformed, self.state(stable_ids=set()))
        self.assertEqual(
            artifact.findings[0].code,
            ConflictCode.VALIDATION_RESULT_PROPOSAL_MISMATCH,
        )
        self.assertIn("operation", dict(artifact.findings[0].details)["mismatched_fields"])

    def test_008_target_id_mismatch_is_detected(self) -> None:
        proposal = self.make_proposal(
            operation=ProposalOperation.CREATE_NEW,
            target=OTHER_TARGET,
        )
        result = self.validate(proposal, stable_ids=set())
        malformed = self.tamper_result(result, target_stable_id=TARGET)
        artifact = self.review(proposal, malformed, self.state(stable_ids=set()))
        mismatch_fields = dict(artifact.findings[0].details)["mismatched_fields"].split(",")
        self.assertEqual(mismatch_fields, ["target_stable_id"])
        self.assertEqual(artifact.status, ReviewStatus.BLOCKED)

    def test_009_expected_revision_mismatch_is_detected(self) -> None:
        proposal = self.make_proposal(
            operation=ProposalOperation.CREATE_NEW,
            target=OTHER_TARGET,
        )
        result = self.validate(proposal, stable_ids=set())
        malformed = self.tamper_result(result, expected_vault_revision=REV_B)
        artifact = self.review(proposal, malformed, self.state(stable_ids=set()))
        self.assertIn(
            ConflictCode.VALIDATION_RESULT_PROPOSAL_MISMATCH,
            {finding.code for finding in artifact.findings},
        )
        self.assertIn(
            "expected_vault_revision",
            dict(artifact.findings[0].details)["mismatched_fields"],
        )

    def test_010_valid_result_performs_operation_specific_analysis(self) -> None:
        artifact = self.clear_update_artifact(before="one\n", after="two\n")
        self.assertEqual(artifact.validation_outcome, ValidationOutcome.VALID.value)
        self.assertEqual(artifact.status, ReviewStatus.CLEAR)
        self.assertIn("-one", artifact.deterministic_text_diff or "")
        self.assertIn("+two", artifact.deterministic_text_diff or "")

    def test_011_invalid_result_blocks_without_normal_diff(self) -> None:
        proposal = self.make_proposal(body="new\n")
        result = self.validate(proposal, stable_ids=set())
        self.assertEqual(result.outcome, ValidationOutcome.INVALID)
        artifact = self.review(
            proposal,
            result,
            self.state(stable_ids=set(), current=None, baseline=None),
        )
        self.assertEqual(artifact.status, ReviewStatus.BLOCKED)
        self.assertEqual(artifact.source_validation_findings[0][0], "UPDATE_TARGET_MISSING")
        self.assertIsNone(artifact.deterministic_text_diff)
        self.assertNotIn(
            ConflictCode.VALIDATION_RESULT_PROPOSAL_MISMATCH,
            {finding.code for finding in artifact.findings},
        )

    def test_012_stale_result_blocks_with_revision_evidence_and_no_diff(self) -> None:
        proposal = self.make_proposal(expected_revision=REV_A)
        result = self.validate(proposal, vault_revision=REV_B)
        current = self.snapshot("old\n", revision=REV_B)
        artifact = self.review(
            proposal,
            result,
            self.state(revision=REV_B, current=current),
        )
        stale = next(
            finding
            for finding in artifact.findings
            if finding.code is ConflictCode.STALE_VAULT_REVISION
        )
        self.assertEqual(artifact.status, ReviewStatus.BLOCKED)
        self.assertEqual(dict(stale.details)["observed"], REV_B)
        self.assertIsNone(artifact.deterministic_text_diff)

    def test_013_unsupported_operation_is_blocking_not_binding_mismatch(self) -> None:
        proposal = self.make_proposal(operation=ProposalOperation.DELETE)
        result = self.validate(proposal)
        artifact = self.review(proposal, result, self.state())
        codes = tuple(item.code for item in artifact.findings)
        self.assertIn(ConflictCode.UNSUPPORTED_OPERATION, codes)
        self.assertNotIn(ConflictCode.VALIDATION_RESULT_PROPOSAL_MISMATCH, codes)
        self.assertEqual(artifact.status, ReviewStatus.BLOCKED)

    def test_014_update_current_snapshot_generates_full_change_material(self) -> None:
        artifact = self.clear_update_artifact(
            before="alpha\nbeta\n",
            after="alpha\ngamma\n",
        )
        self.assertEqual(artifact.before_text_raw_hash, compute_text_raw_hash("alpha\nbeta\n"))
        self.assertTrue(artifact.deterministic_text_diff_hash.startswith("sha256:"))
        self.assertTrue(artifact.change_identity.startswith("kchange:"))
        self.assertTrue(artifact.review_artifact_identity.startswith("kreview:"))

    def test_015_update_verified_baseline_equal_current_allows_clear(self) -> None:
        proposal = self.make_proposal(body="after\n")
        result = self.validate(proposal)
        baseline = self.snapshot("before\n", revision=REV_A)
        current = self.snapshot("before\n", revision=REV_A)
        artifact = self.review(
            proposal,
            result,
            self.state(current=current, baseline=baseline),
        )
        self.assertEqual(artifact.findings, ())
        self.assertEqual(artifact.status, ReviewStatus.CLEAR)
        self.assertTrue(artifact.representation_delta.semantic_content_changed)

    def test_016_missing_baseline_does_not_claim_historical_drift(self) -> None:
        proposal = self.make_proposal(body="after\n")
        result = self.validate(proposal)
        artifact = self.review(
            proposal,
            result,
            self.state(current=self.snapshot("before\n")),
        )
        self.assertEqual(artifact.status, ReviewStatus.REVIEW_REQUIRED)
        self.assertEqual(
            tuple(finding.code for finding in artifact.findings),
            (ConflictCode.TARGET_STATE_COMPARISON_UNAVAILABLE,),
        )
        self.assertIsNotNone(artifact.change_identity)

    def test_017_baseline_revision_mismatch_fails_closed(self) -> None:
        proposal = self.make_proposal(expected_revision=REV_A, body="after\n")
        result = self.validate(proposal)
        baseline = self.snapshot("before\n", revision=REV_B)
        current = self.snapshot("before\n", revision=REV_A)
        artifact = self.review(
            proposal,
            result,
            self.state(current=current, baseline=baseline),
        )
        finding = artifact.findings[0]
        self.assertEqual(finding.code, ConflictCode.UNVERIFIED_TEXT_INPUT)
        self.assertIn("baseline_captured_vault_revision", dict(finding.details)["errors"])
        self.assertIsNone(artifact.change_identity)

    def test_018_current_target_missing_is_blocking(self) -> None:
        proposal = self.make_proposal()
        result = self.validate(proposal)
        artifact = self.review(
            proposal,
            result,
            self.state(current=None, baseline=self.snapshot("old\n")),
        )
        self.assertEqual(artifact.findings[0].code, ConflictCode.TARGET_MISSING)
        self.assertEqual(artifact.status, ReviewStatus.BLOCKED)
        self.assertIsNone(artifact.representation_delta)

    def test_019_current_stable_id_mismatch_is_unverified(self) -> None:
        proposal = self.make_proposal()
        result = self.validate(proposal)
        wrong_snapshot = self.snapshot("old\n", stable_id=OTHER_TARGET)
        artifact = self.review(
            proposal,
            result,
            self.state(current=wrong_snapshot, baseline=None),
        )
        self.assertEqual(artifact.status, ReviewStatus.BLOCKED)
        self.assertEqual(artifact.findings[0].code, ConflictCode.UNVERIFIED_TEXT_INPUT)
        self.assertIn("current_target_stable_id", dict(artifact.findings[0].details)["errors"])

    def test_020_current_snapshot_revision_mismatch_is_unverified(self) -> None:
        proposal = self.make_proposal()
        result = self.validate(proposal)
        current = self.snapshot("old\n", revision=REV_B)
        artifact = self.review(
            proposal,
            result,
            self.state(revision=REV_A, current=current),
        )
        self.assertEqual(artifact.findings[0].severity, ConflictSeverity.BLOCKING)
        self.assertIn(
            "current_captured_vault_revision",
            dict(artifact.findings[0].details)["errors"],
        )
        self.assertIsNone(artifact.deterministic_text_diff)

    def test_021_baseline_stable_id_mismatch_is_unverified(self) -> None:
        proposal = self.make_proposal()
        result = self.validate(proposal)
        current = self.snapshot("old\n")
        baseline = self.snapshot("old\n", stable_id=OTHER_TARGET)
        artifact = self.review(
            proposal,
            result,
            self.state(current=current, baseline=baseline),
        )
        self.assertEqual(artifact.status, ReviewStatus.BLOCKED)
        self.assertIn(
            "baseline_target_stable_id",
            dict(artifact.findings[0].details)["errors"],
        )
        self.assertIsNone(artifact.change_identity)

    def test_022_verified_baseline_current_divergence_detects_target_change(self) -> None:
        proposal = self.make_proposal(body="proposed\n")
        result = self.validate(proposal)
        baseline = self.snapshot("baseline\n")
        current = self.snapshot("changed\n")
        artifact = self.review(
            proposal,
            result,
            self.state(current=current, baseline=baseline),
        )
        finding = artifact.findings[0]
        self.assertEqual(finding.code, ConflictCode.TARGET_CHANGED_SINCE_PROPOSAL)
        self.assertEqual(finding.severity, ConflictSeverity.BLOCKING)
        self.assertIsNone(artifact.deterministic_text_diff)

    def test_023_create_clear_path_has_no_preimage(self) -> None:
        artifact = self.clear_create_artifact("new note\n")
        self.assertEqual(artifact.status, ReviewStatus.CLEAR)
        self.assertIsNone(artifact.before_source_byte_hash)
        self.assertTrue((artifact.deterministic_text_diff or "").startswith("--- /dev/null"))
        self.assertFalse(artifact.representation_delta.before_present)

    def test_024_create_collision_is_deterministically_blocking(self) -> None:
        proposal = self.make_proposal(
            operation=ProposalOperation.CREATE_NEW,
            target=OTHER_TARGET,
        )
        valid_result = self.validate(proposal, stable_ids={TARGET})
        artifact = self.review(
            proposal,
            valid_result,
            self.state(stable_ids={TARGET, OTHER_TARGET}),
        )
        self.assertEqual(
            tuple(finding.code for finding in artifact.findings),
            (ConflictCode.STABLE_ID_COLLISION,),
        )
        self.assertEqual(artifact.status, ReviewStatus.BLOCKED)
        self.assertIsNone(artifact.change_identity)

    def test_025_create_rejects_fake_target_preimage(self) -> None:
        proposal = self.make_proposal(
            operation=ProposalOperation.CREATE_NEW,
            target=OTHER_TARGET,
        )
        result = self.validate(proposal, stable_ids={TARGET})
        fake = self.snapshot("not allowed\n", stable_id=OTHER_TARGET)
        artifact = self.review(
            proposal,
            result,
            self.state(stable_ids={TARGET}, current=fake),
        )
        self.assertEqual(artifact.findings[0].code, ConflictCode.UNVERIFIED_TEXT_INPUT)
        self.assertEqual(artifact.status, ReviewStatus.BLOCKED)
        self.assertNotIn(
            ConflictCode.TARGET_STATE_COMPARISON_UNAVAILABLE,
            {finding.code for finding in artifact.findings},
        )

    def test_026_strict_utf8_factory_rejects_decode_failure(self) -> None:
        with self.assertRaisesRegex(ValueError, "strict UTF-8"):
            create_trusted_target_snapshot(
                source_bytes=b"\xff\xfe",
                source_relative_path="canonical/current-state.md",
                target_stable_id=TARGET,
                captured_vault_revision=REV_A,
            )

    def test_027_bytes_text_mismatch_fails_closed_before_diff(self) -> None:
        proposal = self.make_proposal()
        result = self.validate(proposal)
        valid = self.snapshot("old\n")
        mismatched = replace(valid, trusted_text="different\n")
        artifact = self.review(
            proposal,
            result,
            self.state(current=mismatched, baseline=valid),
        )
        errors = dict(artifact.findings[0].details)["errors"]
        self.assertIn("bytes_text_mismatch", errors)
        self.assertIn("text_raw_hash_mismatch", errors)
        self.assertIsNone(artifact.representation_delta)

    def test_028_source_byte_hash_mismatch_is_unverified(self) -> None:
        proposal = self.make_proposal()
        result = self.validate(proposal)
        valid = self.snapshot("old\n")
        bad = replace(valid, source_byte_hash="sha256:" + "1" * 64)
        artifact = self.review(
            proposal,
            result,
            self.state(current=bad, baseline=valid),
        )
        self.assertEqual(artifact.status, ReviewStatus.BLOCKED)
        self.assertIn(
            "source_byte_hash_mismatch",
            dict(artifact.findings[0].details)["errors"],
        )
        self.assertIsNone(artifact.deterministic_text_diff_hash)

    def test_029_raw_text_hash_mismatch_is_unverified(self) -> None:
        proposal = self.make_proposal()
        result = self.validate(proposal)
        valid = self.snapshot("old\n")
        bad = replace(valid, text_raw_hash="sha256:" + "2" * 64)
        artifact = self.review(proposal, result, self.state(current=bad, baseline=valid))
        self.assertEqual(artifact.findings[0].code, ConflictCode.UNVERIFIED_TEXT_INPUT)
        self.assertIn("text_raw_hash_mismatch", dict(artifact.findings[0].details)["errors"])
        self.assertIsNone(artifact.change_identity)

    def test_030_semantic_text_hash_mismatch_is_unverified(self) -> None:
        proposal = self.make_proposal()
        result = self.validate(proposal)
        valid = self.snapshot("old\r\n")
        bad = replace(valid, semantic_text_hash="sha256:" + "3" * 64)
        artifact = self.review(proposal, result, self.state(current=bad, baseline=valid))
        codes = [finding.code for finding in artifact.findings]
        self.assertEqual(codes, [ConflictCode.UNVERIFIED_TEXT_INPUT])
        self.assertIn(
            "semantic_text_hash_mismatch",
            dict(artifact.findings[0].details)["errors"],
        )

    def test_031_invalid_relative_path_is_unverified(self) -> None:
        proposal = self.make_proposal()
        result = self.validate(proposal)
        valid = self.snapshot("old\n")
        bad = replace(valid, source_relative_path="../escape.md")
        artifact = self.review(proposal, result, self.state(current=bad, baseline=valid))
        self.assertEqual(artifact.status, ReviewStatus.BLOCKED)
        self.assertIn("invalid_relative_path", dict(artifact.findings[0].details)["errors"])
        self.assertNotIn("..", artifact.human_review_preview)

    def test_032_oversized_snapshot_is_blocked_without_identity_material(self) -> None:
        proposal = self.make_proposal(body="small\n")
        result = self.validate(proposal)
        text = "x" * (MAX_SOURCE_BYTES + 1)
        oversized = TrustedTargetSnapshot(
            source_bytes=text.encode("utf-8"),
            trusted_text=text,
            source_relative_path="canonical/current-state.md",
            target_stable_id=TARGET,
            captured_vault_revision=REV_A,
            source_byte_hash=compute_source_byte_hash(text.encode("utf-8")),
            text_raw_hash=compute_text_raw_hash(text),
            semantic_text_hash=compute_semantic_text_hash(text),
        )
        artifact = self.review(
            proposal,
            result,
            self.state(current=oversized, baseline=None),
        )
        self.assertEqual(artifact.findings[0].code, ConflictCode.UNVERIFIED_TEXT_INPUT)
        self.assertIn("source_bytes_oversized", dict(artifact.findings[0].details)["errors"])
        self.assertIsNone(artifact.change_identity)

    def test_033_crlf_normalization_changes_only_line_endings(self) -> None:
        proposal = self.make_proposal(body="a\nb\n")
        result = self.validate(proposal)
        current = self.snapshot("a\r\nb\r\n")
        artifact = self.review(
            proposal,
            result,
            self.state(current=current, baseline=current),
        )
        self.assertEqual(semantic_normalize_v1("a\r\nb\r\n"), "a\nb\n")
        self.assertTrue(artifact.representation_delta.raw_text_changed_semantic_equal)
        self.assertFalse(artifact.representation_delta.semantic_content_changed)

    def test_034_lone_cr_normalization_is_deterministic(self) -> None:
        proposal = self.make_proposal(body="a\nb\n")
        result = self.validate(proposal)
        current = self.snapshot("a\rb\r")
        artifact = self.review(
            proposal,
            result,
            self.state(current=current, baseline=current),
        )
        self.assertEqual(semantic_normalize_v1("a\rb\r"), "a\nb\n")
        self.assertEqual(artifact.representation_delta.before_line_endings.cr_count, 2)
        self.assertEqual(artifact.deterministic_text_diff, "")

    def test_035_unicode_is_preserved_without_normalization(self) -> None:
        text = "Космос café e\u0301 🚀\n"
        proposal = self.make_proposal(body=text + "next\n")
        result = self.validate(proposal)
        current = self.snapshot(text)
        artifact = self.review(
            proposal,
            result,
            self.state(current=current, baseline=current),
        )
        self.assertIn("Космос café e\u0301 🚀", artifact.deterministic_text_diff or "")
        self.assertEqual(semantic_normalize_v1(text), text)
        self.assertEqual(artifact.proposed_text_raw_hash, compute_text_raw_hash(text + "next\n"))

    def test_036_spaces_and_tabs_are_preserved(self) -> None:
        before = "a \t b\n"
        after = "a\t  b\n"
        artifact = self.clear_update_artifact(before=before, after=after)
        self.assertTrue(artifact.representation_delta.semantic_content_changed)
        self.assertIn("-a \t b", artifact.deterministic_text_diff or "")
        self.assertIn("+a\t  b", artifact.deterministic_text_diff or "")

    def test_037_trailing_spaces_are_semantic_content(self) -> None:
        artifact = self.clear_update_artifact(before="line  \n", after="line\n")
        self.assertTrue(artifact.representation_delta.semantic_content_changed)
        self.assertNotEqual(artifact.before_semantic_text_hash, artifact.proposed_semantic_text_hash)
        self.assertNotIn(
            ConflictCode.PROPOSED_CONTENT_SEMANTICALLY_EQUIVALENT,
            {finding.code for finding in artifact.findings},
        )

    def test_038_terminal_newline_is_preserved_in_raw_and_semantic_hashes(self) -> None:
        artifact = self.clear_update_artifact(before="line", after="line\n")
        self.assertTrue(artifact.representation_delta.terminal_newline_changed)
        self.assertTrue(artifact.representation_delta.semantic_content_changed)
        self.assertNotEqual(artifact.before_text_raw_hash, artifact.proposed_text_raw_hash)
        self.assertNotEqual(artifact.before_semantic_text_hash, artifact.proposed_semantic_text_hash)

    def test_039_line_ending_only_delta_remains_visible_with_empty_semantic_diff(self) -> None:
        proposal = self.make_proposal(body="one\ntwo\n")
        result = self.validate(proposal)
        current = self.snapshot("one\r\ntwo\r\n")
        artifact = self.review(
            proposal,
            result,
            self.state(current=current, baseline=current),
        )
        self.assertEqual(artifact.deterministic_text_diff, "")
        self.assertEqual(artifact.findings, ())
        self.assertEqual(artifact.status, ReviewStatus.CLEAR)
        self.assertTrue(artifact.representation_delta.raw_text_changed_semantic_equal)
        self.assertIn("CRLF -> LF", artifact.human_review_preview)


    def test_040_terminal_newline_only_delta_remains_visible(self) -> None:
        artifact = self.clear_update_artifact(before="same", after="same\n")
        self.assertTrue(artifact.representation_delta.terminal_newline_changed)
        self.assertIn("terminal newline changed: true", artifact.human_review_preview)
        self.assertNotEqual(
            artifact.representation_delta.identity,
            self.clear_update_artifact(before="same\n", after="same\nmore\n").representation_delta.identity,
        )

    def test_041_body_equality_does_not_claim_complete_content_identity(self) -> None:
        artifact = self.clear_update_artifact(before="same\n", after="same\n")
        codes = {finding.code for finding in artifact.findings}
        self.assertNotIn(ConflictCode.PROPOSED_CONTENT_ALREADY_IDENTICAL, codes)
        self.assertNotIn(ConflictCode.PROPOSED_CONTENT_SEMANTICALLY_EQUIVALENT, codes)
        self.assertEqual(artifact.status, ReviewStatus.CLEAR)
        self.assertEqual(artifact.deterministic_text_diff, "")
        self.assertFalse(artifact.representation_delta.semantic_content_changed)
        self.assertIn("current structured metadata comparison: unavailable", artifact.human_review_preview)


    def test_042_body_semantic_equivalence_does_not_claim_complete_equivalence(self) -> None:
        proposal = self.make_proposal(body="same\n")
        result = self.validate(proposal)
        current = self.snapshot("same\r\n")
        artifact = self.review(
            proposal,
            result,
            self.state(current=current, baseline=current),
        )
        codes = {finding.code for finding in artifact.findings}
        self.assertNotIn(ConflictCode.PROPOSED_CONTENT_SEMANTICALLY_EQUIVALENT, codes)
        self.assertNotIn(ConflictCode.PROPOSED_CONTENT_ALREADY_IDENTICAL, codes)
        self.assertEqual(artifact.status, ReviewStatus.CLEAR)
        self.assertTrue(artifact.representation_delta.raw_text_changed_semantic_equal)


    def test_043_semantic_content_change_has_no_proposal_effect_finding(self) -> None:
        artifact = self.clear_update_artifact(before="before\n", after="after\n")
        effect_codes = {
            ConflictCode.PROPOSED_CONTENT_ALREADY_IDENTICAL,
            ConflictCode.PROPOSED_CONTENT_SEMANTICALLY_EQUIVALENT,
        }
        self.assertTrue(artifact.representation_delta.semantic_content_changed)
        self.assertTrue(effect_codes.isdisjoint({finding.code for finding in artifact.findings}))
        self.assertEqual(artifact.status, ReviewStatus.CLEAR)

    def test_044_unproven_complete_equality_findings_are_both_absent(self) -> None:
        exact = self.clear_update_artifact(before="x\n", after="x\n")
        semantic = self.clear_update_artifact(before="x\r\n", after="x\n")
        effect_codes = {
            ConflictCode.PROPOSED_CONTENT_ALREADY_IDENTICAL,
            ConflictCode.PROPOSED_CONTENT_SEMANTICALLY_EQUIVALENT,
        }
        self.assertTrue(effect_codes.isdisjoint({item.code for item in exact.findings}))
        self.assertTrue(effect_codes.isdisjoint({item.code for item in semantic.findings}))
        self.assertEqual(exact.status, ReviewStatus.CLEAR)
        self.assertEqual(semantic.status, ReviewStatus.CLEAR)


    def test_045_findings_have_fixed_documented_order(self) -> None:
        proposal = self.make_proposal(
            operation=ProposalOperation.CREATE_NEW,
            target=OTHER_TARGET,
            expected_revision=REV_A,
        )
        result = self.validate(proposal, stable_ids=set())
        artifact = self.review(
            proposal,
            result,
            self.state(revision=REV_B, stable_ids={OTHER_TARGET}),
        )
        self.assertEqual(
            tuple(finding.code for finding in artifact.findings),
            (
                ConflictCode.STALE_VAULT_REVISION,
                ConflictCode.STABLE_ID_COLLISION,
            ),
        )
        self.assertEqual(artifact.status, ReviewStatus.BLOCKED)

    def test_046_duplicate_stale_sources_produce_one_finding(self) -> None:
        proposal = self.make_proposal(expected_revision=REV_A)
        result = self.validate(proposal, vault_revision=REV_B)
        current = self.snapshot("old\n", revision=REV_B)
        artifact = self.review(
            proposal,
            result,
            self.state(revision=REV_C, current=current),
        )
        stale_findings = [
            finding
            for finding in artifact.findings
            if finding.code is ConflictCode.STALE_VAULT_REVISION
        ]
        self.assertEqual(len(stale_findings), 1)
        self.assertEqual(len({finding.code for finding in artifact.findings}), len(artifact.findings))

    def test_047_clear_status_requires_valid_result_and_zero_findings(self) -> None:
        artifact = self.clear_create_artifact()
        self.assertEqual(artifact.validation_outcome, "VALID")
        self.assertEqual(artifact.findings, ())
        self.assertEqual(artifact.status, ReviewStatus.CLEAR)

    def test_048_blocked_status_follows_any_blocking_finding(self) -> None:
        proposal = self.make_proposal(
            operation=ProposalOperation.CREATE_NEW,
            target=OTHER_TARGET,
        )
        result = self.validate(proposal, stable_ids=set())
        artifact = self.review(
            proposal,
            result,
            self.state(stable_ids={OTHER_TARGET}),
        )
        self.assertTrue(any(f.severity is ConflictSeverity.BLOCKING for f in artifact.findings))
        self.assertEqual(artifact.status, ReviewStatus.BLOCKED)
        self.assertIsNone(artifact.change_identity)

    def test_049_review_required_follows_only_nonblocking_findings(self) -> None:
        proposal = self.make_proposal(body="same\n")
        result = self.validate(proposal)
        current = self.snapshot("same\n")
        artifact = self.review(
            proposal,
            result,
            self.state(current=current, baseline=None),
        )
        self.assertTrue(artifact.findings)
        self.assertTrue(all(f.severity is ConflictSeverity.REVIEW for f in artifact.findings))
        self.assertEqual(
            tuple(f.code for f in artifact.findings),
            (ConflictCode.TARGET_STATE_COMPARISON_UNAVAILABLE,),
        )
        self.assertEqual(artifact.status, ReviewStatus.REVIEW_REQUIRED)


    def test_050_review_identity_is_deterministic(self) -> None:
        first = self.clear_update_artifact(before="a\n", after="b\n")
        second = self.clear_update_artifact(before="a\n", after="b\n")
        self.assertEqual(first.review_artifact_identity, second.review_artifact_identity)
        self.assertEqual(first.change_identity, second.change_identity)
        self.assertEqual(first.validation_snapshot, second.validation_snapshot)

    def test_051_identity_domains_are_separated(self) -> None:
        artifact = self.clear_update_artifact(before="a\n", after="b\n")
        digest_values = {
            artifact.deterministic_text_diff_hash,
            artifact.representation_delta.identity,
            "sha256:" + artifact.change_identity.removeprefix("kchange:"),
            "sha256:" + artifact.review_artifact_identity.removeprefix("kreview:"),
        }
        self.assertEqual(len(digest_values), 4)
        self.assertTrue(artifact.change_identity.startswith("kchange:"))
        self.assertTrue(artifact.review_artifact_identity.startswith("kreview:"))

    def test_052_full_diff_is_deterministic_with_fixed_headers_and_context(self) -> None:
        first = self.clear_update_artifact(
            before="0\n1\n2\n3\n4\n5\n6\n",
            after="0\n1\n2\nX\n4\n5\n6\n",
        )
        second = self.clear_update_artifact(
            before="0\n1\n2\n3\n4\n5\n6\n",
            after="0\n1\n2\nX\n4\n5\n6\n",
        )
        diff = first.deterministic_text_diff or ""
        self.assertEqual(diff, second.deterministic_text_diff)
        self.assertIn("--- before-body/canonical.current-state\n", diff)
        self.assertIn("+++ after-body/canonical.current-state\n", diff)
        self.assertIn("@@ -1,7 +1,7 @@", diff)


    def test_053_full_diff_hash_changes_when_full_diff_changes(self) -> None:
        first = self.clear_update_artifact(before="a\n", after="b\n")
        second = self.clear_update_artifact(before="a\n", after="c\n")
        self.assertNotEqual(first.deterministic_text_diff, second.deterministic_text_diff)
        self.assertNotEqual(first.deterministic_text_diff_hash, second.deterministic_text_diff_hash)
        self.assertNotEqual(first.change_identity, second.change_identity)

    def test_054_representation_identity_tracks_line_endings_and_terminal_newline(self) -> None:
        lf = self.clear_update_artifact(before="a\n", after="b\n")
        crlf = self.clear_update_artifact(before="a\r\n", after="b\n")
        no_terminal = self.clear_update_artifact(before="a", after="b\n")
        identities = {
            lf.representation_delta.identity,
            crlf.representation_delta.identity,
            no_terminal.representation_delta.identity,
        }
        self.assertEqual(len(identities), 3)
        self.assertFalse(lf.representation_delta.terminal_newline_changed)
        self.assertTrue(no_terminal.representation_delta.terminal_newline_changed)

    def test_055_preview_is_bounded_by_bytes_and_lines(self) -> None:
        body = "\n".join(f"new-{index}-" + "x" * 120 for index in range(1000)) + "\n"
        before = "\n".join(f"old-{index}-" + "y" * 120 for index in range(1000)) + "\n"
        artifact = self.clear_update_artifact(before=before, after=body)
        preview = artifact.human_review_preview
        self.assertLessEqual(len(preview.encode("utf-8")), MAX_PREVIEW_BYTES)
        self.assertLessEqual(len(preview.splitlines()), MAX_PREVIEW_LINES)
        self.assertIn(TRUNCATION_MARKER, preview)
        self.assertGreater(len((artifact.deterministic_text_diff or "").encode("utf-8")), len(preview.encode("utf-8")))

    def test_056_preview_truncation_is_deterministic(self) -> None:
        before = "\n".join(f"before-{index}" for index in range(900)) + "\n"
        after = "\n".join(f"after-{index}" for index in range(900)) + "\n"
        first = self.clear_update_artifact(before=before, after=after)
        second = self.clear_update_artifact(before=before, after=after)
        self.assertEqual(first.human_review_preview, second.human_review_preview)
        self.assertTrue(first.human_review_preview.endswith(TRUNCATION_MARKER + "\n"))
        self.assertEqual(first.human_review_preview.count(TRUNCATION_MARKER), 1)

    def test_057_stable_id_collection_bound_fails_closed(self) -> None:
        proposal = self.make_proposal(
            operation=ProposalOperation.CREATE_NEW,
            target=OTHER_TARGET,
        )
        result = self.validate(proposal, stable_ids=set())
        too_many = frozenset(f"id.{index}" for index in range(MAX_STABLE_IDS + 1))
        with self.assertRaisesRegex(ValueError, "hard bound"):
            self.state(stable_ids=too_many)
        artifact = self.review(proposal, result, self.state(stable_ids=set()))
        self.assertEqual(artifact.status, ReviewStatus.CLEAR)

    def test_058_proposed_content_utf8_byte_bound_is_enforced(self) -> None:
        body = "🚀" * ((MAX_PROPOSED_CONTENT_BYTES // 4) + 1)
        proposal = self.make_proposal(
            operation=ProposalOperation.CREATE_NEW,
            target=OTHER_TARGET,
            body=body,
        )
        result = self.validate(proposal, stable_ids=set())
        with self.assertRaisesRegex(ValueError, "byte bound"):
            self.review(proposal, result, self.state(stable_ids=set()))

    def test_059_input_stable_id_collection_is_copied_and_not_mutated(self) -> None:
        proposal = self.make_proposal(
            operation=ProposalOperation.CREATE_NEW,
            target=OTHER_TARGET,
        )
        result = self.validate(proposal, stable_ids={TARGET})
        caller_set = {TARGET}
        state = CurrentKnowledgeState(REV_A, caller_set)
        caller_set.add(OTHER_TARGET)
        artifact = self.review(proposal, result, state)
        self.assertEqual(state.current_stable_ids, frozenset({TARGET}))
        self.assertEqual(artifact.status, ReviewStatus.CLEAR)
        self.assertEqual(caller_set, {TARGET, OTHER_TARGET})

    def test_060_artifact_and_nested_collections_are_immutable(self) -> None:
        artifact = self.clear_update_artifact()
        with self.assertRaises(FrozenInstanceError):
            artifact.status = ReviewStatus.BLOCKED
        with self.assertRaises(FrozenInstanceError):
            artifact.proposed_content_snapshot.title = "changed"
        self.assertIsInstance(artifact.findings, tuple)
        self.assertIsInstance(artifact.validation_snapshot, FrozenCanonicalValue)
        self.assertIsInstance(artifact.proposed_content_snapshot, ProposedContentSnapshot)
        self.assertIsInstance(artifact.proposed_content_snapshot.aliases, tuple)
        self.assertIsInstance(artifact.validation_snapshot.mapping_items, tuple)


    def test_061_post_analysis_provenance_mutation_does_not_change_artifact(self) -> None:
        proposal = self.make_proposal(
            operation=ProposalOperation.CREATE_NEW,
            target=OTHER_TARGET,
        )
        result = self.validate(proposal, stable_ids=set())
        artifact = self.review(proposal, result, self.state(stable_ids=set()))
        original_snapshot = artifact.validation_snapshot
        original_identity = artifact.review_artifact_identity
        result.provenance_summary["reason"] = "mutated after analysis"
        result.provenance_summary["nested"] = {"mutable": ["value"]}
        self.assertEqual(artifact.validation_snapshot, original_snapshot)
        self.assertEqual(artifact.review_artifact_identity, original_identity)
        repeated = self.review(proposal, result, self.state(stable_ids=set()))
        self.assertNotEqual(repeated.review_artifact_identity, original_identity)

    def test_062_module_has_no_write_or_persistence_api(self) -> None:
        import modules.knowledge_change_review_ru as review_module

        source = inspect.getsource(review_module)
        tree = ast.parse(source)
        forbidden_calls = {"open", "write_text", "write_bytes", "mkdir", "unlink", "rename", "replace"}
        called = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        self.assertTrue(forbidden_calls.isdisjoint(called))
        artifact = self.clear_create_artifact()
        self.assertEqual(artifact.status, ReviewStatus.CLEAR)

    def test_063_module_has_no_network_subprocess_model_tauri_frontend_coupling(self) -> None:
        import modules.knowledge_change_review_ru as review_module

        source = inspect.getsource(review_module)
        tree = ast.parse(source)
        imported_roots = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        forbidden = {
            "socket", "urllib", "http", "requests", "subprocess", "asyncio",
            "openai", "tauri", "react", "frontend", "model_gateway",
        }
        self.assertTrue(forbidden.isdisjoint(imported_roots))
        artifact = self.clear_update_artifact()
        self.assertIsInstance(artifact, KnowledgeChangeReviewArtifact)

    def test_064_module_uses_no_dynamic_import(self) -> None:
        import modules.knowledge_change_review_ru as review_module

        tree = ast.parse(inspect.getsource(review_module))
        dynamic_names = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in {"__import__", "eval", "exec"}
        }
        self.assertEqual(dynamic_names, set())
        artifact = self.clear_create_artifact()
        self.assertEqual(artifact.findings, ())

    def test_065_create_path_emits_no_update_only_findings(self) -> None:
        artifact = self.clear_create_artifact()
        update_only = {
            ConflictCode.TARGET_MISSING,
            ConflictCode.TARGET_CHANGED_SINCE_PROPOSAL,
            ConflictCode.TARGET_STATE_COMPARISON_UNAVAILABLE,
            ConflictCode.TARGET_SOURCE_BYTES_CHANGED_TEXT_IDENTICAL,
            ConflictCode.PROPOSED_CONTENT_ALREADY_IDENTICAL,
            ConflictCode.PROPOSED_CONTENT_SEMANTICALLY_EQUIVALENT,
        }
        self.assertTrue(update_only.isdisjoint({finding.code for finding in artifact.findings}))
        self.assertFalse(artifact.representation_delta.before_present)
        self.assertIsNone(artifact.before_text_raw_hash)

    def test_066_update_path_never_emits_create_collision(self) -> None:
        artifact = self.clear_update_artifact(before="old\n", after="new\n")
        self.assertNotIn(
            ConflictCode.STABLE_ID_COLLISION,
            {finding.code for finding in artifact.findings},
        )
        self.assertTrue(artifact.representation_delta.before_present)
        self.assertEqual(artifact.status, ReviewStatus.CLEAR)

    def test_067_current_state_rejects_noncanonical_stable_id_grammar(self) -> None:
        with self.assertRaisesRegex(ValueError, "invalid stable ID"):
            CurrentKnowledgeState(
                observed_vault_revision=REV_A,
                current_stable_ids=frozenset({"lc:Bad ID"}),
            )
        artifact = self.clear_create_artifact()
        self.assertNotIn("lc:", artifact.target_stable_id)
        self.assertEqual(artifact.status, ReviewStatus.CLEAR)

    def test_068_snapshot_hash_helpers_bind_exact_bytes_raw_text_and_semantics(self) -> None:
        text = "é\r\nline\n"
        source = text.encode("utf-8")
        snapshot = create_trusted_target_snapshot(
            source_bytes=source,
            source_relative_path="canonical/current-state.md",
            target_stable_id=TARGET,
            captured_vault_revision=REV_A,
        )
        proposal = self.make_proposal(body="changed\n")
        result = self.validate(proposal)
        artifact = self.review(
            proposal,
            result,
            self.state(current=snapshot, baseline=snapshot),
        )
        self.assertEqual(snapshot.source_byte_hash, "sha256:" + hashlib.sha256(source).hexdigest())
        self.assertEqual(snapshot.text_raw_hash, compute_text_raw_hash(text))
        self.assertEqual(snapshot.semantic_text_hash, compute_semantic_text_hash(text))
        self.assertEqual(artifact.before_source_byte_hash, snapshot.source_byte_hash)


    def test_069_source_byte_only_tampering_is_rejected_before_delta_identity(self) -> None:
        proposal = self.make_proposal(body="same\n")
        result = self.validate(proposal)
        valid = self.snapshot("same\n")
        tampered_bytes = b"same\r\n"
        tampered = replace(
            valid,
            source_bytes=tampered_bytes,
            source_byte_hash=compute_source_byte_hash(tampered_bytes),
        )
        artifact = self.review(
            proposal,
            result,
            self.state(current=tampered, baseline=valid),
        )
        self.assertEqual(artifact.status, ReviewStatus.BLOCKED)
        self.assertIn("bytes_text_mismatch", dict(artifact.findings[0].details)["errors"])
        self.assertIsNone(artifact.representation_delta)
        self.assertIsNone(artifact.change_identity)

    def test_070_evidence_reference_bound_is_rechecked_at_e9b_boundary(self) -> None:
        proposal = self.make_proposal(
            operation=ProposalOperation.CREATE_NEW,
            target=OTHER_TARGET,
            evidence_count=1,
        )
        extra = tuple(
            EvidenceReference(reference=f"X-{index}", description="bounded")
            for index in range(33)
        )
        object.__setattr__(proposal.provenance, "evidence_references", extra)
        result = self.validate(proposal, stable_ids=set())
        with self.assertRaisesRegex(ValueError, "evidence references"):
            self.review(proposal, result, self.state(stable_ids=set()))

    def test_071_provenance_entry_bound_rejects_maximal_nested_valid_source_data(self) -> None:
        proposal = self.make_proposal(
            operation=ProposalOperation.CREATE_NEW,
            target=OTHER_TARGET,
            evidence_count=32,
        )
        result = self.validate(proposal, stable_ids=set())
        with self.assertRaisesRegex(ValueError, "provenance entries"):
            self.review(proposal, result, self.state(stable_ids=set()))

    def test_072_snapshot_path_length_bound_fails_closed(self) -> None:
        proposal = self.make_proposal()
        result = self.validate(proposal)
        valid = self.snapshot("old\n")
        oversized_path = "a/" + "b" * 600 + ".md"
        bad = replace(valid, source_relative_path=oversized_path)
        artifact = self.review(
            proposal,
            result,
            self.state(current=bad, baseline=valid),
        )
        self.assertEqual(artifact.findings[0].code, ConflictCode.UNVERIFIED_TEXT_INPUT)
        self.assertIn("invalid_relative_path", dict(artifact.findings[0].details)["errors"])
        self.assertIsNone(artifact.deterministic_text_diff)

    def test_073_stable_id_length_bound_is_enforced_on_current_state(self) -> None:
        oversized_id = "a" * 129
        with self.assertRaisesRegex(ValueError, "invalid stable ID"):
            CurrentKnowledgeState(
                observed_vault_revision=REV_A,
                current_stable_ids=frozenset({oversized_id}),
            )
        artifact = self.clear_create_artifact()
        self.assertEqual(artifact.status, ReviewStatus.CLEAR)
        self.assertLessEqual(len(artifact.target_stable_id), 128)



    def test_074_title_only_change_is_governed_and_visible_without_body_claim(self) -> None:
        baseline = self.metadata_only_artifact()
        changed = self.metadata_only_artifact(title="Renamed Current State")
        self.assertEqual(changed.deterministic_text_diff, "")
        self.assertEqual(changed.proposed_content_snapshot.title, "Renamed Current State")
        self.assertIn('- title: "Renamed Current State"', changed.human_review_preview)
        self.assertNotEqual(baseline.change_identity, changed.change_identity)
        self.assert_no_unproven_equality_findings(changed)

    def test_075_classification_metadata_changes_each_change_governed_identity(self) -> None:
        baseline = self.metadata_only_artifact()
        variants = (
            ("type", "architecture_record"),
            ("status", "proposed"),
            ("knowledge_layer", "architecture"),
        )
        identities: set[str | None] = set()
        for field_name, value in variants:
            with self.subTest(field=field_name):
                artifact = self.metadata_only_artifact(**{field_name: value})
                identities.add(artifact.change_identity)
                self.assertEqual(getattr(artifact.proposed_content_snapshot, field_name), value)
                self.assertIn(f'- {field_name}: "{value}"', artifact.human_review_preview)
                self.assertNotEqual(baseline.review_artifact_identity, artifact.review_artifact_identity)
                self.assert_no_unproven_equality_findings(artifact)
        self.assertEqual(len(identities), len(variants))

    def test_076_evidence_and_authority_metadata_are_not_reduced_to_body_text(self) -> None:
        evidence = self.metadata_only_artifact(evidence_class="B")
        authority = self.metadata_only_artifact(authority="validated-observation")
        self.assertNotEqual(evidence.change_identity, authority.change_identity)
        self.assertIn('- evidence_class: "B"', evidence.human_review_preview)
        self.assertIn('- authority: "validated-observation"', authority.human_review_preview)
        self.assertEqual(evidence.deterministic_text_diff, "")
        self.assertEqual(authority.deterministic_text_diff, "")
        self.assert_no_unproven_equality_findings(evidence)
        self.assert_no_unproven_equality_findings(authority)

    def test_077_canonical_metadata_changes_are_snapshotted_with_exact_types(self) -> None:
        canonical_flag = self.metadata_only_artifact(canonical=False)
        canonical_scope = self.metadata_only_artifact(canonical_scope="architecture")
        self.assertIs(canonical_flag.proposed_content_snapshot.canonical, False)
        self.assertEqual(canonical_scope.proposed_content_snapshot.canonical_scope, "architecture")
        self.assertIn("- canonical: false", canonical_flag.human_review_preview)
        self.assertIn('- canonical_scope: "architecture"', canonical_scope.human_review_preview)
        self.assertNotEqual(canonical_flag.change_identity, canonical_scope.change_identity)

    def test_078_aliases_and_releases_metadata_are_ordered_and_visible(self) -> None:
        aliases = self.metadata_only_artifact(aliases=("state", "current"))
        releases = self.metadata_only_artifact(releases=("v6.84.5.1e9a", "v6.84.5.1e9b"))
        self.assertEqual(aliases.proposed_content_snapshot.aliases, ("state", "current"))
        self.assertEqual(releases.proposed_content_snapshot.releases[-1], "v6.84.5.1e9b")
        self.assertIn('- aliases: ["state","current"]', aliases.human_review_preview)
        self.assertIn('- releases: ["v6.84.5.1e9a","v6.84.5.1e9b"]', releases.human_review_preview)
        self.assertNotEqual(aliases.review_artifact_identity, releases.review_artifact_identity)

    def test_079_source_paths_and_evidence_refs_metadata_are_governed(self) -> None:
        source_paths = self.metadata_only_artifact(
            source_paths=("modules/example.py", "tools/example_test.py"),
        )
        evidence_refs = self.metadata_only_artifact(
            evidence_refs=("EV-000", "EV-001"),
        )
        self.assertIn('"tools/example_test.py"', source_paths.human_review_preview)
        self.assertIn('"EV-001"', evidence_refs.human_review_preview)
        self.assertNotEqual(source_paths.change_identity, evidence_refs.change_identity)
        self.assertEqual(source_paths.deterministic_text_diff, "")
        self.assertEqual(evidence_refs.deterministic_text_diff, "")

    def test_080_supersession_metadata_changes_remain_review_only_not_publication(self) -> None:
        supersedes = self.metadata_only_artifact(supersedes=("canonical.previous-state",))
        superseded_by = self.metadata_only_artifact(superseded_by=("canonical.future-state",))
        self.assertIn('"canonical.previous-state"', supersedes.human_review_preview)
        self.assertIn('"canonical.future-state"', superseded_by.human_review_preview)
        self.assertIn("publication-byte claim: unavailable by contract", supersedes.human_review_preview)
        self.assertFalse(supersedes.representation_delta.after_source_bytes_known)
        self.assertFalse(superseded_by.representation_delta.after_source_bytes_known)

    def test_081_lifecycle_metadata_changes_each_participate_in_identity(self) -> None:
        variants = (
            ("updated", "2026-07-17"),
            ("last_reviewed", "2026-07-18"),
            ("verified_at", "2026-07-16T12:30:00Z"),
        )
        identities: list[str | None] = []
        for field_name, value in variants:
            artifact = self.metadata_only_artifact(**{field_name: value})
            identities.append(artifact.change_identity)
            self.assertIn(field_name, artifact.human_review_preview)
            self.assertEqual(getattr(artifact.proposed_content_snapshot, field_name), value)
            self.assert_no_unproven_equality_findings(artifact)
        self.assertEqual(len(set(identities)), 3)

    def test_082_every_proposed_content_field_is_present_in_snapshot_and_preview(self) -> None:
        artifact = self.metadata_only_artifact(verified_at="2026-07-16T12:30:00Z")
        field_names = tuple(item.name for item in fields(ProposedContentSnapshot))
        self.assertEqual(len(field_names), 18)
        for field_name in field_names:
            with self.subTest(field=field_name):
                self.assertIn(f"- {field_name}:", artifact.human_review_preview)
        self.assertEqual(
            tuple(artifact.proposed_content_snapshot.identity_payload()),
            field_names,
        )

    def test_083_empty_mapping_and_empty_sequence_have_distinct_snapshot_identity(self) -> None:
        proposal_a, result_a, state_a = self.result_with_provenance_summary({"node": {}})
        proposal_b, result_b, state_b = self.result_with_provenance_summary({"node": []})
        artifact_a = self.review(proposal_a, result_a, state_a)
        artifact_b = self.review(proposal_b, result_b, state_b)
        self.assertEqual(artifact_a.status, ReviewStatus.CLEAR)
        self.assertEqual(artifact_b.status, ReviewStatus.CLEAR)
        self.assertNotEqual(
            artifact_a.validation_snapshot.identity_payload(),
            artifact_b.validation_snapshot.identity_payload(),
        )
        self.assertNotEqual(artifact_a.review_artifact_identity, artifact_b.review_artifact_identity)

    def test_084_nested_mapping_and_sequence_type_tags_remain_distinct(self) -> None:
        proposal_a, result_a, state_a = self.result_with_provenance_summary(
            {"outer": [{"inner": []}]},
        )
        proposal_b, result_b, state_b = self.result_with_provenance_summary(
            {"outer": [{"inner": {}}]},
        )
        first = self.review(proposal_a, result_a, state_a)
        second = self.review(proposal_b, result_b, state_b)
        self.assertNotEqual(first.validation_snapshot, second.validation_snapshot)
        first_payload = first.validation_snapshot.identity_payload()
        second_payload = second.validation_snapshot.identity_payload()
        self.assertIn('"type": "sequence"', repr(first_payload).replace("'", '"'))
        self.assertNotEqual(first_payload, second_payload)

    def test_085_validation_snapshot_self_cycle_returns_deterministic_blocked_artifact(self) -> None:
        cyclic: dict[str, object] = {}
        cyclic["self"] = cyclic
        proposal, result, state = self.result_with_provenance_summary(cyclic)
        first = self.review(proposal, result, state)
        second = self.review(proposal, result, state)
        self.assertEqual(first.status, ReviewStatus.BLOCKED)
        self.assertEqual(first.review_artifact_identity, second.review_artifact_identity)
        self.assertIn(("validation_snapshot_error", "cycle_detected"), first.findings[0].details)
        self.assert_no_normal_change_material(first)

    def test_086_validation_snapshot_indirect_cycle_is_caught_without_recursion_error(self) -> None:
        mapping: dict[str, object] = {}
        sequence: list[object] = [mapping]
        mapping["sequence"] = sequence
        proposal, result, state = self.result_with_provenance_summary(mapping)
        artifact = self.review(proposal, result, state)
        self.assertEqual(artifact.status, ReviewStatus.BLOCKED)
        self.assertIn("cycle_detected", repr(artifact.findings))
        self.assertIsInstance(artifact.validation_snapshot, FrozenCanonicalValue)
        self.assert_no_normal_change_material(artifact)

    def test_087_validation_snapshot_excessive_depth_fails_closed(self) -> None:
        value: object = "leaf"
        for _ in range(MAX_VALIDATION_SNAPSHOT_DEPTH + 5):
            value = [value]
        proposal, result, state = self.result_with_provenance_summary(value)
        artifact = self.review(proposal, result, state)
        self.assertEqual(artifact.status, ReviewStatus.BLOCKED)
        self.assertIn("maximum_depth_exceeded", repr(artifact.findings))
        self.assert_no_normal_change_material(artifact)

    def test_088_validation_snapshot_excessive_total_nodes_fails_closed(self) -> None:
        value = [list(range(64)) for _ in range(70)]
        self.assertGreater(1 + 70 + 70 * 64, MAX_VALIDATION_SNAPSHOT_NODES)
        proposal, result, state = self.result_with_provenance_summary(value)
        artifact = self.review(proposal, result, state)
        self.assertIn("maximum_total_nodes_exceeded", repr(artifact.findings))
        self.assertEqual(artifact.status, ReviewStatus.BLOCKED)
        self.assert_no_normal_change_material(artifact)

    def test_089_validation_snapshot_mapping_entry_bound_is_enforced(self) -> None:
        value = {
            f"k{index:03d}": index
            for index in range(MAX_VALIDATION_MAPPING_ENTRIES + 1)
        }
        proposal, result, state = self.result_with_provenance_summary(value)
        artifact = self.review(proposal, result, state)
        self.assertIn("maximum_mapping_entries_exceeded", repr(artifact.findings))
        self.assertEqual(artifact.status, ReviewStatus.BLOCKED)

    def test_090_validation_snapshot_sequence_entry_bound_is_enforced(self) -> None:
        value = list(range(MAX_VALIDATION_SEQUENCE_ENTRIES + 1))
        proposal, result, state = self.result_with_provenance_summary(value)
        artifact = self.review(proposal, result, state)
        self.assertIn("maximum_sequence_entries_exceeded", repr(artifact.findings))
        self.assertIsNone(artifact.deterministic_text_diff_hash)

    def test_091_validation_snapshot_key_length_bound_is_enforced(self) -> None:
        value = {"k" * (MAX_VALIDATION_KEY_LENGTH + 1): "value"}
        proposal, result, state = self.result_with_provenance_summary(value)
        artifact = self.review(proposal, result, state)
        self.assertIn("maximum_mapping_key_length_exceeded", repr(artifact.findings))
        self.assertEqual(artifact.findings[0].code, ConflictCode.UNVERIFIED_TEXT_INPUT)

    def test_092_validation_snapshot_string_value_bound_is_enforced(self) -> None:
        value = {"value": "x" * (MAX_VALIDATION_STRING_LENGTH + 1)}
        proposal, result, state = self.result_with_provenance_summary(value)
        artifact = self.review(proposal, result, state)
        self.assertIn("maximum_string_value_length_exceeded", repr(artifact.findings))
        self.assertEqual(artifact.status, ReviewStatus.BLOCKED)
        self.assert_no_normal_change_material(artifact)

    def test_093_validation_snapshot_unsupported_mutable_type_fails_closed(self) -> None:
        value = {"unsupported": {"set-item"}}
        proposal, result, state = self.result_with_provenance_summary(value)
        artifact = self.review(proposal, result, state)
        self.assertIn("unsupported_value_type", repr(artifact.findings))
        self.assertEqual(artifact.status, ReviewStatus.BLOCKED)
        self.assertIsNone(artifact.change_identity)

    def test_094_windows_drive_root_unc_and_absolute_paths_are_rejected(self) -> None:
        rejected = (
            "C:foo.md",
            "\\foo.md",
            "\\\\server\\share\\foo.md",
            "/foo.md",
            "C:\\foo.md",
        )
        for path in rejected:
            with self.subTest(path=path):
                artifact = self.review_with_invalid_current_path(path)
                self.assertEqual(artifact.status, ReviewStatus.BLOCKED)
                self.assertEqual(artifact.findings[0].code, ConflictCode.UNVERIFIED_TEXT_INPUT)
                self.assert_no_normal_change_material(artifact)

    def test_095_parent_traversal_nul_and_overlength_paths_are_rejected(self) -> None:
        rejected = (
            "canonical/../foo.md",
            "canonical/\x00foo.md",
            "a" * (MAX_PATH_LENGTH + 1),
        )
        observed_errors: set[str] = set()
        for path in rejected:
            artifact = self.review_with_invalid_current_path(path)
            observed_errors.add(artifact.findings[0].details[0][1])
            self.assertEqual(artifact.status, ReviewStatus.BLOCKED)
            self.assert_no_normal_change_material(artifact)
        self.assertEqual(observed_errors, {"invalid_relative_path"})

    def test_096_normal_vault_relative_and_dotted_paths_are_accepted(self) -> None:
        paths = (
            "canonical/current-state.md",
            "architecture.knowledge-layer.md",
            "architecture/knowledge-layer.md",
        )
        for path in paths:
            proposal = self.make_proposal(body="after\n")
            result = self.validate(proposal)
            current = self.snapshot("before\n", path=path)
            artifact = self.review(
                proposal,
                result,
                self.state(current=current, baseline=current),
            )
            self.assertEqual(artifact.status, ReviewStatus.CLEAR)
            self.assertIsNotNone(artifact.change_identity)

    def test_097_string_stable_id_collection_is_rejected_not_split_into_characters(self) -> None:
        with self.assertRaisesRegex(ValueError, "list, tuple, set, or frozenset"):
            CurrentKnowledgeState(
                observed_vault_revision=REV_A,
                current_stable_ids="abc",
            )
        artifact = self.clear_create_artifact()
        self.assertNotEqual(artifact.stable_id_set_hash, compute_text_raw_hash("abc"))

    def test_098_bytes_mapping_generator_and_scalar_stable_id_inputs_are_rejected(self) -> None:
        rejected = (
            b"abc",
            bytearray(b"abc"),
            {TARGET: True},
            (item for item in (TARGET,)),
            [[TARGET]],
            7,
        )
        for value in rejected:
            with self.subTest(value_type=type(value).__name__):
                with self.assertRaises(ValueError):
                    CurrentKnowledgeState(
                        observed_vault_revision=REV_A,
                        current_stable_ids=value,
                    )
        self.assertEqual(self.clear_create_artifact().status, ReviewStatus.CLEAR)

    def test_099_approved_stable_id_collection_types_are_copied_to_frozenset(self) -> None:
        approved = (
            [TARGET],
            (TARGET,),
            {TARGET},
            frozenset({TARGET}),
        )
        proposal = self.make_proposal(
            operation=ProposalOperation.CREATE_NEW,
            target=OTHER_TARGET,
        )
        result = self.validate(proposal, stable_ids={TARGET})
        for collection in approved:
            state = CurrentKnowledgeState(
                observed_vault_revision=REV_A,
                current_stable_ids=collection,
            )
            artifact = self.review(proposal, result, state)
            self.assertIsInstance(state.current_stable_ids, frozenset)
            self.assertEqual(state.current_stable_ids, frozenset({TARGET}))
            self.assertEqual(artifact.status, ReviewStatus.CLEAR)

    def test_100_valid_result_observed_revision_drift_suppresses_normal_change_material(self) -> None:
        proposal = self.make_proposal(expected_revision=REV_A, body="after\n")
        result = self.validate(proposal, vault_revision=REV_A)
        current = self.snapshot("before\n", revision=REV_B)
        baseline = self.snapshot("before\n", revision=REV_A)
        artifact = self.review(
            proposal,
            result,
            self.state(revision=REV_B, current=current, baseline=baseline),
        )
        self.assertEqual(artifact.status, ReviewStatus.BLOCKED)
        self.assertIn(ConflictCode.STALE_VAULT_REVISION, {item.code for item in artifact.findings})
        self.assert_no_normal_change_material(artifact)

    def test_101_validated_revision_mismatch_suppresses_normal_change_material(self) -> None:
        proposal = self.make_proposal(body="after\n")
        result = self.validate(proposal)
        tampered = self.tamper_result(result, validated_vault_revision=REV_B)
        current = self.snapshot("before\n")
        artifact = self.review(
            proposal,
            tampered,
            self.state(current=current, baseline=current),
        )
        self.assertEqual(artifact.status, ReviewStatus.BLOCKED)
        self.assertEqual(artifact.findings[0].code, ConflictCode.STALE_VAULT_REVISION)
        self.assert_no_normal_change_material(artifact)

    def test_102_expected_revision_binding_mismatch_suppresses_normal_change_material(self) -> None:
        proposal = self.make_proposal(
            operation=ProposalOperation.CREATE_NEW,
            target=OTHER_TARGET,
            expected_revision=REV_A,
            body="created\n",
        )
        authentic = self.validate(proposal, stable_ids={TARGET})
        mismatched = self.tamper_result(
            authentic,
            expected_vault_revision=REV_B,
        )
        artifact = self.review(
            proposal,
            mismatched,
            self.state(revision=REV_A, stable_ids={TARGET}),
        )
        codes = tuple(item.code for item in artifact.findings)
        self.assertEqual(codes, (ConflictCode.VALIDATION_RESULT_PROPOSAL_MISMATCH,))
        self.assertEqual(artifact.status.value, "BLOCKED")
        self.assertFalse(any(code is ConflictCode.STALE_VAULT_REVISION for code in codes))
        self.assert_no_normal_change_material(artifact)




if __name__ == "__main__":
    unittest.main(verbosity=2)
