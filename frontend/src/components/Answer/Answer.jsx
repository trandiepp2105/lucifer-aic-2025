import React, { useState, useEffect, useCallback } from 'react';
import ConfirmationModal from '../ConfirmationModal';
import FrameItem from '../FrameItem/FrameItem';
import { useToast } from '../Toast/ToastProvider';
import { useApp } from '../../contexts/AppContext';

import './Answer.scss';

const Answer = ({ 
  round = 'prelims',
  isVisible = true, 
  onFramesUpdate = () => {}, 
  allAnswers = [], // Get from props instead of local state
  setAllAnswers,  // Setter from parent
  refreshAnswers = () => {} // Refresh function from parent
}) => {

  const { queryIndex } = useApp();
  const toast = useToast();
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [answerToDelete, setAnswerToDelete] = useState(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // Effect to fetch answers when component becomes visible or dependencies change
  useEffect(() => {
    if (isVisible) {
      refreshAnswers();
    }
  }, [isVisible, round, queryIndex, refreshAnswers]);

  // Filter answers based on current queryIndex and round
  const getFilteredAnswers = useCallback(() => {
    return allAnswers.filter(answer => 
      answer.query_index === queryIndex && 
      answer.round === round
    );
  }, [allAnswers, queryIndex, round]);

  const filteredAnswers = getFilteredAnswers();

  const handleDelete = (answer) => {
    setAnswerToDelete(answer);
    setIsDeleteModalOpen(true);
  };

  const confirmDelete = async () => {
    if (!answerToDelete) return;

    setIsDeleting(true);
    try {
      // Import service here to avoid import issues
      const { AnswerService } = await import('../../services');
      
      const result = await AnswerService.deleteAnswer(answerToDelete.id);
      
      if (result.success) {
        // Remove answer from local state
        setAllAnswers(prevAnswers => 
          prevAnswers.filter(answer => answer.id !== answerToDelete.id)
        );
        toast.success('Answer deleted successfully', 500);
      } else {
        toast.error(result.error || 'Failed to delete answer', 500);
      }
    } catch (error) {
      toast.error('Failed to delete answer', 500);
    } finally {
      setIsDeleting(false);
      setIsDeleteModalOpen(false);
      setAnswerToDelete(null);
    }
  };

  const cancelDelete = () => {
    setIsDeleteModalOpen(false);
    setAnswerToDelete(null);
  };

  return (
    <div className="answer">
      <div className="answer__header">
        <h2 className="answer__title">Final Answers</h2>
        <div className="answer__info">
          <span className="answer__count">{filteredAnswers.length} answer(s)</span>
          <span className="answer__query">Query #{queryIndex}</span>
          <span className="answer__round">{round.charAt(0).toUpperCase() + round.slice(1)}</span>
        </div>
      </div>

      <div className="answer__content">
        {filteredAnswers.length === 0 ? (
          <div className="answer__empty">
            <p>No final answers found for this query.</p>
          </div>
        ) : (
          <div className="answer__list">
            {filteredAnswers.map((answer, index) => (
              <div key={answer.id} className="answer__item">
                <div className="answer__item-header">
                  <span className="answer__item-index">#{index + 1}</span>
                  <span className="answer__item-timestamp">
                    {new Date(answer.created_at).toLocaleString()}
                  </span>
                </div>
                
                <FrameItem
                  key={`${answer.id}-${answer.frame_index}`}
                  imageUrl={answer.url}
                  frameIndex={answer.frame_index}
                  isSelected={false}
                  onClick={() => {}}
                  videoName={answer.video_name}
                  showActions={true}
                  showVideoName={true}
                  onDelete={() => handleDelete(answer)}
                  customActions={[]}
                />
                
                {answer.qa && (
                  <div className="answer__item-qa">
                    <strong>Q&A:</strong> {answer.qa}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      <ConfirmationModal
        isOpen={isDeleteModalOpen}
        onConfirm={confirmDelete}
        onCancel={cancelDelete}
        title="Delete Answer"
        message={`Are you sure you want to delete this answer?`}
        confirmText="Delete"
        cancelText="Cancel"
        isLoading={isDeleting}
        loadingText="Deleting..."
      />
    </div>
  );
};

export default Answer;
