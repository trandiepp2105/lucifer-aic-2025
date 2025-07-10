import React, { useState, useEffect, useRef } from 'react';
import VideoPlayer from '../VideoPlayer/VideoPlayer';
import FrameItem from '../FrameItem/FrameItem';
import SubmissionModal from '../SubmissionModal/SubmissionModal';
import { useApp } from '../../contexts/AppContext';
import { useToast } from '../Toast/ToastProvider';
import { TeamAnswerService } from '../../services/TeamAnswerService';
import './DisplayListFrame.scss';

const DisplayListFrame = ({ 
  onFrameSelect, 
  selectedFrame, 
  onStageChange, 
  frames = [], 
  currentStage = 1, 
  viewMode = 'gallery', 
  onViewModeChange, 
  availableStages = 1,
  queryMode = 'kis', // Add queryMode prop
  onSend, // Add onSend prop
  sendingFrames = new Set() // Add sendingFrames prop
}) => {
  const [isVideoPlayerOpen, setIsVideoPlayerOpen] = useState(false);
  const [isSubmissionModalOpen, setIsSubmissionModalOpen] = useState(false);
  const [frameToSubmit, setFrameToSubmit] = useState(null);
  
  // Get app context for round and queryIndex
  const { round, queryIndex } = useApp();
  const toast = useToast();
  
  // Ref for content container to control scrolling (where the actual scrollbar is)
  const contentRef = useRef(null);

  // Auto-scroll to top when new data arrives
  useEffect(() => {
    if (frames.length > 0 && contentRef.current) {
      // Smooth scroll to top when new search results arrive
      contentRef.current.scrollTo({
        top: 0,
        behavior: 'smooth'
      });
    }
  }, [frames]); // Trigger when frames data changes

  const handleFrameClick = (frame) => {
    onFrameSelect(frame);
  };

  const handleFrameDoubleClick = (frame) => {
    setIsVideoPlayerOpen(true);
  };

  const handleCloseVideoPlayer = () => {
    setIsVideoPlayerOpen(false);
  };

  const handleSubmitFrame = (frame) => {
    setFrameToSubmit(frame);
    setIsSubmissionModalOpen(true);
  };

  const handleSendFrame = (frame) => {
    // Use onSend prop if available, otherwise use internal implementation
    if (onSend) {
      onSend(frame);
    } else {
      // Fallback to internal implementation for backward compatibility
      handleSendFrameInternal(frame);
    }
  };

  const handleSendFrameInternal = async (frame) => {
    const frameId = `${frame.video_name}-${frame.frame_index}`;
    
    try {
      // Show loading toast
      toast.info('Sending frame...', 2000);
      
      // Prepare team answer data
      const teamAnswerData = {
        video_name: frame.video_name,
        frame_index: frame.frame_index,
        url: frame.url,
        round: round,
        query_index: round === 'final' ? 0 : (queryIndex || 1) // Use 0 for final round, otherwise use queryIndex
      };

      // Call API to create team answer
      const result = await TeamAnswerService.createTeamAnswer(teamAnswerData);
      
      if (result.success) {
        toast.success('Frame sent successfully!', 3000);
      } else {
        // Handle different error types
        if (result.error && result.error.includes('already exists')) {
          toast.warning('This frame has already been sent for this query', 3000);
        } else {
          toast.error(result.error || 'Failed to send frame', 4000);
        }
      }
    } catch (error) {
      console.error('Error sending frame:', error);
      toast.error('An error occurred while sending frame', 4000);
    }
  };

  const handleSubmissionModalClose = () => {
    setIsSubmissionModalOpen(false);
    setFrameToSubmit(null);
  };

  const handleSubmissionComplete = (submissionData) => {
    // TODO: Handle submission logic here
    // You can add API calls or other submission logic
  };

  const handleStageChange = (newStage) => {
    if (newStage >= 1 && newStage <= availableStages) {
      if (onStageChange) {
        onStageChange(newStage);
      }
    }
  };

  const handleViewModeChange = (newViewMode) => {
    if (onViewModeChange) {
      onViewModeChange(newViewMode);
    }
  };

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (event) => {
      if (event.ctrlKey && event.key === 'ArrowLeft') {
        event.preventDefault();
        // Di chuyển vòng: từ stage 1 quay về stage cuối cùng
        const newStage = currentStage === 1 ? availableStages : currentStage - 1;
        if (newStage >= 1 && newStage <= availableStages && onStageChange) {
          onStageChange(newStage);
        }
      } else if (event.ctrlKey && event.key === 'ArrowRight') {
        event.preventDefault();
        // Di chuyển vòng: từ stage cuối quay về stage 1
        const newStage = currentStage === availableStages ? 1 : currentStage + 1;
        if (newStage >= 1 && newStage <= availableStages && onStageChange) {
          onStageChange(newStage);
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [currentStage, availableStages, onStageChange]); // Include all dependencies



  const renderGalleryView = () => {
    if (!frames || frames.length === 0) {
      return (
        <div className="display-frame__empty">
          <p>No frames found. Try performing an OCR search.</p>
        </div>
      );
    }

    // Gallery mode - render flat grid, pass frames directly to FrameItem
    return (
      <div className="display-frame__gallery">
        {frames.map((frame, index) => (
          <FrameItem
            key={`${frame.video_name}-${frame.frame_index}-${index}`}
            frame={frame}
            isSelected={
              selectedFrame && 
              selectedFrame.video_name === frame.video_name && 
              parseInt(selectedFrame.frame_index) === parseInt(frame.frame_index)
            }
            onClick={handleFrameClick}
            onDoubleClick={handleFrameDoubleClick}
            onSubmit={handleSubmitFrame}
            onSend={handleSendFrame}
            showFilename={true}
            className="display-frame__item"
            isSending={sendingFrames.has(`${frame.video_name}-${frame.frame_index}`)}
          />
        ))}
      </div>
    );
  };

  const renderSameVideoView = () => {
    if (!frames || frames.length === 0) {
      return (
        <div className="display-frame__empty">
          <p>No frames found. Try performing an OCR search.</p>
        </div>
      );
    }

    return (
      <div className="display-frame__samevideo-gallery">
        {frames.map((videoFrames, videoIndex) => {
          // videoFrames is an array of frames from the same video
          if (!Array.isArray(videoFrames) || videoFrames.length === 0) {
            return null;
          }

          // Get video name from the first frame
          const videoName = videoFrames[0]?.video_name || `Video ${videoIndex + 1}`;

          return (
            <div key={videoName} className="display-frame__video-section">
              {videoIndex > 0 && <div className="display-frame__video-separator"></div>}
              <div className="display-frame__video-grid">
                {videoFrames.map((frame, frameIndex) => (
                  <FrameItem
                    key={`${frame.video_name}-${frame.frame_index}-${frameIndex}`}
                    frame={frame}
                    isSelected={
                      selectedFrame && 
                      selectedFrame.video_name === frame.video_name && 
                      parseInt(selectedFrame.frame_index) === parseInt(frame.frame_index)
                    }
                    onClick={handleFrameClick}
                    onDoubleClick={handleFrameDoubleClick}
                    onSubmit={handleSubmitFrame}
                    onSend={handleSendFrame}
                    showFilename={true}
                    className="display-frame__item"
                    isSending={sendingFrames.has(`${frame.video_name}-${frame.frame_index}`)}
                  />
                ))}
              </div>
            </div>
          );
        }).filter(Boolean)} {/* Filter out null items */}
      </div>
    );
  };

  const renderTimelineView = () => (
    <div className="display-frame__timeline">
      <div className="display-frame__timeline-placeholder">
        <h3>Timeline View</h3>
        <p>Timeline view implementation will be added here</p>
        <p>This will show frames in a horizontal timeline format</p>
      </div>
    </div>
  );

  return (
    <div className="display-frame">
      <div className="display-frame__header">
        <div className="display-frame__stage-selector">
          <div className="display-frame__stages">
            {Array.from({ length: availableStages }, (_, i) => i + 1).map((stage) => (
              <button
                key={stage}
                className={`display-frame__stage ${currentStage === stage ? 'display-frame__stage--active' : ''}`}
                onClick={() => handleStageChange(stage)}
              >
                Stage {stage}
              </button>
            ))}
          </div>
        </div>
        <div className="display-frame__controls">
          <button
            className={`display-frame__view-btn ${viewMode === 'gallery' ? 'display-frame__view-btn--active' : ''}`}
            onClick={() => handleViewModeChange('gallery')}
          >
            <span>⊞</span> Gallery
          </button>
          <button
            className={`display-frame__view-btn ${viewMode === 'samevideo' ? 'display-frame__view-btn--active' : ''}`}
            onClick={() => handleViewModeChange('samevideo')}
          >
            <span>▬</span> SameVideo
          </button>
        </div>
      </div>
      
      <div className="display-frame__content" ref={contentRef}>
        {viewMode === 'gallery' && renderGalleryView()}
        {viewMode === 'samevideo' && renderSameVideoView()}
        {viewMode === 'timeline' && renderTimelineView()}
      </div>

      <VideoPlayer
        isOpen={isVideoPlayerOpen}
        onClose={handleCloseVideoPlayer}
        currentFrame={selectedFrame}
        onFrameSelect={onFrameSelect}
      />

      <SubmissionModal
        isOpen={isSubmissionModalOpen}
        onClose={handleSubmissionModalClose}
        onSubmit={handleSubmissionComplete}
        frame={frameToSubmit}
        queryMode={queryMode}
      />
    </div>
  );
};

export default DisplayListFrame;
