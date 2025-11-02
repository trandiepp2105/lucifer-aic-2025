import { apiConfig } from './apiConfig';
import { fetchVideoMetadata } from '../utils/videoMetadata';

class SubmissionService {
  constructor() {
    this.baseURL = `${apiConfig.baseURL}/submit`;
  }

  /**
   * Submit KIS answer
   * @param {string} videoName - The video name
   * @param {number} frameIndex - The frame index
   * @param {string} dresSession - DRES session ID (optional)
   * @param {string} evaluationId - DRES evaluation ID (optional)
   * @returns {Promise} API response
   */
  async submitKISAnswer(videoName, frameIndex, dresSession = null, evaluationId = null) {
    try {
      // Fetch fps from video metadata
      let fps = 25; // default fps
      try {
        // Create minimal frame object for metadata fetching (only video_name needed now)
        const frameObject = { 
          video_name: videoName
        };
        const metadata = await fetchVideoMetadata(frameObject);
        fps = metadata.fps || 25;
      } catch (error) {
        console.warn('Failed to fetch video metadata, using default fps:', error);
      }

      const requestBody = {
        video_name: videoName,
        frame_index: frameIndex,
        fps: fps
      };
      
      // Add DRES session info if provided
      if (dresSession) {
        requestBody.dres_session = dresSession;
      }
      if (evaluationId) {
        requestBody.evaluation_id = evaluationId;
      }

      const response = await fetch(`${this.baseURL}/kis/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody)
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
   * @param {string} dresSession - DRES session ID (optional)
   * @param {string} evaluationId - DRES evaluation ID (optional)
   * @returns {Promise} API response
   */
  async submitQAAnswer(videoName, frameIndex, qa, dresSession = null, evaluationId = null) {
    try {
      // Fetch fps from video metadata
      let fps = 25; // default fps
      try {
        // Create minimal frame object for metadata fetching (only video_name needed now)
        const frameObject = { 
          video_name: videoName
        };
        const metadata = await fetchVideoMetadata(frameObject);
        fps = metadata.fps || 25;
      } catch (error) {
        console.warn('Failed to fetch video metadata, using default fps:', error);
      }

      const requestBody = {
        video_name: videoName,
        frame_index: frameIndex,
        qa: qa,
        fps: fps
      };
      
      // Add DRES session info if provided
      if (dresSession) {
        requestBody.dres_session = dresSession;
      }
      if (evaluationId) {
        requestBody.evaluation_id = evaluationId;
      }

      const response = await fetch(`${this.baseURL}/qa/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody)
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
   * @param {string} dresSession - DRES session ID (optional)
   * @param {string} evaluationId - DRES evaluation ID (optional)
   * @returns {Promise} API response
   */
  async submitTRAKEAnswer(frameItems, dresSession = null, evaluationId = null) {
    try {
      // Get fps from first item's video metadata only (optimization)
      let fps = 25; // default fps
      if (frameItems.length > 0) {
        try {
          // Create minimal frame object for metadata fetching using first item (only video_name needed now)
          const frameObject = { 
            video_name: frameItems[0].video_name
          };
          const metadata = await fetchVideoMetadata(frameObject);
          fps = metadata.fps || 25;
        } catch (error) {
          console.warn(`Failed to fetch video metadata for ${frameItems[0].video_name}, using default fps:`, error);
        }
      }
      
      // Add fps to each frame item (all items use same fps from first item)
      const frameItemsWithFps = frameItems.map(item => ({
        ...item,
        fps: fps
      }));
      
      // Create request body
      const requestBody = frameItemsWithFps;
      
      // Add DRES session info to the body if provided (as metadata)
      const requestBodyWithMeta = {
        frame_items: requestBody,
      };
      
      if (dresSession) {
        requestBodyWithMeta.dres_session = dresSession;
      }
      if (evaluationId) {
        requestBodyWithMeta.evaluation_id = evaluationId;
      }
      
      // If no DRES info, send just the frame items array for backwards compatibility
      const finalRequestBody = (dresSession || evaluationId) ? requestBodyWithMeta : requestBody;
      
      const response = await fetch(`${this.baseURL}/trake/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(finalRequestBody)
      });
      
      const data = await response.json();
      
      if (!response.ok) {
        // Create error object with response structure expected by frontend
        const error = new Error(data.message || `HTTP error! status: ${response.status}`);
        error.response = {
          data: data
        };
        throw error;
      }
      
      return data;
    } catch (error) {
      console.error('Error submitting TRAKE answer:', error);
      throw error;
    }
  }
}

export default new SubmissionService();
