import React, { useState, useEffect } from 'react';
import FrameItem from '../FrameItem/FrameItem';
import { useApp } from '../../contexts/AppContext';
import { AnswerService } from '../../services/AnswerService';
import { useToast } from '../Toast/ToastProvider';
import './SubmissionModal.scss';

const SubmissionModal = ({ 
  isOpen, 
  onClose, 
  onSubmit, 
  frame
}) => {
  const { round, queryMode, queryIndex } = useApp();
  const toast = useToast();
  const [answer, setAnswer] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setAnswer('');
    }
  }, [isOpen]);

  const handleSubmit = async () => {
    if (!frame) {
      toast.error('No frame selected');
      return;
    }

    setIsSubmitting(true);

    try {
      // Prepare answer data according to backend requirements
      const answerData = {
        video_name: frame.video_name,
        frame_index: frame.frame_index,
        url: frame.url,
        round: round,
      };

      // Add query_index only for prelims round
      if (round === 'prelims') {
        answerData.query_index = queryIndex;
      }

      // Add QA text only for Q&A mode
      if (queryMode === 'qa' && answer.trim()) {
        answerData.qa = answer.trim();
      }

      // Submit to backend
      const response = await AnswerService.createAnswer(answerData);

      if (response.success) {
        toast.success('Answer submitted successfully!');
        
        // Call parent onSubmit callback if provided
        if (onSubmit) {
          onSubmit({
            frame,
            answer: queryMode === 'qa' ? answer : null,
            answerData: response.data
          });
        }
        
        onClose();
      } else {
        toast.error(`Failed to submit answer: ${response.error}`);
      }
    } catch (error) {
      toast.error('Error submitting answer');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCancel = () => {
    setAnswer('');
    onClose();
  };

  const handleBackdropClick = (e) => {
    if (e.target === e.currentTarget) {
      handleCancel();
    }
  };

  if (!isOpen || !frame) {
    return null;
  }

  return (
    <div className="submission-modal" onClick={handleBackdropClick}>
      <div className="submission-modal__content">
        <div className="submission-modal__header">
          <h3 className="submission-modal__title">Submit Answer</h3>
          <button 
            className="submission-modal__close"
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

        <div className="submission-modal__body">
          <div className="submission-modal__frame">
            <FrameItem 
              frame={frame}
              isSelected={false}
              showFilename={true}
              size="large"
              className="submission-modal__frame-item"
            />
          </div>

          {/* <div className="submission-modal__info">
            <p><strong>Round:</strong> {round}</p>
            {round === 'prelims' && (
              <p><strong>Query Index:</strong> {queryIndex}</p>
            )}
            <p><strong>Mode:</strong> {queryMode.toUpperCase()}</p>
          </div> */}

          {queryMode === 'qa' && (
            <div className="submission-modal__answer">
              <label htmlFor="answer-input" className="submission-modal__label">
                Your Answer:
              </label>
              <textarea
                id="answer-input"
                className="submission-modal__textarea"
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                placeholder="Enter your answer here..."
                rows={3}
                disabled={isSubmitting}
              />
            </div>
          )}
        </div>

        <div className="submission-modal__footer">
          <button 
            className="submission-modal__button submission-modal__button--cancel"
            onClick={handleCancel}
            disabled={isSubmitting}
          >
            Cancel
          </button>
          <button 
            className="submission-modal__button submission-modal__button--submit"
            onClick={handleSubmit}
            disabled={isSubmitting}
          >
            {isSubmitting ? 'Submitting...' : 'Submit'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default SubmissionModal;
