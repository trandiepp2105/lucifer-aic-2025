// Utility functions for managing URL parameters

/**
 * Get all URL parameters as an object
 */
export const getUrlParams = () => {
  const urlParams = new URLSearchParams(window.location.search);
  return Object.fromEntries(urlParams.entries());
};

/**
 * Get a specific URL parameter
 */
export const getUrlParam = (key, defaultValue = null) => {
  const urlParams = new URLSearchParams(window.location.search);
  return urlParams.get(key) || defaultValue;
};

/**
 * Update URL parameters
 */
export const updateUrlParams = (params) => {
  const url = new URL(window.location);
  
  Object.entries(params).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== '') {
      url.searchParams.set(key, value);
    } else {
      url.searchParams.delete(key);
    }
  });
  
  window.history.replaceState({}, '', url);
};

/**
 * Get session ID from URL
 */
export const getSessionIdFromUrl = () => {
  return getUrlParam('session');
};

/**
 * Get stage from URL
 */
export const getStageFromUrl = () => {
  const stage = getUrlParam('stage');
  return stage ? parseInt(stage) : 1; // Default to stage 1
};

/**
 * Get view mode from URL
 */
export const getViewModeFromUrl = () => {
  return getUrlParam('viewmode', 'gallery'); // Default to gallery
};

/**
 * Get round from URL
 */
export const getRoundFromUrl = () => {
  return getUrlParam('round', 'prelims'); // Default to prelims
};

/**
 * Get query mode from URL
 */
export const getQueryModeFromUrl = () => {
  return getUrlParam('querymode', 'kis'); // Default to kis
};

/**
 * Get active section from URL
 */
export const getActiveSectionFromUrl = () => {
  return getUrlParam('section', 'chat'); // Default to chat
};

/**
 * Initialize all app state from URL parameters
 */
export const initializeStateFromUrl = () => {
  return {
    session: getSessionIdFromUrl(),
    stage: getStageFromUrl(),
    viewMode: getViewModeFromUrl(),
    round: getRoundFromUrl(),
    queryMode: getQueryModeFromUrl(),
    section: getActiveSectionFromUrl()
  };
};

/**
 * Update all app state in URL parameters
 */
export const updateAllUrlParams = (state) => {
  const currentParams = getUrlParams();
  const params = {};
  let hasChanges = false;
  
  // Check each parameter and only update if changed
  if (state.session && state.session !== currentParams.session) {
    params.session = state.session;
    hasChanges = true;
  }
  
  if (state.stage && state.stage.toString() !== currentParams.stage) {
    params.stage = state.stage;
    hasChanges = true;
  }
  
  if (state.viewMode && state.viewMode !== currentParams.viewmode) {
    params.viewmode = state.viewMode;
    hasChanges = true;
  }
  
  if (state.round && state.round !== currentParams.round) {
    params.round = state.round;
    hasChanges = true;
  }
  
  if (state.queryMode && state.queryMode !== currentParams.querymode) {
    params.querymode = state.queryMode;
    hasChanges = true;
  }
  
  if (state.section && state.section !== currentParams.section) {
    params.section = state.section;
    hasChanges = true;
  }
  
  // Only update URL if there are changes
  if (hasChanges) {
    updateUrlParams(params);
  }
};
