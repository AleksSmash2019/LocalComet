"""Workspace confinement policy for LocalComet.

A reusable security primitive that confines filesystem operations to a single
confirmed workspace. Mirrors the Rust workspace.rs authority on the Python side
and aligns with modules/files.py safe_path() confinement.

NOTE on product wiring: the desktop sidecar currently performs no filesystem
operations (files.* methods are unsupported_method), so this policy is a
foundation primitive plus the reference implementation for workspace.set
handling. The desktop's authoritative workspace boundary is the Rust approval
scope (src-tauri/src/workspace.rs + approval_commands.rs::set_workspace).
"""

from __future__ import annotations

import hashlib
from pathlib import Path


class WorkspacePolicyError(Exception):
    """Raised when a workspace path is invalid or a path escapes confinement."""


class WorkspacePolicy:
    def __init__(self, canonical_path: str, digest: str, session_id: str):
        resolved = Path(canonical_path).resolve()
        if not resolved.exists():
            raise WorkspacePolicyError(f"workspace does not exist: {resolved}")
        if not resolved.is_dir():
            raise WorkspacePolicyError(f"workspace is not a directory: {resolved}")
        self._path = resolved
        self._digest = digest
        self._session_id = session_id

    @property
    def canonical_path(self) -> str:
        return str(self._path)

    @property
    def digest(self) -> str:
        return self._digest

    @property
    def session_id(self) -> str:
        return self._session_id

    def validate_path(self, requested: "str | Path") -> Path:
        """Return the resolved path if inside the workspace, else raise.

        Resolution happens before the containment check so symlink/junction
        escape is caught (the resolved target, not the raw string, is tested).
        """
        target = Path(requested).resolve()
        try:
            target.relative_to(self._path)
        except ValueError as exc:
            raise WorkspacePolicyError(
                f"path {target} is outside workspace {self._path}"
            ) from exc
        return target

    def is_within(self, requested: "str | Path") -> bool:
        try:
            self.validate_path(requested)
            return True
        except WorkspacePolicyError:
            return False


def workspace_digest(canonical_path: str) -> str:
    return hashlib.sha256(str(canonical_path).encode("utf-8")).hexdigest()


def make_policy(canonical_path: str, session_id: str) -> WorkspacePolicy:
    return WorkspacePolicy(canonical_path, workspace_digest(canonical_path), session_id)


def _self_test() -> int:
    import tempfile

    failures = []

    def check(condition: bool, label: str) -> None:
        if not condition:
            failures.append(label)

    with tempfile.TemporaryDirectory(prefix="lc_ws_a_") as ws_a, tempfile.TemporaryDirectory(
        prefix="lc_ws_b_"
    ) as ws_b:
        policy = make_policy(ws_a, session_id="0" * 64)
        check(policy.canonical_path == str(Path(ws_a).resolve()), "canonical_path")
        check(len(policy.digest) == 64, "digest length")

        inside = Path(ws_a) / "file.txt"
        inside.write_text("x", encoding="utf-8")
        check(policy.is_within(inside), "inside path accepted")
        check(policy.validate_path(inside) == inside.resolve(), "validate_path returns resolved")

        outside = Path(ws_b) / "other.txt"
        check(not policy.is_within(outside), "outside path rejected")
        try:
            policy.validate_path(outside)
            failures.append("validate_path did not raise for outside path")
        except WorkspacePolicyError:
            pass

        # Traversal escape must be rejected after resolution.
        traversal = Path(ws_a) / ".." / Path(ws_b).name / "escape.txt"
        check(not policy.is_within(traversal), "traversal escape rejected")

    # Non-existent workspace must fail closed.
    try:
        make_policy(str(Path(tempfile.gettempdir()) / "lc_nonexistent_ws_zzz"), "1" * 64)
        failures.append("non-existent workspace did not raise")
    except WorkspacePolicyError:
        pass

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1
    print("OK: workspace_policy self-test passed")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(_self_test())
