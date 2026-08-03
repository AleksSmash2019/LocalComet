"""Regression test for P0-2C: required trust-chain files must not be skipped."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "trust_chain_invariants", ROOT / "tests" / "test_trust_chain_invariants.py"
)
assert SPEC and SPEC.loader
trust_chain = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(trust_chain)


class TrustChainGateTests(unittest.TestCase):
    def test_missing_required_file_fails_instead_of_being_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = io.StringIO()
            with (
                patch.object(trust_chain, "REPO_ROOT", root),
                patch.object(trust_chain, "TRUST_CHAIN_FILES", ["required.txt"]),
                contextlib.redirect_stdout(output),
            ):
                result = trust_chain.main()
        self.assertEqual(result, 1)
        self.assertIn("MISSING:", output.getvalue())


if __name__ == "__main__":
    unittest.main(verbosity=2)
