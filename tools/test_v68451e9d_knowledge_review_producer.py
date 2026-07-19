"""Focused tests for the bounded trusted in-memory knowledge-review producer."""

from __future__ import annotations

import builtins
import copy
from dataclasses import FrozenInstanceError, replace
import inspect
import json
from pathlib import Path
import socket
import subprocess
import sys
import unittest
from unittest import mock

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.desktop_control_plane_ru import (
    CONTROL_PLANE_METHODS,
    ControlPlaneLimits,
    DesktopControlPlane,
)
import modules.desktop_control_plane_ru as control_plane_contract
from modules.desktop_sidecar_runtime_ru import CONTROL_PLANE_CAPABILITIES
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
    ValidationResult,
    compute_proposal_instance_id,
)
from modules.knowledge_change_review_ru import (
    CurrentKnowledgeState,
    KnowledgeChangeReviewArtifact,
    ReviewStatus,
    analyze_review,
    create_trusted_target_snapshot,
)


DESKTOP = ROOT / "desktop" / "localcomet-desktop"
REV_A = "sha256:" + "a" * 64
REV_B = "sha256:" + "b" * 64
TARGET = "canonical.current-state"
OTHER_TARGET = "architecture.knowledge-layer"
PRODUCER_TESTS: set[str] = set()
PRODUCER_CALLS = 0
FAULT_RESULTS: list[dict[str, str]] = []


class KnowledgeReviewProducerTests(unittest.TestCase):
    def make_proposal(
        self,
        *,
        operation: ProposalOperation,
        target: str,
        body: str,
    ) -> KnowledgeChangeProposal:
        proposer = ProposerMetadata(
            agent_type="test-agent",
            agent_instance_id="producer-instance",
            model_identifier="none",
            source_workflow="e9d-focused-tests",
        )
        provenance = Provenance(
            reason="bounded producer test",
            source_observation="trusted in-process input",
            related_stable_ids=(target,),
            evidence_references=(
                EvidenceReference(reference="EV-PRODUCER-001", description="producer evidence"),
            ),
            workflow_origin="e9d-focused-test",
        )
        content = ProposedNoteContent(
            title="Producer Review",
            body_text=body,
            type="project_state",
            status="accepted",
            knowledge_layer="canonical",
            evidence_class="A",
            authority="repository",
            canonical=True,
            canonical_scope="producer-review",
            aliases=("producer",),
            releases=("v6.84.5.1e9d",),
            source_paths=("modules/desktop_control_plane_ru.py",),
            evidence_refs=("EV-PRODUCER-001",),
            supersedes=(),
            superseded_by=(),
            updated="2026-07-16",
            last_reviewed="2026-07-16",
            verified_at=None,
        )
        hint = (
            CanonicalLocationHint(
                relative_path=f"canonical/{target.replace('.', '-')}.md",
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
            expected_vault_revision=REV_A,
            proposer=proposer,
            provenance=provenance,
            proposed_content=content,
            canonical_location_hint=hint,
        )
        return KnowledgeChangeProposal(
            proposal_id=compute_proposal_instance_id(temporary),
            contract_version=E9A_CONTRACT_VERSION,
            operation=operation,
            target_stable_id=target,
            expected_vault_revision=REV_A,
            proposer=proposer,
            provenance=provenance,
            proposed_content=content,
            canonical_location_hint=hint,
        )

    def make_inputs(
        self,
        kind: str = "create",
        *,
        target: str = OTHER_TARGET,
        body: str = "created by trusted producer\n",
    ) -> tuple[KnowledgeChangeProposal, ValidationResult, CurrentKnowledgeState]:
        if kind == "update" or kind == "review_required":
            proposal = self.make_proposal(
                operation=ProposalOperation.UPDATE_EXISTING,
                target=TARGET,
                body=body,
            )
            validation = ProposalValidator(REV_A, {TARGET}).validate(proposal)
            current = create_trusted_target_snapshot(
                source_bytes=b"existing body\n",
                source_relative_path="canonical/current-state.md",
                target_stable_id=TARGET,
                captured_vault_revision=REV_A,
            )
            state = CurrentKnowledgeState(
                observed_vault_revision=REV_A,
                current_stable_ids={TARGET},
                current_target=current,
                baseline_target=current if kind == "update" else None,
            )
            return proposal, validation, state

        proposal = self.make_proposal(
            operation=ProposalOperation.CREATE_NEW,
            target=target,
            body=body,
        )
        validation = ProposalValidator(REV_A, {TARGET}).validate(proposal)
        state = CurrentKnowledgeState(
            observed_vault_revision=REV_B if kind == "blocked" else REV_A,
            current_stable_ids={TARGET},
        )
        return proposal, validation, state

    def produce(
        self,
        plane: DesktopControlPlane,
        inputs: tuple[KnowledgeChangeProposal, ValidationResult, CurrentKnowledgeState],
    ) -> KnowledgeChangeReviewArtifact:
        global PRODUCER_CALLS
        PRODUCER_CALLS += 1
        PRODUCER_TESTS.add(self._testMethodName)
        return plane.produce_knowledge_review(*inputs)

    @staticmethod
    def list_reviews(plane: DesktopControlPlane) -> dict[str, object]:
        return dict(
            plane.dispatch(
                "knowledge.review.list",
                {"offset": 0, "limit": 50},
                request_id="producer-list",
            ).response
        )

    @staticmethod
    def get_review(plane: DesktopControlPlane, identity: str) -> dict[str, object]:
        return dict(
            plane.dispatch(
                "knowledge.review.get",
                {"review_artifact_identity": identity},
                request_id="producer-get",
            ).response
        )

    def record_fault(self, name: str, detector: str) -> None:
        FAULT_RESULTS.append({"fault": name, "detector": detector, "result": "DETECTED"})

    def test_001_default_control_plane_remains_truthfully_empty(self) -> None:
        response = self.list_reviews(DesktopControlPlane())
        self.assertEqual(response["items"], [])
        self.assertEqual(response["total_count"], 0)
        self.assertEqual(response["source"], "LOCAL_CONTROL_PLANE")
        self.assertIs(response["fixture"], False)

    def test_002_real_create_new_clear_artifact_is_produced(self) -> None:
        artifact = self.produce(DesktopControlPlane(), self.make_inputs())
        self.assertIs(type(artifact), KnowledgeChangeReviewArtifact)
        self.assertIs(artifact.status, ReviewStatus.CLEAR)
        self.assertEqual(artifact.operation, "CREATE_NEW")

    def test_003_real_update_existing_clear_artifact_is_produced(self) -> None:
        artifact = self.produce(
            DesktopControlPlane(),
            self.make_inputs("update", body="updated body\n"),
        )
        self.assertIs(artifact.status, ReviewStatus.CLEAR)
        self.assertEqual(artifact.operation, "UPDATE_EXISTING")
        self.assertIsNotNone(artifact.change_identity)

    def test_004_review_required_artifact_is_preserved(self) -> None:
        artifact = self.produce(
            DesktopControlPlane(),
            self.make_inputs("review_required", body="review body\n"),
        )
        self.assertIs(artifact.status, ReviewStatus.REVIEW_REQUIRED)
        self.assertTrue(artifact.findings)

    def test_005_blocked_artifact_is_not_filtered(self) -> None:
        plane = DesktopControlPlane()
        artifact = self.produce(plane, self.make_inputs("blocked"))
        listed = self.list_reviews(plane)
        fetched = self.get_review(plane, artifact.review_artifact_identity)
        self.assertIs(artifact.status, ReviewStatus.BLOCKED)
        self.assertEqual(listed["returned_count"], 1)
        self.assertEqual(fetched["projection"]["status"], "BLOCKED")
        self.assertIsNone(fetched["projection"]["change_identity"])
        self.record_fault("blocked artifact filtered out", "produced BLOCKED list/get retention")

    def test_006_produced_artifact_is_immediately_visible_through_list(self) -> None:
        plane = DesktopControlPlane()
        artifact = self.produce(plane, self.make_inputs())
        response = self.list_reviews(plane)
        self.assertEqual(response["total_count"], 1)
        self.assertEqual(response["items"][0]["review_artifact_identity"], artifact.review_artifact_identity)

    def test_007_produced_artifact_is_visible_through_exact_get(self) -> None:
        plane = DesktopControlPlane()
        artifact = self.produce(plane, self.make_inputs("update"))
        response = self.get_review(plane, artifact.review_artifact_identity)
        self.assertEqual(response["contract"], "localcomet.knowledge-review-get/1.0")
        self.assertEqual(response["projection"]["review_artifact_identity"], artifact.review_artifact_identity)

    def test_008_exact_kprop_kchange_kreview_identities_are_preserved(self) -> None:
        plane = DesktopControlPlane()
        proposal, validation, state = self.make_inputs("update", body="identity body\n")
        artifact = self.produce(plane, (proposal, validation, state))
        projection = self.get_review(plane, artifact.review_artifact_identity)["projection"]
        self.assertEqual(projection["proposal_id"], proposal.proposal_id)
        self.assertEqual(projection["change_identity"], artifact.change_identity)
        self.assertEqual(projection["review_artifact_identity"], artifact.review_artifact_identity)

    def test_009_ordering_is_deterministic_independent_of_production_order(self) -> None:
        inputs = [
            self.make_inputs(target=f"producer.target-{index:03d}", body=f"body {index}\n")
            for index in range(3)
        ]
        expected = sorted(analyze_review(*item).review_artifact_identity for item in inputs)
        plane = DesktopControlPlane()
        for item in reversed(inputs):
            self.produce(plane, item)
        actual = [item["review_artifact_identity"] for item in self.list_reviews(plane)["items"]]
        self.assertEqual(actual, expected)
        self.record_fault("ordering made nondeterministic", "reverse insertion canonical-order assertion")

    def test_010_exact_duplicate_production_is_idempotent(self) -> None:
        plane = DesktopControlPlane()
        inputs = self.make_inputs()
        first = self.produce(plane, inputs)
        second = self.produce(plane, inputs)
        self.assertIs(first, second)
        self.assertEqual(self.list_reviews(plane)["total_count"], 1)

    def test_011_identity_collision_with_unequal_artifact_fails_closed(self) -> None:
        plane = DesktopControlPlane()
        inputs = self.make_inputs()
        original = self.produce(plane, inputs)
        collision = replace(
            original,
            human_review_preview=original.human_review_preview + "\ncollision probe",
        )
        with mock.patch.object(control_plane_contract, "analyze_review", return_value=collision):
            with self.assertRaisesRegex(ValueError, "collision"):
                self.produce(plane, inputs)
        fetched = self.get_review(plane, original.review_artifact_identity)["projection"]
        self.assertNotIn("collision probe", fetched["human_review_preview"]["preview_text"])
        self.record_fault("duplicate collision silently overwritten", "unequal same-identity injection")

    def test_012_arbitrary_mapping_proposal_is_rejected(self) -> None:
        plane = DesktopControlPlane()
        _, validation, state = self.make_inputs()
        PRODUCER_TESTS.add(self._testMethodName)
        with self.assertRaisesRegex(TypeError, "exact KnowledgeChangeProposal"):
            plane.produce_knowledge_review({}, validation, state)
        self.record_fault("arbitrary mapping accepted", "exact proposal type gate")

    def test_013_wrong_validation_type_is_rejected(self) -> None:
        plane = DesktopControlPlane()
        proposal, _, state = self.make_inputs()
        PRODUCER_TESTS.add(self._testMethodName)
        with self.assertRaisesRegex(TypeError, "exact ValidationResult"):
            plane.produce_knowledge_review(proposal, {}, state)

    def test_014_wrong_current_state_type_is_rejected(self) -> None:
        plane = DesktopControlPlane()
        proposal, validation, _ = self.make_inputs()
        PRODUCER_TESTS.add(self._testMethodName)
        with self.assertRaisesRegex(TypeError, "exact CurrentKnowledgeState"):
            plane.produce_knowledge_review(proposal, validation, {})

    def test_015_hard_artifact_count_bound_rejects_distinct_addition(self) -> None:
        plane = DesktopControlPlane(
            limits=ControlPlaneLimits(maximum_knowledge_review_artifacts=1),
        )
        self.produce(plane, self.make_inputs(target="producer.bound-first"))
        with self.assertRaisesRegex(ValueError, "limit reached"):
            self.produce(plane, self.make_inputs(target="producer.bound-second"))
        self.record_fault("artifact bound disabled", "one-item ControlPlaneLimits boundary")

    def test_016_full_collection_fails_without_hidden_eviction(self) -> None:
        plane = DesktopControlPlane(
            limits=ControlPlaneLimits(maximum_knowledge_review_artifacts=1),
        )
        first = self.produce(plane, self.make_inputs(target="producer.eviction-first"))
        with self.assertRaises(ValueError):
            self.produce(plane, self.make_inputs(target="producer.eviction-second"))
        response = self.list_reviews(plane)
        self.assertEqual(response["total_count"], 1)
        self.assertEqual(response["items"][0]["review_artifact_identity"], first.review_artifact_identity)
        self.record_fault("hidden eviction enabled", "full-list retention after rejected add")

    def test_017_source_inputs_are_not_mutated_or_retained_mutably(self) -> None:
        plane = DesktopControlPlane()
        proposal, validation, state = self.make_inputs()
        proposal_before = copy.deepcopy(proposal.to_dict())
        validation_before = copy.deepcopy(validation.to_dict())
        stable_ids_before = state.current_stable_ids
        artifact = self.produce(plane, (proposal, validation, state))
        self.assertEqual(proposal.to_dict(), proposal_before)
        self.assertEqual(validation.to_dict(), validation_before)
        self.assertIs(state.current_stable_ids, stable_ids_before)
        before = self.get_review(plane, artifact.review_artifact_identity)
        validation.provenance_summary["reason"] = "caller mutation after production"
        after = self.get_review(plane, artifact.review_artifact_identity)
        self.assertEqual(before, after)

    def test_018_returned_artifact_is_an_immutable_snapshot(self) -> None:
        artifact = self.produce(DesktopControlPlane(), self.make_inputs())
        with self.assertRaises(FrozenInstanceError):
            artifact.status = ReviewStatus.BLOCKED
        self.assertFalse(hasattr(artifact, "__dict__"))

    def test_019_constructor_injection_remains_compatible_with_production(self) -> None:
        injected = analyze_review(*self.make_inputs(target="producer.injected"))
        plane = DesktopControlPlane(knowledge_reviews=[injected])
        produced = self.produce(plane, self.make_inputs(target="producer.produced"))
        identities = [item["review_artifact_identity"] for item in self.list_reviews(plane)["items"]]
        self.assertEqual(identities, sorted((injected.review_artifact_identity, produced.review_artifact_identity)))

    def test_020_real_analyze_review_dependency_cannot_be_bypassed(self) -> None:
        plane = DesktopControlPlane()
        with mock.patch.object(
            control_plane_contract,
            "analyze_review",
            wraps=analyze_review,
        ) as analyzer:
            artifact = self.produce(plane, self.make_inputs())
        analyzer.assert_called_once()
        self.assertIs(type(artifact), KnowledgeChangeReviewArtifact)
        self.record_fault("analyze_review bypassed", "wrapped real analyzer call assertion")

    def test_021_producer_is_not_exposed_as_an_ipc_method(self) -> None:
        self.produce(DesktopControlPlane(), self.make_inputs())
        self.assertEqual(
            {method for method in CONTROL_PLANE_METHODS if method.startswith("knowledge.review.")},
            {
                "knowledge.review.decision.create",
                "knowledge.review.get",
                "knowledge.review.list",
                "knowledge.review.refresh",
                "knowledge.review.snapshot",
            },
        )
        self.assertNotIn("produce_knowledge_review", CONTROL_PLANE_METHODS)
        self.assertNotIn("knowledge.review.register", CONTROL_PLANE_METHODS)
        self.assertNotIn("knowledge.review.upload", CONTROL_PLANE_METHODS)
        self.record_fault("producer exposed as IPC method", "exact review allowlist assertion")

    def test_022_no_sidecar_rust_tauri_or_frontend_producer_surface_exists(self) -> None:
        self.produce(DesktopControlPlane(), self.make_inputs())
        self.assertEqual(tuple(CONTROL_PLANE_METHODS), tuple(CONTROL_PLANE_CAPABILITIES))
        paths = (
            DESKTOP / "src-tauri" / "src" / "control_plane.rs",
            DESKTOP / "src-tauri" / "src" / "lib.rs",
            DESKTOP / "src" / "lib" / "bridge" / "knowledgeReview.ts",
        )
        combined = "\n".join(path.read_text(encoding="utf-8") for path in paths)
        self.assertNotIn("produce_knowledge_review", combined)
        self.assertNotIn("knowledge.review.produce", combined)

    def test_023_no_registration_or_decision_creation_vocabulary_in_producer(self) -> None:
        self.produce(DesktopControlPlane(), self.make_inputs())
        source = inspect.getsource(DesktopControlPlane.produce_knowledge_review).lower()
        for forbidden in (
            "register",
            "upload",
            "replace_all",
            "humanreviewdecision",
            "kdecision",
            "decision.create",
            "vault",
            "publish",
        ):
            self.assertNotIn(forbidden, source)

    def test_024_production_uses_no_filesystem_network_subprocess_or_model_path(self) -> None:
        plane = DesktopControlPlane()
        inputs = self.make_inputs()
        with (
            mock.patch.object(builtins, "open", side_effect=AssertionError("filesystem access")),
            mock.patch.object(Path, "open", side_effect=AssertionError("filesystem access")),
            mock.patch.object(socket, "socket", side_effect=AssertionError("network access")),
            mock.patch.object(socket, "create_connection", side_effect=AssertionError("network access")),
            mock.patch.object(subprocess, "Popen", side_effect=AssertionError("subprocess access")),
            mock.patch.object(subprocess, "run", side_effect=AssertionError("subprocess access")),
        ):
            artifact = self.produce(plane, inputs)
        source = inspect.getsource(DesktopControlPlane.produce_knowledge_review).lower()
        self.assertNotIn("model", source)
        self.assertNotIn("persist", source)
        self.assertIs(type(artifact), KnowledgeChangeReviewArtifact)

    def test_025_list_get_contracts_and_real_source_remain_unchanged(self) -> None:
        plane = DesktopControlPlane()
        artifact = self.produce(plane, self.make_inputs())
        listed = self.list_reviews(plane)
        fetched = self.get_review(plane, artifact.review_artifact_identity)
        self.assertEqual(listed["contract"], "localcomet.knowledge-review-list/1.0")
        self.assertEqual(fetched["contract"], "localcomet.knowledge-review-get/1.0")
        for response in (listed, fetched):
            self.assertEqual(response["source"], "LOCAL_CONTROL_PLANE")
            self.assertIs(response["fixture"], False)


def _run() -> int:
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(KnowledgeReviewProducerTests)
    expected_tests = suite.countTestCases()
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    transitive_count = len(PRODUCER_TESTS)
    transitive_ratio = transitive_count / expected_tests if expected_tests else 0.0
    evidence = {
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "successful": result.wasSuccessful(),
        "producer_api_calls": PRODUCER_CALLS,
        "tests_transitively_calling_producer": transitive_count,
        "transitive_ratio": transitive_ratio,
        "deliberate_faults": sorted(FAULT_RESULTS, key=lambda item: item["fault"]),
    }
    print("PRODUCER_EVIDENCE_JSON=" + json.dumps(evidence, sort_keys=True, ensure_ascii=False))
    if transitive_ratio < 0.8:
        print("PRODUCER_SUBSTANCE_FAILURE=less than 80% of focused tests called producer")
        return 1
    if len(FAULT_RESULTS) < 8:
        print("PRODUCER_FAULT_FAILURE=fewer than 8 deliberate faults detected")
        return 1
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(_run())
