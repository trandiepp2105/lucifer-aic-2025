// API Configuration
const getBaseURL = () => {
  // Try to get from environment variable first
  if (process.env.REACT_APP_API_ENDPOINT) {
    return process.env.REACT_APP_API_ENDPOINT;
  }
  
  // In production, use relative path through nginx
  if (process.env.NODE_ENV === 'production') {
    return '/api';
  }
  
  // Development fallback - can point to nginx or direct backend
  return process.env.REACT_APP_DEV_API_URL || 'http://localhost/api';
};

export const apiConfig = {
  baseURL: getBaseURL(),
  timeout: 30000, // 30 seconds
  retryAttempts: 3,
  retryDelay: 1000, // 1 second
};
