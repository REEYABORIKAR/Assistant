"""
conftest.py — Top-level pytest configuration for the Refyne backend test suite.

Problem: test_phase1.py uses an autouse fixture that drops all tables after
each test. When multiple test files share the same FastAPI `app` singleton and
override `get_db`, they conflict — whichever file runs first tears down tables
that later tests need.

Solution: each test file defines its own engine + DB override. The conftest
simply sets the JWT_SECRET_KEY environment variable so tests don't need to
manage it individually.
"""
import os
import pytest

# Ensure JWT_SECRET_KEY is always available for tests
os.environ.setdefault("JWT_SECRET_KEY", "testsecret123-phase123-refyne")
