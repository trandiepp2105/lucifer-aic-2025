import React, { useState, useEffect, useRef } from 'react';
import VideoPlayer from '../VideoPlayer/VideoPlayer';
import FrameItem from '../FrameItem/FrameItem';
import SubmissionModal from '../SubmissionModal/SubmissionModal';
import TeamAnswerModal from '../TeamAnswerModal/TeamAnswerModal';
import ImageZoomModal from '../ImageZoomModal/ImageZoomModal';
import { useApp } from '../../contexts/AppContext';
import { useToast } from '../Toast/ToastProvider';
import { useFrameActions } from '../../hooks/useFrameActions';
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
  availableStages = [1],
  queryMode = 'kis', // Add queryMode prop
  onSend, // Add onSend prop
  sendingFrames = new Set(), // Add sendingFrames prop
  allTeamAnswers = [] // Add allTeamAnswers prop for validation
}) => {
  const [isVideoPlayerOpen, setIsVideoPlayerOpen] = useState(false);
  const [isImageZoomOpen, setIsImageZoomOpen] = useState(false);
  const [frameToZoom, setFrameToZoom] = useState(null);
  
  // Use the shared frame actions hook
  const {
    isSubmissionModalOpen,
    isTeamAnswerModalOpen,
    frameToSubmit,
    handleSendFrame: hookHandleSendFrame,
    handleSubmitFrame,
    handleTeamAnswerModalClose,
    handleTeamAnswerComplete,
    handleSubmissionModalClose,
    handleSubmissionComplete
  } = useFrameActions(queryMode, allTeamAnswers);
  
  // Debug modal states
  useEffect(() => {
    // Modal states tracking
  }, [isVideoPlayerOpen, isSubmissionModalOpen, isTeamAnswerModalOpen, frameToSubmit]);
  
  // Get app context for round and queryIndex
  const { round, queryIndex, validateQueryModeConsistency } = useApp();
  const toast = useToast();
  
  // Debug queryMode prop
  useEffect(() => {
    // QueryMode tracking
  }, [queryMode]);
  
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

  const handleFrameZoom = (frame) => {
    setFrameToZoom(frame);
    setIsImageZoomOpen(true);
  };

  const handleCloseImageZoom = () => {
    setIsImageZoomOpen(false);
    setFrameToZoom(null);
  };

  const handleSendFrame = (frame) => {
    // Use onSend prop if available, otherwise use hook implementation
    if (onSend) {
      onSend(frame);
    } else {
      // Use hook implementation for backward compatibility
      hookHandleSendFrame(frame);
    }
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
            onZoom={handleFrameZoom}
            showFilename={true}
            className="display-frame__item"
            isSending={sendingFrames.has(`${frame.video_name}-${frame.frame_index}`)}
            enableDrag={true}
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
                    onZoom={handleFrameZoom}
                    showFilename={true}
                    className="display-frame__item"
                    isSending={sendingFrames.has(`${frame.video_name}-${frame.frame_index}`)}
                    enableDrag={true}
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
            {(Array.isArray(availableStages) ? availableStages : Array.from({ length: availableStages }, (_, i) => i + 1)).map((stage) => (
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

      {isVideoPlayerOpen && (
        <VideoPlayer
          isOpen={isVideoPlayerOpen}
          onClose={handleCloseVideoPlayer}
          currentFrame={selectedFrame}
          onFrameSelect={onFrameSelect}
          onSubmit={handleSubmitFrame}
          onSend={handleSendFrame}
          sendingFrames={sendingFrames}
          allTeamAnswers={allTeamAnswers}
        />
      )}

      <SubmissionModal
        isOpen={isSubmissionModalOpen}
        onClose={handleSubmissionModalClose}
        onSubmit={handleSubmissionComplete}
        frame={frameToSubmit}
        queryMode={queryMode}
      />

      <TeamAnswerModal
        isOpen={isTeamAnswerModalOpen}
        onClose={handleTeamAnswerModalClose}
        onSubmit={handleTeamAnswerComplete}
        frame={frameToSubmit}
        allTeamAnswers={allTeamAnswers}
      />

      <ImageZoomModal
        isOpen={isImageZoomOpen}
        onClose={handleCloseImageZoom}
        imageUrl={frameToZoom?.url}
        imageAlt={frameToZoom ? `Frame ${frameToZoom.video_name}-${frameToZoom.frame_index}` : ''}
        frame={frameToZoom}
      />
    </div>
  );
};

export default DisplayListFrame;
