# Modeling Quickstart

This folder contains the fastest path to start building the real interview model.

## Files
1. annotation_guidelines.md: Labeling rubric and policy
2. sample_labeled_data.jsonl: Starter dataset format
3. train_evaluator.py: Train evaluator model on labeled turns
4. eval_interview_model.py: Benchmark trained evaluator
5. inference_contract.md: Production request/response contract

## 1) Create data
Start with JSONL following sample_labeled_data.jsonl format.

## 2) Train evaluator
Run from backend/modeling:

python3 train_evaluator.py \
  --data sample_labeled_data.jsonl \
  --model microsoft/deberta-v3-base \
  --output ./artifacts/evaluator_v1 \
  --epochs 3 \
  --batch-size 4

## 3) Evaluate model
python3 eval_interview_model.py \
  --model ./artifacts/evaluator_v1 \
  --data sample_labeled_data.jsonl \
  --group-by role_target

## 4) Integrate in API
Use inference_contract.md as the strict contract for:
1. generate-question
2. evaluate-answer
3. generate-feedback

## Notes
1. Current scripts assume transformers and torch are installed.
2. For production quality, use at least 8k-12k labeled turns.
3. Keep annotation rubric fixed for stable training.
