from __future__ import annotations

from pathlib import Path

import pytest

from modules.workspace_memory_ru import (
    DocumentState,
    MemoryState,
    WorkspaceMemoryError,
    WorkspaceMemoryStore,
)


def make_store(tmp_path: Path) -> WorkspaceMemoryStore:
    root = tmp_path / "workspace"
    root.mkdir()
    return WorkspaceMemoryStore(root, workspace_id="ws-a", owner_id="owner-a", members=("member-a",))


def test_ingest_search_and_citation_are_bounded_and_provenance_rich(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    source = root / "guide.md"
    source.write_text("# Runtime\nCPU and Vulkan runtime selection.\n\n# Safety\nWorkspace boundary is enforced.", encoding="utf-8")
    store = WorkspaceMemoryStore(root, workspace_id="ws-a", owner_id="owner-a")

    document = store.ingest_document(workspace_id="ws-a", actor_id="owner-a", source_path=source)
    assert document.state is DocumentState.INDEXED
    assert document.document_id.startswith("doc-")
    assert len(document.chunk_ids) == 2

    hits = store.search(workspace_id="ws-a", actor_id="owner-a", query="Vulkan runtime")
    assert hits
    assert hits[0].citation.document_id == document.document_id
    assert hits[0].citation.source_sha256 == document.source_sha256
    assert hits[0].citation.chunk_id in document.chunk_ids
    assert str(root) not in repr(hits[0].citation)
    assert hits[0].chunk.section == "Runtime"

    repeated = store.ingest_document(workspace_id="ws-a", actor_id="owner-a", source_path=source)
    assert repeated.document_id == document.document_id
    assert repeated.chunk_ids == document.chunk_ids


def test_workspace_boundary_and_membership_fail_closed(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    outside = tmp_path / "outside.md"
    outside.write_text("secret", encoding="utf-8")

    with pytest.raises(WorkspaceMemoryError) as mismatch:
        store.search(workspace_id="ws-other", actor_id="owner-a", query="secret")
    assert mismatch.value.code == "WORKSPACE_MISMATCH"

    with pytest.raises(WorkspaceMemoryError) as membership:
        store.search(workspace_id="ws-a", actor_id="unknown", query="secret")
    assert membership.value.code == "MEMBERSHIP_REQUIRED"

    with pytest.raises(WorkspaceMemoryError) as escape:
        store.ingest_document(workspace_id="ws-a", actor_id="owner-a", source_path=outside)
    assert escape.value.code == "WORKSPACE_PATH_ESCAPE"


def test_source_type_and_query_limits_are_enforced(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    source = root / "data.json"
    source.write_text("{}", encoding="utf-8")
    store = WorkspaceMemoryStore(root, workspace_id="ws-a", owner_id="owner-a")

    with pytest.raises(WorkspaceMemoryError) as source_error:
        store.ingest_document(workspace_id="ws-a", actor_id="owner-a", source_path=source)
    assert source_error.value.code == "UNSUPPORTED_SOURCE_TYPE"

    with pytest.raises(WorkspaceMemoryError) as query_error:
        store.search(workspace_id="ws-a", actor_id="owner-a", query="x" * 513)
    assert query_error.value.code == "QUERY_INVALID"


def test_memory_requires_explicit_confirmation_before_activation_and_deletion_is_verified(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    source = root / "notes.txt"
    source.write_text("Important project decision.", encoding="utf-8")
    store = WorkspaceMemoryStore(root, workspace_id="ws-a", owner_id="owner-a")
    document = store.ingest_document(workspace_id="ws-a", actor_id="owner-a", source_path=source)

    candidate = store.propose_memory(
        workspace_id="ws-a",
        actor_id="owner-a",
        content="Project uses a local-only control plane.",
        source_chunk_ids=document.chunk_ids,
    )
    assert candidate.state is MemoryState.CANDIDATE
    with pytest.raises(WorkspaceMemoryError) as premature:
        store.activate_memory(workspace_id="ws-a", actor_id="owner-a", memory_id=candidate.memory_id)
    assert premature.value.code == "MEMORY_STATE_INVALID"

    confirmed = store.confirm_memory(workspace_id="ws-a", actor_id="owner-a", memory_id=candidate.memory_id)
    assert confirmed.state is MemoryState.USER_CONFIRMED
    active = store.activate_memory(workspace_id="ws-a", actor_id="owner-a", memory_id=candidate.memory_id)
    assert active.state is MemoryState.ACTIVE
    assert active.source_chunk_ids == document.chunk_ids

    deleted = store.delete_memory(workspace_id="ws-a", actor_id="owner-a", memory_id=candidate.memory_id)
    assert deleted == {"memory_id": candidate.memory_id, "deleted": True, "verified": True}
    with pytest.raises(WorkspaceMemoryError) as missing:
        store.get_memory(workspace_id="ws-a", actor_id="owner-a", memory_id=candidate.memory_id)
    assert missing.value.code == "MEMORY_NOT_FOUND"


def test_memory_source_must_belong_to_current_workspace(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    with pytest.raises(WorkspaceMemoryError) as missing:
        store.propose_memory(
            workspace_id="ws-a",
            actor_id="owner-a",
            content="not grounded",
            source_chunk_ids=("chunk-not-found",),
        )
    assert missing.value.code == "MEMORY_SOURCE_NOT_FOUND"
