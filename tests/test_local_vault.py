import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modules.local_vault import LocalVault, LocalVaultError, VaultConflictError


class LocalVaultTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="localcomet-vault-test-")
        self.root = Path(self.temp.name)
        (self.root / "Notes").mkdir()
        with (self.root / "Notes" / "one.md").open("w", encoding="utf-8", newline="") as handle:
            handle.write("# One\n")
        (self.root / ".obsidian").mkdir()
        (self.root / ".obsidian" / "app.json").write_text("{}", encoding="utf-8")
        self.vault = LocalVault(self.root)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_list_and_read_markdown_are_bounded_to_content(self) -> None:
        self.assertEqual(("Notes/one.md",), self.vault.list_markdown())
        note = self.vault.read_markdown("Notes/one.md")
        self.assertEqual("# One\n", note.content)
        self.assertEqual(64, len(note.sha256))

    def test_create_and_update_require_explicit_proposal_apply(self) -> None:
        created = self.vault.propose_create("Notes/two.md", "# Two\n")
        self.assertFalse((self.root / "Notes" / "two.md").exists())
        applied = self.vault.apply_proposal(created)
        self.assertEqual("# Two\n", applied.content)

        current = self.vault.read_markdown("Notes/two.md")
        proposal = self.vault.propose_update("Notes/two.md", current.sha256, "# Updated\n")
        updated = self.vault.apply_proposal(proposal)
        self.assertEqual("# Updated\n", updated.content)

    def test_update_conflict_does_not_overwrite_newer_note(self) -> None:
        current = self.vault.read_markdown("Notes/one.md")
        proposal = self.vault.propose_update("Notes/one.md", current.sha256, "# Proposed\n")
        with (self.root / "Notes" / "one.md").open("w", encoding="utf-8", newline="") as handle:
            handle.write("# Newer\n")
        with self.assertRaises(VaultConflictError):
            self.vault.apply_proposal(proposal)
        self.assertEqual("# Newer\n", self.vault.read_markdown("Notes/one.md").content)

    def test_rejects_escape_obsidian_and_non_markdown_paths(self) -> None:
        for path in ("../escape.md", str(self.root / "absolute.md"), ".obsidian/app.md", "Notes/data.json"):
            with self.subTest(path=path), self.assertRaises(LocalVaultError):
                self.vault.read_markdown(path)

    def test_rejects_symlink_escape_when_platform_allows_symlinks(self) -> None:
        outside = Path(self.temp.name).parent / f"localcomet-vault-outside-{os.getpid()}"
        outside.mkdir(exist_ok=True)
        link = self.root / "linked"
        try:
            link.symlink_to(outside, target_is_directory=True)
        except (OSError, NotImplementedError):
            outside.rmdir()
            self.skipTest("symlink creation is unavailable on this Windows account")
        try:
            with self.assertRaises(LocalVaultError):
                self.vault.propose_create("linked/escape.md", "escape")
        finally:
            link.unlink(missing_ok=True)
            outside.rmdir()

    def test_byte_limit_is_enforced(self) -> None:
        vault = LocalVault(self.root, max_bytes=4)
        with self.assertRaises(LocalVaultError):
            vault.propose_create("Notes/large.md", "12345")

    def test_apply_rejects_tampered_proposal(self) -> None:
        proposal = self.vault.propose_create("Notes/tampered.md", "safe")
        tampered = type(proposal)(
            operation=proposal.operation,
            relative_path=proposal.relative_path,
            expected_sha256=proposal.expected_sha256,
            new_sha256="0" * 64,
            content=proposal.content,
            diff=proposal.diff,
        )
        with self.assertRaises(VaultConflictError):
            self.vault.apply_proposal(tampered)


if __name__ == "__main__":
    unittest.main()
