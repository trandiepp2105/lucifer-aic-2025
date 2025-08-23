import { apiConfig } from './apiConfig';

class SubmissionService {
  constructor() {
    this.baseURL = `${apiConfig.baseURL}/submissions`;
  }

  /**
   * Submit KIS answer
   * @param {string} videoName - The video name
   * @param {number} frameIndex - The frame index
   * @returns {Promise} API response
   */
  async submitKISAnswer(videoName, frameIndex) {
    try {
      const response = await fetch(`${this.baseURL}/kis/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          video_name: videoName,
          frame_index: frameIndex
        })
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.message || `HTTP error! status: ${response.status}`);
      }
      
      return await response.json();
    } catch (error) {
      console.error('Error submitting KIS answer:', error);
      throw error;
    }
  }

  /**
   * Submit QA answer
   * @param {string} videoName - The video name
   * @param {number} frameIndex - The frame index
   * @param {string} qa - The QA text
   * @returns {Promise} API response
   */
  async submitQAAnswer(videoName, frameIndex, qa) {
    try {
      const response = await fetch(`${this.baseURL}/qa/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          video_name: videoName,
          frame_index: frameIndex,
          qa: qa
        })
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.message || `HTTP error! status: ${response.status}`);
      }
      
      return await response.json();
    } catch (error) {
      console.error('Error submitting QA answer:', error);
      throw error;
    }
  }

  /**
   * Submit TRAKE answer
   * @param {Array} frameItems - Array of frame items with {video_name, frame_index, group}
   * @returns {Promise} API response
   */
  async submitTRAKEAnswer(frameItems) {
    try {
      const response = await fetch(`${this.baseURL}/trake/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(frameItems)
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.message || `HTTP error! status: ${response.status}`);
      }
      
      return await response.json();
    } catch (error) {
      console.error('Error submitting TRAKE answer:', error);
      throw error;
    }
  }
}

export default new SubmissionService();
