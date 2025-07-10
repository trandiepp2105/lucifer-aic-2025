/**
 * Extract meaningful error message from API response
 * @param {Object} response - API response object
 * @returns {string} Error message
 */
export const getErrorMessage = (response) => {
  if (response?.error) {
    return response.error;
  }
  
  if (response?.detail) {
    return response.detail;
  }
  
  if (response?.message) {
    return response.message;
  }
  
  return 'An unknown error occurred';
};

/**
 * Handle API errors consistently
 * @param {Error} error - JavaScript Error object
 * @returns {Object} Standardized error response
 */
export const handleApiError = (error) => {
  if (error.name === 'TypeError' && error.message.includes('fetch')) {
    return {
      success: false,
      error: 'Network error: Unable to connect to server',
      type: 'network'
    };
  }
  
  if (error.name === 'AbortError') {
    return {
      success: false,
      error: 'Request timeout',
      type: 'timeout'
    };
  }
  
  return {
    success: false,
    error: error.message || 'An unexpected error occurred',
    type: 'unknown'
  };
};
