"""
Evaluation runner: runs all questions from questions.jsonl through the RAG system
and writes results to results.jsonl.

Usage:
    python eval/run_eval.py
    python eval/run_eval.py --questions eval/questions.jsonl --output eval/results.jsonl
"""
import argparse
import json
import logging
import os
import sys
from pathlib import Path

# Ensure src is on the path when running from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

QUESTIONS_PATH = Path("eval/questions.jsonl")
RESULTS_PATH = Path("eval/results.jsonl")


def load_questions(path: Path) -> list[dict]:
    questions = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                questions.append(json.loads(line))
    return questions


def run_eval(questions_path: Path, results_path: Path) -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY not set.", file=sys.stderr)
        sys.exit(1)

    from src.query import query as rag_query

    questions = load_questions(questions_path)
    print(f"Running eval on {len(questions)} questions...")

    results_path.parent.mkdir(parents=True, exist_ok=True)
    with open(results_path, "w", encoding="utf-8") as out:
        for i, q in enumerate(questions, 1):
            print(f"[{i}/{len(questions)}] {q['question'][:40]}...")
            try:
                result = rag_query(q["question"], k=3)
                record = {
                    "question": q["question"],
                    "expected_source": q.get("expected_source", ""),
                    "retrieved": result["retrieved"],
                    "answer": result["answer"],
                    "verdict": "",  # Human judge fills this
                }
            except Exception as e:
                record = {
                    "question": q["question"],
                    "expected_source": q.get("expected_source", ""),
                    "retrieved": [],
                    "answer": f"ERROR: {e}",
                    "verdict": "",
                }
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
            print(f"  → retrieved: {record['retrieved']}")

    print(f"\nDone. Results written to {results_path}")


def main():
    parser = argparse.ArgumentParser(description="Run RAG evaluation")
    parser.add_argument("--questions", default=str(QUESTIONS_PATH), help="Path to questions.jsonl")
    parser.add_argument("--output", default=str(RESULTS_PATH), help="Path to results.jsonl")
    args = parser.parse_args()
    run_eval(Path(args.questions), Path(args.output))


if __name__ == "__main__":
    main()
