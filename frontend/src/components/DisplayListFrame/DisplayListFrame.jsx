import React, { useState, useEffect, useRef, useCallback } from 'react';
import VideoPlayer from '../VideoPlayer/VideoPlayer';
import FrameItem from '../FrameItem/FrameItem';
import SubmissionModal from '../SubmissionModal/SubmissionModal';
import TeamAnswerModal from '../TeamAnswerModal/TeamAnswerModal';
import ImageZoomModal from '../ImageZoomModal/ImageZoomModal';
import { useApp } from '../../contexts/AppContext';
import { useToast } from '../Toast/ToastProvider';
import { useFrameActions } from '../../hooks/useFrameActions';
import { TeamAnswerService } from '../../services/TeamAnswerService';
import { TeamTRAKEAnswerService } from '../../services/TeamTRAKEAnswerService';
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
  allTeamAnswers = [], // Add allTeamAnswers prop for validation
  allTRAKEAnswers = [], // Add allTRAKEAnswers prop
  onClearFrames, // Add callback to clear frames when viewMode changes
  activeGroup, // Add activeGroup prop
}) => {
  const [isVideoPlayerOpen, setIsVideoPlayerOpen] = useState(false);
  const [isImageZoomOpen, setIsImageZoomOpen] = useState(false);
  const [frameToZoom, setFrameToZoom] = useState(null);
  
  // Use the shared frame actions hook
  const {
    submissionModal,
    openSubmissionModal,
    closeSubmissionModal,
    handleSubmissionConfirm,
    isTeamAnswerModalOpen,
    frameToSubmit,
    handleSendFrame: hookHandleSendFrame,
    handleSubmitFrame,
    handleTeamAnswerModalClose,
    handleTeamAnswerComplete,
    submitKISAnswer,
    submitQAAnswer,
    submitTRAKEAnswer
  } = useFrameActions(queryMode, allTeamAnswers);
  
  // Debug modal states
  useEffect(() => {
    // Modal states tracking
  }, [isVideoPlayerOpen, submissionModal.isOpen, isTeamAnswerModalOpen, frameToSubmit]);
  
  // Get app context for round and queryIndex
  const { 
    round, 
    queryIndex, 
    validateQueryModeConsistency, 
    tempTrakeItems, 
    clearTempTrakeItems,
    addTempTrakeItem,
    removeTempTrakeItem,
    session
  } = useApp();
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
    // Clear frames when switching view modes to prevent data structure mismatch
    if (onClearFrames) {
      onClearFrames();
    }
    
    if (onViewModeChange) {
      onViewModeChange(newViewMode);
    }
  };

  // // Hàm mở modal xác nhận submit group TRAKE
  // const handleSubmitTrakeGroup = (frameList) => {
  //   openSubmissionModal('trake', frameList);
  // };

  // Handle push TRAKE group
  const handlePushTrakeGroup = async () => {
    console.log('🚀 handlePushTrakeGroup called');
    console.log('📊 activeGroup:', activeGroup);
    console.log('📊 tempTrakeItems:', tempTrakeItems);
    
    if (!tempTrakeItems || tempTrakeItems.length === 0) {
      toast.error('No items selected for TRAKE group');
      return;
    }

    if (!session) {
      toast.error('Session not available');
      return;
    }

    try {
      // Prepare the data for submission
      const traKeAnswers = tempTrakeItems.map(item => ({
        video_name: item.video_name,
        frame_index: item.frame_index,
        url: item.url,
        query_index: queryIndex,
        // Include activeGroup if available, otherwise backend will auto-assign
        ...(activeGroup && { group: activeGroup })
      }));

      console.log('📤 About to submit TRAKE answers:', traKeAnswers);
      console.log('📤 Each item group value:', traKeAnswers.map(item => ({ frame_index: item.frame_index, group: item.group })));

      console.log('🔥 About to call TeamTRAKEAnswerService.createBulkTRAKEAnswers...');
      
      // Submit the TRAKE group
      const response = await TeamTRAKEAnswerService.createBulkTRAKEAnswers({ items: traKeAnswers });
      
      console.log('🔥 API call completed, response:', response);
      
      // Clear temp items on success
      clearTempTrakeItems();
      
      // Show appropriate success message based on backend response
      if (response.stats) {
        const { created, skipped } = response.stats;
        if (created > 0 && skipped > 0) {
          toast.success(`Added ${created} new items to group ${response.group}, skipped ${skipped} existing items`);
        } else if (created > 0) {
          toast.success(`Successfully added ${created} items to group ${response.group}`);
        } else {
          toast.info(`All items already exist in group ${response.group}`);
        }
      } else {
        toast.success(`Successfully submitted TRAKE group with ${tempTrakeItems.length} items`);
      }
    } catch (error) {
      console.error('Error submitting TRAKE group:', error);
      // Handle specific validation errors
      if (error.message && error.message.includes('same video name')) {
        toast.error('All selected frames must be from the same video');
      } else if (error.message && error.message.includes('video name')) {
        toast.error('Video name validation failed');
      } else {
        toast.error('Failed to submit TRAKE group');
      }
    }
  };

  // Handle submit TRAKE - use submission modal for confirmation
  const handleSubmitTrake = async () => {
    if (!tempTrakeItems || tempTrakeItems.length === 0) {
      toast.error('No TRAKE items to submit');
      return;
    }

    // Convert tempTrakeItems to the format expected by submission service
    const frameList = tempTrakeItems.map(item => ({
      video_name: item.video_name,
      frame_index: item.frame_index,
      group: item.group || activeGroup
    }));

    // Use submission modal for confirmation
    submitTRAKEAnswer(frameList);
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

    // Ensure frames is a flat array for gallery view
    // Filter out any undefined, null, or non-object items
    const validFrames = frames.filter(frame => 
      frame && 
      typeof frame === 'object' && 
      frame.video_name && 
      frame.frame_index !== undefined
    );

    if (validFrames.length === 0) {
      return (
        <div className="display-frame__empty">
          <p>No valid frames found. Try performing a new search.</p>
        </div>
      );
    }

    // Gallery mode - render flat grid, pass frames directly to FrameItem
    return (
      <div className="display-frame__gallery">
        {validFrames.map((frame, index) => {
          const isChecked = queryMode === 'tra' ? isFrameInTempTrake(frame) : false;
          
          return (
            <FrameItem
              key={`gallery-${frame.video_name}-${frame.frame_index}-${index}`}
              frame={frame}
              isSelected={
                selectedFrame && 
                selectedFrame.video_name === frame.video_name && 
                parseInt(selectedFrame.frame_index) === parseInt(frame.frame_index)
              }
              onClick={handleFrameClick}
              onDoubleClick={handleFrameDoubleClick}
              onSubmit={handleSubmitFrame}
              onSend={queryMode === 'tra' ? undefined : handleSendFrame}
              onZoom={handleFrameZoom}
              showFilename={true}
              className="display-frame__item"
              isSending={sendingFrames.has(`${frame.video_name}-${frame.frame_index}`)}
              enableDrag={true}
              showCheckbox={queryMode === 'tra'}
              isChecked={isChecked}
              onCheckboxChange={handleCheckboxChange}
            />
          );
        })}
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

    // Ensure frames is array of arrays for samevideo view
    // Filter out any invalid video groups
    const validVideoGroups = frames.filter(videoFrames => 
      Array.isArray(videoFrames) && 
      videoFrames.length > 0 && 
      videoFrames.every(frame => 
        frame && 
        typeof frame === 'object' && 
        frame.video_name && 
        frame.frame_index !== undefined
      )
    );

    if (validVideoGroups.length === 0) {
      return (
        <div className="display-frame__empty">
          <p>No valid video groups found. Try performing a new search.</p>
        </div>
      );
    }

    return (
      <div className="display-frame__samevideo-gallery">
        {validVideoGroups.map((videoFrames, videoIndex) => {
          // Get video name from the first frame
          const videoName = videoFrames[0]?.video_name || `Video ${videoIndex + 1}`;

          return (
            <div 
              key={`video-${videoIndex}-${videoName}`}
              className="display-frame__video-section"
            >
              {videoIndex > 0 && <div className="display-frame__video-separator"></div>}
              <div className="display-frame__video-grid">
                {videoFrames.map((frame, frameIndex) => {
                  const isChecked = queryMode === 'tra' ? isFrameInTempTrake(frame) : false;
                  
                  return (
                    <FrameItem
                      key={`samevideo-${videoIndex}-${frame.video_name}-${frame.frame_index}-${frameIndex}`}
                      frame={frame}
                      isSelected={
                        selectedFrame && 
                        selectedFrame.video_name === frame.video_name && 
                        parseInt(selectedFrame.frame_index) === parseInt(frame.frame_index)
                      }
                      onClick={handleFrameClick}
                      onDoubleClick={handleFrameDoubleClick}
                      onSubmit={handleSubmitFrame}
                      onSend={queryMode === 'tra' ? undefined : handleSendFrame}
                      onZoom={handleFrameZoom}
                      showFilename={true}
                      className="display-frame__item"
                      isSending={sendingFrames.has(`${frame.video_name}-${frame.frame_index}`)}
                      enableDrag={true}
                      showCheckbox={queryMode === 'tra'}
                      isChecked={isChecked}
                      onCheckboxChange={handleCheckboxChange}
                    />
                  );
                })}
              </div>
            </div>
          );
        })}
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

  // Check if a frame is in temp TRAKE items
  const isFrameInTempTrake = useCallback((frame) => {
    return tempTrakeItems.some(item => 
      item.video_name === frame.video_name && 
      item.frame_index === frame.frame_index
    );
  }, [tempTrakeItems]);

  // Handle checkbox change for TRAKE mode
  const handleCheckboxChange = useCallback((frame, isChecked) => {
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
        
        {/* TRAKE Actions - only show in TRA mode when temp items exist */}
        {queryMode === 'tra' && tempTrakeItems && tempTrakeItems.length > 0 && (
          <div className="display-frame__trake-actions">
            <button
              className="display-frame__push-trake-btn"
              onClick={handlePushTrakeGroup}
              title={`Push TRAKE group with ${tempTrakeItems.length} items`}
            >
              <img src="/assets/team.svg" alt="Team" />
              <span>TEAM ({tempTrakeItems.length})</span>
            </button>
            <button
              className="display-frame__submit-trake-btn"
              onClick={handleSubmitTrake}
              title={`Submit TRAKE with ${tempTrakeItems.length} items`}
            >
              <img src="/assets/send.svg" alt="Submit" />
              <span>SUBMIT ({tempTrakeItems.length})</span>
            </button>
          </div>
        )}
        
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
          allTRAKEAnswers={allTRAKEAnswers}
          searchResults={frames} // Pass search results for TRAKE mode
        />
      )}

      <SubmissionModal
        isOpen={submissionModal.isOpen}
        onClose={closeSubmissionModal}
        onConfirm={handleSubmissionConfirm}
        submissionType={submissionModal.type}
        frameData={submissionModal.frameData}
        qaText={submissionModal.qaText}
        isSubmitting={submissionModal.isSubmitting}
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
