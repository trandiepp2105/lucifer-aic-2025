import { apiConfig } from './apiConfig';
import { handleApiError } from './apiHelpers';

class TeamAnswerServiceClass {
  constructor() {
    this.baseURL = `${apiConfig.baseURL}/team-answers/`;
  }

  /**
   * Create a new team answer (for Send button)
   * @param {Object} teamAnswerData - Team answer data
   * @param {string} teamAnswerData.video_name - Name of the video
   * @param {number} teamAnswerData.frame_index - Frame index in the video
   * @param {string} teamAnswerData.url - URL of the frame image
   * @param {string} teamAnswerData.qa - Question and answer text (optional)
   * @param {number} teamAnswerData.query_index - Query index
   * @param {string} teamAnswerData.round - Round type: 'prelims' or 'final'
   * @returns {Promise<Object>} Response with team answer data
   */
  async createTeamAnswer(teamAnswerData) {
    try {
      const response = await fetch(this.baseURL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(teamAnswerData)
      });

      const data = await response.json();

      if (!response.ok) {
        return {
          success: false,
          error: data.message || `HTTP error! status: ${response.status}`,
          errors: data.errors || {},
          status: response.status
        };
      }

      return {
        success: true,
        data: data.data
      };
    } catch (error) {
      return handleApiError(error);
    }
  }

  /**
   * Get all team answers with optional filtering
   * @param {Object} params - Query parameters
   * @param {string} params.round - Filter by round
   * @param {number} params.query_index - Filter by query index
   * @param {string} params.video_name - Filter by video name
   * @param {number} params.page - Page number
   * @param {number} params.page_size - Items per page
   * @returns {Promise<Object>} Response with team answers data
   */
  async getTeamAnswers(params = {}) {
    try {
      const queryParams = new URLSearchParams();
      
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== '') {
          queryParams.append(key, value);
        }
      });

      const url = queryParams.toString() ? 
        `${this.baseURL}?${queryParams.toString()}` : 
        this.baseURL;

      const response = await fetch(url, {
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
   * Get a specific team answer
   * @param {number} teamAnswerId - Team answer ID
   * @returns {Promise<Object>} Response with team answer data
   */
  async getTeamAnswer(teamAnswerId) {
    try {
      const response = await fetch(`${this.baseURL}/${teamAnswerId}/`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      const data = await response.json();

      if (!response.ok) {
        return {
          success: false,
          error: data.message || `HTTP error! status: ${response.status}`,
          status: response.status
        };
      }

      return {
        success: true,
        data: data.data
      };
    } catch (error) {
      return handleApiError(error);
    }
  }

  /**
   * Update a team answer
   * @param {number} teamAnswerId - Team answer ID
   * @param {Object} teamAnswerData - Updated team answer data
   * @returns {Promise<Object>} Response with updated team answer data
   */
  async updateTeamAnswer(teamAnswerId, teamAnswerData) {
    try {
      const response = await fetch(`${this.baseURL}/${teamAnswerId}/`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(teamAnswerData)
      });

      const data = await response.json();

      if (!response.ok) {
        return {
          success: false,
          error: data.message || `HTTP error! status: ${response.status}`,
          errors: data.errors || {},
          status: response.status
        };
      }

      return {
        success: true,
        data: data.data
      };
    } catch (error) {
      return handleApiError(error);
    }
  }

  /**
   * Delete a team answer
   * @param {number} teamAnswerId - Team answer ID
   * @returns {Promise<Object>} Response data
   */
  async deleteTeamAnswer(teamAnswerId) {
    try {
      const response = await fetch(`${this.baseURL}/${teamAnswerId}/`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        const data = await response.json();
        return {
          success: false,
          error: data.message || `HTTP error! status: ${response.status}`,
          status: response.status
        };
      }

      const data = await response.json();
      return {
        success: true,
        message: data.message
      };
    } catch (error) {
      return handleApiError(error);
    }
  }

  /**
   * Check if a team answer exists for the given combination
   * @param {string} video_name - Video name
   * @param {number} frame_index - Frame index
   * @param {number} query_index - Query index
   * @returns {Promise<Object>} Response indicating if team answer exists
   */
  async checkTeamAnswerExists(video_name, frame_index, query_index) {
    try {
      const response = await this.getTeamAnswers({
        video_name,
        query_index,
        page_size: 1
      });

      if (response.success) {
        // Check if any of the returned team answers has the same frame_index
        const exists = response.data.data.some(teamAnswer => 
          teamAnswer.video_name === video_name && 
          teamAnswer.frame_index === frame_index &&
          teamAnswer.query_index === query_index
        );
        
        return {
          success: true,
          exists
        };
      }
      
      return response;
    } catch (error) {
      return handleApiError(error);
    }
  }

  /**
   * Delete all team answers for a specific query index and round
   * @param {Object} params - Query parameters
   * @param {number} params.query_index - Query index
   * @param {string} params.round - Round type: 'prelims' or 'final'
   * @returns {Promise<Object>} Response with deletion result
   */
  async deleteAllTeamAnswers(params = {}) {
    try {
      const queryParams = new URLSearchParams();
      
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== '') {
          queryParams.append(key, value);
        }
      });

      const url = queryParams.toString() ? 
        `${this.baseURL}delete-all/?${queryParams.toString()}` : 
        `${this.baseURL}delete-all/`;

      const response = await fetch(url, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      const data = await response.json();

      if (!response.ok) {
        return {
          success: false,
          error: data.message || `HTTP error! status: ${response.status}`,
          status: response.status
        };
      }

      return {
        success: true,
        data: data.data
      };
    } catch (error) {
      return handleApiError(error);
    }
  }
}

// Export singleton instance
export const TeamAnswerService = new TeamAnswerServiceClass();
export default TeamAnswerService;
