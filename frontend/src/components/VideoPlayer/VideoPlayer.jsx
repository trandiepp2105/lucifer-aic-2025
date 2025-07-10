import React, { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import ReactPlayer from 'react-player';
import FrameItem from '../FrameItem/FrameItem';
import SubmissionModal from '../SubmissionModal/SubmissionModal';
import { useApp } from '../../contexts/AppContext';
import './VideoPlayer.scss';

const VideoPlayer = ({ isOpen, onClose, currentFrame, onFrameSelect, onSubmit, onSend, sendingFrames = new Set() }) => {
  const { queryMode } = useApp();
  const playerRef = useRef(null);
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
  const [useNativeVideo, setUseNativeVideo] = useState(false);
  const [isSubmissionModalOpen, setIsSubmissionModalOpen] = useState(false);
  const [frameToSubmit, setFrameToSubmit] = useState(null);
  const nativeVideoRef = useRef(null);
  const seekTimeoutRef = useRef(null);
  const loadingTimeoutRef = useRef(null);

  // Generate video URL from frame URL
  const generateVideoUrl = (frameUrl, videoName) => {
    if (!frameUrl || !videoName) return '';
    // Extract context (base URL) and construct video path
    // "http://127.0.0.1/media/frames/L09_V025/9590.jpg" -> "http://127.0.0.1/media/videos/L09_V025.mp4"
    const urlParts = frameUrl.split('/');
    const context = urlParts.slice(0, 3).join('/'); // "http://127.0.0.1"
    return `${context}/media/videos/${videoName}.mp4`;
  };

  // Generate info URL from frame URL
  const generateInfoUrl = (frameUrl) => {
    if (!frameUrl) return '';
    // Extract base path and add /info
    // "http://127.0.0.1/media/frames/L09_V025/9590.jpg" -> "http://127.0.0.1/media/frames/L09_V025/info"
    const basePath = frameUrl.substring(0, frameUrl.lastIndexOf('/'));
    return `${basePath}/info.json`;
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

  // Check if video file is accessible
  const checkVideoAccessibility = async (videoUrl) => {
    try {
      const response = await fetch(videoUrl, { 
        method: 'HEAD',
        mode: 'cors',
        credentials: 'omit'
      });
      return response.ok;
    } catch (error) {
      return false;
    }
  };

  // Load video info when currentFrame changes
  useEffect(() => {
    if (!currentFrame || !isOpen) return;

    const loadVideoInfo = async () => {
      try {
        const videoUrl = generateVideoUrl(currentFrame.thumbnail || currentFrame.url, currentFrame.video_name);
        
        // Check if video file is accessible
        const accessible = await checkVideoAccessibility(videoUrl);
        setIsVideoAccessible(accessible);
        
        if (!accessible) {
          setVideoError('Video file is not accessible. This may be due to CORS restrictions or the video file being unavailable.');
        } else {
          setVideoError(null);
        }
        
        const infoUrl = generateInfoUrl(currentFrame.thumbnail || currentFrame.url);
        let response;
        let info;
        
        try {
          // Try to fetch specific video info
          response = await fetch(infoUrl, { 
            method: 'GET',
            mode: 'cors',
            credentials: 'omit'
          });
          if (!response.ok) throw new Error(`Video info not found: ${response.status}`);
          info = await response.json();
        } catch (error) {
          // Fallback to default info if specific info not found
          
          // For any error, use hardcoded default values immediately
          // This avoids additional network requests that might also fail
          info = { fps: 25, duration: 21.06 };
        }
        
        setVideoInfo(info);
        setVideoSrc(videoUrl);
        
        // Update internal current frame and reset state
        setInternalCurrentFrame(currentFrame);
        setHasInitialSeeked(false);
        setIsReady(false);
        setIsLoading(true);
        setUseNativeVideo(false); // Reset to try ReactPlayer first
        
        // Set a timeout to clear loading state if video doesn't load
        if (loadingTimeoutRef.current) {
          clearTimeout(loadingTimeoutRef.current);
        }
        loadingTimeoutRef.current = setTimeout(() => {
          setIsLoading(false);
          if (!isReady) {
            setUseNativeVideo(true);
          }
        }, 5000); // 5 second timeout to try native video
      } catch (error) {
        setVideoError('Failed to load video information. Using default values.');
        // Set hardcoded default values if all else fails
        const hardcodedInfo = { fps: 25, duration: 21.06 };
        setVideoInfo(hardcodedInfo);
        setVideoSrc(generateVideoUrl(currentFrame.thumbnail || currentFrame.url, currentFrame.video_name));
        setInternalCurrentFrame(currentFrame);
        setHasInitialSeeked(false);
        setIsReady(false);
        setIsLoading(true);
      }
    };

    loadVideoInfo();
  }, [currentFrame?.id, isOpen]);

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
      setUseNativeVideo(false);
      
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

  // Safe seeking function with better error handling
  const safeSeekTo = (time, type = 'seconds') => {
    if (useNativeVideo && nativeVideoRef.current) {
      try {
        nativeVideoRef.current.currentTime = time;
        return true;
      } catch (error) {
        return false;
      }
    }
    
    if (!playerRef.current) {
      return false;
    }
    
    try {
      // Check if ReactPlayer is properly initialized
      if (playerRef.current && typeof playerRef.current.seekTo === 'function') {
        playerRef.current.seekTo(time, type);
        return true;
      } else {
        // Try fallback to native video if ReactPlayer is not working
        if (!useNativeVideo) {
          setUseNativeVideo(true);
        }
        return false;
      }
    } catch (error) {
      return false;
    }
  };

  // ReactPlayer event handlers
  const handleReady = () => {
    setIsReady(true);
    setIsLoading(false);
    
    // Clear loading timeout
    if (loadingTimeoutRef.current) {
      clearTimeout(loadingTimeoutRef.current);
      loadingTimeoutRef.current = null;
    }
    
    // Clear any existing video errors when player is ready
    if (videoError) {
      setVideoError(null);
    }
    
    // Log player info for debugging
    if (playerRef.current) {
      console.log('Player internal player type:', playerRef.current.getInternalPlayer()?.constructor?.name);
      console.log('Player duration:', playerRef.current.getDuration());
      console.log('Player ref methods:', Object.keys(playerRef.current));
    }
    
    // Add a small delay to ensure player is fully ready
    setTimeout(() => {
      // Seek to initial frame time when player is ready
      if (videoInfo && currentFrame && !hasInitialSeeked) {
        const initialTime = calculateTimeFromFrame(parseInt(currentFrame.frame_index), videoInfo.fps);
        console.log('Seeking to initial time:', initialTime, 'for frame:', currentFrame.frame_index);
        if (safeSeekTo(initialTime, 'seconds')) {
          setCurrentTime(initialTime);
          setHasInitialSeeked(true);
        } else {
          console.error('Failed to seek to initial time');
          setHasInitialSeeked(true); // Prevent infinite attempts
        }
      }
    }, 500); // Increased delay to ensure player is ready
  };

  // Initial seek effect when player is ready
  useEffect(() => {
    if (isReady && videoInfo && currentFrame && !hasInitialSeeked) {
      const initialTime = calculateTimeFromFrame(parseInt(currentFrame.frame_index), videoInfo.fps);
      console.log('Seeking to initial time (useEffect):', initialTime, 'for frame:', currentFrame.frame_index);
      if (safeSeekTo(initialTime, 'seconds')) {
        setCurrentTime(initialTime);
        setHasInitialSeeked(true);
      } else {
        console.error('Failed to seek to initial time in useEffect');
        setHasInitialSeeked(true); // Prevent infinite attempts
      }
    }
  }, [isReady, videoInfo, currentFrame?.frame_index, hasInitialSeeked]);

  const handleDuration = (duration) => {
    console.log('Duration loaded:', duration);
    setDuration(duration);
  };

  const handleProgress = (progress) => {
    setCurrentTime(progress.playedSeconds);
  };

  const handlePlay = () => {
    setIsPlaying(true);
  };

  const handlePause = () => {
    setIsPlaying(false);
  };

  const handleError = (error) => {
    console.error('ReactPlayer error:', error);
    console.error('Error details:', {
      message: error?.message,
      name: error?.name,
      stack: error?.stack,
      target: error?.target,
      type: error?.type
    });
    setIsLoading(false);
    
    // Try native video player as fallback
    if (!useNativeVideo) {
      console.log('ReactPlayer failed, trying native HTML5 video');
      setUseNativeVideo(true);
      return;
    }
    
    // If native video also fails, show error
    if (error && (error.message?.includes('CORS') || error.message?.includes('Failed to fetch') || 
                  error.name === 'TypeError' || error.message?.includes('blocked by CORS') ||
                  error.message?.includes('NetworkError') || error.message?.includes('net::ERR_FAILED'))) {
      setVideoError('Video cannot be played due to CORS or network restrictions. Please check server configuration.');
      setIsVideoAccessible(false);
    } else if (error?.target?.error?.code) {
      // Media error codes
      const errorCode = error.target.error.code;
      const errorMessages = {
        1: 'Video loading aborted',
        2: 'Network error occurred while loading video',
        3: 'Video decoding failed',
        4: 'Video format not supported'
      };
      setVideoError(errorMessages[errorCode] || 'Video playback error occurred');
    } else {
      setVideoError('Video playback error. The video file may be corrupted or unavailable.');
    }
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
    if (useNativeVideo && nativeVideoRef.current) {
      const video = nativeVideoRef.current;
      
      if (isPlaying) {
        video.pause();
      } else {
        const playPromise = video.play();
        if (playPromise !== undefined) {
          playPromise.catch(error => {
            console.error('Native video play failed:', error);
            // Don't set error state for play interruption
            if (!error.message.includes('interrupted')) {
              setVideoError('Failed to play video: ' + error.message);
            }
          });
        }
      }
      return;
    }
    
    if (!playerRef.current) return;

    try {
      setIsPlaying(!isPlaying);
    } catch (error) {
      console.error('Error toggling play/pause:', error);
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
    
    if (safeSeekTo(newTime, 'seconds')) {
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
    
    // Update native video volume
    if (useNativeVideo && nativeVideoRef.current) {
      nativeVideoRef.current.volume = newVolume;
    }
  };

  const skip = (seconds) => {
    const newTime = Math.max(0, Math.min(duration, currentTime + seconds));
    
    // Set user seeking flag
    setIsUserSeeking(true);
    
    if (safeSeekTo(newTime, 'seconds')) {
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

  // Native video event handlers
  const handleNativeVideoLoadedMetadata = () => {
    console.log('Native video metadata loaded');
    setIsLoading(false);
    setIsReady(true);
    if (nativeVideoRef.current) {
      setDuration(nativeVideoRef.current.duration);
      console.log('Native video duration:', nativeVideoRef.current.duration);
      
      // Seek to initial frame time for native video
      if (videoInfo && currentFrame && !hasInitialSeeked) {
        const initialTime = calculateTimeFromFrame(parseInt(currentFrame.frame_index), videoInfo.fps);
        console.log('Seeking native video to initial time:', initialTime, 'for frame:', currentFrame.frame_index);
        nativeVideoRef.current.currentTime = initialTime;
        setCurrentTime(initialTime);
        setHasInitialSeeked(true);
      }
    }
  };

  const handleNativeVideoTimeUpdate = () => {
    if (nativeVideoRef.current) {
      setCurrentTime(nativeVideoRef.current.currentTime);
    }
  };

  const handleNativeVideoPlay = () => {
    setIsPlaying(true);
  };

  const handleNativeVideoPause = () => {
    setIsPlaying(false);
  };

  const handleNativeVideoError = (error) => {
    console.error('Native video error:', error);
    setVideoError('Native video playback failed. The video may not be supported or accessible.');
    setIsLoading(false);
  };

  const handleFrameClick = (frame) => {
    if (!videoInfo) return;
    
    // Calculate time for the selected frame
    const frameTime = calculateTimeFromFrame(parseInt(frame.frame_index), videoInfo.fps);
    
    // Set user seeking flag
    setIsUserSeeking(true);
    
    // Update video time
    if (safeSeekTo(frameTime, 'seconds')) {
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
              
              {useNativeVideo && (
                <div className="video-player__fallback-notice">
                  <p>🔧 Using native HTML5 video player (ReactPlayer fallback)</p>
                </div>
              )}
              
              {!useNativeVideo ? (
                <ReactPlayer
                  ref={playerRef}
                  className="video-player__video"
                  url={videoSrc}
                  playing={isPlaying}
                  volume={volume}
                  onReady={handleReady}
                  onDuration={handleDuration}
                  onProgress={handleProgress}
                  onPlay={handlePlay}
                  onPause={handlePause}
                  onError={handleError}
                  onClick={handleVideoClick}
                  width="100%"
                  height="100%"
                  controls={false}
                  config={{
                    file: {
                      attributes: {
                        preload: 'metadata',
                        crossOrigin: 'anonymous'
                      },
                      forceHLS: false,
                      forceDASH: false,
                      forceVideo: true
                    }
                  }}
                  onBuffer={() => {
                    console.log('Video buffering...');
                    setIsLoading(true);
                  }}
                  onBufferEnd={() => {
                    console.log('Video buffer ended');
                    setIsLoading(false);
                  }}
                  onSeek={(seconds) => console.log('Video seeked to:', seconds)}
                  onLoadStart={() => {
                    console.log('Video load started');
                    setIsLoading(true);
                  }}
                  onCanPlay={() => {
                    console.log('Video can play');
                    setIsLoading(false);
                  }}
                  onCanPlayThrough={() => {
                    console.log('Video can play through');
                    setIsLoading(false);
                  }}
                />
              ) : (
                <video
                  ref={nativeVideoRef}
                  className="video-player__video"
                  src={videoSrc}
                  onLoadedMetadata={handleNativeVideoLoadedMetadata}
                  onTimeUpdate={handleNativeVideoTimeUpdate}
                  onPlay={handleNativeVideoPlay}
                  onPause={handleNativeVideoPause}
                  onError={handleNativeVideoError}
                  onClick={handleVideoClick}
                  preload="metadata"
                  crossOrigin="anonymous"
                  style={{ width: '100%', height: '100%' }}
                />
              )}
              
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
    </div>
  );
};

export default VideoPlayer;
