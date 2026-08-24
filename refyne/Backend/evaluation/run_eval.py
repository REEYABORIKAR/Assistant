"""
Evaluation CLI Entrypoint.

Runs all evaluations (retrieval, generation, requirement quality)
and produces a timestamped report.

Usage:
    python -m evaluation.run_eval [--project-id PROJECT_ID] [--k 5] [--output-dir DIR]
"""
import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

# Ensure backend is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evaluation.generation_eval import print_generation_report, run_generation_eval
from evaluation.requirement_eval import print_requirement_report, run_requirement_eval
from evaluation.retrieval_eval import print_retrieval_report, run_retrieval_eval


def create_mock_retriever():
    """Create a mock retriever for dry-run testing without a live DB."""
    from unittest.mock import MagicMock

    from app.rag.retrieval.schemas import (
        RetrievalMetadata,
        SearchResponse,
    )

    def mock_retrieve(project_id, query, top_k=5, document_ids=None, user_role=None):
        """Return empty results for dry-run."""
        return SearchResponse(
            query=query,
            project_id=project_id,
            results=[],
            citations=[],
            source_documents=[],
            context="",
            metadata=RetrievalMetadata(
                semantic_results_count=0,
                bm25_results_count=0,
                merged_candidates_count=0,
                final_results_count=0,
                min_score_threshold=0.1,
            ),
        )

    mock = MagicMock()
    mock.retrieve = mock_retrieve
    return mock


def run_all_evals(
    project_id: str = None,
    k: int = 5,
    output_dir: str = None,
) -> dict:
    """Run all evaluations and produce a combined report."""
    if output_dir is None:
        output_dir = str(Path(__file__).resolve().parent / "results")
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    report = {"timestamp": timestamp, "evaluations": {}}

    backend_dir = str(Path(__file__).resolve().parent.parent)

    # --- Requirement Quality (no DB needed) ---
    print("Running requirement quality evaluation...")
    try:
        req_results = run_requirement_eval()
        report["evaluations"]["requirement_quality"] = req_results
        print(print_requirement_report(req_results))
    except Exception as e:
        print(f"  Requirement eval failed: {e}")
        report["evaluations"]["requirement_quality"] = {"error": str(e)}

    print()

    # --- Retrieval Evaluation ---
    print("Running retrieval evaluation...")
    if project_id:
        try:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker

            from app.core.config import settings

            engine = create_engine(settings.DATABASE_URL)
            Session = sessionmaker(bind=engine)
            db = Session()

            from app.rag.retrieval.hybrid import HybridRetriever
            retriever = HybridRetriever(db)

            retrieval_results = run_retrieval_eval(retriever, project_id, k=k, user_role="ADMIN")
            report["evaluations"]["retrieval"] = retrieval_results
            print(print_retrieval_report(retrieval_results))

            # Run a few generation evals if retriever works
            generations = []
            dataset_path = str(Path(__file__).resolve().parent / "datasets" / "questions.json")
            with open(dataset_path) as f:
                questions = json.load(f)

            from app.services.generation import generate_answer
            for q in questions[:5]:  # Limit to 5 for speed
                resp = retriever.retrieve(project_id=project_id, query=q["query"], top_k=k, user_role="ADMIN")
                gen = generate_answer(query=q["query"], context=resp.context, citations=resp.citations)
                generations.append({
                    "query": q["query"],
                    "answer": gen.get("answer", ""),
                    "context": resp.context,
                    "citations": resp.citations,
                })

            gen_results = run_generation_eval(generations)
            report["evaluations"]["generation"] = gen_results
            print(print_generation_report(gen_results))

            db.close()
        except Exception as e:
            print(f"  Retrieval/generation eval failed: {e}")
            report["evaluations"]["retrieval"] = {"error": str(e)}
    else:
        print("  Skipping (no --project-id provided)")
        report["evaluations"]["retrieval"] = {"skipped": True, "reason": "no project_id"}
        report["evaluations"]["generation"] = {"skipped": True, "reason": "no project_id"}

    # --- Save report ---
    report_path = os.path.join(output_dir, f"eval_report_{timestamp}.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\nReport saved to: {report_path}")

    return report


def main():
    parser = argparse.ArgumentParser(description="Run Refyne evaluation suite")
    parser.add_argument("--project-id", help="Project ID with ingested documents")
    parser.add_argument("--k", type=int, default=5, help="Top-k for retrieval eval (default: 5)")
    parser.add_argument("--output-dir", help="Directory for reports (default: evaluation/results)")
    args = parser.parse_args()

    print("=" * 60)
    print("  Refyne Evaluation Suite")
    print(f"  {datetime.now(UTC).isoformat()}")
    print("=" * 60)
    print()

    report = run_all_evals(
        project_id=args.project_id,
        k=args.k,
        output_dir=args.output_dir,
    )

    print()
    print("=" * 60)
    print("  Summary")
    print("=" * 60)
    for name, data in report.get("evaluations", {}).items():
        if isinstance(data, dict) and "aggregate" in data:
            print(f"  {name}: OK")
        elif isinstance(data, dict) and "error" in data:
            print(f"  {name}: FAILED ({data['error'][:60]})")
        else:
            print(f"  {name}: {type(data).__name__}")


if __name__ == "__main__":
    main()
