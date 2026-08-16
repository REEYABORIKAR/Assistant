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

# Keep the existing retrieval suite fast and deterministic: disable the
# Phase-4 heavy features (cross-encoder model download, query expansion).
# They are tested separately with stubbed models / pure-function unit tests.
# NOTE: must be set before app.core.config.Settings is instantiated.
os.environ["RERANK_ENABLED"] = "false"
os.environ["QUERY_EXPANSION_ENABLED"] = "false"

# Never hit the real Groq API during tests.
os.environ["GROQ_API_KEY"] = ""
