# FSA & System Update Report: Interview Dialogue Manager

## 1) Objective

We formalized interview flow as a **Finite State Automaton (FSA)** and aligned the end-to-end product around it:

- explicit state transitions,
- invalid-transition prevention,
- deterministic panel routing,
- LLM-first question/evaluation behavior,
- clearer UI turn structure,
- richer resume understanding for interview grounding.

---

## 2) FSA Definition

Implemented in `backend/controller/interview_controller.py` as `InterviewState`.

### States

- `START`
- `ROLE_SELECTED`
- `RESUME_PROCESSED`
- `QUESTION_ASKED`
- `ANSWER_RECEIVED`
- `ANSWER_EVALUATED`
- `FOLLOW_UP`
- `INTERVIEW_COMPLETE`

### Transition Function

Implemented in `transition_state(current_state, event)`.

Key legal transitions:

- `START --select_role--> ROLE_SELECTED`
- `ROLE_SELECTED --process_resume--> RESUME_PROCESSED`
- `RESUME_PROCESSED --ask_question--> QUESTION_ASKED`
- `QUESTION_ASKED --submit_answer--> ANSWER_RECEIVED`
- `ANSWER_RECEIVED --evaluate_answer--> ANSWER_EVALUATED`
- `ANSWER_EVALUATED --follow_up--> FOLLOW_UP`
- `ANSWER_EVALUATED --next_question--> QUESTION_ASKED`
- `ANSWER_EVALUATED --end_interview--> INTERVIEW_COMPLETE`
- `FOLLOW_UP --submit_answer--> ANSWER_RECEIVED`
- `FOLLOW_UP --end_interview--> INTERVIEW_COMPLETE`

Invalid transitions raise `ValueError` and are surfaced as request errors where appropriate.

---

## 3) Backend Integration

### `start_session(...)`

`InterviewController.start_session(...)` applies:

1. `START -> ROLE_SELECTED`
2. `ROLE_SELECTED -> RESUME_PROCESSED`
3. `RESUME_PROCESSED -> QUESTION_ASKED`

Session stores:

- `current_state`
- `current_question`
- `question_count`
- `max_questions`
- `current_interviewer`
- `panel_index`

### `handle_answer(...)`

`InterviewController.handle_answer(...)`:

- accepts answers only in `{QUESTION_ASKED, FOLLOW_UP}`,
- transitions via `submit_answer` then `evaluate_answer`,
- branches to `follow_up`, `next_question`, or `end_interview`,
- returns `current_state` in response payload.

Submitting after `INTERVIEW_COMPLETE` is rejected with an invalid-state error.

---

## 4) Panel Routing

Panel flow uses deterministic speaker rotation in controller logic:

1. `Friendly HR`
2. `Strict Interviewer`
3. `Deep Technical Expert`
4. `Interrupting Skeptic`

`next_panel_speaker(...)` advances by `panel_index` and keeps follow-up flow reproducible for demo/evaluation.

---

## 5) LLM-First Inference Behavior

To reduce generic rule-based interviews, model routes were hardened:

- `ALLOW_RULE_BASED_FALLBACK=false` in strict mode,
- if provider fails, routes return `503` instead of silent rule fallbacks,
- model client retries with `retry-after` support for `429` limits,
- prompts were tightened for more diagnostic questioning and stronger scoring anchors.

Files touched:

- `backend/routes/model_inference.py`
- `backend/services/github_models_inference.py`
- `backend/.env`
- `backend/.env.example`

---

## 6) UI Flow Clarification (Question vs Feedback)

The interview chat flow was changed to avoid confusion:

### Previous behavior

Question and previous-answer feedback were concatenated into a single assistant bubble.

### Current behavior

After a user answer, UI now renders **two separate blocks**:

1. feedback card (`role: "feedback"`) for the previous answer,
2. assistant question bubble (`role: "assistant"`) for the next turn.

This removes mixed-context messaging and improves turn clarity.

File: `frontend/src/pages/InterviewUI.jsx`

---

## 7) Feedback Color Semantics

Feedback card color now maps to score quality:

- low score: red theme,
- medium score: yellow theme,
- strong score: green theme.

Implemented via `feedbackTheme(score)` in `InterviewUI.jsx`, affecting card background, border accent, header label, and text color.

---

## 8) Expanded Interview Configuration

Frontend option banks were significantly expanded to increase scenario diversity:

- more `ROLES`,
- more `QUESTION_TYPES`,
- more `INTERVIEW_MODES`,
- richer per-mode `INTERVIEWERS`,
- expanded `PANEL_PERSONAS` roster.

This supports broader mock interview use cases across engineering, product, design, business, and leadership.

File: `frontend/src/pages/InterviewUI.jsx`

---

## 9) Resume Parser Improvements

Resume understanding was upgraded to better drive interview relevance:

- section detection (`experience`, `projects`, `education`, `skills`, ...),
- normalized skill alias extraction,
- stronger experience and project separation,
- richer achievements parsing (action + metrics),
- contact extraction and experience-year estimation,
- improved summary generation.

Additional parsed fields now include:

- `contact`
- `years_experience`
- `sections_detected`

Core file: `backend/services/resume_parser.py`

---

## 10) Dependency/Requirements Update

`backend/requirements.txt` was aligned with actual runtime imports:

- added: `sentence-transformers==2.2.2` (used by NLP engine),
- removed: `spacy==3.7.2` (unused in backend and problematic on current env).

Import sanity check passed after update.

---

## 11) Validation Summary

Validated outcomes include:

- FSA transition correctness and invalid-state rejection,
- clean post-answer UI flow (feedback then next question),
- feedback color response by score band,
- improved resume extraction for `experience` and `projects`,
- dependency import sanity (`ALL_IMPORTS_OK`).

---

## 12) FSA Diagram

```text
START
  ↓
ROLE_SELECTED
  ↓
RESUME_PROCESSED
  ↓
QUESTION_ASKED
  ↓
ANSWER_RECEIVED
  ↓
ANSWER_EVALUATED
  ↓
FOLLOW_UP or QUESTION_ASKED
  ↓
INTERVIEW_COMPLETE
```

Panel note: `FOLLOW_UP` selects the next interviewer persona deterministically.

---

