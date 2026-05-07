/**
 * Interview Context
 * Global state management for interview data
 */

import React, { createContext, useState, useCallback } from 'react';

export const InterviewContext = createContext();

export const InterviewProvider = ({ children }) => {
  const [interview, setInterview] = useState(null);
  const [sessionId, setSessionId] = useState(null);

  const value = {
    interview,
    setInterview,
    sessionId,
    setSessionId,
  };

  return (
    <InterviewContext.Provider value={value}>
      {children}
    </InterviewContext.Provider>
  );
};

export default InterviewContext;
