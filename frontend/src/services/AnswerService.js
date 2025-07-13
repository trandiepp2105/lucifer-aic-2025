import { apiConfig } from './apiConfig';
import { getErrorMessage, handleApiError } from './apiHelpers';

class AnswerServiceClass {
  constructor() {
    this.baseURL = `${apiConfig.baseURL}/answers/`;
  }

  /**
   * Get all answers with optional filtering
   * @param {Object} params - Query parameters
   * @param {string} [params.round] - Filter by round
   * @param {number} [params.query_index] - Filter by query index
   * @param {string} [params.video_name] - Filter by video name
   * @param {number} [params.page=1] - Page number
   * @param {number} [params.page_size=10] - Items per page
   * @returns {Promise<Object>} Response with answers data
   */
  async getAnswers(params = {}) {
    try {
      const queryParams = new URLSearchParams();
      
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          queryParams.append(key, value);
        }
      });

      const response = await fetch(`${this.baseURL}/?${queryParams}`, {
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
        data: data.data || data,
        total: data.total,
        page: data.page,
        pages: data.pages
      };
    } catch (error) {
      return handleApiError(error);
    }
  }

  /**
   * Create a new answer
   * @param {Object} answerData - Answer data
   * @param {string} answerData.video_name - Name of the video
   * @param {number} answerData.frame_index - Frame index in the video
   * @param {string} answerData.url - URL of the frame image
   * @param {string} [answerData.qa] - Question and answer text (optional)
   * @param {number} [answerData.query_index=0] - Query index
   * @param {string} [answerData.round='prelims'] - Round type
   * @returns {Promise<Object>} Response with created answer data
   */
  async createAnswer(answerData) {
    try {
      const response = await fetch(`${this.baseURL}/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(answerData),
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
        data: data.data || data
      };
    } catch (error) {
      return handleApiError(error);
    }
  }

  /**
   * Get a specific answer by ID
   * @param {number} answerId - Answer ID
   * @returns {Promise<Object>} Response with answer data
   */
  async getAnswer(answerId) {
    try {
      const response = await fetch(`${this.baseURL}/${answerId}/`, {
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
        data: data.data || data
      };
    } catch (error) {
      return handleApiError(error);
    }
  }

  /**
   * Update an answer
   * @param {number} answerId - Answer ID
   * @param {Object} answerData - Updated answer data
   * @returns {Promise<Object>} Response with updated answer data
   */
  async updateAnswer(answerId, answerData) {
    try {
      const response = await fetch(`${this.baseURL}/${answerId}/`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(answerData)
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
        data: data.data || data
      };
    } catch (error) {
      return handleApiError(error);
    }
  }

  /**
   * Delete an answer
   * @param {number} answerId - Answer ID
   * @returns {Promise<Object>} Response data
   */
  async deleteAnswer(answerId) {
    try {
      const response = await fetch(`${this.baseURL}/${answerId}/`, {
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

      return { success: true, message: 'Answer deleted successfully' };
    } catch (error) {
      return handleApiError(error);
    }
  }

  /**
   * Delete all answers with optional filtering
   * @param {Object} params - Filter parameters
   * @param {string} [params.round] - Filter by round
   * @param {number} [params.query_index] - Filter by query index
   * @returns {Promise<Object>} Response with deletion status
   */
  async deleteAllAnswers(params = {}) {
    try {
      const queryParams = new URLSearchParams();
      
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          queryParams.append(key, value);
        }
      });

      const response = await fetch(`${this.baseURL}bulk-delete/?${queryParams}`, {
        method: 'DELETE',
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
        message: data.message || 'Answers deleted successfully',
        deleted_count: data.deleted_count || 0
      };
    } catch (error) {
      return handleApiError(error);
    }
  }
}

export const AnswerService = new AnswerServiceClass();
