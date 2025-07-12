import React, { useState, useEffect, useCallback, useRef } from 'react';
import FrameItem from '../FrameItem/FrameItem';
import { useApp } from '../../contexts/AppContext';
import { useToast } from '../Toast/ToastProvider';
import './TeamAnswerModal.scss';

const TeamAnswerModal = ({ 
  isOpen, 
  onClose, 
  onSubmit, 
  frame,
  allTeamAnswers = [], // Add allTeamAnswers prop
  isEditMode = false  // Add edit mode prop
}) => {
  const { round, queryIndex } = useApp();
  const toast = useToast();
  const modalRef = useRef(null);
  const textareaRef = useRef(null);
  const [qaText, setQaText] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Auto-fill QA text when modal opens
  useEffect(() => {
    if (isOpen) {
      if (isEditMode && frame && frame.qa) {
        // In edit mode, use the current QA text from the frame
        setQaText(frame.qa || '');
      } else {
        // In create mode, find existing team answers for current query index
        const relevantAnswers = allTeamAnswers.filter(answer => 
          answer.query_index === queryIndex && answer.round === round
        );
        
        if (relevantAnswers.length > 0) {
          // Use QA from first team answer as default
          const defaultQA = relevantAnswers[0].qa || '';
          setQaText(defaultQA);
        } else {
          setQaText('');
        }
      }
    }
  }, [isOpen, allTeamAnswers, queryIndex, round, isEditMode, frame]);

  // Focus modal when it opens to ensure it receives keyboard events
  useEffect(() => {
    if (isOpen && modalRef.current) {
      modalRef.current.focus();
    }
  }, [isOpen]);

  // Focus textarea and move cursor to end when modal opens or text changes
  useEffect(() => {
    if (isOpen && textareaRef.current) {
      // Small delay to ensure modal is fully rendered
      setTimeout(() => {
        if (textareaRef.current) { // Check again in timeout
          textareaRef.current.focus();
          // Move cursor to end of text
          const length = qaText.length;
          textareaRef.current.setSelectionRange(length, length);
        }
      }, 100);
    }
  }, [isOpen]); // Only trigger when modal opens, not when text changes

  const handleSubmit = useCallback(async () => {
    if (!frame) {
      toast.error('No frame selected');
      return;
    }

    if (!qaText.trim()) {
      toast.error('Please enter Q&A text');
      return;
    }

    setIsSubmitting(true);

    try {
      // Call the onSubmit callback with QA data
      if (onSubmit) {
        await onSubmit({ qaText: qaText.trim() });
      }
    } catch (error) {
      console.error('Error submitting team answer:', error);
      toast.error('An error occurred while submitting team answer', 4000);
    } finally {
      setIsSubmitting(false);
    }
  }, [frame, qaText, onSubmit, toast]);

  // Handle Enter key to submit and block all other Enter behaviors
  useEffect(() => {
    const handleKeyDown = (e) => {
      // Only handle if modal is open and event is within modal
      if (!isOpen || !modalRef.current) return;
      
      // Check if the event target is within our modal
      if (!modalRef.current.contains(e.target)) return;
      
      if (e.key === 'Enter' && !e.shiftKey) {
        // Prevent default behavior and stop propagation
        e.preventDefault();
        e.stopPropagation();
        
        // Only submit if not already submitting and QA text is not empty
        if (!isSubmitting && qaText.trim()) {
          handleSubmit();
        }
      }
    };

    if (isOpen && modalRef.current) {
      // Only add listener to the modal element, not document
      modalRef.current.addEventListener('keydown', handleKeyDown, true);
    }

    return () => {
      if (modalRef.current) {
        modalRef.current.removeEventListener('keydown', handleKeyDown, true);
      }
    };
  }, [isOpen, isSubmitting, qaText, handleSubmit]);

  const handleCancel = () => {
    setQaText('');
    onClose();
  };

  const handleBackdropClick = (e) => {
    if (e.target === e.currentTarget) {
      handleCancel();
    }
  };

  const handleModalKeyDown = (e) => {
    // Only handle Enter key within this modal
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      e.stopPropagation();
      
      if (!isSubmitting && qaText.trim()) {
        handleSubmit();
      }
    }
  };

  if (!isOpen || !frame) {
    return null;
  }

  return (
    <div 
      ref={modalRef}
      className="team-answer-modal" 
      onClick={handleBackdropClick} 
      onKeyDown={handleModalKeyDown} 
      tabIndex={-1}
    >
      <div className="team-answer-modal__content" tabIndex={-1}>
        <div className="team-answer-modal__header">
          <h3 className="team-answer-modal__title">
            {isEditMode ? 'Edit Team Answer' : 'Send Team Answer'}
          </h3>
          <button 
            className="team-answer-modal__close"
            onClick={handleCancel}
            aria-label="Close modal"
            disabled={isSubmitting}
          >
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>

        <div className="team-answer-modal__body">
          <div className="team-answer-modal__frame">
            <FrameItem 
              frame={frame}
              isSelected={false}
              showFilename={true}
              size="large"
              className="team-answer-modal__frame-item"
            />
          </div>

          <div className="team-answer-modal__answer">
            <label htmlFor="qa-input" className="team-answer-modal__label">
              Q&A Text:
            </label>
            <textarea
              ref={textareaRef}
              id="qa-input"
              className="team-answer-modal__textarea"
              value={qaText}
              onChange={(e) => setQaText(e.target.value)}
              placeholder="Enter your Q&A text here..."
              rows={3}
              disabled={isSubmitting}
            />
          </div>
        </div>

        <div className="team-answer-modal__footer">
          <button 
            className="team-answer-modal__button team-answer-modal__button--cancel"
            onClick={handleCancel}
            disabled={isSubmitting}
          >
            Cancel
          </button>
          <button 
            className="team-answer-modal__button team-answer-modal__button--submit"
            onClick={handleSubmit}
            disabled={isSubmitting || !qaText.trim()}
          >
            {isSubmitting ? (isEditMode ? 'Updating...' : 'Sending...') : (isEditMode ? 'Update' : 'Send')}
          </button>
        </div>
      </div>
    </div>
  );
};

export default TeamAnswerModal;
