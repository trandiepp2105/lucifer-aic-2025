import React, { createContext, useContext, useReducer, useEffect } from 'react';
import { TeamAnswerService } from '../services/TeamAnswerService';

// Function to get initial state from URL
const getInitialStateFromURL = () => {
  const defaultState = {
    session: null,        // số
    queryMode: 'kis',     // 'kis' hoặc 'qa'
    round: 'final',     // 'prelims' hoặc 'final'
    viewMode: 'gallery',  // 'gallery' hoặc 'samevideo'
    stage: 1,             // số
    section: 'chat',      // 'chat' hoặc 'history'
  };

  // Determine queryIndex based on round
  const getDefaultQueryIndex = (round) => {
    return round === 'final' ? 0 : 1;
  };

  // Only read URL params on client side
  if (typeof window === 'undefined') {
    return {
      ...defaultState,
      queryIndex: getDefaultQueryIndex(defaultState.round)
    };
  }

  const urlParams = new URLSearchParams(window.location.search);
  const urlState = { ...defaultState };
  
  const sessionParam = urlParams.get('session');
  if (sessionParam) {
    urlState.session = parseInt(sessionParam, 10);
  }
  
  const queryModeParam = urlParams.get('querymode');
  if (queryModeParam && ['kis', 'qa'].includes(queryModeParam)) {
    urlState.queryMode = queryModeParam;
  }
  
  const roundParam = urlParams.get('round');
  if (roundParam && ['prelims', 'final'].includes(roundParam)) {
    urlState.round = roundParam;
  }
  
  const viewModeParam = urlParams.get('viewmode');
  if (viewModeParam && ['gallery', 'samevideo'].includes(viewModeParam)) {
    urlState.viewMode = viewModeParam;
  }
  
  const stageParam = urlParams.get('stage');
  if (stageParam) {
    urlState.stage = parseInt(stageParam, 10);
  }
  
  const sectionParam = urlParams.get('section');
  if (sectionParam && ['chat', 'history'].includes(sectionParam)) {
    urlState.section = sectionParam;
  }
  
  const queryIndexParam = urlParams.get('queryindex');
  if (queryIndexParam) {
    urlState.queryIndex = parseInt(queryIndexParam, 10);
  } else {
    // Set default queryIndex based on round
    urlState.queryIndex = getDefaultQueryIndex(urlState.round);
  }

  console.log('AppContext: Initial state from URL:', urlState);
  return urlState;
};

// Initial state - read from URL immediately
const initialState = getInitialStateFromURL();

// Action types
const ActionTypes = {
  SET_SESSION: 'SET_SESSION',
  SET_QUERY_MODE: 'SET_QUERY_MODE',
  SET_ROUND: 'SET_ROUND',
  SET_VIEW_MODE: 'SET_VIEW_MODE',
  SET_STAGE: 'SET_STAGE',
  SET_SECTION: 'SET_SECTION',
  SET_QUERY_INDEX: 'SET_QUERY_INDEX',
  UPDATE_FROM_URL: 'UPDATE_FROM_URL',
  RESET_STATE: 'RESET_STATE',
  AUTO_DETECT_QUERY_MODE: 'AUTO_DETECT_QUERY_MODE',
};

// Reducer
const appReducer = (state, action) => {
  switch (action.type) {
    case ActionTypes.SET_SESSION:
      return { ...state, session: action.payload };
    case ActionTypes.SET_QUERY_MODE:
      return { ...state, queryMode: action.payload };
    case ActionTypes.SET_ROUND:
      return { 
        ...state, 
        round: action.payload,
        queryIndex: action.payload === 'final' ? 0 : (state.queryIndex || 1)
      };
    case ActionTypes.SET_VIEW_MODE:
      return { ...state, viewMode: action.payload };
    case ActionTypes.SET_STAGE:
      return { ...state, stage: action.payload };
    case ActionTypes.SET_SECTION:
      return { ...state, section: action.payload };
    case ActionTypes.SET_QUERY_INDEX:
      return { ...state, queryIndex: action.payload };
    case ActionTypes.AUTO_DETECT_QUERY_MODE:
      return { ...state, queryMode: action.payload };
    case ActionTypes.UPDATE_FROM_URL:
      return { ...state, ...action.payload };
    case ActionTypes.RESET_STATE:
      return { ...initialState, ...action.payload };
    default:
      return state;
  }
};

// Context
const AppContext = createContext();

// Provider component
export const AppProvider = ({ children }) => {
  const [state, dispatch] = useReducer(appReducer, initialState);

  // URL state management
  const updateUrlState = (newState) => {
    const urlParams = new URLSearchParams(window.location.search);
    
    if (newState.session !== undefined && newState.session !== null) {
      urlParams.set('session', newState.session.toString());
    }
    if (newState.queryMode !== undefined) {
      urlParams.set('querymode', newState.queryMode);
    }
    if (newState.round !== undefined) {
      urlParams.set('round', newState.round);
    }
    if (newState.viewMode !== undefined) {
      urlParams.set('viewmode', newState.viewMode);
    }
    if (newState.stage !== undefined) {
      urlParams.set('stage', newState.stage.toString());
    }
    if (newState.section !== undefined) {
      urlParams.set('section', newState.section);
    }
    if (newState.queryIndex !== undefined) {
      urlParams.set('queryindex', newState.queryIndex.toString());
    }

    const newUrl = `${window.location.pathname}?${urlParams.toString()}`;
    window.history.replaceState(null, '', newUrl);
  };

  // Load initial state from URL - REMOVED since we read URL in initialState
  // This prevents race condition between default state and URL params
  
  // Remove auto-detect from here - will be handled in HomePage
  // useEffect(() => {
  //   const detectQueryMode = () => {
  //     // Auto-detect logic moved to HomePage
  //   };
  //   detectQueryMode();
  // }, [state.queryIndex, state.round]);

  // Update URL when state changes - with proper dependencies
  useEffect(() => {
    updateUrlState({
      session: state.session,
      queryMode: state.queryMode,
      round: state.round,
      viewMode: state.viewMode,
      stage: state.stage,
      section: state.section,
      queryIndex: state.queryIndex,
    });
  }, [state.session, state.queryMode, state.round, state.viewMode, state.stage, state.section, state.queryIndex]);

  // Actions
  const actions = {
    setSession: (session) => dispatch({ type: ActionTypes.SET_SESSION, payload: session }),
    setQueryMode: (mode) => dispatch({ type: ActionTypes.SET_QUERY_MODE, payload: mode }),
    setRound: (round) => dispatch({ type: ActionTypes.SET_ROUND, payload: round }),
    setViewMode: (mode) => dispatch({ type: ActionTypes.SET_VIEW_MODE, payload: mode }),
    setStage: (stage) => dispatch({ type: ActionTypes.SET_STAGE, payload: stage }),
    setSection: (section) => dispatch({ type: ActionTypes.SET_SECTION, payload: section }),
    setQueryIndex: (index) => dispatch({ type: ActionTypes.SET_QUERY_INDEX, payload: index }),
    resetState: (keepState = {}) => dispatch({ type: ActionTypes.RESET_STATE, payload: keepState }),
  };

  // Utility function to validate queryMode consistency (will use allTeamAnswers from caller)
  const validateQueryModeConsistency = (allTeamAnswers, queryIndex, round, proposedMode) => {
    try {
      // Filter team answers for current queryIndex and round
      const relevantAnswers = allTeamAnswers.filter(answer => 
        answer.query_index === queryIndex && answer.round === round
      );
      
      if (relevantAnswers.length > 0) {
        // Check existing team answers
        const existingAnswer = relevantAnswers[0];
        const existingMode = (existingAnswer.qa && existingAnswer.qa.trim() !== '') ? 'qa' : 'kis';
        
        if (existingMode !== proposedMode) {
          return {
            valid: false,
            existingMode,
            message: `Query index ${queryIndex} already has team answers with type "${existingMode}". Cannot create answer with type "${proposedMode}".`
          };
        }
      }
      
      return { valid: true };
    } catch (error) {
      console.error('Error validating queryMode consistency:', error);
      return { valid: true }; // Allow if we can't validate
    }
  };

  const value = {
    ...state,
    ...actions,
    validateQueryModeConsistency,
  };

  return (
    <AppContext.Provider value={value}>
      {children}
    </AppContext.Provider>
  );
};

// Custom hook to use the context
export const useApp = () => {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useApp must be used within an AppProvider');
  }
  return context;
};

export default AppContext;
