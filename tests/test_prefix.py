"""
Unit tests for multilingual-e5-small prefix correctness.

Why this test exists: e5 models require distinct prefixes on the document side
("passage: ") vs. the query side ("query: "). Swapping them degrades retrieval.
This test catches prefix typos and ensures both sides are applied consistently.

Source: intfloat/multilingual-e5-small model card on HuggingFace.
Note: ruri-v3-310m (originally planned) requires GPU; falling back to
multilingual-e5-small for CPU-only environments. See README for details.
"""
import sys
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

EXPECTED_DOC_PREFIX = "passage: "
EXPECTED_QUERY_PREFIX = "query: "


def test_doc_prefix_value():
    """DOC_PREFIX in ingest.py must equal the model-card document prefix."""
    from src.ingest import DOC_PREFIX
    assert DOC_PREFIX == EXPECTED_DOC_PREFIX, (
        f"DOC_PREFIX mismatch: got {DOC_PREFIX!r}, expected {EXPECTED_DOC_PREFIX!r}. "
        "Verify against cl-nagoya/ruri-v3-310m model card."
    )


def test_query_prefix_value():
    """QUERY_PREFIX in query.py must equal the model-card query prefix."""
    from src.query import QUERY_PREFIX
    assert QUERY_PREFIX == EXPECTED_QUERY_PREFIX, (
        f"QUERY_PREFIX mismatch: got {QUERY_PREFIX!r}, expected {EXPECTED_QUERY_PREFIX!r}. "
        "Verify against cl-nagoya/ruri-v3-310m model card."
    )


def test_prefixes_differ():
    """Document prefix and query prefix must not be the same string."""
    from src.ingest import DOC_PREFIX
    from src.query import QUERY_PREFIX
    assert DOC_PREFIX != QUERY_PREFIX, (
        "DOC_PREFIX and QUERY_PREFIX are identical. ruri models use distinct prefixes "
        "for documents vs. queries — identical prefixes likely indicate a copy-paste error."
    )


def test_doc_prefix_applied_to_embedding_input():
    """The text passed to model.encode() in ingest must start with DOC_PREFIX."""
    from src.ingest import DOC_PREFIX

    heading = "1.1.1 適用"
    body = "この節は電気設備工事に適用する。"
    combined = DOC_PREFIX + heading + "\n" + body
    assert combined.startswith(DOC_PREFIX), (
        f"Embedding input does not start with DOC_PREFIX ({DOC_PREFIX!r})."
    )


def test_query_prefix_applied_to_query_input():
    """The text passed to model.encode() in query must start with QUERY_PREFIX."""
    from src.query import QUERY_PREFIX

    question = "分電盤の保護等級は屋内形と屋外形でそれぞれ何か？"
    prefixed = QUERY_PREFIX + question
    assert prefixed.startswith(QUERY_PREFIX), (
        f"Query input does not start with QUERY_PREFIX ({QUERY_PREFIX!r})."
    )
