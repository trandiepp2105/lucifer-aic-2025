import { apiConfig } from './apiConfig';
import { getErrorMessage, handleApiError } from './apiHelpers';

// SessionService for managing query sessions
class SessionService {
  static get baseURL() {
    return `${apiConfig.baseURL}/sessions`;
  }

  /**
   * Get all sessions from server
   * @returns {Promise<Array>} List of sessions
   */
  static async getSessions() {
    try {
      const response = await fetch(`${this.baseURL}/`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });
      
      if (response.ok) {
        const result = await response.json();
        return result.data || []; // Extract data array from response
      } else {
        throw new Error(`Failed to fetch sessions: ${response.status}`);
      }
    } catch (error) {
      throw error;
    }
  }

  /**
   * Create a new session
   * @param {string} name - Session name
   * @param {string} description - Session description
   * @returns {Promise<Object>} Created session
   */
  static async createSession(name = '', description = '') {
    try {
      const requestBody = {};
      if (name) requestBody.name = name;
      if (description) requestBody.description = description;
      
      const response = await fetch(`${this.baseURL}/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody),
      });
      
      if (response.ok) {
        const result = await response.json();
        return result.data; // Extract data from response
      } else {
        throw new Error(`Failed to create session: ${response.status}`);
      }
    } catch (error) {
      throw error;
    }
  }

  /**
   * Delete a session
   * @param {number} sessionId - Session ID to delete
   * @returns {Promise<boolean>} Success status
   */
  static async deleteSession(sessionId) {
    try {
      const response = await fetch(`${this.baseURL}/${sessionId}/`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
        },
      });
      
      return response.ok;
    } catch (error) {
      throw error;
    }
  }

  /**
   * Update session name
   * @param {number} sessionId - Session ID
   * @param {string} name - New session name
   * @param {string} description - New session description
   * @returns {Promise<Object>} Updated session
   */
  static async updateSession(sessionId, name, description = '') {
    try {
      const response = await fetch(`${this.baseURL}/${sessionId}/`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name,
          description,
        }),
      });
      
      if (response.ok) {
        const result = await response.json();
        return result.data;
      } else {
        throw new Error(`Failed to update session: ${response.status}`);
      }
    } catch (error) {
      throw error;
    }
  }
}

export default SessionService;
