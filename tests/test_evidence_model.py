"""Evidence model tests for LocalComet B5LP repair.

Validates:
- tools/ inclusion in source tree digest
- stable digest for unchanged sources
- meta/ exclusion from source digest and provenance checks
- dynamic CURRENT_TREE in historical checker
- historical evidence tree/body validation
- stale evidence detection
- superseded/ subdirectory exclusion
"""

import hashlib
import inspect
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))

import check_evidence_provenance  # noqa: E402
import check_historical_evidence  # noqa: E402
import refresh_evidence  # noqa: E402


def _make_evidence_text(tree_digest, body="gate output here\n", status=None, exit_code=0):
    body_sha = hashlib.sha256(body.encode("utf-8")).hexdigest()
    lines = [
        "# command: python fake_gate.py",
        f"# exit_code: {exit_code}",
        f"# tree_digest: {tree_digest}",
        f"# body_sha256: {body_sha}",
        "# timestamp: 2026-07-30T00:00:00+00:00",
        "# platform: Windows AMD64 python=3.12.0",
        "# source_files: 100",
    ]
    if status:
        lines.append(f"# evidence_status: {status}")
    lines.append("---")
    lines.append(body)
    return "\n".join(lines)


class TestTreeDigest(unittest.TestCase):
    def test_tools_directory_change_affects_tree_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            tools_dir = root / "tools"
            tools_dir.mkdir()
            tool_file = tools_dir / "test.py"
            tool_file.write_text("x = 1\n", encoding="utf-8")

            globs = ["tools/**/*.py"]
            with patch.object(refresh_evidence, "REPO_ROOT", root), \
                 patch.object(refresh_evidence, "SOURCE_GLOBS", globs):
                digest_before = refresh_evidence.tree_digest()

            tool_file.write_text("x = 2\n", encoding="utf-8")
            with patch.object(refresh_evidence, "REPO_ROOT", root), \
                 patch.object(refresh_evidence, "SOURCE_GLOBS", globs):
                digest_after = refresh_evidence.tree_digest()

            self.assertNotEqual(digest_before, digest_after)

    def test_unchanged_sources_produce_stable_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            core = root / "core"
            core.mkdir()
            (core / "main.py").write_text("print('hi')\n", encoding="utf-8")

            globs = ["core/**/*.py"]
            with patch.object(refresh_evidence, "REPO_ROOT", root), \
                 patch.object(refresh_evidence, "SOURCE_GLOBS", globs):
                d1 = refresh_evidence.tree_digest()
                d2 = refresh_evidence.tree_digest()
                d3 = refresh_evidence.tree_digest()

            self.assertEqual(d1, d2)
            self.assertEqual(d2, d3)

    def test_evidence_meta_files_do_not_affect_source_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            core = root / "core"
            core.mkdir()
            (core / "app.py").write_text("val = 1\n", encoding="utf-8")

            meta = root / "artifacts" / "evidence" / "meta"
            meta.mkdir(parents=True)
            (meta / "report.txt").write_text("checker log\n", encoding="utf-8")

            globs = ["core/**/*.py"]
            with patch.object(refresh_evidence, "REPO_ROOT", root), \
                 patch.object(refresh_evidence, "SOURCE_GLOBS", globs):
                digest_before = refresh_evidence.tree_digest()

            (meta / "another.txt").write_text("more logs\n", encoding="utf-8")
            with patch.object(refresh_evidence, "REPO_ROOT", root), \
                 patch.object(refresh_evidence, "SOURCE_GLOBS", globs):
                digest_after = refresh_evidence.tree_digest()

            self.assertEqual(digest_before, digest_after)


class TestProvenanceChecker(unittest.TestCase):
    def test_meta_provenance_reports_excluded_from_current_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            evidence_dir = root / "artifacts" / "evidence"
            evidence_dir.mkdir(parents=True)
            meta_dir = evidence_dir / "meta"
            meta_dir.mkdir()

            digest = "a" * 64
            valid = _make_evidence_text(digest)
            for name in ("cargo_test.txt", "trust_chain.txt", "cmd_parity.txt", "tool_risk_registry.txt"):
                (evidence_dir / name).write_text(valid, encoding="utf-8")
            (meta_dir / "report.txt").write_text("not evidence\n", encoding="utf-8")

            with patch.object(check_evidence_provenance, "EVIDENCE_DIR", evidence_dir), \
                 patch.object(refresh_evidence, "REPO_ROOT", root), \
                 patch.object(refresh_evidence, "SOURCE_GLOBS", []), \
                 patch("check_evidence_provenance.tree_digest", return_value=digest):
                result = check_evidence_provenance.main()

            self.assertEqual(result, 0)

    def test_missing_required_current_evidence_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            evidence_dir = pathlib.Path(tmp) / "artifacts" / "evidence"
            evidence_dir.mkdir(parents=True)
            digest = "a" * 64
            for name in ("cargo_test.txt", "trust_chain.txt", "cmd_parity.txt"):
                (evidence_dir / name).write_text(_make_evidence_text(digest), encoding="utf-8")
            with patch.object(check_evidence_provenance, "EVIDENCE_DIR", evidence_dir), \
                 patch("check_evidence_provenance.tree_digest", return_value=digest):
                result = check_evidence_provenance.main()
            self.assertEqual(result, 1)

    def test_stale_tree_digest_is_rejected_for_current_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            evidence_dir = root / "artifacts" / "evidence"
            evidence_dir.mkdir(parents=True)

            stale_digest = "b" * 64
            live_digest = "c" * 64
            (evidence_dir / "gate.txt").write_text(
                _make_evidence_text(stale_digest), encoding="utf-8"
            )

            with patch.object(check_evidence_provenance, "EVIDENCE_DIR", evidence_dir), \
                 patch("check_evidence_provenance.tree_digest", return_value=live_digest):
                result = check_evidence_provenance.main()

            self.assertEqual(result, 1)

    def test_nonzero_exit_is_rejected_even_with_current_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            evidence_dir = pathlib.Path(tmp) / "artifacts" / "evidence"
            evidence_dir.mkdir(parents=True)
            digest = "d" * 64
            for name in ("cargo_test.txt", "trust_chain.txt", "cmd_parity.txt", "tool_risk_registry.txt"):
                (evidence_dir / name).write_text(
                    _make_evidence_text(digest, exit_code=1 if name == "cargo_test.txt" else 0),
                    encoding="utf-8",
                )
            with patch.object(check_evidence_provenance, "EVIDENCE_DIR", evidence_dir), \
                 patch("check_evidence_provenance.tree_digest", return_value=digest):
                result = check_evidence_provenance.main()
            self.assertEqual(result, 1)

    def test_body_mismatch_is_rejected_even_with_current_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            evidence_dir = pathlib.Path(tmp) / "artifacts" / "evidence"
            evidence_dir.mkdir(parents=True)
            digest = "e" * 64
            for name in ("cargo_test.txt", "trust_chain.txt", "cmd_parity.txt", "tool_risk_registry.txt"):
                (evidence_dir / name).write_text(_make_evidence_text(digest), encoding="utf-8")
            cargo = evidence_dir / "cargo_test.txt"
            cargo.write_text(cargo.read_text(encoding="utf-8") + "tampered\n", encoding="utf-8")
            with patch.object(check_evidence_provenance, "EVIDENCE_DIR", evidence_dir), \
                 patch("check_evidence_provenance.tree_digest", return_value=digest):
                result = check_evidence_provenance.main()
            self.assertEqual(result, 1)

    def test_superseded_evidence_is_excluded_from_both_tiers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            evidence_dir = root / "artifacts" / "evidence"
            evidence_dir.mkdir(parents=True)
            superseded = evidence_dir / "superseded"
            superseded.mkdir()

            digest = "d" * 64
            for name in ("cargo_test.txt", "trust_chain.txt", "cmd_parity.txt", "tool_risk_registry.txt"):
                (evidence_dir / name).write_text(_make_evidence_text(digest), encoding="utf-8")
            (superseded / "old.txt").write_text(
                _make_evidence_text("e" * 64), encoding="utf-8"
            )

            with patch.object(check_evidence_provenance, "EVIDENCE_DIR", evidence_dir), \
                 patch("check_evidence_provenance.tree_digest", return_value=digest):
                result = check_evidence_provenance.main()

            self.assertEqual(result, 0)


class TestHistoricalChecker(unittest.TestCase):
    def test_historical_checker_uses_dynamic_live_digest(self):
        source = inspect.getsource(check_historical_evidence)
        self.assertNotIn(
            'CURRENT_TREE = "',
            source,
            "CURRENT_TREE must not be a hardcoded string literal",
        )

    def test_historical_evidence_with_current_tree_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            hist_dir = root / "artifacts" / "evidence" / "historical"
            hist_dir.mkdir(parents=True)

            live_tree = "f" * 64
            body = "old gate output\n"
            text = _make_evidence_text(live_tree, body=body, status="HISTORICAL")
            (hist_dir / "old_gate.txt").write_text(text, encoding="utf-8", newline="\n")

            manifest_name = check_historical_evidence.MANIFEST_NAME
            file_sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
            manifest_line = f"{file_sha}  old_gate.txt  {live_tree}\n"
            (hist_dir / manifest_name).write_text(manifest_line, encoding="utf-8", newline="\n")

            with patch.object(check_historical_evidence, "HISTORICAL_DIR", hist_dir), \
                 patch.object(check_historical_evidence, "CURRENT_TREE", live_tree), \
                 patch.object(check_historical_evidence, "EXPECTED_HISTORICAL_COUNT", 1):
                result = check_historical_evidence.main()

            self.assertEqual(result, 1)

    def test_original_historical_digests_are_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            hist_dir = root / "artifacts" / "evidence" / "historical"
            hist_dir.mkdir(parents=True)

            original_tree = "8a0d1d80e798f3d2a93cf84fd76829844186c88386e61ac906c067c3de7e7d88"
            body = "baseline output\n"
            text = _make_evidence_text(original_tree, body=body, status="HISTORICAL")
            (hist_dir / "baseline.txt").write_text(text, encoding="utf-8", newline="\n")

            manifest_name = check_historical_evidence.MANIFEST_NAME
            file_sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
            manifest_line = f"{file_sha}  baseline.txt  {original_tree}\n"
            (hist_dir / manifest_name).write_text(manifest_line, encoding="utf-8", newline="\n")

            with patch.object(check_historical_evidence, "HISTORICAL_DIR", hist_dir), \
                 patch.object(check_historical_evidence, "CURRENT_TREE", "f" * 64), \
                 patch.object(check_historical_evidence, "EXPECTED_HISTORICAL_COUNT", 1):
                result = check_historical_evidence.main()

            self.assertEqual(result, 0)

    def test_body_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            hist_dir = root / "artifacts" / "evidence" / "historical"
            hist_dir.mkdir(parents=True)

            original_tree = "cc18487be7113bd5e12ead31aff35f923bf34a70b77892bf135b99d9971cb498"
            body = "original body\n"
            text = _make_evidence_text(original_tree, body=body, status="HISTORICAL")
            tampered = text.replace("original body\n", "TAMPERED body\n")
            (hist_dir / "tampered.txt").write_text(tampered, encoding="utf-8", newline="\n")

            manifest_name = check_historical_evidence.MANIFEST_NAME
            file_sha = hashlib.sha256(tampered.encode("utf-8")).hexdigest()
            manifest_line = f"{file_sha}  tampered.txt  {original_tree}\n"
            (hist_dir / manifest_name).write_text(manifest_line, encoding="utf-8", newline="\n")

            with patch.object(check_historical_evidence, "HISTORICAL_DIR", hist_dir), \
                 patch.object(check_historical_evidence, "CURRENT_TREE", "f" * 64), \
                 patch.object(check_historical_evidence, "EXPECTED_HISTORICAL_COUNT", 1):
                result = check_historical_evidence.main()

            self.assertEqual(result, 1)


if __name__ == "__main__":
    unittest.main()
