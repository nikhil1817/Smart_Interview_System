# Interview Annotation Guidelines

## Goal
Create high-quality labels for interview turns so the evaluator model can score answers consistently and generate actionable feedback.

## Unit Of Annotation
Annotate one candidate answer turn at a time.

Required fields per record:
1. role_target
2. question_type
3. mode
4. interviewer_persona
5. current_question
6. candidate_answer
7. human_scores
8. human_feedback
9. next_best_question

## Score Rubric (1-10)
Use integer scores from 1 to 10.

1. clarity
- 1-3: hard to follow, confusing, vague structure
- 4-6: understandable but uneven or noisy
- 7-8: clear and easy to follow
- 9-10: crisp, precise, and very readable

2. technical_depth
- 1-3: no meaningful technical substance
- 4-6: basic detail, limited depth
- 7-8: strong technical explanation and tradeoffs
- 9-10: expert-level depth and nuanced reasoning

3. structure_star
- Behavioral: Situation, Task, Action, Result quality
- Technical: logical decomposition and stepwise reasoning
- 1-3: no structure
- 4-6: partial structure
- 7-8: strong structure
- 9-10: excellent structure and flow

4. relevance
- 1-3: mostly off-topic
- 4-6: partly relevant
- 7-8: clearly relevant
- 9-10: tightly aligned to the question and role

5. communication
- 1-3: poor tone, weak communication
- 4-6: acceptable but rough
- 7-8: effective and professional
- 9-10: excellent communication and confidence

6. overall
Overall interview quality for this answer.
Do not use a simple average when one dimension is critically weak.

## Feedback Writing Rules
Use 2-4 sentences.

Must include:
1. One specific strength
2. One specific weakness
3. One concrete improvement step

Good example:
"You gave a clear summary and included measurable impact. The answer missed system tradeoffs and failure handling. Next time, add one explicit downside and how you mitigated it."

Bad example:
"Good job. Improve technical depth."

## Next Question Rules
Write the next question that a strong interviewer would ask.

1. Must build on the candidate answer
2. Must match selected question_type and role_target
3. Keep one question only
4. Keep under 30 words

## Labeling Policy
1. Do not infer hidden facts not present in text
2. Penalize fabricated claims if obvious
3. Score content quality, not writing style preference
4. Be fair across accents, grammar variance, and phrasing differences
5. If uncertain, add a note in an optional field named annotation_note

## Quality Control
Every batch of 200 records:
1. Double-label 10 percent of records
2. Compute agreement on overall score
3. If agreement gap > 1.5 points, run rubric calibration

## JSONL Template
Use one JSON object per line.

{
  "session_id": "uuid",
  "role_target": "Backend Engineer",
  "question_type": "System Design",
  "mode": "stress",
  "interviewer_persona": "Tough Critic",
  "resume_summary": "Built distributed APIs and improved latency by 40 percent.",
  "conversation_context": [
    {"speaker": "assistant", "text": "Design a scalable API gateway."},
    {"speaker": "user", "text": "I would start with routing and caching..."}
  ],
  "current_question": "How would you handle failover for regional outages?",
  "candidate_answer": "I would use active-active regions with health-based routing...",
  "human_scores": {
    "clarity": 7,
    "technical_depth": 8,
    "structure_star": 6,
    "relevance": 8,
    "communication": 7,
    "overall": 7
  },
  "human_feedback": "Strong high-level architecture and clear failover direction. You did not explain consistency tradeoffs across regions. Add your replication strategy and expected recovery targets.",
  "next_best_question": "What consistency model would you choose for cross-region writes and why?"
}
