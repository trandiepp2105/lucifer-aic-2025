import React, { useState, useEffect } from 'react';
import FrameItem from '../FrameItem/FrameItem';
import './SubmissionModal.scss';

const SubmissionModal = ({ 
  isOpen, 
  onClose, 
  onConfirm, 
  submissionType, // 'kis', 'qa', 'trake'
  frameData, // For KIS/QA: single frame object, For TRAKE: array of frames
  qaText = '', // For QA submission
  isSubmitting = false,
  onRemoveTrakeItem // Callback to remove a TRAKE item
}) => {
  const [localQAText, setLocalQAText] = useState(qaText || '');
  const [localFrameData, setLocalFrameData] = useState(frameData);

  useEffect(() => {
    if (isOpen && submissionType === 'qa') {
      setLocalQAText(qaText || '');
    }
  }, [isOpen, submissionType, qaText]);

  useEffect(() => {
    setLocalFrameData(frameData);
  }, [frameData]);

  if (!isOpen) return null;

  const handleBackdropClick = (e) => {
    if (e.target === e.currentTarget && !isSubmitting) {
      onClose();
    }
  };

  const handleConfirm = () => {
    if (!isSubmitting && onConfirm) {
      if (submissionType === 'qa') {
        onConfirm(localQAText);
      } else {
        onConfirm();
      }
    }
  };

  const handleCancel = () => {
    if (!isSubmitting && onClose) {
      onClose();
    }
  };

  const getSubmissionTitle = () => {
    switch (submissionType) {
      case 'kis':
        return 'Confirm KIS Submission';
      case 'qa':
        return 'Confirm QA Submission';
      case 'trake':
        return 'Confirm TRAKE Submission';
      default:
        return 'Confirm Submission';
    }
  };

  const getSubmissionMessage = () => {
    switch (submissionType) {
      case 'kis':
        return 'Are you sure you want to submit this frame for KIS answer?';
      case 'qa':
        return 'Are you sure you want to submit this frame with QA text?';
      case 'trake':
        return `Are you sure you want to submit ${Array.isArray(localFrameData) ? localFrameData.length : 1} frame(s) for TRAKE answer?`;
      default:
        return 'Are you sure you want to submit this answer?';
    }
  };

  const handleRemoveTrakeItem = (frameToRemove) => {
    if (onRemoveTrakeItem) {
      onRemoveTrakeItem(frameToRemove);
    }
    // Update local state
    setLocalFrameData(prevData => {
      if (Array.isArray(prevData)) {
        return prevData.filter(frame => 
          !(frame.video_name === frameToRemove.video_name && 
            frame.frame_index === frameToRemove.frame_index)
        );
      }
      return prevData;
    });
  };

  const renderFramePreview = () => {
    if (submissionType === 'trake' && Array.isArray(localFrameData)) {
      // For TRAKE, show horizontal scrollable list of all frames
      return (
        <div className="submission-modal__trake-frames">
          <div className="submission-modal__trake-frames-label">
            Frames to submit ({localFrameData.length} total):
          </div>
          <div className="submission-modal__trake-frames-list">
            {localFrameData.map((frame, index) => (
              <div key={`${frame.video_name}-${frame.frame_index}`} className="submission-modal__trake-frame-item">
                <button
                  className="submission-modal__trake-frame-delete"
                  onClick={() => handleRemoveTrakeItem(frame)}
                  disabled={isSubmitting}
                  title="Remove this frame"
                  type="button"
                >
                  ×
                </button>
                <FrameItem
                  frame={frame}
                  size="small"
                  showFilename={true}
                  className="submission-modal__frame"
                />
                <div className="submission-modal__frame-number">#{index + 1}</div>
              </div>
            ))}
          </div>
        </div>
      );
    } else if (localFrameData && !Array.isArray(localFrameData)) {
      // For KIS/QA, show the single frame
      return (
        <div className="submission-modal__single-frame">
          <FrameItem
            frame={localFrameData}
            size="medium"
            showFilename={true}
            className="submission-modal__frame"
          />
        </div>
      );
    }
    return null;
  };

  const renderQAText = () => {
    if (submissionType === 'qa') {
      return (
        <div className="submission-modal__qa-section">
          <div className="submission-modal__qa-label">QA Text:</div>
          <textarea
            className="submission-modal__qa-input"
            value={localQAText}
            onChange={e => setLocalQAText(e.target.value)}
            rows={3}
            disabled={isSubmitting}
            placeholder="Enter your QA answer here..."
            style={{ width: '100%', resize: 'vertical', marginTop: '0.5rem' }}
          />
        </div>
      );
    }
    return null;
  };

  return (
    <div className="submission-modal__backdrop" onClick={handleBackdropClick}>
      <div className={`submission-modal submission-modal--${submissionType}`}>
        <div className="submission-modal__header">
          <h3 className="submission-modal__title">{getSubmissionTitle()}</h3>
          <button 
            className="submission-modal__close"
            onClick={handleCancel}
            disabled={isSubmitting}
            type="button"
          >
            ×
          </button>
        </div>
        
        <div className="submission-modal__content">
          <p className="submission-modal__message">{getSubmissionMessage()}</p>
          
          {renderFramePreview()}
          {renderQAText()}
        </div>
        
        <div className="submission-modal__actions">
          <button 
            className="submission-modal__cancel"
            onClick={handleCancel}
            disabled={isSubmitting}
            type="button"
          >
            Cancel
          </button>
          <button 
            className={`submission-modal__confirm ${isSubmitting ? 'submission-modal__loading' : ''}`}
            onClick={handleConfirm}
            disabled={isSubmitting}
            type="button"
          >
            {isSubmitting ? (
              <>
                <span className="submission-modal__spinner">⟳</span>
                Submitting...
              </>
            ) : (
              'Submit Answer'
            )}
          </button>
        </div>
      </div>
    </div>
  );
};

export default SubmissionModal;
