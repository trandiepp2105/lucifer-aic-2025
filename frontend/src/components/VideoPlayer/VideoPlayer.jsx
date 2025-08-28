import React, { useState, useRef, useEffect, useCallback } from 'react';
import { createPortal } from 'react-dom';
import Hls from 'hls.js';
import FrameItem from '../FrameItem/FrameItem';
import SubmissionModal from '../SubmissionModal/SubmissionModal';
import TeamAnswerModal from '../TeamAnswerModal/TeamAnswerModal';
import ImageZoomModal from '../ImageZoomModal/ImageZoomModal';
import TeamAnswer from '../TeamAnswer/TeamAnswer';
import { useApp } from '../../contexts/AppContext';
import { useFrameActions } from '../../hooks/useFrameActions';
import './VideoPlayer.scss';

const VideoPlayer = ({ 
  isOpen, 
  onClose, 
  currentFrame, 
  onFrameSelect, 
  onSubmit, 
  onSend, 
  sendingFrames = new Set(), 
  allTeamAnswers = [], 
  setAllTeamAnswers,
  searchResults = [],
  onRefresh
}) => {
  const { queryMode, tempTrakeItems, addTempTrakeItem, removeTempTrakeItem } = useApp();
  
  // Use the shared frame actions hook
  const {
    submissionModal,
    closeSubmissionModal,
    handleSubmissionConfirm,
    isTeamAnswerModalOpen,
    frameToSubmit,
    handleSendFrame,
    handleSubmitFrame,
    handleTeamAnswerModalClose,
    handleTeamAnswerComplete
  } = useFrameActions(queryMode, allTeamAnswers);
  
  const videoRef = useRef(null);
  const hlsRef = useRef(null);
  const progressRef = useRef(null);
  const galleryRef = useRef(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(1);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [showControls, setShowControls] = useState(true);
  const [isLoading, setIsLoading] = useState(true);
  const [videoInfo, setVideoInfo] = useState(null);
  const [videoSrc, setVideoSrc] = useState('');
  
  // Separate currentFrame (selected) and centerFrame (gallery center) management
  const [internalCurrentFrame, setInternalCurrentFrame] = useState(currentFrame); // Selected frame
  const [centerFrame, setCenterFrame] = useState(currentFrame); // Gallery center frame
  
  const [hasInitialSeeked, setHasInitialSeeked] = useState(''); // Store frame key instead of boolean
  const [isReady, setIsReady] = useState(false);
  const [videoError, setVideoError] = useState(null);
  const [isVideoAccessible, setIsVideoAccessible] = useState(true);
  const [isUserSeeking, setIsUserSeeking] = useState(false);
  const [isImageZoomOpen, setIsImageZoomOpen] = useState(false);
  const [frameToZoom, setFrameToZoom] = useState(null);
  const [showTimePreview, setShowTimePreview] = useState(false);
  const [previewTime, setPreviewTime] = useState(0);
  const [previewPosition, setPreviewPosition] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const [dragStartTime, setDragStartTime] = useState(0);
  const [previewImageUrl, setPreviewImageUrl] = useState('');
  const imageUpdateTimeoutRef = useRef(null);
  const seekTimeoutRef = useRef(null);
  const loadingTimeoutRef = useRef(null);

  // Generate video URL from frame URL - only HLS
  const generateVideoUrl = (frameUrl, videoName) => {
    if (!frameUrl || !videoName) return '';
    // Extract context (base URL) and construct video path
    // "http://127.0.0.1/media/frames/L09_V025/9590.jpg" -> "http://127.0.0.1/media/videos_hls/L09_V025/playlist.m3u8"
    const urlParts = frameUrl.split('/');
    const context = urlParts.slice(0, 3).join('/'); // "http://127.0.0.1"
    
    // Only use HLS, no fallback to MP4
    const hlsUrl = `${context}/media/videos_hls/${videoName}/playlist.m3u8`;
    
    return hlsUrl;
  };

  // Generate metadata URL from frame URL
  const generateMetadataUrl = (frameUrl) => {
    if (!frameUrl) return '';
    // Extract base path and add /metadata.json
    // "http://127.0.0.1/media/frames/L09_V025/9590.jpg" -> "http://127.0.0.1/media/frames/L09_V025/metadata.json"
    const basePath = frameUrl.substring(0, frameUrl.lastIndexOf('/'));
    return `${basePath}/metadata.json`;
  };

  // Generate neighboring frames based on centerFrame for gallery display
  const generateNeighboringFrames = (baseCenterFrame) => {
    if (!baseCenterFrame) return [];
    
    const frames = [];
    const centerFrameIndex = parseInt(baseCenterFrame.frame_index);
    
    // Generate 30 frames before and after (only frame_index divisible by 7)
    for (let i = -30; i <= 30; i++) {
      const targetFrameIndex = centerFrameIndex + (i * 7);
      
      // Skip if frame index would be negative
      if (targetFrameIndex < 0) continue;
      
      let frameData;
      
      if (i === 0) {
        // This is the center frame - ensure all fields are present
        frameData = {
          id: baseCenterFrame.id || `${baseCenterFrame.video_name}-${baseCenterFrame.frame_index}`,
          filename: baseCenterFrame.filename || `${baseCenterFrame.video_name}/${baseCenterFrame.frame_index}`,
          thumbnail: baseCenterFrame.thumbnail || baseCenterFrame.url,
          url: baseCenterFrame.url || baseCenterFrame.thumbnail,
          video_name: baseCenterFrame.video_name,
          frame_index: baseCenterFrame.frame_index,
          isCenter: true,
          offset: 0
        };
      } else {
        // Create new frame URL by replacing frame_index in the original URL
        const baseUrl = baseCenterFrame.thumbnail || baseCenterFrame.url;
        const newUrl = baseUrl.replace(
          `/${centerFrameIndex}.webp`, 
          `/${targetFrameIndex}.webp`
        );
        
        frameData = {
          id: `${baseCenterFrame.video_name}-${targetFrameIndex}`,
          filename: `${baseCenterFrame.video_name}/${targetFrameIndex}`,
          thumbnail: newUrl,
          url: newUrl,
          video_name: baseCenterFrame.video_name,
          frame_index: targetFrameIndex,
          isCenter: false,
          offset: i
        };
      }
      
      frames.push(frameData);
    }
    
    return frames;
  };

  // Get current video frames based on centerFrame
  const videoFrames = generateNeighboringFrames(centerFrame);

  // Calculate frame index from current time and FPS
  const calculateFrameFromTime = (time, fps) => {
    const frameNumber = Math.round(time * fps);
    // Round to nearest frame divisible by 7
    return Math.round(frameNumber / 7) * 7;
  };

  // Calculate time from frame index and FPS
  const calculateTimeFromFrame = (frameIndex, fps) => {
    return frameIndex / fps;
  };

  // Load video info only when video name changes (not on every frame change)
  useEffect(() => {
    if (!currentFrame || !isOpen) return;

    const loadVideoInfo = async () => {
      try {
        const videoUrl = generateVideoUrl(currentFrame.thumbnail || currentFrame.url, currentFrame.video_name);
        
        // Check if HLS file is accessible
        let accessible = false;
        
        try {
          const hlsResponse = await fetch(videoUrl, { 
            method: 'HEAD',
            mode: 'cors',
            credentials: 'omit'
          });
          accessible = hlsResponse.ok;
        } catch (error) {
          console.log('HLS not available:', error);
        }
        
        setIsVideoAccessible(accessible);
        
        if (!accessible) {
          setVideoError('HLS video file is not accessible. This may be due to CORS restrictions or the video file being unavailable.');
          return;
        } else {
          setVideoError(null);
        }
        
        const metadataUrl = generateMetadataUrl(currentFrame.thumbnail || currentFrame.url);
        let metadata;
        
        try {
          // Try to fetch video metadata
          const response = await fetch(metadataUrl, { 
            method: 'GET',
            mode: 'cors',
            credentials: 'omit'
          });
          if (!response.ok) throw new Error(`Metadata not found: ${response.status}`);
          metadata = await response.json();
          
          // Validate metadata structure
          if (!metadata.fps || !metadata.duration) {
            throw new Error('Invalid metadata structure');
          }
        } catch (error) {
          console.log('Metadata not available, using defaults:', error);
          // Fallback to default values if metadata not found - use fps=25 as default
          metadata = { fps: 25, duration: 21.06 };
        }
        
        setVideoInfo(metadata);
        setVideoSrc(videoUrl);
        
        // Initialize both frames when video opens
        const isDifferentVideo = internalCurrentFrame?.video_name !== currentFrame.video_name;
        setInternalCurrentFrame(currentFrame);
        setCenterFrame(currentFrame); // Set initial center frame
        
        // Only reset hasInitialSeeked if it's a different video
        if (isDifferentVideo) {
          setHasInitialSeeked('');
          setIsLoading(true); // Only set loading for different video
        }
        
        setIsReady(false);
        
        // Set a timeout to clear loading state if video doesn't load
        if (loadingTimeoutRef.current) {
          clearTimeout(loadingTimeoutRef.current);
        }
        loadingTimeoutRef.current = setTimeout(() => {
          setIsLoading(false);
        }, 5000); // 5 second timeout
      } catch (error) {
        setVideoError('Failed to load video information. Using default values.');
        // Set hardcoded default values if all else fails
        const hardcodedInfo = { fps: 25, duration: 21.06 };
        setVideoInfo(hardcodedInfo);
        const videoUrl = generateVideoUrl(currentFrame.thumbnail || currentFrame.url, currentFrame.video_name);
        setVideoSrc(videoUrl);
        
        // Only reset hasInitialSeeked if it's a different video
        const isDifferentVideo = internalCurrentFrame?.video_name !== currentFrame.video_name;
        setInternalCurrentFrame(currentFrame);
        setCenterFrame(currentFrame);
        
        if (isDifferentVideo) {
          setHasInitialSeeked('');
          setIsLoading(true); // Only set loading for different video
        }
        
        setIsReady(false);
      }
    };

    loadVideoInfo();
  }, [currentFrame?.video_name, isOpen]);

  // Update centerFrame based on video current time (for gallery display)
  useEffect(() => {
    if (!videoInfo || !internalCurrentFrame || isUserSeeking) return;

    const newFrameIndex = calculateFrameFromTime(currentTime, videoInfo.fps);
    const currentCenterFrameIndex = parseInt(centerFrame?.frame_index || 0);
    
    // Only update centerFrame if frame index changed significantly (for gallery)
    if (Math.abs(newFrameIndex - currentCenterFrameIndex) >= 7) {
      const baseUrl = (internalCurrentFrame.thumbnail || internalCurrentFrame.url);
      const baseFrameIndex = parseInt(internalCurrentFrame.frame_index);
      
      const newUrl = baseUrl.replace(
        `/${baseFrameIndex}.webp`, 
        `/${newFrameIndex}.webp`
      );
      
      const newCenterFrame = {
        id: `${internalCurrentFrame.video_name}-${newFrameIndex}`,
        filename: `${internalCurrentFrame.video_name}/${newFrameIndex}`,
        thumbnail: newUrl,
        url: newUrl,
        video_name: internalCurrentFrame.video_name,
        frame_index: newFrameIndex
      };
      
      setCenterFrame(newCenterFrame);
    }
  }, [currentTime, videoInfo, isUserSeeking]);

  // HLS initialization effect
  useEffect(() => {
    const video = videoRef.current;
    
    if (!video || !videoSrc || !isOpen) return;

    // Clean up existing HLS instance
    if (hlsRef.current) {
      hlsRef.current.destroy();
      hlsRef.current = null;
    }

    if (Hls.isSupported()) {
      // Initialize HLS
      const hls = new Hls({
        enableWorker: false,
        lowLatencyMode: true,
        backBufferLength: 90
      });
      hlsRef.current = hls;

      hls.loadSource(videoSrc);
      hls.attachMedia(video);

      hls.on(Hls.Events.MANIFEST_PARSED, () => {
        setIsLoading(false);
        setIsReady(true);
        setVideoError(null);
        
        // Clear loading timeout
        if (loadingTimeoutRef.current) {
          clearTimeout(loadingTimeoutRef.current);
          loadingTimeoutRef.current = null;
        }
      });

      hls.on(Hls.Events.ERROR, (event, data) => {
        console.error('HLS error:', data);
        if (data.fatal) {
          switch (data.type) {
            case Hls.ErrorTypes.NETWORK_ERROR:
              console.log('Fatal network error encountered, try to recover');
              hls.startLoad();
              break;
            case Hls.ErrorTypes.MEDIA_ERROR:
              console.log('Fatal media error encountered, try to recover');
              hls.recoverMediaError();
              break;
            default:
              console.log('Fatal error, destroying HLS instance');
              setVideoError('HLS playback error occurred. The video stream may be corrupted or unavailable.');
              setIsLoading(false);
              hls.destroy();
              break;
          }
        }
      });

      hls.on(Hls.Events.LEVEL_LOADED, () => {
        setDuration(video.duration || 0);
      });

    } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
      // Fallback for Safari (native HLS support)
      video.src = videoSrc;
      
      const handleLoadedMetadata = () => {
        console.log('Video metadata loaded (Safari native HLS)');
        setIsLoading(false);
        setIsReady(true);
        setDuration(video.duration);
        setVideoError(null);
        
        // Clear loading timeout
        if (loadingTimeoutRef.current) {
          clearTimeout(loadingTimeoutRef.current);
          loadingTimeoutRef.current = null;
        }
      };
      
      const handleError = (error) => {
        console.error('Video error:', error);
        setVideoError('HLS video playback failed. The video may not be supported or accessible.');
        setIsLoading(false);
      };
      
      video.addEventListener('loadedmetadata', handleLoadedMetadata);
      video.addEventListener('error', handleError);
      
      return () => {
        video.removeEventListener('loadedmetadata', handleLoadedMetadata);
        video.removeEventListener('error', handleError);
      };
    } else {
      setVideoError('HLS is not supported in this browser');
      setIsLoading(false);
    }

    return () => {
      if (hlsRef.current) {
        hlsRef.current.destroy();
        hlsRef.current = null;
      }
    };
  }, [videoSrc, isOpen]);

  // Separate effect for initial seek when video is ready - only seek to start frame once
  useEffect(() => {
    const video = videoRef.current;
    
    if (!video || !videoInfo || !currentFrame || !isReady) return;
    
    // Create unique frame key to track if we've seeked to this specific frame
    const frameKey = `${currentFrame.video_name}-${currentFrame.frame_index}`;
    
    // Only seek if we haven't seeked to this specific frame yet
    if (hasInitialSeeked === frameKey) return;
    
    const initialTime = calculateTimeFromFrame(parseInt(currentFrame.frame_index), videoInfo.fps);
    
    video.currentTime = initialTime;
    setCurrentTime(initialTime);
    setHasInitialSeeked(frameKey); // Store the frame key we've seeked to
  }, [isReady, videoInfo, currentFrame?.video_name, currentFrame?.frame_index, hasInitialSeeked]);

  useEffect(() => {
    if (!isOpen) {
      setIsPlaying(false);
      setCurrentTime(0);
      setIsLoading(true);
      setVideoInfo(null);
      setVideoSrc('');
      setIsReady(false);
      setHasInitialSeeked('');
      setVideoError(null);
      setIsVideoAccessible(true);
      setIsUserSeeking(false);
      
      // Clean up HLS
      if (hlsRef.current) {
        hlsRef.current.destroy();
        hlsRef.current = null;
      }
      
      // Clear any pending timeouts
      if (seekTimeoutRef.current) {
        clearTimeout(seekTimeoutRef.current);
        seekTimeoutRef.current = null;
      }
      if (loadingTimeoutRef.current) {
        clearTimeout(loadingTimeoutRef.current);
        loadingTimeoutRef.current = null;
      }
    }
  }, [isOpen]);

  // Video event handlers
  const handleVideoTimeUpdate = () => {
    if (videoRef.current) {
      setCurrentTime(videoRef.current.currentTime);
    }
  };

  const handleVideoPlay = () => {
    setIsPlaying(true);
    // Clear loading when video actually starts playing
    setIsLoading(false);
  };

  const handleVideoPause = () => {
    setIsPlaying(false);
  };

  const handleVideoLoadedMetadata = () => {
    if (videoRef.current) {
      setDuration(videoRef.current.duration);
    }
  };

  const handleVideoCanPlay = () => {
    // Clear loading when video can start playing
    setIsLoading(false);
  };

  // Safe seeking function
  const safeSeekTo = (time) => {
    if (videoRef.current) {
      try {
        videoRef.current.currentTime = time;
        return true;
      } catch (error) {
        console.error('Seek failed:', error);
        return false;
      }
    }
    return false;
  };

  const handleFrameZoom = (frame) => {
    setFrameToZoom(frame);
    setIsImageZoomOpen(true);
  };

  const handleCloseImageZoom = () => {
    setIsImageZoomOpen(false);
    setFrameToZoom(null);
  };

  useEffect(() => {
    let hideControlsTimer;
    
    if (isPlaying && showControls) {
      hideControlsTimer = setTimeout(() => {
        setShowControls(false);
      }, 3000);
    }

    return () => {
      if (hideControlsTimer) {
        clearTimeout(hideControlsTimer);
      }
    };
  }, [isPlaying, showControls]);

  const togglePlayPause = () => {
    const video = videoRef.current;
    if (!video) return;
    
    if (isPlaying) {
      video.pause();
    } else {
      const playPromise = video.play();
      if (playPromise !== undefined) {
        playPromise.catch(error => {
          console.error('Video play failed:', error);
          // Don't set error state for play interruption
          if (!error.message.includes('interrupted')) {
            setVideoError('Failed to play video: ' + error.message);
          }
        });
      }
    }
  };

  const handleProgressClick = (e) => {
    const progressBar = progressRef.current;
    if (!progressBar) return;

    const rect = progressBar.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const newTime = (clickX / rect.width) * duration;
    
    // Store playing state before seeking
    const wasPlaying = isPlaying;
    
    // Set user seeking flag
    setIsUserSeeking(true);
    
    if (safeSeekTo(newTime)) {
      setCurrentTime(newTime);
      
      // Resume playing if it was playing before seek
      if (wasPlaying && videoRef.current) {
        setTimeout(() => {
          videoRef.current.play().catch(error => {
            console.log('Resume play after progress seek failed:', error);
          });
        }, 100);
      }
    }
    
    // Clear user seeking flag after a delay
    if (seekTimeoutRef.current) {
      clearTimeout(seekTimeoutRef.current);
    }
    seekTimeoutRef.current = setTimeout(() => {
      setIsUserSeeking(false);
    }, 1000);
  };

  const handleVolumeChange = (e) => {
    const newVolume = parseFloat(e.target.value);
    setVolume(newVolume);
    
    // Update video volume
    if (videoRef.current) {
      videoRef.current.volume = newVolume;
    }
  };

  const skip = (seconds) => {
    const newTime = Math.max(0, Math.min(duration, currentTime + seconds));
    
    // Store playing state before seeking
    const wasPlaying = isPlaying;
    
    // Set user seeking flag
    setIsUserSeeking(true);
    
    if (safeSeekTo(newTime)) {
      setCurrentTime(newTime);
      
      // Resume playing if it was playing before seek
      if (wasPlaying && videoRef.current) {
        setTimeout(() => {
          videoRef.current.play().catch(error => {
            console.log('Resume play after skip failed:', error);
          });
        }, 100);
      }
    }
    
    // Clear user seeking flag after a delay
    if (seekTimeoutRef.current) {
      clearTimeout(seekTimeoutRef.current);
    }
    seekTimeoutRef.current = setTimeout(() => {
      setIsUserSeeking(false);
    }, 1000);
  };

  const formatTime = (time) => {
    if (isNaN(time)) return '0:00';
    
    const minutes = Math.floor(time / 60);
    const seconds = Math.floor(time % 60);
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  };

  const handleKeyDown = (e) => {
    e.preventDefault();
    
    switch (e.key) {
      case ' ':
      case 'k':
        togglePlayPause();
        break;
      case 'ArrowLeft':
        skip(-10);
        break;
      case 'ArrowRight':
        skip(10);
        break;
      case 'j':
        skip(-10);
        break;
      case 'l':
        skip(10);
        break;
      case 'f':
        toggleFullscreen();
        break;
      case 'Escape':
        onClose();
        break;
      default:
        break;
    }
  };

  const toggleFullscreen = () => {
    // This would require additional fullscreen API implementation
    setIsFullscreen(!isFullscreen);
  };

  const handleOverlayClick = (e) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  const handleVideoClick = () => {
    togglePlayPause();
  };

  const handleMouseMove = () => {
    setShowControls(true);
  };

  const handleFrameClick = (frame) => {
    if (!videoInfo) return;    
    // Calculate time for the selected frame
    const frameTime = calculateTimeFromFrame(parseInt(frame.frame_index), videoInfo.fps);
    
    // Set user seeking flag
    setIsUserSeeking(true);
    
    // Update video time (seek to selected frame) but don't auto-play
    if (safeSeekTo(frameTime)) {
      setCurrentTime(frameTime);
    }
    
    // Update current frame (selected frame) and center frame (for gallery)
    setInternalCurrentFrame(frame);
    setCenterFrame(frame); // Update gallery center to clicked frame
    
    // Notify parent component
    if (onFrameSelect) {
      onFrameSelect(frame);
    }
    
    // Clear user seeking flag after a delay
    if (seekTimeoutRef.current) {
      clearTimeout(seekTimeoutRef.current);
    }
    seekTimeoutRef.current = setTimeout(() => {
      setIsUserSeeking(false);
    }, 1000);
  };

  // Check if a frame is in temp TRAKE items
  const isFrameInTempTrake = React.useCallback((frame) => {
    return tempTrakeItems.some(item => 
      item.video_name === frame.video_name && 
      item.frame_index === frame.frame_index
    );
  }, [tempTrakeItems]);

  // Handle checkbox change for TRAKE mode
  const handleCheckboxChange = React.useCallback((frame, isChecked) => {
    if (isChecked) {
      addTempTrakeItem({
        video_name: frame.video_name,
        frame_index: frame.frame_index,
        url: frame.url,
      });
    } else {
      removeTempTrakeItem({
        video_name: frame.video_name,
        frame_index: frame.frame_index,
      });
    }
  }, [addTempTrakeItem, removeTempTrakeItem]);

  // Scroll to center frame in gallery to keep it centered
  const scrollToCenterFrame = useCallback(() => {
    if (centerFrame && galleryRef.current && videoFrames.length > 0) {
      const frameElement = galleryRef.current.querySelector(`[data-frame-id="${centerFrame.id}"]`);
      if (frameElement) {
        frameElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }
  }, [centerFrame?.id, videoFrames.length]);

  // Scroll to center frame when it changes or when frames are loaded
  useEffect(() => {
    scrollToCenterFrame();
  }, [scrollToCenterFrame]);

  // Scroll to center frame on initial render and when VideoPlayer opens
  useEffect(() => {
    if (isOpen && centerFrame && videoFrames.length > 0) {
      // Use a small delay to ensure DOM is ready
      const timeoutId = setTimeout(() => {
        scrollToCenterFrame();
      }, 100);
      
      return () => clearTimeout(timeoutId);
    }
  }, [isOpen, centerFrame?.id, videoFrames.length, scrollToCenterFrame]);

  // Cleanup effect
  useEffect(() => {
    return () => {
      if (seekTimeoutRef.current) {
        clearTimeout(seekTimeoutRef.current);
      }
      if (loadingTimeoutRef.current) {
        clearTimeout(loadingTimeoutRef.current);
      }
      if (imageUpdateTimeoutRef.current) {
        clearTimeout(imageUpdateTimeoutRef.current);
      }
    };
  }, []);

  const handleProgressMouseMove = (e) => {
    const progressBar = progressRef.current;
    if (!progressBar || !duration) return;

    const rect = progressBar.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const hoverTime = Math.max(0, Math.min(duration, (mouseX / rect.width) * duration));
    
    setPreviewTime(hoverTime);
    
    // Calculate tooltip position with bounds checking
    const tooltipWidth = 160; // Width of tooltip
    const minX = tooltipWidth / 2; // Minimum distance from left edge
    const maxX = rect.width - tooltipWidth / 2; // Maximum distance from right edge
    
    // Clamp mouseX to prevent overflow
    const clampedMouseX = Math.max(minX, Math.min(maxX, mouseX));
    setPreviewPosition(clampedMouseX);
    
    setShowTimePreview(true);

    // Throttle image URL updates to avoid too many requests
    if (imageUpdateTimeoutRef.current) {
      clearTimeout(imageUpdateTimeoutRef.current);
    }
    
    imageUpdateTimeoutRef.current = setTimeout(() => {
      const imageUrl = getFrameUrlFromTime(hoverTime);
      setPreviewImageUrl(imageUrl);
    }, 100); // 100ms throttle
  };

  // Handler for starting drag on slider handle
  const handleSliderMouseDown = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
    setDragStartTime(currentTime);
    setShowTimePreview(true);
    
    const progressBar = progressRef.current;
    if (!progressBar || !duration) return;

    const rect = progressBar.getBoundingClientRect();
    
    const handleMouseMove = (e) => {
      const mouseX = Math.max(0, Math.min(rect.width, e.clientX - rect.left));
      const newTime = (mouseX / rect.width) * duration;
      
      setPreviewTime(newTime);
      setPreviewPosition(mouseX);
      
      // Update video time during drag for smooth preview
      if (videoRef.current && !videoRef.current.seeking) {
        videoRef.current.currentTime = newTime;
      }
    };

    const handleMouseUp = () => {
      setIsDragging(false);
      
      // Final seek to the desired time
      safeSeekTo(previewTime);
      
      setTimeout(() => {
        setShowTimePreview(false);
      }, 1000);
      
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  };

  // Helper function to get frame index from time
  const getFrameFromTime = (time) => {
    if (!videoInfo?.fps) return 0;
    return Math.floor(time * videoInfo.fps);
  };

  // Helper function to get rounded frame index (divisible by 7) from time
  const getRoundedFrameFromTime = (time) => {
    if (!videoInfo?.fps) return 0;
    const frameIndex = Math.floor(time * videoInfo.fps);
    // Round to nearest frame divisible by 7
    return Math.round(frameIndex / 7) * 7;
  };

  // Helper function to get frame URL from time
  const getFrameUrlFromTime = (time) => {
    if (!videoInfo?.fps || !currentFrame?.url) return null;
    
    // Get rounded frame index (divisible by 7) for thumbnail
    const frameIndex = getRoundedFrameFromTime(time);
    
    // Extract the base URL pattern from current frame URL
    // Handle different URL patterns like:
    // http://ip/path/frame_123.webp -> http://ip/path/frame_{frameIndex}.webp
    // http://ip/path/123.webp -> http://ip/path/{frameIndex}.webp
    const url = currentFrame.url;
    
    if (url.includes('/frame_')) {
      // Pattern: /frame_123.webp
      return url.replace(/\/frame_\d+\.webp$/, `/frame_${frameIndex}.webp`);
    } else {
      // Pattern: /123.webp
      return url.replace(/\/\d+\.webp$/, `/${frameIndex}.webp`);
    }
  };

  const handleProgressMouseEnter = () => {
    if (duration > 0) {
      setShowTimePreview(true);
    }
  };

  const handleProgressMouseLeave = () => {
    setShowTimePreview(false);
    setPreviewImageUrl(''); // Reset image URL
    
    // Clear any pending image updates
    if (imageUpdateTimeoutRef.current) {
      clearTimeout(imageUpdateTimeoutRef.current);
    }
  };

  if (!isOpen) return null;

  return (
    <div 
      className="video-player-overlay"
      onClick={handleOverlayClick}
      onKeyDown={handleKeyDown}
      tabIndex={0}
      onMouseMove={handleMouseMove}
    >
      <div className="video-player-container">
        <button className="video-player__close" onClick={onClose}>
          ×
        </button>
        
        <div className="video-player__layout">
          {/* Left side - Video Player */}
          <div className="video-player__video-section">
            <div className="video-player__wrapper">
              {isLoading && (
                <div className="video-player__loading">
                  <div className="video-player__spinner"></div>
                  <span>Loading video...</span>
                </div>
              )}
              
              {videoError && (
                <div className="video-player__error">
                  <div className="video-player__error-icon">⚠️</div>
                  <div className="video-player__error-message">
                    <strong>Video Error</strong>
                    <p>{videoError}</p>
                    {!isVideoAccessible && (
                      <div className="video-player__error-details">
                        <p>Possible solutions:</p>
                        <ul>
                          <li>Check if the video server is running</li>
                          <li>Verify CORS settings on the server</li>
                          <li>Try accessing the video URL directly: <code>{videoSrc}</code></li>
                        </ul>
                      </div>
                    )}
                  </div>
                </div>
              )}
              
              <video
                ref={videoRef}
                className="video-player__video"
                onTimeUpdate={handleVideoTimeUpdate}
                onPlay={handleVideoPlay}
                onPause={handleVideoPause}
                onLoadedMetadata={handleVideoLoadedMetadata}
                onCanPlay={handleVideoCanPlay}
                onClick={handleVideoClick}
                playsInline
                muted={false}
                style={{ width: '100%', height: '100%' }}
              >
                Your browser does not support the video tag.
              </video>
              
              <div className={`video-player__controls ${showControls ? 'visible' : ''}`}>
                <div 
                  className="video-player__progress"
                  ref={progressRef}
                  onClick={handleProgressClick}
                  onMouseMove={handleProgressMouseMove}
                  onMouseEnter={handleProgressMouseEnter}
                  onMouseLeave={handleProgressMouseLeave}
                >
                  <div 
                    className="video-player__progress-filled"
                    style={{ width: `${(currentTime / duration) * 100}%` }}
                  ></div>
                  
                  {/* Slider handle (nucleus) */}
                  <div 
                    className={`video-player__progress-handle ${isDragging ? 'dragging' : ''}`}
                    style={{ left: `${isDragging ? (previewPosition / progressRef.current?.getBoundingClientRect().width * 100) : (currentTime / duration) * 100}%` }}
                    onMouseDown={handleSliderMouseDown}
                  ></div>
                  
                  {/* Time preview tooltip */}
                  {showTimePreview && (
                    <div 
                      className="video-player__time-preview"
                      style={{ 
                        left: `${previewPosition}px`
                      }}
                    >
                      {/* Frame thumbnail */}
                      {getFrameUrlFromTime(previewTime) ? (
                        <img 
                          className="video-player__preview-thumbnail"
                          src={getFrameUrlFromTime(previewTime)} 
                          alt={`Frame ${getRoundedFrameFromTime(previewTime)}`}
                          onError={(e) => {
                            // Hide image if failed to load
                            e.target.style.display = 'none';
                          }}
                        />
                      ) : (
                        <div className="video-player__preview-loading">
                          <div className="video-player__preview-spinner"></div>
                        </div>
                      )}
                      
                      <div className="video-player__preview-info">
                        <div className="video-player__preview-time">{formatTime(previewTime)}</div>
                        <div className="video-player__preview-frame">Frame {getRoundedFrameFromTime(previewTime)}</div>
                      </div>
                    </div>
                  )}
                </div>
                
                <div className="video-player__controls-row">
                  <div className="video-player__controls-left">
                    <button 
                      className="video-player__control-btn video-player__control-btn--play"
                      onClick={togglePlayPause}
                      disabled={isLoading}
                      title={isPlaying ? 'Pause' : 'Play'}
                    >
                      <img 
                        src={isPlaying ? '/assets/pause.svg' : '/assets/play.svg'} 
                        alt={isPlaying ? 'Pause' : 'Play'}
                      />
                    </button>
                    
                    <button 
                      className="video-player__control-btn"
                      onClick={() => skip(-10)}
                      disabled={isLoading}
                      title="Skip back 10s"
                    >
                      <img src="/assets/previous.svg" alt="Previous" />
                    </button>
                    
                    <button 
                      className="video-player__control-btn"
                      onClick={() => skip(10)}
                      disabled={isLoading}
                      title="Skip forward 10s"
                    >
                      <img src="/assets/previous.svg" alt="Next" style={{ transform: 'scaleX(-1)' }} />
                    </button>
                    
                    <div className="video-player__time">
                      {formatTime(currentTime)} / {formatTime(duration)}
                    </div>
                  </div>
                  
                  <div className="video-player__controls-right">
                    <div className="video-player__volume-container">
                      <img src="/assets/sound.svg" alt="Volume" className="video-player__volume-icon" />
                      <input
                        type="range"
                        min="0"
                        max="1"
                        step="0.1"
                        value={volume}
                        onChange={handleVolumeChange}
                        className="video-player__volume-slider"
                      />
                    </div>
                    
                    <button 
                      className="video-player__control-btn"
                      onClick={toggleFullscreen}
                      title="Fullscreen"
                    >
                      <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                        <path d="M1.5 1a.5.5 0 0 0-.5.5v4a.5.5 0 0 1-1 0v-4A1.5 1.5 0 0 1 1.5 0h4a.5.5 0 0 1 0 1h-4zM10 .5a.5.5 0 0 1 .5-.5h4A1.5 1.5 0 0 1 16 1.5v4a.5.5 0 0 1-1 0v-4a.5.5 0 0 0-.5-.5h-4a.5.5 0 0 1-.5-.5zM.5 10a.5.5 0 0 1 .5.5v4a.5.5 0 0 0 .5.5h4a.5.5 0 0 1 0 1h-4A1.5 1.5 0 0 1 0 14.5v-4a.5.5 0 0 1 .5-.5zm15 0a.5.5 0 0 1 .5.5v4a1.5 1.5 0 0 1-1.5 1.5h-4a.5.5 0 0 1 0-1h4a.5.5 0 0 0 .5-.5v-4a.5.5 0 0 1 .5-.5z"/>
                      </svg>
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Right side - Frame Gallery */}
          <div className="video-player__gallery-section">
            {/* Debug info */}
            {/* <div className="video-player__debug-info" style={{ 
              padding: '8px', 
              fontSize: '12px', 
              background: '#f5f5f5', 
              marginBottom: '8px',
              borderRadius: '4px'
            }}>
              <div><strong>Current Frame (Selected):</strong> {internalCurrentFrame?.frame_index || 'N/A'}</div>
              <div><strong>Center Frame (Gallery):</strong> {centerFrame?.frame_index || 'N/A'}</div>
              <div><strong>Video Time:</strong> {formatTime(currentTime)}</div>
              <div><strong>Video Playing:</strong> {isPlaying ? 'Yes' : 'No'}</div>
            </div> */}
            
            <div className="video-player__gallery" ref={galleryRef}>
              {videoFrames.length > 0 ? (
                videoFrames.map((frame) => (
                  <div
                    key={frame.id}
                    className="video-player__gallery-item"
                    data-frame-id={frame.id}
                  >
                    <FrameItem
                      frame={frame}
                      isSelected={internalCurrentFrame?.id === frame.id}
                      onClick={handleFrameClick}
                      onSubmit={handleSubmitFrame}
                      onSend={handleSendFrame}
                      onZoom={handleFrameZoom}
                      showFilename={true}
                      size="small"
                      className={`video-player__frame ${
                        internalCurrentFrame?.id === frame.id ? 'current' : ''
                      } ${
                        frame.isCenter ? 'center' : ''
                      }`}
                      isSending={sendingFrames.has(`${frame.video_name}-${frame.frame_index}`)}
                      // TRAKE mode specific props
                      showCheckbox={queryMode === 'tra'}
                      isChecked={queryMode === 'tra' ? isFrameInTempTrake(frame) : false}
                      onCheckboxChange={queryMode === 'tra' ? handleCheckboxChange : undefined}
                    />
                  </div>
                ))
              ) : (
                <div className="video-player__gallery-empty">
                  <p>No frames available for this video</p>
                </div>
              )}
            </div>
          </div>

          {/* Team Answer Section - replaces PreviewTRAKEAnswer */}
          <TeamAnswer
            selectedFrame={currentFrame}
            isVisible={true}
            onToggle={null} // Remove empty function - allow component to handle
            onFrameSelect={onFrameSelect}
            onFrameDoubleClick={onFrameSelect}
            onSubmit={onSubmit}
            allTeamAnswers={allTeamAnswers}
            setAllTeamAnswers={setAllTeamAnswers}
            onRefresh={onRefresh}
            isCompact={true}
            className="video-player__team-answer-section"
          />
        </div>
      </div>

      {/* SubmissionModal overlay within VideoPlayer - render at body level */}
      {submissionModal.isOpen && createPortal(
        <SubmissionModal
          isOpen={submissionModal.isOpen}
          onClose={closeSubmissionModal}
          onConfirm={handleSubmissionConfirm}
          submissionType={submissionModal.type}
          frameData={submissionModal.frameData}
          qaText={submissionModal.qaText}
          isSubmitting={submissionModal.isSubmitting}
        />,
        document.body
      )}

      {/* TeamAnswerModal overlay within VideoPlayer - render at body level */}
      {isTeamAnswerModalOpen && frameToSubmit && createPortal(
        <TeamAnswerModal
          isOpen={isTeamAnswerModalOpen}
          onClose={handleTeamAnswerModalClose}
          onSubmit={handleTeamAnswerComplete}
          frame={frameToSubmit}
          allTeamAnswers={allTeamAnswers}
        />,
        document.body
      )}

      {/* ImageZoomModal overlay within VideoPlayer - render at body level */}
      {isImageZoomOpen && frameToZoom && createPortal(
        <ImageZoomModal
          isOpen={isImageZoomOpen}
          onClose={handleCloseImageZoom}
          imageUrl={frameToZoom?.url}
          imageAlt={frameToZoom ? `Frame ${frameToZoom.video_name}-${frameToZoom.frame_index}` : ''}
          frame={frameToZoom}
        />,
        document.body
      )}
    </div>
  );
};

export default VideoPlayer;
