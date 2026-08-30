"""Shared pytest fixtures / test isolation for the backend test suite.

Several handler packages each expose a module named ``app`` and the tests load
them via ``import app`` + ``importlib.reload``. Because they share the module
name ``app`` in ``sys.modules``, the resolved module depended on test collection
order, which made some tests order-dependent (e.g. upload vs. practice).

This autouse fixture removes the ambiguous ``app`` module (and its sibling
handler-local modules) from ``sys.modules`` before each test, so every test
re-imports the module it actually intends to.
"""

import os
import sys

import pytest

# Modules that live inside individual handler directories and are imported by
# their unqualified name across multiple test files.
_AMBIGUOUS_MODULES = {'app', 'textract_parser', 'answer_checker'}


@pytest.fixture(autouse=True)
def _isolate_handler_modules():
    for name in list(_AMBIGUOUS_MODULES):
        sys.modules.pop(name, None)
    # Snapshot env so a test that mutates handler env vars (e.g. table names to
    # load a module) cannot leak those values into other test files that read
    # the same env vars at import time.
    saved_env = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved_env)
    for name in list(_AMBIGUOUS_MODULES):
        sys.modules.pop(name, None)
