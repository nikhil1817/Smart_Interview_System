import argparse
import json
from typing import Dict, List

import numpy as np
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

LABELS = [
    "clarity",
    "technical_depth",
    "structure_star",
    "relevance",
    "communication",
    "overall",
]


def load_jsonl(path: str) -> List[dict]:
    rows: List[dict] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    if not rows:
        raise ValueError("No data found in eval JSONL")
    return rows


def build_input(row: dict) -> str:
    ctx = row.get("conversation_context", [])
    ctx_lines = [f"{t.get('speaker', 'unknown')}: {t.get('text', '')}" for t in ctx[-4:]]
    return (
        f"Role: {row.get('role_target', '')}\n"
        f"QuestionType: {row.get('question_type', '')}\n"
        f"Mode: {row.get('mode', '')}\n"
        f"Interviewer: {row.get('interviewer_persona', '')}\n"
        f"ResumeSummary: {row.get('resume_summary', '')}\n"
        f"ConversationContext:\n{'\n'.join(ctx_lines)}\n"
        f"CurrentQuestion: {row.get('current_question', '')}\n"
        f"CandidateAnswer: {row.get('candidate_answer', '')}"
    )


def extract_labels(row: dict) -> np.ndarray:
    scores = row.get("human_scores", {})
    return np.array([float(scores.get(label, 0.0)) for label in LABELS], dtype=np.float32)


def corr_safe(x: np.ndarray, y: np.ndarray) -> float:
    if np.std(x) == 0 or np.std(y) == 0:
        return 0.0
    return float(np.corrcoef(x, y)[0, 1])


def evaluate_rows(rows: List[dict], model, tokenizer, max_length: int) -> Dict[str, float]:
    texts = [build_input(row) for row in rows]
    gold = np.stack([extract_labels(row) for row in rows], axis=0)

    enc = tokenizer(texts, truncation=True, padding=True, max_length=max_length, return_tensors="pt")
    with torch.no_grad():
        logits = model(**enc).logits
    pred = logits.detach().cpu().numpy()

    mae = np.mean(np.abs(pred - gold), axis=0)
    rmse = np.sqrt(np.mean((pred - gold) ** 2, axis=0))

    metrics: Dict[str, float] = {
        "count": float(len(rows)),
        "mae_mean": float(np.mean(mae)),
        "rmse_mean": float(np.mean(rmse)),
    }

    for i, label in enumerate(LABELS):
        metrics[f"mae_{label}"] = float(mae[i])
        metrics[f"rmse_{label}"] = float(rmse[i])
        metrics[f"corr_{label}"] = corr_safe(pred[:, i], gold[:, i])

    return metrics


def evaluate_by_group(rows: List[dict], model, tokenizer, max_length: int, key: str) -> Dict[str, Dict[str, float]]:
    grouped: Dict[str, List[dict]] = {}
    for row in rows:
        grouped.setdefault(str(row.get(key, "unknown")), []).append(row)

    results: Dict[str, Dict[str, float]] = {}
    for group_name, group_rows in grouped.items():
        results[group_name] = evaluate_rows(group_rows, model, tokenizer, max_length)

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate interview scoring model")
    parser.add_argument("--model", required=True, help="Path to trained evaluator model")
    parser.add_argument("--data", required=True, help="Path to eval JSONL")
    parser.add_argument("--max-length", type=int, default=512)
    parser.add_argument("--group-by", choices=["role_target", "mode", "question_type"], default=None)
    parser.add_argument("--output-json", default=None, help="Optional path to save metrics JSON")
    args = parser.parse_args()

    tokenizer = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForSequenceClassification.from_pretrained(args.model)
    model.eval()

    rows = load_jsonl(args.data)

    overall = evaluate_rows(rows, model, tokenizer, args.max_length)
    print("Overall metrics")
    for k in sorted(overall.keys()):
        print(f"{k}: {overall[k]:.4f}")

    grouped = {}
    if args.group_by:
        grouped = evaluate_by_group(rows, model, tokenizer, args.max_length, args.group_by)
        print(f"\nMetrics by {args.group_by}")
        for group_name, metrics in grouped.items():
            print(f"- {group_name}: mae_mean={metrics['mae_mean']:.4f}, rmse_mean={metrics['rmse_mean']:.4f}")

    if args.output_json:
        payload = {
            "overall": overall,
            "grouped": grouped,
        }
        with open(args.output_json, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        print(f"\nSaved metrics JSON to {args.output_json}")


if __name__ == "__main__":
    main()
