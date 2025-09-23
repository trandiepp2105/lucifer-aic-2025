import { apiConfig } from './apiConfig';

export class DresLoginService {
  /**
   * Login to DRES server
   * @param {Object} credentials - Login credentials
   * @param {string} credentials.username - Username
   * @param {string} credentials.password - Password
   * @returns {Promise<Object>} Response with user data and sessionId
   */
  static async login(credentials) {
    try {
      const response = await fetch(`${apiConfig.baseURL}/dres-login/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(credentials),
        timeout: apiConfig.timeout,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      
      return {
        success: true,
        data: data,
      };
    } catch (error) {
      console.error('DRES login error:', error);
      return {
        success: false,
        error: error.message || 'Login failed',
      };
    }
  }
}

export class DresSessionService {
  /**
   * Get the latest DRES session from server
   * @returns {Promise<Object>} Response with latest session data
   */
  static async getLatestSession() {
    try {
      const response = await fetch(`${apiConfig.baseURL}/dres-session/`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
        timeout: apiConfig.timeout,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      
      return {
        success: true,
        data: data,
      };
    } catch (error) {
      console.error('DRES session fetch error:', error);
      return {
        success: false,
        error: error.message || 'Failed to fetch DRES session',
      };
    }
  }

  static async updateEvaluationId(evaluationId) {
    try {
      const response = await fetch(`${apiConfig.baseURL}/dres-session/`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          evaluation_id: evaluationId
        })
      });

      const data = await response.json();
      
      if (response.ok) {
        return {
          success: true,
          data: data
        };
      } else {
        console.error('Failed to update evaluation ID:', data);
        return {
          success: false,
          error: data.error || 'Failed to update evaluation ID'
        };
      }
    } catch (error) {
      console.error('Error updating evaluation ID:', error);
      return {
        success: false,
        error: 'Network error'
      };
    }
  }
}
