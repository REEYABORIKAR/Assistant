"""
Retrieval Evaluation Module.

Measures retrieval quality using Recall@K, Precision@K, and MRR.
Requires a pre-ingested project with known document/chunk mappings.
"""
import json
import sys
from pathlib import Path

# Ensure backend is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.rag.retrieval.hybrid import HybridRetriever
from app.rag.retrieval.schemas import SearchResponse


def load_questions(dataset_path: str) -> list[dict]:
    """Load evaluation questions from JSON dataset."""
    with open(dataset_path) as f:
        return json.load(f)


def recall_at_k(retrieved_chunk_ids: list[str], expected_chunk_ids: list[str], k: int) -> float:
    """Fraction of expected chunks that appear in top-k retrieved."""
    if not expected_chunk_ids:
        return 1.0
    retrieved_set = set(retrieved_chunk_ids[:k])
    relevant_retrieved = set(expected_chunk_ids) & retrieved_set
    return len(relevant_retrieved) / len(expected_chunk_ids)


def precision_at_k(retrieved_chunk_ids: list[str], expected_chunk_ids: list[str], k: int) -> float:
    """Fraction of top-k retrieved chunks that are actually relevant."""
    if k == 0:
        return 0.0
    retrieved_set = set(retrieved_chunk_ids[:k])
    relevant_retrieved = set(expected_chunk_ids) & retrieved_set
    return len(relevant_retrieved) / k


def mean_reciprocal_rank(retrieved_chunk_ids: list[str], expected_chunk_ids: list[str]) -> float:
    """Reciprocal rank of the first relevant result."""
    expected_set = set(expected_chunk_ids)
    for i, chunk_id in enumerate(retrieved_chunk_ids):
        if chunk_id in expected_set:
            return 1.0 / (i + 1)
    return 0.0


def evaluate_single_query(
    retriever: HybridRetriever,
    project_id: str,
    question: dict,
    k: int = 5,
    user_role: str | None = None,
) -> dict:
    """Run retrieval for a single question and compute metrics."""
    query = question["query"]
    expected_chunks = question["expected_chunks"]

    response: SearchResponse = retriever.retrieve(
        project_id=project_id,
        query=query,
        top_k=k,
        user_role=user_role,
    )

    retrieved_chunk_ids = [r.chunk_id for r in response.results]

    return {
        "query": query,
        "expected_chunks": expected_chunks,
        "retrieved_chunks": retrieved_chunk_ids,
        "recall_at_k": recall_at_k(retrieved_chunk_ids, expected_chunks, k),
        "precision_at_k": precision_at_k(retrieved_chunk_ids, expected_chunks, k),
        "mrr": mean_reciprocal_rank(retrieved_chunk_ids, expected_chunks),
        "num_results": len(response.results),
        "category": question.get("category", "unknown"),
    }


def run_retrieval_eval(
    retriever: HybridRetriever,
    project_id: str,
    dataset_path: str | None = None,
    k: int = 5,
    user_role: str | None = None,
) -> dict:
    """Run full retrieval evaluation and return aggregated results."""
    if dataset_path is None:
        dataset_path = str(Path(__file__).resolve().parent / "datasets" / "questions.json")

    questions = load_questions(dataset_path)
    results = []

    for q in questions:
        result = evaluate_single_query(retriever, project_id, q, k=k, user_role=user_role)
        results.append(result)

    # Aggregate
    n = len(results)
    if n == 0:
        return {"per_query": [], "aggregate": {"recall": 0, "precision": 0, "mrr": 0, "n": 0}}

    agg = {
        "recall": sum(r["recall_at_k"] for r in results) / n,
        "precision": sum(r["precision_at_k"] for r in results) / n,
        "mrr": sum(r["mrr"] for r in results) / n,
        "n": n,
        "k": k,
    }

    return {"per_query": results, "aggregate": agg}


def print_retrieval_report(eval_results: dict) -> str:
    """Format retrieval evaluation results as a readable string."""
    agg = eval_results["aggregate"]
    lines = [
        "Retrieval Quality",
        f"  Recall@{agg.get('k', 5)}:    {agg['recall']:.2f}",
        f"  Precision@{agg.get('k', 5)}: {agg['precision']:.2f}",
        f"  MRR:           {agg['mrr']:.2f}",
        f"  Queries:       {agg['n']}",
    ]

    # Per-category breakdown
    per_query = eval_results.get("per_query", [])
    categories = {}
    for r in per_query:
        cat = r.get("category", "unknown")
        if cat not in categories:
            categories[cat] = {"recall": [], "precision": [], "mrr": []}
        categories[cat]["recall"].append(r["recall_at_k"])
        categories[cat]["precision"].append(r["precision_at_k"])
        categories[cat]["mrr"].append(r["mrr"])

    if categories:
        lines.append("  By category:")
        for cat, metrics in sorted(categories.items()):
            n = len(metrics["recall"])
            avg_r = sum(metrics["recall"]) / n
            avg_p = sum(metrics["precision"]) / n
            avg_m = sum(metrics["mrr"]) / n
            lines.append(f"    {cat}: recall={avg_r:.2f} precision={avg_p:.2f} mrr={avg_m:.2f} (n={n})")

    return "\n".join(lines)
