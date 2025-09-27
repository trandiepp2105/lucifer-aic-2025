/**
 * Utility functions for handling video metadata
 */

import axios from 'axios';

// Cache for all metadata (loaded once)
let allMetadataCache = null;
let isLoading = false;
let loadPromise = null;

/**
 * Load all metadata from public/all_metadata.json
 * @returns {Promise<Object>} - Promise resolving to metadata object with video_name as keys
 */
const loadAllMetadata = async () => {
  if (allMetadataCache) {
    return allMetadataCache;
  }
  
  if (isLoading && loadPromise) {
    return loadPromise;
  }
  
  isLoading = true;
  loadPromise = (async () => {
    try {
      console.log('Loading all metadata from /all_metadata.json');
      const response = await axios.get('/all_metadata.json', {
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json'
        },
        withCredentials: false,
        timeout: 10000, // 10 second timeout for initial load
        validateStatus: (status) => status >= 200 && status < 300
      });
      
      allMetadataCache = response.data;
      console.log(`Loaded metadata for ${Object.keys(allMetadataCache).length} videos`);
      return allMetadataCache;
    } catch (error) {
      console.error('Failed to load all_metadata.json:', error);
      // Return empty object as fallback
      allMetadataCache = {};
      return allMetadataCache;
    } finally {
      isLoading = false;
      loadPromise = null;
    }
  })();
  
  return loadPromise;
};

/**
 * Fetch video metadata (fps, duration) for a frame
 * @param {Object} frame - Frame object with video_name and url
 * @returns {Promise<Object>} - Promise resolving to metadata object with fps and duration
 */
/**
 * Fetch video metadata from all_metadata.json
 * @param {Object} frame - Frame object with video_name
 * @returns {Promise<Object>} - Promise resolving to metadata object with fps and duration
 */
export const fetchVideoMetadata = async (frame) => {
  if (!frame || !frame.video_name) {
    return { fps: 25, duration: 21.06 }; // Default fallback
  }

  try {
    // Load all metadata (cached after first load)
    const allMetadata = await loadAllMetadata();
    
    // Lookup metadata for this specific video
    const videoMetadata = allMetadata[frame.video_name];
    
    if (!videoMetadata) {
      console.warn(`No metadata found for video: ${frame.video_name}`);
      return { fps: 25, duration: 21.06 }; // Default fallback
    }
    
    // Validate metadata structure
    if (!videoMetadata.fps || !videoMetadata.duration) {
      console.warn(`Invalid metadata structure for video: ${frame.video_name}`, videoMetadata);
      return { fps: 25, duration: 21.06 }; // Default fallback
    }
    
    return {
      fps: videoMetadata.fps,
      duration: videoMetadata.duration
    };
  } catch (error) {
    console.error(`Failed to fetch metadata for ${frame.video_name}:`, error);
    return { fps: 25, duration: 21.06 }; // Default fallback
  }
};

/**
 * Get FPS for a specific frame
 * @param {Object} frame - Frame object with video_name and url
 * @returns {Promise<number>} - Promise resolving to FPS value
 */
export const getFrameFPS = async (frame) => {
  const metadata = await fetchVideoMetadata(frame);
  return metadata.fps || 25;
};
