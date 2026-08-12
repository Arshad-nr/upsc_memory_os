"""
UPSC Memory OS — RAGAS Evaluation Pipeline
===========================================
Uses ragas 0.1.21 with Gemini as the judge LLM.

Strategy:
  - Phase 1: Run the live RAG pipeline to generate answers (uses our backend's call_gemini)
  - Phase 2: Hand off to RAGAS which uses ChatGoogleGenerativeAI as judge LLM

Usage:
    cd backend
    python -m evaluation.evaluate_rag

Requires:
    pip install ragas==0.1.21 langchain-google-genai datasets
"""

import asyncio
import json
import os
import sys
import time

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datasets import Dataset
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall,
)
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.run_config import RunConfig

from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings

from core.config import settings
from core.vector_store import init_models, retrieve_hybrid
from services.rag.classifier import classify_query, dynamic_k
from services.rag.synthesizer import synthesize


# ── Configuration ────────────────────────────────────────────────────
EVAL_DATASET_PATH = os.path.join(os.path.dirname(__file__), "eval_dataset.json")
TEST_USER_ID = "76284362-c5cd-4688-82d1-08079fc68e5c"

# Seconds between API calls during Phase 1 (our RAG pipeline).
PIPELINE_CALL_GAP = 5.0

# Max retries when Phase 1 hits a rate limit or returns a failed answer.
MAX_PIPELINE_RETRIES = 5
RETRY_PAUSE_SECONDS = 20.0


async def run_rag_pipeline(question: str) -> dict:
    """
    Run the full RAG pipeline for a single question.
    Returns the answer, retrieved contexts, and query type.
    """
    # Step 1: Classify
    query_type = await classify_query(question)
    await asyncio.sleep(PIPELINE_CALL_GAP)

    # Step 2: Retrieve (local — no API call)
    k = dynamic_k(query_type)
    chunks = await asyncio.to_thread(retrieve_hybrid, TEST_USER_ID, question, k)

    if not chunks:
        return {
            "answer": "No relevant context found in your notes.",
            "contexts": [],
            "query_type": query_type,
        }

    # Step 3: Synthesize (llm.py handles 429 retries internally)
    result = await synthesize(question, query_type, chunks)
    await asyncio.sleep(PIPELINE_CALL_GAP)

    # Extract context texts for RAGAS
    context_texts = [
        c.get("parent_content") or c.get("content", "")
        for c in chunks
    ]

    return {
        "answer": result["answer"],
        "contexts": context_texts,
        "query_type": result["query_type"],
    }


async def build_evaluation_dataset() -> Dataset:
    """
    Run every question through the live RAG pipeline
    and collect (question, answer, contexts, ground_truth) tuples.
    """
    with open(EVAL_DATASET_PATH, "r", encoding="utf-8") as f:
        test_cases = json.load(f)

    questions = []
    answers = []
    contexts = []
    ground_truths = []

    total = len(test_cases)
    start_time = time.time()

    for i, tc in enumerate(test_cases):
        q_preview = tc["question"][:55]
        print(f"[Pipeline] [{i+1}/{total}] {q_preview}...")

        # Retry loop: re-run if the pipeline returns a failed answer
        result = None
        for attempt in range(MAX_PIPELINE_RETRIES):
            result = await run_rag_pipeline(tc["question"])
            if result["answer"] != "Could not generate answer.":
                break
            print(f"           [Retry] Failed answer. Pausing {RETRY_PAUSE_SECONDS}s... (Attempt {attempt+1})")
            await asyncio.sleep(RETRY_PAUSE_SECONDS)

        questions.append(tc["question"])
        answers.append(result["answer"])
        contexts.append(result["contexts"])
        ground_truths.append(tc["ground_truth"])

        elapsed = time.time() - start_time
        avg_per_q = elapsed / (i + 1)
        remaining = avg_per_q * (total - i - 1)
        print(f"           → {result['query_type']} | "
              f"contexts: {len(result['contexts'])} | "
              f"ETA: {remaining:.0f}s")

    print(f"\n[Pipeline] Complete: {total} questions in {time.time()-start_time:.0f}s")

    return Dataset.from_dict({
        "question": questions,
        "answer": answers,
        "contexts": contexts,
        "ground_truth": ground_truths,
    })


def run_evaluation():
    """Main evaluation entry point."""
    print("=" * 60)
    print("  UPSC Memory OS — RAGAS Evaluation")
    print("=" * 60)

    # ── 1. Validate ──────────────────────────────────────────────
    if TEST_USER_ID == "YOUR_TEST_USER_UUID_HERE":
        print("\n❌ ERROR: Set TEST_USER_ID in evaluate_rag.py!")
        sys.exit(1)

    if not os.path.exists(EVAL_DATASET_PATH):
        print(f"\n❌ ERROR: Dataset not found at {EVAL_DATASET_PATH}")
        sys.exit(1)

    api_key = settings.GEMINI_API_KEYS[0] if settings.GEMINI_API_KEYS else ""
    if not api_key:
        print("\n❌ ERROR: No GEMINI_API_KEY found in .env!")
        sys.exit(1)

    # ── 2. Initialize local embedding models ─────────────────────
    print("\n[Eval] Loading embedding models...")
    init_models()

    # ── 3. Phase 1: Run live RAG pipeline on all questions ───────
    print("[Eval] Phase 1: Running RAG pipeline on test questions...\n")
    dataset = asyncio.run(build_evaluation_dataset())

    # ── 4. Phase 2: Set up RAGAS judge ───────────────────────────
    print("\n[Eval] Phase 2: Setting up RAGAS with Gemini as judge...")

    # RAGAS requires LangChain models wrapped with its own wrappers
    judge_llm = LangchainLLMWrapper(
        ChatGoogleGenerativeAI(
            model=settings.GEMINI_FLASH_MODEL,
            google_api_key=api_key,
            temperature=0,
        )
    )
    judge_embeddings = LangchainEmbeddingsWrapper(
        GoogleGenerativeAIEmbeddings(
            model="models/embedding-001",
            google_api_key=api_key,
        )
    )

    run_config = RunConfig(
        max_workers=2,
        max_retries=15,
        max_wait=90,
        timeout=300,
    )

    # ── 5. Run RAGAS metrics ─────────────────────────────────────
    print("[Eval] Running RAGAS metrics (4 metrics × {} questions)...\n".format(
        len(dataset)))

    results = evaluate(
        dataset=dataset,
        llm=judge_llm,
        embeddings=judge_embeddings,
        metrics=[
            faithfulness,
            answer_relevancy,
            context_precision,
            context_recall,
        ],
        run_config=run_config,
    )

    # ── 6. Print results ─────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  RAGAS EVALUATION RESULTS")
    print("=" * 60)

    scores = {
        "Faithfulness":      results.get("faithfulness", 0),
        "Answer Relevancy":  results.get("answer_relevancy", 0),
        "Context Precision": results.get("context_precision", 0),
        "Context Recall":    results.get("context_recall", 0),
    }

    for name, score in scores.items():
        bar = "█" * int(score * 20) + "░" * (20 - int(score * 20))
        status = "✅" if score >= 0.7 else "⚠️" if score >= 0.5 else "❌"
        print(f"  {status} {name:<20} {bar} {score:.3f}")

    ragas_score = sum(scores.values()) / len(scores)
    print(f"\n  {'─' * 46}")
    print(f"  Overall RAGAS Score:  {ragas_score:.3f}")
    print("=" * 60)

    # ── 7. Save detailed per-question results ────────────────────
    df = results.to_pandas()
    output_path = os.path.join(os.path.dirname(__file__), "eval_results.csv")
    df.to_csv(output_path, index=False)
    print(f"\n📊 Detailed results saved to: {output_path}")

    # ── 8. Diagnosis ─────────────────────────────────────────────
    print("\n🔍 Diagnosis (questions scoring < 0.5 on any metric):\n")
    problem_count = 0
    for _, row in df.iterrows():
        issues = []
        if row.get("faithfulness", 1) < 0.5:
            issues.append("🔴 HALLUCINATING — tighten synthesizer prompt")
        if row.get("answer_relevancy", 1) < 0.5:
            issues.append("🟡 OFF-TOPIC — check classifier routing")
        if row.get("context_precision", 1) < 0.5:
            issues.append("🟠 BAD RANKING — tune hybrid fusion weights")
        if row.get("context_recall", 1) < 0.5:
            issues.append("🔵 MISSING CONTEXT — increase k or fix chunking")
        if issues:
            problem_count += 1
            print(f"  Q: {row['question'][:70]}...")
            for issue in issues:
                print(f"     {issue}")
            print()

    if problem_count == 0:
        print("  ✅ No major issues detected! All questions scored above 0.5.\n")
    else:
        print(f"  Found {problem_count} problematic question(s). "
              f"Check eval_results.csv for full details.\n")


if __name__ == "__main__":
    run_evaluation()
