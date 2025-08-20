import React, { createContext, useContext, useReducer, useEffect } from 'react';
import { TeamAnswerService } from '../services/TeamAnswerService';
import { QueryService } from '../services/QueryService';

// Store session param from URL for validation (outside of state)
let urlSessionParam = null;

// Function to get initial state from URL
const getInitialStateFromURL = () => {
  const defaultState = {
    session: null,        // số
    sessionLoading: true, // loading state for session validation
    queryMode: 'kis',     // 'kis' hoặc 'qa'
    round: 'final',     // 'prelims' hoặc 'final'
    viewMode: 'gallery',  // 'gallery' hoặc 'samevideo'
    stage: 1,             // số
    section: 'chat',      // 'chat' hoặc 'history'
    k: 50,                // top k results (1-200)
    searchUrl: '',        // search server endpoint
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
  
  // Set session from URL immediately, store for validation
  const sessionParam = urlParams.get('session');
  if (sessionParam) {
    urlState.session = sessionParam; // Set immediately for components
    urlSessionParam = sessionParam; // Also store globally for validation
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
  
  const kParam = urlParams.get('k');
  if (kParam) {
    const k = parseInt(kParam, 10);
    if (k >= 1 && k <= 200) {
      urlState.k = k;
    }
  }
  
  const searchUrlParam = urlParams.get('searchurl');
  if (searchUrlParam) {
    urlState.searchUrl = decodeURIComponent(searchUrlParam);
  }
  
  const queryIndexParam = urlParams.get('queryindex');
  if (queryIndexParam) {
    urlState.queryIndex = parseInt(queryIndexParam, 10);
  } else {
    // Set default queryIndex based on round
    urlState.queryIndex = getDefaultQueryIndex(urlState.round);
  }

  return urlState;
};

// Initial state - read from URL immediately
const initialState = getInitialStateFromURL();

// Action types
const ActionTypes = {
  SET_SESSION: 'SET_SESSION',
  SET_SESSION_LOADING: 'SET_SESSION_LOADING',
  SET_QUERY_MODE: 'SET_QUERY_MODE',
  SET_ROUND: 'SET_ROUND',
  SET_VIEW_MODE: 'SET_VIEW_MODE',
  SET_STAGE: 'SET_STAGE',
  SET_SECTION: 'SET_SECTION',
  SET_QUERY_INDEX: 'SET_QUERY_INDEX',
  SET_K: 'SET_K',
  SET_SEARCH_URL: 'SET_SEARCH_URL',
  UPDATE_FROM_URL: 'UPDATE_FROM_URL',
  RESET_STATE: 'RESET_STATE',
  AUTO_DETECT_QUERY_MODE: 'AUTO_DETECT_QUERY_MODE',
};

// Reducer
const appReducer = (state, action) => {
  switch (action.type) {
    case ActionTypes.SET_SESSION:
      return { ...state, session: action.payload, sessionLoading: false };
    case ActionTypes.SET_SESSION_LOADING:
      return { ...state, sessionLoading: action.payload };
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
    case ActionTypes.SET_K:
      return { ...state, k: action.payload };
    case ActionTypes.SET_SEARCH_URL:
      return { ...state, searchUrl: action.payload };
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
    if (newState.k !== undefined) {
      urlParams.set('k', newState.k.toString());
    }
    if (newState.searchUrl !== undefined && newState.searchUrl !== '') {
      urlParams.set('searchurl', encodeURIComponent(newState.searchUrl));
    } else {
      urlParams.delete('searchurl');
    }

    const newUrl = `${window.location.pathname}?${urlParams.toString()}`;
    window.history.replaceState(null, '', newUrl);
  };

  // Load initial state from URL - REMOVED since we read URL in initialState
  // This prevents race condition between default state and URL params
  
  // Session validation and initialization
  useEffect(() => {
    const initializeSession = async () => {
      // Check if there's a session in current state (from URL)
      if (state.session) {
        dispatch({ type: ActionTypes.SET_SESSION_LOADING, payload: true });
        
        try {
          const response = await QueryService.validateSession(state.session);
          if (response.success && response.data) {
            dispatch({ type: ActionTypes.SET_SESSION_LOADING, payload: false });
            return;
          }
        } catch (error) {
          console.error('Session validation error:', error);
        }
      }
      
      // Create new session if no valid session found
      dispatch({ type: ActionTypes.SET_SESSION_LOADING, payload: true });
      
      try {
        const response = await QueryService.createSession();
        if (response.success && response.data) {
          const newSessionId = response.data.data.id;
          dispatch({ type: ActionTypes.SET_SESSION, payload: newSessionId });
        } else {
          console.error('Failed to create session');
        }
      } catch (error) {
        console.error('Error creating session:', error);
      }
      
      dispatch({ type: ActionTypes.SET_SESSION_LOADING, payload: false });
      urlSessionParam = null; // Clear after use
    };
    
    initializeSession();
  }, []); // Empty dependency array - only run once on mount
  
  // Remove auto-detect from here - will be handled in HomePage
  // useEffect(() => {
  //   const detectQueryMode = () => {
  //     // Auto-detect logic moved to HomePage
  //   };
  //   detectQueryMode();
  // }, [state.queryIndex, state.round]);

  // Update URL when state changes - with proper dependencies
  useEffect(() => {
    const urlStateToUpdate = {
      queryMode: state.queryMode,
      round: state.round,
      viewMode: state.viewMode,
      stage: state.stage,
      section: state.section,
      queryIndex: state.queryIndex,
      k: state.k,
      searchUrl: state.searchUrl,
    };
    
    // Only include session if it's not null - let Sidebar manage session in URL
    if (state.session !== null) {
      urlStateToUpdate.session = state.session;
    }
    
    updateUrlState(urlStateToUpdate);
  }, [state.session, state.queryMode, state.round, state.viewMode, state.stage, state.section, state.queryIndex, state.k, state.searchUrl]);

  // Actions
  const actions = {
    setSession: (session) => dispatch({ type: ActionTypes.SET_SESSION, payload: session }),
    setQueryMode: (mode) => dispatch({ type: ActionTypes.SET_QUERY_MODE, payload: mode }),
    setRound: (round) => dispatch({ type: ActionTypes.SET_ROUND, payload: round }),
    setViewMode: (mode) => dispatch({ type: ActionTypes.SET_VIEW_MODE, payload: mode }),
    setStage: (stage) => dispatch({ type: ActionTypes.SET_STAGE, payload: stage }),
    setSection: (section) => dispatch({ type: ActionTypes.SET_SECTION, payload: section }),
    setQueryIndex: (index) => dispatch({ type: ActionTypes.SET_QUERY_INDEX, payload: index }),
    setK: (k) => dispatch({ type: ActionTypes.SET_K, payload: k }),
    setSearchUrl: (url) => dispatch({ type: ActionTypes.SET_SEARCH_URL, payload: url }),
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
