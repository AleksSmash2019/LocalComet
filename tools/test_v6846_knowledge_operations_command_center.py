"""Focused v6.84.6 Human-Governed Knowledge Operations Command Center tests."""

from __future__ import annotations

import inspect
import json
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.desktop_control_plane_ru import (
    CONTROL_PLANE_METHODS,
    ControlPlaneError,
    ControlPlaneLimits,
    DesktopControlPlane,
    validate_control_plane_payload,
)
from modules.knowledge_contract_ru import KnowledgeAdapterError, KnowledgeErrorCode
from modules.knowledge_change_review_decision_ru import CONTRACT_VERSION as DECISION_CONTRACT
from modules.knowledge_change_review_ru import CONTRACT_VERSION as REVIEW_CONTRACT, ReviewStatus
import tools.test_v68451e9d_knowledge_review_producer as producer_fixtures

REV_A = producer_fixtures.REV_A
REV_B = producer_fixtures.REV_B


class _ReadOnlyAdapter:
    """Model the real adapter distinction between cached and filesystem revisions."""

    def __init__(
        self,
        cached_revision: str | None = REV_A,
        filesystem_revision: str | None | object = ...,
        *,
        refresh_failure: bool = False,
    ) -> None:
        self.cached_revision = cached_revision
        self.filesystem_revision = (
            cached_revision if filesystem_revision is ... else filesystem_revision
        )
        self.refresh_failure = refresh_failure
        self.refresh_calls = 0

    def status(self) -> dict[str, object]:
        return {
            "state": "READY" if self.cached_revision else "NOT_CONFIGURED",
            "vault_revision": self.cached_revision,
            "last_error_code": (
                None if self.cached_revision else "KNOWLEDGE_NOT_CONFIGURED"
            ),
        }

    def refresh(self) -> dict[str, object]:
        self.refresh_calls += 1
        if self.refresh_failure:
            raise KnowledgeAdapterError(
                KnowledgeErrorCode.KNOWLEDGE_REFRESH_FAILED,
                "test refresh failure",
            )
        self.cached_revision = self.filesystem_revision
        return {
            "state": "READY" if self.cached_revision else "NOT_CONFIGURED",
            "previous_revision": None,
            "current_revision": self.cached_revision,
            "changed": True,
        }


class KnowledgeOperationsCommandCenterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.builder = producer_fixtures.KnowledgeReviewProducerTests()

    def make_plane(
        self,
        *,
        cached_revision: str | None = REV_A,
        filesystem_revision: str | None | object = ...,
        refresh_failure: bool = False,
        refresh_available: bool = True,
        maximum_decisions: int = 128,
    ) -> tuple[DesktopControlPlane, _ReadOnlyAdapter]:
        adapter = _ReadOnlyAdapter(
            cached_revision,
            filesystem_revision,
            refresh_failure=refresh_failure,
        )
        if not refresh_available:
            adapter.refresh = None  # type: ignore[method-assign]
        limits = ControlPlaneLimits(maximum_knowledge_review_decisions=maximum_decisions)
        return DesktopControlPlane(limits=limits, knowledge_adapter=adapter), adapter

    def produce(self, plane: DesktopControlPlane, kind: str = "create"):
        inputs = self.builder.make_inputs(kind)
        return plane.produce_knowledge_review(*inputs)

    def dispatch(self, plane: DesktopControlPlane, method: str, payload: dict[str, object]):
        return plane.dispatch(method, payload, request_id=f"test-{method}").response

    def decision_payload(
        self,
        artifact,
        *,
        decision: str = "APPROVE",
        comment: str = "",
        proposal_id: str | None = None,
        review_identity: str | None = None,
        change_identity: str | None | object = ...,
        revision: str | None = None,
    ) -> dict[str, object]:
        exact_change = artifact.change_identity if change_identity is ... else change_identity
        return {
            "review_contract_version": REVIEW_CONTRACT,
            "proposal_id": proposal_id or artifact.proposal_id,
            "review_artifact_identity": review_identity or artifact.review_artifact_identity,
            "change_identity": exact_change,
            "observed_vault_revision": revision or artifact.observed_vault_revision,
            "decision": decision,
            "comment": comment,
            "actor_identifier": "local-reviewer",
            "actor_display_name": "Local Reviewer",
            "actor_source": "LOCALCOMET_REVIEW_CENTER",
        }

    def test_001_exact_command_surface(self) -> None:
        review_methods = {
            method for method in CONTROL_PLANE_METHODS if method.startswith("knowledge.review.")
        }
        self.assertEqual(
            {
                "knowledge.review.decision.create",
                "knowledge.review.get",
                "knowledge.review.list",
                "knowledge.review.refresh",
                "knowledge.review.snapshot",
            },
            review_methods,
        )
        for forbidden in ("register", "upload", "write", "publish", "delete", "clear"):
            self.assertFalse(any(forbidden in method for method in review_methods))

    def test_002_snapshot_default_empty_and_hard_stop(self) -> None:
        plane, _ = self.make_plane()
        value = self.dispatch(plane, "knowledge.review.snapshot", {})
        self.assertEqual("localcomet.knowledge-review-snapshot/1.0", value["contract"])
        self.assertEqual(0, value["inbox_count"])
        self.assertEqual([], value["review_states"])
        self.assertTrue(value["hard_stop"])
        self.assertFalse(value["persistence"])
        self.assertFalse(value["vault_write_authority"])
        self.assertFalse(value["publication_authority"])

    def test_003_snapshot_marks_fresh_clear_review(self) -> None:
        plane, _ = self.make_plane()
        artifact = self.produce(plane)
        value = self.dispatch(plane, "knowledge.review.snapshot", {})
        self.assertEqual(1, value["inbox_count"])
        self.assertEqual(0, value["stale_count"])
        self.assertEqual(artifact.review_artifact_identity, value["review_states"][0]["review_artifact_identity"])
        self.assertIs(value["review_states"][0]["stale"], False)

    def test_004_snapshot_marks_stale_review(self) -> None:
        plane, adapter = self.make_plane()
        artifact = self.produce(plane)
        adapter.cached_revision = REV_B
        value = self.dispatch(plane, "knowledge.review.snapshot", {})
        self.assertEqual(1, value["stale_count"])
        self.assertEqual(artifact.review_artifact_identity, value["review_states"][0]["review_artifact_identity"])
        self.assertIs(value["review_states"][0]["stale"], True)

    def test_005_unknown_freshness_is_explicit_null(self) -> None:
        plane, _ = self.make_plane(cached_revision=None, filesystem_revision=None)
        self.produce(plane)
        value = self.dispatch(plane, "knowledge.review.snapshot", {})
        self.assertFalse(value["freshness_known"])
        self.assertIsNone(value["current_vault_revision"])
        self.assertIsNone(value["review_states"][0]["stale"])

    def test_006_refresh_calls_read_only_adapter(self) -> None:
        plane, adapter = self.make_plane()
        self.produce(plane)
        value = self.dispatch(plane, "knowledge.review.refresh", {})
        self.assertEqual(1, adapter.refresh_calls)
        self.assertTrue(value["refresh_requested"])
        self.assertTrue(value["refresh_succeeded"])
        self.assertEqual("localcomet.knowledge-review-refresh/1.0", value["contract"])

    def test_007_real_approve_creates_exact_e9c_decision(self) -> None:
        plane, adapter = self.make_plane()
        artifact = self.produce(plane)
        value = self.dispatch(
            plane,
            "knowledge.review.decision.create",
            self.decision_payload(artifact),
        )
        decision = value["decision"]
        self.assertEqual(DECISION_CONTRACT, decision["contract_version"])
        self.assertEqual(artifact.proposal_id, decision["proposal_id"])
        self.assertEqual(artifact.review_artifact_identity, decision["review_artifact_identity"])
        self.assertEqual(artifact.change_identity, decision["change_identity"])
        self.assertEqual("APPROVE", decision["decision"])
        self.assertTrue(decision["hard_stop"])
        self.assertFalse(value["vault_modified"])
        self.assertFalse(value["persistence"])
        self.assertFalse(value["publication"])
        self.assertEqual(1, adapter.refresh_calls)
        self.assertEqual(artifact.observed_vault_revision, adapter.cached_revision)

    def test_008_duplicate_decision_is_idempotent(self) -> None:
        plane, adapter = self.make_plane()
        artifact = self.produce(plane)
        payload = self.decision_payload(artifact, decision="REJECT", comment="exact")
        first = self.dispatch(plane, "knowledge.review.decision.create", payload)
        second = self.dispatch(plane, "knowledge.review.decision.create", payload)
        self.assertFalse(first["duplicate"])
        self.assertTrue(second["duplicate"])
        self.assertEqual(first["decision"]["decision_identity"], second["decision"]["decision_identity"])
        self.assertEqual(2, adapter.refresh_calls)
        self.assertEqual(
            1,
            self.dispatch(plane, "knowledge.review.snapshot", {})["session_decision_count"],
        )

    def test_009_stale_revision_blocks_every_decision(self) -> None:
        plane, adapter = self.make_plane(cached_revision=REV_A, filesystem_revision=REV_B)
        artifact = self.produce(plane)
        for decision in ("APPROVE", "REJECT", "REQUEST_CHANGES"):
            with self.subTest(decision=decision):
                payload = self.decision_payload(
                    artifact,
                    decision=decision,
                    comment="change details" if decision == "REQUEST_CHANGES" else "",
                )
                with self.assertRaises(ControlPlaneError) as context:
                    self.dispatch(plane, "knowledge.review.decision.create", payload)
                self.assertEqual("policy_blocked", context.exception.code)
        self.assertEqual(3, adapter.refresh_calls)
        self.assertEqual(
            0,
            self.dispatch(plane, "knowledge.review.snapshot", {})["session_decision_count"],
        )

    def test_025_refresh_failure_blocks_every_decision_without_storage(self) -> None:
        plane, adapter = self.make_plane(refresh_failure=True)
        artifact = self.produce(plane)
        for decision in ("APPROVE", "REJECT", "REQUEST_CHANGES"):
            with self.subTest(decision=decision):
                payload = self.decision_payload(
                    artifact,
                    decision=decision,
                    comment="change details" if decision == "REQUEST_CHANGES" else "",
                )
                with self.assertRaises(ControlPlaneError) as context:
                    self.dispatch(plane, "knowledge.review.decision.create", payload)
                self.assertEqual("sidecar_unavailable", context.exception.code)
        self.assertEqual(3, adapter.refresh_calls)
        self.assertEqual(
            0,
            self.dispatch(plane, "knowledge.review.snapshot", {})["session_decision_count"],
        )

    def test_026_refresh_unavailable_blocks_every_decision_without_storage(self) -> None:
        plane, adapter = self.make_plane(refresh_available=False)
        artifact = self.produce(plane)
        for decision in ("APPROVE", "REJECT", "REQUEST_CHANGES"):
            with self.subTest(decision=decision):
                payload = self.decision_payload(
                    artifact,
                    decision=decision,
                    comment="change details" if decision == "REQUEST_CHANGES" else "",
                )
                with self.assertRaises(ControlPlaneError) as context:
                    self.dispatch(plane, "knowledge.review.decision.create", payload)
                self.assertEqual("sidecar_unavailable", context.exception.code)
        self.assertEqual(0, adapter.refresh_calls)
        self.assertEqual(
            0,
            self.dispatch(plane, "knowledge.review.snapshot", {})["session_decision_count"],
        )

    def test_027_unknown_fresh_revision_blocks_every_decision_without_storage(self) -> None:
        plane, adapter = self.make_plane(
            cached_revision=REV_A,
            filesystem_revision=None,
        )
        artifact = self.produce(plane)
        for decision in ("APPROVE", "REJECT", "REQUEST_CHANGES"):
            with self.subTest(decision=decision):
                payload = self.decision_payload(
                    artifact,
                    decision=decision,
                    comment="change details" if decision == "REQUEST_CHANGES" else "",
                )
                with self.assertRaises(ControlPlaneError) as context:
                    self.dispatch(plane, "knowledge.review.decision.create", payload)
                self.assertEqual("sidecar_unavailable", context.exception.code)
        self.assertEqual(3, adapter.refresh_calls)
        self.assertEqual(
            0,
            self.dispatch(plane, "knowledge.review.snapshot", {})["session_decision_count"],
        )

    def test_028_decision_path_never_uses_cached_status_as_freshness_authority(self) -> None:
        plane, adapter = self.make_plane(cached_revision=REV_A, filesystem_revision=REV_B)
        artifact = self.produce(plane)
        status_before = adapter.status()
        self.assertEqual(REV_A, status_before["vault_revision"])
        with self.assertRaises(ControlPlaneError) as context:
            self.dispatch(
                plane,
                "knowledge.review.decision.create",
                self.decision_payload(artifact, decision="REJECT"),
            )
        self.assertEqual("policy_blocked", context.exception.code)
        self.assertEqual(1, adapter.refresh_calls)
        self.assertEqual(REV_B, adapter.cached_revision)

    def test_010_blocked_approve_is_forbidden(self) -> None:
        plane, adapter = self.make_plane(cached_revision=REV_B, filesystem_revision=REV_B)
        artifact = self.produce(plane, "blocked")
        adapter.filesystem_revision = artifact.observed_vault_revision
        self.assertIs(artifact.status, ReviewStatus.BLOCKED)
        with self.assertRaises(ControlPlaneError) as context:
            self.dispatch(
                plane,
                "knowledge.review.decision.create",
                self.decision_payload(artifact, decision="APPROVE"),
            )
        self.assertEqual("policy_blocked", context.exception.code)

    def test_011_blocked_reject_and_request_changes_remain_available(self) -> None:
        plane, adapter = self.make_plane(cached_revision=REV_B, filesystem_revision=REV_B)
        artifact = self.produce(plane, "blocked")
        adapter.filesystem_revision = artifact.observed_vault_revision
        reject = self.dispatch(
            plane,
            "knowledge.review.decision.create",
            self.decision_payload(artifact, decision="REJECT"),
        )
        request = self.dispatch(
            plane,
            "knowledge.review.decision.create",
            self.decision_payload(
                artifact,
                decision="REQUEST_CHANGES",
                comment="Resolve the blocking finding.",
            ),
        )
        self.assertIsNone(reject["decision"]["change_identity"])
        self.assertIsNone(request["decision"]["change_identity"])

    def test_012_request_changes_requires_meaningful_comment(self) -> None:
        plane, _ = self.make_plane()
        artifact = self.produce(plane)
        with self.assertRaises(ControlPlaneError) as context:
            self.dispatch(
                plane,
                "knowledge.review.decision.create",
                self.decision_payload(
                    artifact,
                    decision="REQUEST_CHANGES",
                    comment=" \t ",
                ),
            )
        self.assertEqual("invalid_payload", context.exception.code)

    def test_013_proposal_identity_mismatch_fails_closed(self) -> None:
        plane, _ = self.make_plane()
        artifact = self.produce(plane)
        with self.assertRaises(ControlPlaneError):
            self.dispatch(
                plane,
                "knowledge.review.decision.create",
                self.decision_payload(artifact, proposal_id="kprop:" + "f" * 64),
            )

    def test_014_review_identity_mismatch_cannot_select_another_artifact(self) -> None:
        plane, _ = self.make_plane()
        artifact = self.produce(plane)
        with self.assertRaises(ControlPlaneError) as context:
            self.dispatch(
                plane,
                "knowledge.review.decision.create",
                self.decision_payload(artifact, review_identity="kreview:" + "f" * 64),
            )
        self.assertEqual("request_not_found", context.exception.code)

    def test_015_change_identity_mismatch_fails_closed(self) -> None:
        plane, _ = self.make_plane()
        artifact = self.produce(plane)
        with self.assertRaises(ControlPlaneError):
            self.dispatch(
                plane,
                "knowledge.review.decision.create",
                self.decision_payload(artifact, change_identity="kchange:" + "f" * 64),
            )

    def test_016_observed_revision_mismatch_fails_closed(self) -> None:
        plane, _ = self.make_plane()
        artifact = self.produce(plane)
        with self.assertRaises(ControlPlaneError):
            self.dispatch(
                plane,
                "knowledge.review.decision.create",
                self.decision_payload(artifact, revision=REV_B),
            )

    def test_017_payload_extra_field_rejected(self) -> None:
        plane, _ = self.make_plane()
        artifact = self.produce(plane)
        payload = self.decision_payload(artifact)
        payload["unexpected"] = True
        with self.assertRaises(ControlPlaneError) as context:
            self.dispatch(plane, "knowledge.review.decision.create", payload)
        self.assertEqual("invalid_payload", context.exception.code)

    def test_018_decision_capacity_fails_without_eviction(self) -> None:
        plane, _ = self.make_plane(maximum_decisions=1)
        artifact = self.produce(plane)
        first = self.dispatch(
            plane,
            "knowledge.review.decision.create",
            self.decision_payload(artifact, decision="REJECT", comment="first"),
        )
        with self.assertRaises(ControlPlaneError) as context:
            self.dispatch(
                plane,
                "knowledge.review.decision.create",
                self.decision_payload(artifact, decision="REJECT", comment="second"),
            )
        self.assertEqual("busy", context.exception.code)
        snapshot = self.dispatch(plane, "knowledge.review.snapshot", {})
        self.assertEqual(1, snapshot["session_decision_count"])
        self.assertTrue(first["decision"]["decision_identity"].startswith("kdecision:"))

    def test_019_status_exposes_only_bounded_session_counts(self) -> None:
        plane, _ = self.make_plane()
        artifact = self.produce(plane)
        self.dispatch(
            plane,
            "knowledge.review.decision.create",
            self.decision_payload(artifact, decision="REJECT"),
        )
        status = self.dispatch(plane, "app.status", {})
        self.assertEqual(1, status["counts"]["knowledge_reviews"])
        self.assertEqual(1, status["counts"]["human_review_decisions"])
        serialized = json.dumps(status).lower()
        self.assertNotIn("kdecision:", serialized)
        self.assertNotIn("actor_identifier", serialized)
        self.assertNotIn("comment", serialized)

    def test_020_production_owner_has_no_write_or_persistence_call(self) -> None:
        source = inspect.getsource(DesktopControlPlane._create_knowledge_review_decision)
        for forbidden in (
            "open(",
            "write_text",
            "write_bytes",
            "sqlite",
            "requests.",
            "subprocess",
            "publish",
            "merge(",
        ):
            self.assertNotIn(forbidden, source)
        self.assertIn('"vault_modified": False', source)
        self.assertIn('"persistence": False', source)
        self.assertIn('"publication": False', source)


    def test_021_payload_validation_enforces_utf8_and_fixed_actor_source(self) -> None:
        plane, _ = self.make_plane()
        artifact = self.produce(plane)
        payload = self.decision_payload(artifact, decision="REJECT")

        oversized_comment = dict(payload, comment="😀" * 1_025)
        self.assertIn(
            "invalid_comment",
            validate_control_plane_payload(
                "knowledge.review.decision.create",
                oversized_comment,
            ),
        )

        oversized_actor = dict(payload, actor_identifier="😀" * 129)
        self.assertIn(
            "invalid_actor_identifier",
            validate_control_plane_payload(
                "knowledge.review.decision.create",
                oversized_actor,
            ),
        )

        wrong_source = dict(payload, actor_source="UNTRUSTED_FRONTEND")
        self.assertIn(
            "invalid_actor_source",
            validate_control_plane_payload(
                "knowledge.review.decision.create",
                wrong_source,
            ),
        )

    def test_022_payload_validation_enforces_decision_comment_and_change_policy(self) -> None:
        plane, _ = self.make_plane()
        artifact = self.produce(plane)

        request_changes = self.decision_payload(
            artifact,
            decision="REQUEST_CHANGES",
            comment="   ",
        )
        self.assertIn(
            "request_changes_comment_required",
            validate_control_plane_payload(
                "knowledge.review.decision.create",
                request_changes,
            ),
        )


    def test_023_session_reset_is_a_new_empty_control_plane_instance(self) -> None:
        plane, _ = self.make_plane()
        artifact = self.produce(plane)
        self.dispatch(
            plane,
            "knowledge.review.decision.create",
            self.decision_payload(artifact, decision="REJECT"),
        )
        self.assertEqual(
            self.dispatch(plane, "knowledge.review.snapshot", {})[
                "session_decision_count"
            ],
            1,
        )

        replacement, _ = self.make_plane()
        snapshot = self.dispatch(replacement, "knowledge.review.snapshot", {})
        self.assertEqual(snapshot["inbox_count"], 0)
        self.assertEqual(snapshot["session_decision_count"], 0)

    def test_024_decision_response_contains_only_bounded_evidence_and_hard_stop(self) -> None:
        plane, _ = self.make_plane()
        artifact = self.produce(plane)
        result = self.dispatch(
            plane,
            "knowledge.review.decision.create",
            self.decision_payload(artifact, decision="REJECT"),
        )
        serialized = json.dumps(result, ensure_ascii=False, sort_keys=True)
        self.assertLess(len(serialized.encode("utf-8")), 262_144)
        self.assertTrue(result["hard_stop"])
        self.assertFalse(result["vault_modified"])
        self.assertFalse(result["persistence"])
        self.assertFalse(result["publication"])
        for forbidden in (
            "vault_root",
            "absolute_path",
            "write_file",
            "publish",
            "execute",
            "environment",
        ):
            self.assertNotIn(forbidden, serialized.lower())



if __name__ == "__main__":
    result = unittest.main(verbosity=2, exit=False)
    if not result.result.wasSuccessful():
        raise SystemExit(1)
