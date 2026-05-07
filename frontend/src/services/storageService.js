/**
 * Storage Service
 * Handles local storage and session storage
 */

export const storageService = {
  setSessionId: (sessionId) => {
    localStorage.setItem('sessionId', sessionId);
  },

  getSessionId: () => {
    return localStorage.getItem('sessionId');
  },

  setInterview: (interview) => {
    localStorage.setItem('interview', JSON.stringify(interview));
  },

  getInterview: () => {
    const interview = localStorage.getItem('interview');
    return interview ? JSON.parse(interview) : null;
  },

  clearSession: () => {
    localStorage.removeItem('sessionId');
    localStorage.removeItem('interview');
  },
};

export default storageService;
