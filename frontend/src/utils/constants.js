/**
 * Constants
 * Application constants and configurations
 */

export const INTERVIEW_MODES = {
  STANDARD: 'standard',
  PANEL: 'panel',
};

export const AGENT_NAMES = {
  TECHNICAL: 'technical',
  HR: 'hr',
  SKEPTIC: 'skeptic',
  EVALUATOR: 'evaluator',
};

export const API_ENDPOINTS = {
  START_INTERVIEW: '/interview/start-interview',
  SUBMIT_ANSWER: '/interview/answer',
  GET_NEXT_QUESTION: '/interview/next-question',
  END_INTERVIEW: '/interview/end',
  GET_REPORT: '/interview/report',
  TRANSCRIBE: '/voice/transcribe',
  SYNTHESIZE: '/voice/synthesize',
};

export default {
  INTERVIEW_MODES,
  AGENT_NAMES,
  API_ENDPOINTS,
};
