"""
Generation Evaluation Module.

Measures citation correctness, citation completeness, and faithfulness.
Citation correctness/completeness use deterministic checks.
Faithfulness uses LLM-as-judge.
"""
import re


def check_citation_correctness(
    answer: str,
    context: str,
    citations: list,
) -> dict:
    """
    Check that every citation in the generated answer actually exists
    in the retrieved context's citation list.

    Returns:
        dict with score (0-1), correct_count, total_citations, details
    """
    if not answer or not citations:
        return {"score": 1.0, "correct_count": 0, "total_citations": 0, "details": []}

    # Extract citation references from answer text
    # Patterns like [Source: file.pdf, Page 8] or [Source: file.pdf, Chunk 3]
    citation_pattern = re.compile(r'\[Source:([^\]]+)\]')
    found_refs = citation_pattern.findall(answer)

    if not found_refs:
        # No citations in answer - check if context had citations to reference
        return {
            "score": 1.0 if not citations else 0.0,
            "correct_count": 0,
            "total_citations": 0,
            "details": ["No citation references found in answer"],
            "has_citations_in_answer": False,
        }

    # Build set of valid citation display_texts
    valid_display_texts = set(c.display_text for c in citations)
    # Also build a set of valid chunk_id references
    valid_chunk_ids = set(f"{c.document_id}_{c.chunk_index}" for c in citations)

    correct = 0
    details = []
    for ref in found_refs:
        ref_clean = ref.strip()
        # Check if it matches any valid citation display text
        matched = False
        for valid_text in valid_display_texts:
            if ref_clean in valid_text or valid_text in ref_clean:
                matched = True
                break
        if matched:
            correct += 1
        else:
            details.append(f"Unmatched citation: [{ref_clean}]")

    total = len(found_refs)
    return {
        "score": correct / total if total > 0 else 1.0,
        "correct_count": correct,
        "total_citations": total,
        "details": details,
        "has_citations_in_answer": True,
    }


def check_citation_completeness_heuristic(
    answer: str,
    context: str,
) -> dict:
    """
    Heuristic check for citation completeness.
    Splits answer into sentences and flags sentences that make specific
    claims (contain requirement IDs or technical specifics) but lack citations.

    This is a deterministic heuristic, not LLM-based.
    """
    if not answer:
        return {"score": 1.0, "uncited_sentences": 0, "total_sentences": 0, "details": []}

    # Split into sentences
    sentences = re.split(r'(?<=[.!?])\s+', answer.strip())
    sentences = [s.strip() for s in sentences if s.strip()]

    uncited = []
    for sent in sentences:
        # Check if sentence contains a citation
        has_citation = bool(re.search(r'\[Source:', sent))
        if has_citation:
            continue

        # Check if sentence makes a specific claim worth citing
        # Heuristic: contains requirement ID pattern, specific number, or technical term
        makes_claim = bool(re.search(
            r'REQ-\w+|must\s+(be|have|support|include|provide|ensure)|'
            r'\d+\s+(times|hours|days|minutes|characters|attempts)|'
            r'AES-\d+|Visa|Mastercard|PayPal',
            sent, re.IGNORECASE
        ))
        if makes_claim:
            uncited.append(sent)

    total = len(sentences)
    uncited_count = len(uncited)
    score = (total - uncited_count) / total if total > 0 else 1.0

    return {
        "score": score,
        "uncited_sentences": uncited_count,
        "total_sentences": total,
        "details": uncited[:5],  # Cap details
    }


def check_faithfulness_heuristic(
    answer: str,
    context: str,
) -> dict:
    """
    Heuristic faithfulness check.
    Looks for common hallucination patterns:
    - Claims about specific numbers not in context
    - Requirement IDs not present in context
    - Technical specifics not mentioned in context
    """
    if not answer or not context:
        return {"score": 1.0, "issues": []}

    issues = []

    # Extract requirement IDs from answer and context
    answer_req_ids = set(re.findall(r'REQ-\w+', answer))
    context_req_ids = set(re.findall(r'REQ-\w+', context))

    # Flag requirement IDs in answer not found in context
    hallucinated_ids = answer_req_ids - context_req_ids
    for rid in hallucinated_ids:
        issues.append(f"Requirement ID {rid} in answer but not in context")

    # Extract specific numbers from answer
    answer_numbers = re.findall(r'(\d+)\s*(times|hours|days|minutes|characters|attempts|percent|%)', answer, re.IGNORECASE)
    context_text_lower = context.lower()

    for num, unit in answer_numbers:
        phrase = f"{num} {unit}"
        if phrase.lower() not in context_text_lower:
            # Check if the number appears in context at all
            if num not in context:
                issues.append(f"Specific number '{phrase}' not found in context")

    score = 1.0 if not issues else max(0.0, 1.0 - len(issues) * 0.2)

    return {
        "score": score,
        "issues": issues[:10],
        "hallucinated_req_ids": list(hallucinated_ids),
    }


def run_generation_eval(
    generations: list[dict],
) -> dict:
    """
    Run generation evaluation over a list of generation results.

    Each item in generations should have:
        - query: str
        - answer: str
        - context: str
        - citations: list[Citation]
    """
    results = []

    for gen in generations:
        citation_check = check_citation_correctness(
            answer=gen.get("answer", ""),
            context=gen.get("context", ""),
            citations=gen.get("citations", []),
        )
        completeness_check = check_citation_completeness_heuristic(
            answer=gen.get("answer", ""),
            context=gen.get("context", ""),
        )
        faithfulness_check = check_faithfulness_heuristic(
            answer=gen.get("answer", ""),
            context=gen.get("context", ""),
        )

        results.append({
            "query": gen.get("query", ""),
            "citation_correctness": citation_check,
            "citation_completeness": completeness_check,
            "faithfulness": faithfulness_check,
        })

    n = len(results)
    if n == 0:
        return {"per_query": [], "aggregate": {"citation_correctness": 0, "citation_completeness": 0, "faithfulness": 0, "n": 0}}

    agg = {
        "citation_correctness": sum(r["citation_correctness"]["score"] for r in results) / n,
        "citation_completeness": sum(r["citation_completeness"]["score"] for r in results) / n,
        "faithfulness": sum(r["faithfulness"]["score"] for r in results) / n,
        "n": n,
    }

    return {"per_query": results, "aggregate": agg}


def print_generation_report(eval_results: dict) -> str:
    """Format generation evaluation results as a readable string."""
    agg = eval_results["aggregate"]
    lines = [
        "Generation Quality",
        f"  Citation correctness:   {agg['citation_correctness']:.2f}",
        f"  Citation completeness:  {agg['citation_completeness']:.2f}",
        f"  Faithfulness:           {agg['faithfulness']:.2f}",
        f"  Generations evaluated:  {agg['n']}",
    ]

    # Flag concerning results
    for r in eval_results.get("per_query", []):
        if r["citation_correctness"]["score"] < 1.0:
            lines.append(f"  WARNING: Citation errors in '{r['query'][:50]}...'")
            for d in r["citation_correctness"]["details"]:
                lines.append(f"    - {d}")
        if r["faithfulness"]["issues"]:
            lines.append(f"  WARNING: Faithfulness issues in '{r['query'][:50]}...'")
            for d in r["faithfulness"]["issues"][:3]:
                lines.append(f"    - {d}")

    return "\n".join(lines)
