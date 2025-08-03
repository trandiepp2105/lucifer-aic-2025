import React, { useState, useRef, useEffect, useCallback } from 'react';
import { createPortal } from 'react-dom';
import Hls from 'hls.js';
import FrameItem from '../FrameItem/FrameItem';
import SubmissionModal from '../SubmissionModal/SubmissionModal';
import ImageZoomModal from '../ImageZoomModal/ImageZoomModal';
import { useApp } from '../../contexts/AppContext';
import './VideoPlayer.scss';

const VideoPlayer = ({ isOpen, onClose, currentFrame, onFrameSelect, onSubmit, onSend, sendingFrames = new Set() }) => {
  const { queryMode } = useApp();
  const videoRef = useRef(null);
  const hlsRef = useRef(null);
  const progressBarRef = useRef(null);

  const [playing, setPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(1);
  const [muted, setMuted] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [videoInfo, setVideoInfo] = useState(null);
  const [videoSrc, setVideoSrc] = useState('');
  const [internalCurrentFrame, setInternalCurrentFrame] = useState(currentFrame);
  const [hasInitialSeeked, setHasInitialSeeked] = useState(false);
  const [isReady, setIsReady] = useState(false);
  const [videoError, setVideoError] = useState(null);
  const [isVideoAccessible, setIsVideoAccessible] = useState(true);
  const [isUserSeeking, setIsUserSeeking] = useState(false);
  const [isSubmissionModalOpen, setIsSubmissionModalOpen] = useState(false);
  const [isImageZoomOpen, setIsImageZoomOpen] = useState(false);
  const [frameToSubmit, setFrameToSubmit] = useState(null);
  const [frameToZoom, setFrameToZoom] = useState(null);
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

const VideoPlayer = ({ isOpen, onClose, currentFrame, onFrameSelect, onSubmit, onSend, sendingFrames = new Set() }) => {
  const { queryMode } = useApp();
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
  const [internalCurrentFrame, setInternalCurrentFrame] = useState(currentFrame);
  const [hasInitialSeeked, setHasInitialSeeked] = useState(false);
  const [isReady, setIsReady] = useState(false);
  const [videoError, setVideoError] = useState(null);
  const [isVideoAccessible, setIsVideoAccessible] = useState(true);
  const [isUserSeeking, setIsUserSeeking] = useState(false);
  const [isSubmissionModalOpen, setIsSubmissionModalOpen] = useState(false);
  const [isImageZoomOpen, setIsImageZoomOpen] = useState(false);
  const [frameToSubmit, setFrameToSubmit] = useState(null);
  const [frameToZoom, setFrameToZoom] = useState(null);
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

  // Generate neighboring frames (30 before and after current frame)
  const generateNeighboringFrames = (centerFrame) => {
    if (!centerFrame) return [];
    
    const frames = [];
    const centerFrameIndex = parseInt(centerFrame.frame_index);
    
    // Generate 30 frames before and after (only frame_index divisible by 7)
    for (let i = -30; i <= 30; i++) {
      const targetFrameIndex = centerFrameIndex + (i * 7);
      
      // Skip if frame index would be negative
      if (targetFrameIndex < 0) continue;
      
      let frameData;
      
      if (i === 0) {
        // This is the center frame (current frame) - ensure all fields are present
        frameData = {
          id: centerFrame.id || `${centerFrame.video_name}-${centerFrame.frame_index}`,
          filename: centerFrame.filename || `${centerFrame.video_name}/${centerFrame.frame_index}`,
          thumbnail: centerFrame.thumbnail || centerFrame.url,
          url: centerFrame.url || centerFrame.thumbnail,
          video_name: centerFrame.video_name,
          frame_index: centerFrame.frame_index,
          isCenter: true,
          offset: 0
        };
      } else {
        // Create new frame URL by replacing frame_index in the original URL
        const baseUrl = centerFrame.thumbnail || centerFrame.url;
        const newUrl = baseUrl.replace(
          `/${centerFrameIndex}.jpg`, 
          `/${targetFrameIndex}.jpg`
        );
        
        frameData = {
          id: `${centerFrame.video_name}-${targetFrameIndex}`,
          filename: `${centerFrame.video_name}/${targetFrameIndex}`,
          thumbnail: newUrl,
          url: newUrl,
          video_name: centerFrame.video_name,
          frame_index: targetFrameIndex,
          isCenter: false,
          offset: i
        };
      }
      
      frames.push(frameData);
    }
    
    return frames;
  };

  // Get current video frames
  const videoFrames = generateNeighboringFrames(internalCurrentFrame);

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

  // Load video info when currentFrame changes
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
          // Fallback to default values if metadata not found
          metadata = { fps: 25, duration: 21.06 };
        }
        
        setVideoInfo(metadata);
        setVideoSrc(videoUrl);
        
        // Update internal current frame and reset state
        setInternalCurrentFrame(currentFrame);
        setHasInitialSeeked(false);
        setIsReady(false);
        setIsLoading(true);
        
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
        const videoUrls = generateVideoUrl(currentFrame.thumbnail || currentFrame.url, currentFrame.video_name);
        setVideoSrc(videoUrls.hlsUrl); // Try HLS first
        setInternalCurrentFrame(currentFrame);
        setHasInitialSeeked(false);
        setIsReady(false);
        setIsLoading(true);
      }
    };

    loadVideoInfo();
  }, [currentFrame?.id, isOpen]);

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
        console.log('HLS manifest loaded successfully');
        setIsLoading(false);
        setIsReady(true);
        setVideoError(null);
        
        // Clear loading timeout
        if (loadingTimeoutRef.current) {
          clearTimeout(loadingTimeoutRef.current);
          loadingTimeoutRef.current = null;
        }
        
        // Seek to initial frame time when ready
        if (videoInfo && currentFrame && !hasInitialSeeked) {
          const initialTime = calculateTimeFromFrame(parseInt(currentFrame.frame_index), videoInfo.fps);
          console.log('Seeking to initial time:', initialTime, 'for frame:', currentFrame.frame_index);
          video.currentTime = initialTime;
          setCurrentTime(initialTime);
          setHasInitialSeeked(true);
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
        
        // Seek to initial frame time
        if (videoInfo && currentFrame && !hasInitialSeeked) {
          const initialTime = calculateTimeFromFrame(parseInt(currentFrame.frame_index), videoInfo.fps);
          console.log('Seeking to initial time:', initialTime, 'for frame:', currentFrame.frame_index);
          video.currentTime = initialTime;
          setCurrentTime(initialTime);
          setHasInitialSeeked(true);
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
      console.error('HLS is not supported in this browser');
      setVideoError('HLS is not supported in this browser');
      setIsLoading(false);
    }

    return () => {
      if (hlsRef.current) {
        hlsRef.current.destroy();
        hlsRef.current = null;
      }
    };
  }, [videoSrc, isOpen, videoInfo, currentFrame?.frame_index, hasInitialSeeked]);

  // Update current frame based on video time
  useEffect(() => {
    if (!videoInfo || !internalCurrentFrame || isUserSeeking) return;

    const newFrameIndex = calculateFrameFromTime(currentTime, videoInfo.fps);
    const baseUrl = (internalCurrentFrame.thumbnail || internalCurrentFrame.url);
    const baseFrameIndex = parseInt(internalCurrentFrame.frame_index);
    
    // Only update if frame index changed significantly
    if (Math.abs(newFrameIndex - baseFrameIndex) >= 7) {
      const newUrl = baseUrl.replace(
        `/${baseFrameIndex}.jpg`, 
        `/${newFrameIndex}.jpg`
      );
      
      const newFrame = {
        id: `${internalCurrentFrame.video_name}-${newFrameIndex}`,
        filename: `${internalCurrentFrame.video_name}/${newFrameIndex}`,
        thumbnail: newUrl,
        url: newUrl,
        video_name: internalCurrentFrame.video_name,
        frame_index: newFrameIndex
      };
      
      setInternalCurrentFrame(newFrame);
      
      // Notify parent component
      if (onFrameSelect) {
        onFrameSelect(newFrame);
      }
    }
  }, [currentTime, videoInfo, isUserSeeking]);

  useEffect(() => {
    if (!isOpen) {
      setIsPlaying(false);
      setCurrentTime(0);
      setIsLoading(true);
      setVideoInfo(null);
      setVideoSrc('');
      setIsReady(false);
      setHasInitialSeeked(false);
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
  };

  const handleVideoPause = () => {
    setIsPlaying(false);
  };

  const handleVideoLoadedMetadata = () => {
    if (videoRef.current) {
      setDuration(videoRef.current.duration);
    }
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

  const handleSubmitFrame = (frame) => {
    // For VideoPlayer, open internal SubmissionModal instead of calling parent onSubmit
    setFrameToSubmit(frame);
    setIsSubmissionModalOpen(true);
  };

  const handleSendFrame = (frame) => {
    if (onSend) {
      onSend(frame);
    }
  };

  const handleSubmissionModalClose = () => {
    setIsSubmissionModalOpen(false);
    setFrameToSubmit(null);
  };

  const handleSubmissionComplete = (submissionData) => {
    // Call parent onSend if available
    if (onSend) {
      onSend(submissionData);
    }
    // Close modal
    handleSubmissionModalClose();
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
    
    // Set user seeking flag
    setIsUserSeeking(true);
    
    if (safeSeekTo(newTime)) {
      setCurrentTime(newTime);
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
    
    // Set user seeking flag
    setIsUserSeeking(true);
    
    if (safeSeekTo(newTime)) {
      setCurrentTime(newTime);
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
    
    // Update video time
    if (safeSeekTo(frameTime)) {
      setCurrentTime(frameTime);
    }
    
    // Update current frame
    setInternalCurrentFrame(frame);
    
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

  // Scroll to selected frame in gallery when internalCurrentFrame changes
  useEffect(() => {
    if (internalCurrentFrame && galleryRef.current && videoFrames.length > 0) {
      const frameElement = galleryRef.current.querySelector(`[data-frame-id="${internalCurrentFrame.id}"]`);
      if (frameElement) {
        frameElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }
  }, [internalCurrentFrame?.id, videoFrames.length]);

  // Cleanup effect
  useEffect(() => {
    return () => {
      if (seekTimeoutRef.current) {
        clearTimeout(seekTimeoutRef.current);
      }
      if (loadingTimeoutRef.current) {
        clearTimeout(loadingTimeoutRef.current);
      }
    };
  }, []);

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
                >
                  <div 
                    className="video-player__progress-filled"
                    style={{ width: `${(currentTime / duration) * 100}%` }}
                  ></div>
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
                      className="video-player__frame"
                      isSending={sendingFrames.has(`${frame.video_name}-${frame.frame_index}`)}
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
        </div>
      </div>

      {/* SubmissionModal overlay within VideoPlayer - render at body level */}
      {isSubmissionModalOpen && frameToSubmit && createPortal(
        <SubmissionModal
          isOpen={isSubmissionModalOpen}
          onClose={handleSubmissionModalClose}
          onSubmit={handleSubmissionComplete}
          frame={frameToSubmit}
          queryMode={queryMode}
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