"""Test isolation guards for the LocalComet suite.

Several legacy suites (tools/test_v678_router_registry.py,
tools/test_v680_reproducibility.py) set ``LOCALCOMET_ROOT`` /
``LOCALCOMET_ROOT_DIR`` to a temporary directory in order to import
``LocalComet_Control_Panel`` against a throwaway tree, and one of them also
calls ``os.chdir``.  Neither restores the previous process state.

Because pytest runs every module in a single process, that leaked state made
later suites resolve the project root to an already-deleted temp directory.
The result was an order-dependent, non-deterministic failure set: three
consecutive full runs of the very same commit produced 3, 19 and 1 failures.

These autouse fixtures snapshot and restore the mutated process-global state
around every test, so a run's failure set reflects the code under test rather
than the order tests happened to execute in.

This file only isolates state. It does not change assertions, and a genuinely
failing test keeps failing.
"""
from __future__ import annotations

import os
import sys

import pytest

# Process-global environment variables mutated by legacy suites without cleanup.
_LEAKED_ENV_VARS = (
    "LOCALCOMET_ROOT",
    "LOCALCOMET_ROOT_DIR",
    "LOCALCOMET_PACKAGING_CHECK",
)


@pytest.fixture(autouse=True)
def _restore_localcomet_env():
    """Restore LOCALCOMET_* env vars mutated during a test."""
    saved = {name: os.environ.get(name) for name in _LEAKED_ENV_VARS}
    try:
        yield
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


# Top-level package/module names that legacy suites re-import against a
# temporary project root. Leaving them in sys.modules pins later tests to an
# already-deleted temp directory.
_ROOT_BOUND_MODULES = (
    "LocalComet_Control_Panel",
    "modules",
    "core",
    "agents",
    "next",
    "config",
)


def _is_root_bound(name: str) -> bool:
    return any(name == base or name.startswith(base + ".") for base in _ROOT_BOUND_MODULES)


@pytest.fixture(autouse=True)
def _restore_module_cache():
    """Undo sys.modules mutations that bind modules to a temporary root.

    Legacy suites call ``sys.modules.pop("LocalComet_Control_Panel")`` and
    re-import it while ``LOCALCOMET_ROOT`` points at a temp tree. Dependent
    ``modules.*`` / ``core.*`` imports get cached against that tree and outlive
    the test. Restoring the snapshot keeps each test's view of the project root
    consistent with the real repository.
    """
    saved = {name: mod for name, mod in sys.modules.items() if _is_root_bound(name)}
    try:
        yield
    finally:
        for name in [n for n in sys.modules if _is_root_bound(n)]:
            if name not in saved:
                del sys.modules[name]
        sys.modules.update(saved)


@pytest.fixture(autouse=True)
def _restore_cwd():
    """Restore the working directory mutated via os.chdir during a test."""
    saved = os.getcwd()
    try:
        yield
    finally:
        try:
            if os.getcwd() != saved:
                os.chdir(saved)
        except OSError:
            # The test deleted the directory it chdir'd into; fall back to the
            # snapshot taken before the test ran.
            os.chdir(saved)
