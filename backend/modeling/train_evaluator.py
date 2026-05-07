import argparse
import inspect
import json
import os
import random
from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
import torch
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    Trainer,
    TrainingArguments,
)

LABELS = [
    "clarity",
    "technical_depth",
    "structure_star",
    "relevance",
    "communication",
    "overall",
]


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


@dataclass
class TurnRecord:
    role_target: str
    question_type: str
    mode: str
    interviewer_persona: str
    resume_summary: str
    conversation_context: List[Dict[str, str]]
    current_question: str
    candidate_answer: str
    human_scores: Dict[str, float]


def load_jsonl(path: str) -> List[TurnRecord]:
    records: List[TurnRecord] = []
    with open(path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            missing = [k for k in ["role_target", "question_type", "mode", "interviewer_persona", "current_question", "candidate_answer", "human_scores"] if k not in obj]
            if missing:
                raise ValueError(f"Missing keys at line {line_no}: {missing}")
            records.append(
                TurnRecord(
                    role_target=obj["role_target"],
                    question_type=obj["question_type"],
                    mode=obj["mode"],
                    interviewer_persona=obj["interviewer_persona"],
                    resume_summary=obj.get("resume_summary", ""),
                    conversation_context=obj.get("conversation_context", []),
                    current_question=obj["current_question"],
                    candidate_answer=obj["candidate_answer"],
                    human_scores=obj["human_scores"],
                )
            )
    if not records:
        raise ValueError("No training data found in JSONL file")
    return records


def build_input_text(record: TurnRecord, max_context_turns: int = 4) -> str:
    context_lines = []
    for turn in record.conversation_context[-max_context_turns:]:
        speaker = turn.get("speaker", "unknown")
        text = turn.get("text", "")
        context_lines.append(f"{speaker}: {text}")

    context_text = "\n".join(context_lines)
    prompt = (
        f"Role: {record.role_target}\n"
        f"QuestionType: {record.question_type}\n"
        f"Mode: {record.mode}\n"
        f"Interviewer: {record.interviewer_persona}\n"
        f"ResumeSummary: {record.resume_summary}\n"
        f"ConversationContext:\n{context_text}\n"
        f"CurrentQuestion: {record.current_question}\n"
        f"CandidateAnswer: {record.candidate_answer}"
    )
    return prompt


class InterviewDataset(torch.utils.data.Dataset):
    def __init__(self, encodings: Dict[str, List[int]], labels: np.ndarray):
        self.encodings = encodings
        self.labels = labels

    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        item = {k: torch.tensor(v[idx]) for k, v in self.encodings.items()}
        item["labels"] = torch.tensor(self.labels[idx], dtype=torch.float32)
        return item

    def __len__(self) -> int:
        return len(self.labels)


def compute_metrics(eval_pred):
    preds, labels = eval_pred
    if isinstance(preds, tuple):
        preds = preds[0]

    preds = np.array(preds)
    labels = np.array(labels)

    mae = np.mean(np.abs(preds - labels), axis=0)
    rmse = np.sqrt(np.mean((preds - labels) ** 2, axis=0))

    metrics = {
        "mae_mean": float(np.mean(mae)),
        "rmse_mean": float(np.mean(rmse)),
    }
    for i, label in enumerate(LABELS):
        metrics[f"mae_{label}"] = float(mae[i])
        metrics[f"rmse_{label}"] = float(rmse[i])
    return metrics


def split_records(records: List[TurnRecord], val_ratio: float, seed: int) -> Tuple[List[TurnRecord], List[TurnRecord]]:
    indices = list(range(len(records)))
    rng = random.Random(seed)
    rng.shuffle(indices)

    val_size = max(1, int(len(records) * val_ratio)) if len(records) > 1 else 0
    val_indices = set(indices[:val_size])

    train_records = [records[i] for i in indices if i not in val_indices]
    val_records = [records[i] for i in indices if i in val_indices]

    if not train_records:
        train_records = val_records
        val_records = []

    return train_records, val_records


def records_to_xy(records: List[TurnRecord]) -> Tuple[List[str], np.ndarray]:
    texts: List[str] = []
    labels: List[List[float]] = []

    for record in records:
        texts.append(build_input_text(record))
        labels.append([float(record.human_scores.get(label, 0.0)) for label in LABELS])

    return texts, np.array(labels, dtype=np.float32)


def main() -> None:
    torch.set_default_dtype(torch.float32)

    parser = argparse.ArgumentParser(description="Train evaluator model for interview scoring")
    parser.add_argument("--data", required=True, help="Path to JSONL labeled data")
    parser.add_argument("--model", default="microsoft/deberta-v3-base", help="Hugging Face base model")
    parser.add_argument("--output", default="./artifacts/evaluator", help="Output directory")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--max-length", type=int, default=512)
    parser.add_argument("--val-ratio", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    set_seed(args.seed)
    os.makedirs(args.output, exist_ok=True)

    records = load_jsonl(args.data)
    train_records, val_records = split_records(records, args.val_ratio, args.seed)

    tokenizer = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForSequenceClassification.from_pretrained(
        args.model,
        num_labels=len(LABELS),
        problem_type="regression",
    )
    model = model.float()

    train_texts, train_labels = records_to_xy(train_records)
    train_enc = tokenizer(train_texts, truncation=True, padding=True, max_length=args.max_length)
    train_ds = InterviewDataset(train_enc, train_labels)

    eval_ds = None
    if val_records:
        val_texts, val_labels = records_to_xy(val_records)
        val_enc = tokenizer(val_texts, truncation=True, padding=True, max_length=args.max_length)
        eval_ds = InterviewDataset(val_enc, val_labels)

    ta_params = set(inspect.signature(TrainingArguments.__init__).parameters.keys())
    training_kwargs = {
        "output_dir": args.output,
        "learning_rate": 2e-5,
        "per_device_train_batch_size": args.batch_size,
        "per_device_eval_batch_size": args.batch_size,
        "num_train_epochs": args.epochs,
        "weight_decay": 0.01,
        "logging_steps": 20,
        "seed": args.seed,
    }

    if "evaluation_strategy" in ta_params:
        training_kwargs["evaluation_strategy"] = "epoch" if eval_ds is not None else "no"
    elif "eval_strategy" in ta_params:
        training_kwargs["eval_strategy"] = "epoch" if eval_ds is not None else "no"

    if "save_strategy" in ta_params:
        training_kwargs["save_strategy"] = "epoch"

    if "load_best_model_at_end" in ta_params:
        training_kwargs["load_best_model_at_end"] = True if eval_ds is not None else False
    if "metric_for_best_model" in ta_params and eval_ds is not None:
        training_kwargs["metric_for_best_model"] = "mae_mean"
    if "greater_is_better" in ta_params:
        training_kwargs["greater_is_better"] = False
    if "report_to" in ta_params:
        training_kwargs["report_to"] = "none"
    if "use_cpu" in ta_params:
        training_kwargs["use_cpu"] = True
    elif "no_cuda" in ta_params:
        training_kwargs["no_cuda"] = True
    if "use_mps_device" in ta_params:
        training_kwargs["use_mps_device"] = False
    if "fp16" in ta_params:
        training_kwargs["fp16"] = False
    if "bf16" in ta_params:
        training_kwargs["bf16"] = False

    training_args = TrainingArguments(**training_kwargs)

    trainer_kwargs = {
        "model": model,
        "args": training_args,
        "train_dataset": train_ds,
        "eval_dataset": eval_ds,
        "compute_metrics": compute_metrics if eval_ds is not None else None,
    }

    trainer_params = set(inspect.signature(Trainer.__init__).parameters.keys())
    if "tokenizer" in trainer_params:
        trainer_kwargs["tokenizer"] = tokenizer

    trainer = Trainer(**trainer_kwargs)

    trainer.train()
    trainer.save_model(args.output)
    tokenizer.save_pretrained(args.output)

    with open(os.path.join(args.output, "label_config.json"), "w", encoding="utf-8") as f:
        json.dump({"labels": LABELS}, f, indent=2)

    print(f"Saved model artifacts to {args.output}")


if __name__ == "__main__":
    main()
