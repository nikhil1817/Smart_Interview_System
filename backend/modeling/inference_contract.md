# Production Inference API Contract

## Version
v1

## Base Path
/api/v1/model

## Endpoint 1: Generate Next Question
POST /api/v1/model/generate-question

Purpose:
Generate the next interviewer turn with persona and reasoning metadata.

### Request Body
```json
{
  "session_id": "string",
  "role_target": "Backend Engineer",
  "question_type": "System Design",
  "mode": "stress",
  "interviewer_persona": "Tough Critic",
  "resume_summary": "Built distributed APIs and reduced latency by 40 percent.",
  "conversation_context": [
    {"speaker": "assistant", "text": "Design a scalable API gateway."},
    {"speaker": "user", "text": "I would start with regional routing..."}
  ],
  "candidate_answer": "I would keep auth stateless and push policy checks to the edge.",
  "constraints": {
    "max_question_words": 35,
    "difficulty": "medium"
  }
}
```

### Response Body
```json
{
  "question": "How would you handle consistency during regional failover?",
  "intent": "probe_tradeoff",
  "difficulty": "medium",
  "persona_style": "challenging",
  "expected_signals": ["specific metrics", "failure mode reasoning"],
  "trace_id": "string"
}
```

## Endpoint 2: Evaluate Candidate Answer
POST /api/v1/model/evaluate-answer

Purpose:
Score a candidate answer against rubric dimensions.

### Request Body
```json
{
  "session_id": "string",
  "role_target": "Backend Engineer",
  "question_type": "System Design",
  "mode": "stress",
  "current_question": "How would you handle consistency during regional failover?",
  "candidate_answer": "I would use active-active with bounded staleness and conflict resolution...",
  "conversation_context": [
    {"speaker": "assistant", "text": "How would you handle consistency during regional failover?"}
  ]
}
```

### Response Body
```json
{
  "scores": {
    "clarity": 7.2,
    "technical_depth": 8.1,
    "structure_star": 6.0,
    "relevance": 8.5,
    "communication": 7.3,
    "overall": 7.4
  },
  "confidence": 0.82,
  "uncertainty_flags": [],
  "trace_id": "string"
}
```

## Endpoint 3: Generate Coaching Feedback
POST /api/v1/model/generate-feedback

Purpose:
Generate actionable feedback from evaluator output.

### Request Body
```json
{
  "session_id": "string",
  "current_question": "How would you handle consistency during regional failover?",
  "candidate_answer": "I would use active-active with bounded staleness...",
  "scores": {
    "clarity": 7.2,
    "technical_depth": 8.1,
    "structure_star": 6.0,
    "relevance": 8.5,
    "communication": 7.3,
    "overall": 7.4
  },
  "role_target": "Backend Engineer",
  "question_type": "System Design"
}
```

### Response Body
```json
{
  "feedback": "Strong technical depth and relevant architecture choices. You did not explain tradeoffs around write conflicts and recovery objectives. Add explicit RPO and RTO targets and one fallback strategy.",
  "improvement_actions": [
    "State one consistency model and why",
    "Name expected RPO and RTO",
    "Describe conflict resolution strategy"
  ],
  "trace_id": "string"
}
```

## Error Contract
All endpoints return this on failure:

```json
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "Human-readable error message",
    "details": {}
  },
  "trace_id": "string"
}
```

## JSON Schema (Condensed)

### Score Object
```json
{
  "type": "object",
  "required": ["clarity", "technical_depth", "structure_star", "relevance", "communication", "overall"],
  "properties": {
    "clarity": {"type": "number", "minimum": 0, "maximum": 10},
    "technical_depth": {"type": "number", "minimum": 0, "maximum": 10},
    "structure_star": {"type": "number", "minimum": 0, "maximum": 10},
    "relevance": {"type": "number", "minimum": 0, "maximum": 10},
    "communication": {"type": "number", "minimum": 0, "maximum": 10},
    "overall": {"type": "number", "minimum": 0, "maximum": 10}
  }
}
```

### Conversation Turn
```json
{
  "type": "object",
  "required": ["speaker", "text"],
  "properties": {
    "speaker": {"type": "string", "enum": ["assistant", "user"]},
    "text": {"type": "string", "minLength": 1}
  }
}
```
