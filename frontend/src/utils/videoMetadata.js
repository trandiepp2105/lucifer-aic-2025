/**
 * Utility functions for handling video metadata
 */

// Cache for storing metadata to avoid repeated requests
const metadataCache = new Map();

/**
 * Generate metadata URL from frame URL
 * @param {string} frameUrl - The frame URL
 * @returns {string} - The metadata URL
 */
export const generateMetadataUrl = (frameUrl) => {
  if (!frameUrl) return '';
  // Extract base path and add /metadata.json
  // "http://127.0.0.1/media/frames/L09_V025/9590.jpg" -> "http://127.0.0.1/media/frames/L09_V025/metadata.json"
  const basePath = frameUrl.substring(0, frameUrl.lastIndexOf('/'));
  return `${basePath}/metadata.json`;
};

/**
 * Fetch video metadata (fps, duration) for a frame
 * @param {Object} frame - Frame object with video_name and url
 * @returns {Promise<Object>} - Promise resolving to metadata object with fps and duration
 */
export const fetchVideoMetadata = async (frame) => {
  if (!frame || !frame.video_name) {
    return { fps: 25, duration: 21.06 }; // Default fallback
  }

  const cacheKey = frame.video_name;
  
  // Check cache first
  if (metadataCache.has(cacheKey)) {
    return metadataCache.get(cacheKey);
  }

  try {
    const metadataUrl = generateMetadataUrl(frame.thumbnail || frame.url);
    
    const response = await fetch(metadataUrl, { 
      method: 'GET',
      mode: 'cors',
      credentials: 'omit'
    });
    
    if (!response.ok) {
      throw new Error(`Metadata not found: ${response.status}`);
    }
    
    const metadata = await response.json();
    
    // Validate metadata structure
    if (!metadata.fps || !metadata.duration) {
      throw new Error('Invalid metadata structure');
    }
    
    // Cache the metadata
    metadataCache.set(cacheKey, metadata);
    
    return metadata;
  } catch (error) {
    console.log(`Metadata not available for ${frame.video_name}, using defaults:`, error);
    // Fallback to default values if metadata not found - use fps=25 as default
    const fallbackMetadata = { fps: 25, duration: 21.06 };
    
    // Cache the fallback to avoid repeated requests
    metadataCache.set(cacheKey, fallbackMetadata);
    
    return fallbackMetadata;
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

/**
 * Clear metadata cache (useful for testing or when videos change)
 */
export const clearMetadataCache = () => {
  metadataCache.clear();
};
