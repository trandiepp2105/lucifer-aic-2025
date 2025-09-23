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
   * @returns {Promise} API response
   */
  async submitKISAnswer(videoName, frameIndex) {
    try {
      // Fetch fps from video metadata
      let fps = 25; // default fps
      try {
        // Create minimal frame object for metadata fetching
        const frameObject = { 
          video_name: videoName,
          url: `${process.env.REACT_APP_CFRAMES_PATH}/${videoName}/metadata.json`
        };
        const metadata = await fetchVideoMetadata(frameObject);
        fps = metadata.fps || 25;
      } catch (error) {
        console.warn('Failed to fetch video metadata, using default fps:', error);
      }

      const response = await fetch(`${this.baseURL}/kis/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          video_name: videoName,
          frame_index: frameIndex,
          fps: fps
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
      // Fetch fps from video metadata
      let fps = 25; // default fps
      try {
        // Create minimal frame object for metadata fetching
        const frameObject = { 
          video_name: videoName,
          url: `${process.env.REACT_APP_CFRAMES_PATH}/${videoName}/metadata.json`
        };
        const metadata = await fetchVideoMetadata(frameObject);
        fps = metadata.fps || 25;
      } catch (error) {
        console.warn('Failed to fetch video metadata, using default fps:', error);
      }

      const response = await fetch(`${this.baseURL}/qa/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          video_name: videoName,
          frame_index: frameIndex,
          qa: qa,
          fps: fps
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
      // Get fps from first item's video metadata only (optimization)
      let fps = 25; // default fps
      if (frameItems.length > 0) {
        try {
          // Create minimal frame object for metadata fetching using first item
          const frameObject = { 
            video_name: frameItems[0].video_name,
            url: `${process.env.REACT_APP_CFRAMES_PATH}/${frameItems[0].video_name}/metadata.json`
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
      
      const response = await fetch(`${this.baseURL}/trake/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(frameItemsWithFps)
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
