import { apiConfig } from './apiConfig';
import { getErrorMessage, handleApiError } from './apiHelpers';

class QueryServiceClass {
  constructor() {
    this.baseURL = `${apiConfig.baseURL}/queries`;
    this.sessionURL = `${apiConfig.baseURL}/sessions`;
  }

  // Session APIs
  /**
   * Create a new query session
   * @returns {Promise<Object>} Response with session data
   */
  async createSession() {
    try {
      const response = await fetch(this.sessionURL + '/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({})
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      return { success: true, data };
    } catch (error) {
      return handleApiError(error);
    }
  }

  /**
   * Get all sessions
   * @returns {Promise<Object>} Response with sessions data
   */
  async getSessions() {
    try {
      const response = await fetch(this.sessionURL + '/', {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      return { success: true, data };
    } catch (error) {
      return handleApiError(error);
    }
  }

  /**
   * Delete a session and all its queries
   * @param {number} sessionId - Session ID to delete
   * @returns {Promise<Object>} Response data
   */
  async deleteSession(sessionId) {
    try {
      const response = await fetch(`${this.sessionURL}/${sessionId}/`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      return { success: true, message: 'Session deleted successfully' };
    } catch (error) {
      return handleApiError(error);
    }
  }

  /**
   * Get queries for a specific session
   * @param {number} sessionId - Session ID
   * @param {Object} params - Query parameters
   * @param {number} params.stage - Filter by stage (1, 2, or 3)
   * @returns {Promise<Object>} Response with queries data
   */
  async getQueriesBySession(sessionId, params = {}) {
    try {
      const queryParams = new URLSearchParams({
        session: sessionId
      });

      // Only add other parameters if explicitly provided
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== '' && key !== 'session') {
          queryParams.append(key, value);
        }
      });

      const response = await fetch(`${this.baseURL}/?${queryParams}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      return { success: true, data };
    } catch (error) {
      return handleApiError(error);
    }
  }

  /**
   * Get all queries with pagination
   * @param {Object} params - Query parameters
   * @param {number} params.page - Page number
   * @param {number} params.page_size - Items per page
   * @param {number} params.stage - Filter by stage (1, 2, or 3)
   * @returns {Promise<Object>} Response with queries data
   */
  async getQueries(params = {}) {
    try {
      const queryParams = new URLSearchParams();
      
      // Only add pagination if explicitly requested
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== '') {
          queryParams.append(key, value);
        }
      });

      const url = queryParams.toString() ? 
        `${this.baseURL}/?${queryParams.toString()}` : 
        `${this.baseURL}/`;

      const response = await fetch(url, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      const data = await response.json();

      if (!response.ok) {
        return {
          success: false,
          error: data.detail || data.error || `HTTP ${response.status}`,
          status: response.status
        };
      }

      return {
        success: true,
        data: data.results || data,
        pagination: {
          count: data.count,
          next: data.next,
          previous: data.previous,
          page: params.page || 1,
          page_size: params.page_size || 20
        }
      };
    } catch (error) {
      return handleApiError(error);
    }
  }

  /**
   * Get a specific query by ID
   * @param {string|number} queryId - Query ID
   * @returns {Promise<Object>} Response with query data
   */
  async getQuery(queryId) {
    try {
      const response = await fetch(`${this.baseURL}/${queryId}/`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      const data = await response.json();

      if (!response.ok) {
        return {
          success: false,
          error: data.detail || data.error || `HTTP ${response.status}`,
          status: response.status
        };
      }

      return {
        success: true,
        data: data
      };
    } catch (error) {
      return handleApiError(error);
    }
  }

  /**
   * Create a new query
   * @param {Object} queryData - Query data
   * @param {string} queryData.text - Query text
   * @param {string} queryData.ocr - OCR text
   * @param {string} queryData.speech - Speech text
   * @param {File} queryData.image - Image file
   * @param {number} queryData.session - Session ID
   * @param {number} queryData.stage - Stage index (1, 2, or 3)
   * @returns {Promise<Object>} Response with created query data
   */
  async createQuery(queryData) {
    try {
      const formData = new FormData();
      
      // Add session ID if provided
      if (queryData.session) {
        formData.append('session', queryData.session);
      }
      
      // Add stage if provided, default to 1
      const stage = queryData.stage || 1;
      formData.append('stage', stage);
      
      // Add text fields if they exist
      if (queryData.text) {
        formData.append('text', queryData.text);
      }
      if (queryData.ocr) {
        formData.append('ocr', queryData.ocr);
      }
      if (queryData.speech) {
        formData.append('speech', queryData.speech);
      }
      
      // Add image file if it exists
      if (queryData.image) {
        formData.append('image', queryData.image);
      }

      const response = await fetch(`${this.baseURL}/`, {
        method: 'POST',
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        return {
          success: false,
          error: data.detail || data.error || `HTTP ${response.status}`,
          status: response.status
        };
      }

      return {
        success: true,
        data: data
      };
    } catch (error) {
      return handleApiError(error);
    }
  }

  /**
   * Update an existing query
   * @param {string|number} queryId - Query ID
   * @param {Object} queryData - Updated query data
   * @param {number} queryData.stage - Stage index (1, 2, or 3)
   * @returns {Promise<Object>} Response with updated query data
   */
  async updateQuery(queryId, queryData) {
    try {
      const formData = new FormData();
      
      // Add stage if provided
      if (queryData.stage !== undefined) {
        formData.append('stage', queryData.stage);
      }
      
      // Add text fields if they exist
      if (queryData.text !== undefined) {
        formData.append('text', queryData.text);
      }
      if (queryData.ocr !== undefined) {
        formData.append('ocr', queryData.ocr);
      }
      if (queryData.speech !== undefined) {
        formData.append('speech', queryData.speech);
      }
      
      // Add image file if it exists, or explicitly set to null if removed
      if (queryData.image !== undefined) {
        if (queryData.image === null) {
          // Explicitly set image to null to remove it
          formData.append('image', '');
        } else {
          formData.append('image', queryData.image);
        }
      }

      const response = await fetch(`${this.baseURL}/${queryId}/`, {
        method: 'PUT',
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        return {
          success: false,
          error: data.detail || data.error || `HTTP ${response.status}`,
          status: response.status
        };
      }

      return {
        success: true,
        data: data
      };
    } catch (error) {
      return handleApiError(error);
    }
  }

  /**
   * Partially update an existing query
   * @param {string|number} queryId - Query ID
   * @param {Object} queryData - Partial query data
   * @returns {Promise<Object>} Response with updated query data
   */
  async patchQuery(queryId, queryData) {
    try {
      const formData = new FormData();
      
      // Add only the fields that are provided
      Object.keys(queryData).forEach(key => {
        if (queryData[key] !== undefined && queryData[key] !== null) {
          if (key === 'image' && queryData[key] instanceof File) {
            formData.append(key, queryData[key]);
          } else {
            formData.append(key, queryData[key]);
          }
        }
      });

      const response = await fetch(`${this.baseURL}/${queryId}/`, {
        method: 'PATCH',
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        return {
          success: false,
          error: data.detail || data.error || `HTTP ${response.status}`,
          status: response.status
        };
      }

      return {
        success: true,
        data: data
      };
    } catch (error) {
      return handleApiError(error);
    }
  }

  /**
   * Delete a specific query
   * @param {string|number} queryId - Query ID
   * @returns {Promise<Object>} Response confirmation
   */
  async deleteQuery(queryId) {
    try {
      const response = await fetch(`${this.baseURL}/${queryId}/`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        const data = await response.json();
        return {
          success: false,
          error: data.detail || data.error || `HTTP ${response.status}`,
          status: response.status
        };
      }

      return {
        success: true,
        message: 'Query deleted successfully'
      };
    } catch (error) {
      return handleApiError(error);
    }
  }

  /**
   * Delete all queries (bulk delete)
   * @returns {Promise<Object>} Response with deletion count
   */
  async deleteAllQueries() {
    try {
      // First get all queries to get their IDs
      const queriesResponse = await this.getQueries(); // Get all queries (no pagination limit)
      if (!queriesResponse.success) {
        return {
          success: false,
          error: 'Failed to fetch queries for deletion',
          status: 500
        };
      }

      const queryIds = queriesResponse.data.data.map(query => query.id);
      if (queryIds.length === 0) {
        return {
          success: true,
          data: { message: 'No queries to delete', deleted_count: 0 }
        };
      }

      const response = await fetch(`${this.baseURL}/bulk-delete/`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ ids: queryIds }),
      });

      const data = await response.json();

      if (!response.ok) {
        return {
          success: false,
          error: data.detail || data.error || `HTTP ${response.status}`,
          status: response.status
        };
      }

      return {
        success: true,
        deleted_count: data.deleted_count || 0,
        message: data.message || 'All queries deleted successfully'
      };
    } catch (error) {
      return handleApiError(error);
    }
  }

  /**
   * Validate if a session exists
   * @param {number} sessionId - Session ID to validate
   * @returns {Promise<Object>} Response data
   */
  async validateSession(sessionId) {
    try {
      const response = await fetch(`${this.sessionURL}/${sessionId}/`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const data = await response.json();
        return { success: true, data };
      } else if (response.status === 404) {
        return { success: false, error: 'Session not found', status: 404 };
      } else {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
    } catch (error) {
      return handleApiError(error);
    }
  }

}

// Export singleton instance

export const QueryService = new QueryServiceClass();
