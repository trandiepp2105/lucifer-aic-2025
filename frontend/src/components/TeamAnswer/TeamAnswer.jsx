import React, { useEffect, useRef, useState, useCallback } from 'react';
import FrameItem from '../FrameItem/FrameItem';
import ConfirmationModal from '../ConfirmationModal';
import { useApp } from '../../contexts/AppContext';
import { useToast } from '../Toast/ToastProvider';
import { TeamAnswerService } from '../../services';
import './TeamAnswer.scss';

const TeamAnswer = ({ selectedFrame, isVisible, onToggle, onFrameSelect, onFrameDoubleClick, onSubmit }) => {
  const selectedFrameRef = useRef(null);
  const teamAnswerRef = useRef(null);
  const renderCountRef = useRef(0);
  renderCountRef.current += 1;
  
  console.log('TeamAnswer component render #', renderCountRef.current, 'isVisible:', isVisible);
  
  const [allTeamAnswers, setAllTeamAnswers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [deletingFrames, setDeletingFrames] = useState(new Set());
  const [deletingAll, setDeletingAll] = useState(false);
  const [showDeleteAllModal, setShowDeleteAllModal] = useState(false);
  
  // Get app context for queryIndex and round
  const { queryIndex, round } = useApp();
  const toast = useToast();

  // Fetch team answers from server
  const fetchTeamAnswers = async () => {
    try {
      setLoading(true);
      
      console.log('Fetching all team answers from server...');
      
      // Get all team answers without any query params
      const response = await TeamAnswerService.getTeamAnswers();

      console.log('All team answers response:', response);

      if (response.success) {
        console.log('All team answers data:', response.data);
        console.log('All team answers array:', response.data.data);
        setAllTeamAnswers(response.data.data || []);
      } else {
        console.error('Failed to fetch all team answers:', response.error);
        toast.error('Failed to load team answers', 500);
      }
    } catch (error) {
      console.error('Error fetching all team answers:', error);
      toast.error('Error loading team answers', 500);
    } finally {
      setLoading(false);
    }
  };

  // Filter team answers based on current queryIndex and round
  const getFilteredTeamAnswers = useCallback(() => {
    // Determine query index based on round
    const currentQueryIndex = round === 'final' ? 0 : (queryIndex || 1);
    const currentRound = round || 'prelims';
    
    console.log('Filtering team answers for:', {
      query_index: currentQueryIndex,
      round: currentRound,
      totalAnswers: allTeamAnswers.length
    });
    
    const filtered = allTeamAnswers.filter(teamAnswer => {
      return teamAnswer.query_index === currentQueryIndex && 
             teamAnswer.round === currentRound;
    });
    
    console.log('Filtered team answers:', {
      count: filtered.length,
      answers: filtered
    });
    
    return filtered;
  }, [allTeamAnswers, queryIndex, round]);

  // Handle delete team answer
  const handleDeleteTeamAnswer = async (teamAnswer) => {
    const frameId = `${teamAnswer.video_name}-${teamAnswer.frame_index}`;
    
    console.log('Deleting team answer:', teamAnswer);
    
    // Check if already deleting
    if (deletingFrames.has(frameId)) {
      console.log('Already deleting this frame:', frameId);
      return;
    }

    try {
      // Add frame to deleting set
      setDeletingFrames(prev => new Set(prev).add(frameId));
      
      // Show loading toast
      toast.info('Deleting team answer...', 500);
      
      console.log('Calling deleteTeamAnswer API with ID:', teamAnswer.id);
      const response = await TeamAnswerService.deleteTeamAnswer(teamAnswer.id);
      
      console.log('Delete response:', response);
      
      if (response.success) {
        toast.success('Team answer deleted successfully!', 500);
        // Refresh the list
        console.log('Refreshing team answers list...');
        fetchTeamAnswers();
      } else {
        console.error('Delete failed:', response.error);
        toast.error(response.error || 'Failed to delete team answer', 500);
      }
    } catch (error) {
      console.error('Error deleting team answer:', error);
      toast.error('An error occurred while deleting team answer', 500);
    } finally {
      // Remove frame from deleting set
      setDeletingFrames(prev => {
        const newSet = new Set(prev);
        newSet.delete(frameId);
        return newSet;
      });
    }
  };

  // Handle delete all team answers for current query index
  const handleDeleteAllTeamAnswers = async () => {
    if (deletingAll) {
      console.log('Already deleting all team answers');
      return;
    }

    // Show confirmation modal instead of alert
    setShowDeleteAllModal(true);
  };

  // Handle confirmed delete all team answers
  const handleConfirmDeleteAll = async () => {
    const currentQueryIndex = round === 'final' ? 0 : (queryIndex || 1);
    
    try {
      setDeletingAll(true);
      setShowDeleteAllModal(false);
      
      // Show loading toast
      toast.info('Deleting all team answers...', 500);
      
      console.log('Deleting all team answers for query index:', currentQueryIndex, 'round:', round);
      
      const response = await TeamAnswerService.deleteAllTeamAnswers({
        query_index: currentQueryIndex,
        round: round || 'prelims'
      });
      
      console.log('Delete all response:', response);
      
      if (response.success) {
        toast.success('All team answers deleted successfully!', 500);
        // Refresh the list
        console.log('Refreshing team answers list...');
        fetchTeamAnswers();
      } else {
        console.error('Delete all failed:', response.error);
        toast.error(response.error || 'Failed to delete all team answers', 500);
      }
    } catch (error) {
      console.error('Error deleting all team answers:', error);
      toast.error('An error occurred while deleting all team answers', 500);
    } finally {
      setDeletingAll(false);
    }
  };

  // Fetch team answers when component becomes visible (only once)
  useEffect(() => {
    console.log('TeamAnswer useEffect triggered - isVisible:', isVisible, 'queryIndex:', queryIndex, 'round:', round);
    if (isVisible) {
      fetchTeamAnswers();
    }
  }, [isVisible, queryIndex, round]); // Remove fetchTeamAnswers dependency and add queryIndex, round

  // Auto scroll to selected frame when component becomes visible
  useEffect(() => {
    if (isVisible && selectedFrameRef.current && teamAnswerRef.current) {
      const timeout = setTimeout(() => {
        const contentContainer = teamAnswerRef.current.querySelector('.team-answer__content');
        const centerFrameWrapper = selectedFrameRef.current;
        
        if (centerFrameWrapper && contentContainer) {
          // Get all frame wrappers to find the index of center frame
          const allFrameWrappers = contentContainer.querySelectorAll('.team-answer__frame-wrapper');
          const centerFrameIndex = Array.from(allFrameWrappers).indexOf(centerFrameWrapper);
          
          if (centerFrameIndex >= 0) {
            // Use fixed height for simple and accurate calculation
            const frameHeight = 160; // Fixed height from CSS
            const gap = 12.8; // 0.8rem gap (0.8 * 16px)
            const itemHeight = frameHeight + gap;
            const containerHeight = contentContainer.clientHeight;
            
            // Calculate scroll to center the specific frame
            const targetScrollTop = (centerFrameIndex * itemHeight) - (containerHeight / 2) + (frameHeight / 2);
            
            // Scroll immediately without animation for instant response
            contentContainer.scrollTop = Math.max(0, targetScrollTop);
          }
        }
      }, 100); // Small delay to ensure DOM is ready

      return () => clearTimeout(timeout);
    }
  }, [isVisible, selectedFrame?.video_name, selectedFrame?.frame_index]);

  if (!isVisible) {
    return (
      <div className="team-answer team-answer--collapsed">
        <button 
          className="team-answer__toggle"
          onClick={onToggle}
          title="Show team answers"
        >
          <img src="/assets/team.svg" alt="Show" />
        </button>
      </div>
    );
  }

  // Get filtered team answers for current queryIndex and round
  const teamAnswers = getFilteredTeamAnswers();
  
  // Get current query info for modal message
  const currentQueryIndex = round === 'final' ? 0 : (queryIndex || 1);
  const currentRound = round || 'prelims';

  return (
    <div className="team-answer" ref={teamAnswerRef}>
      <ConfirmationModal
        isOpen={showDeleteAllModal}
        onClose={() => setShowDeleteAllModal(false)}
        onConfirm={handleConfirmDeleteAll}
        title="Delete All Team Answers"
        message={`Are you sure you want to delete all team answers for query ${currentQueryIndex} in ${currentRound} round? This action cannot be undone.`}
        confirmText="Delete All"
        cancelText="Cancel"
        isLoading={deletingAll}
      />
      <div className="team-answer__header">
        <button 
          className="team-answer__reload"
          onClick={fetchTeamAnswers}
          disabled={loading}
          title="Reload team answers"
        >
          {loading ? (
            <span className="team-answer__spinner">⟳</span>
          ) : (
            <img src="/assets/reload.svg" alt="Reload" />
          )}
        </button>
        <button 
          className="team-answer__delete-all"
          onClick={handleDeleteAllTeamAnswers}
          disabled={deletingAll || loading}
          title="Delete all team answers"
        >
          {deletingAll ? (
            <span className="team-answer__spinner">⟳</span>
          ) : (
            <img src="/assets/trash-bin.svg" alt="Delete All" />
          )}
        </button>
        <button 
          className="team-answer__close"
          onClick={onToggle}
          title="Hide team answers"
        >
          <img src="/assets/team.svg" alt="Close" />
        </button>
      </div>
      
      <div className="team-answer__content">
        {loading && (
          <div className="team-answer__loading">
            <p>Loading team answers...</p>
          </div>
        )}
        
        {!loading && teamAnswers.length === 0 && (
          <div className="team-answer__empty">
            <p>No team answers found</p>
          </div>
        )}
        
        {!loading && teamAnswers.length > 0 && (
          <div className="team-answer__list">
            <div className="team-answer__grid">
              {teamAnswers.map((teamAnswer) => {
                const frameId = `${teamAnswer.video_name}-${teamAnswer.frame_index}`;
                const isSelected = selectedFrame && 
                  selectedFrame.video_name === teamAnswer.video_name && 
                  parseInt(selectedFrame.frame_index) === parseInt(teamAnswer.frame_index);
                
                return (
                  <div
                    key={teamAnswer.id}
                    ref={isSelected ? selectedFrameRef : null}
                    className="team-answer__item"
                    data-frame-id={frameId}
                    data-frame-index={teamAnswer.frame_index}
                  >
                    <FrameItem
                      frame={teamAnswer}
                      isSelected={isSelected}
                      onClick={(clickedFrame) => {
                        if (onFrameSelect) {
                          onFrameSelect(clickedFrame);
                        }
                      }}
                      onDoubleClick={(clickedFrame) => {
                        if (onFrameDoubleClick) {
                          onFrameDoubleClick(clickedFrame);
                        }
                      }}
                      onSubmit={onSubmit}
                      // No onSend prop - we don't want send button
                      showFilename={true}
                      size="small"
                      className="team-answer__frame"
                    />
                    <button
                      className={`team-answer__delete-btn ${
                        deletingFrames.has(frameId) ? 'team-answer__delete-btn--loading' : ''
                      }`}
                      onClick={() => handleDeleteTeamAnswer(teamAnswer)}
                      disabled={deletingFrames.has(frameId)}
                      title="Delete team answer"
                    >
                      {deletingFrames.has(frameId) ? (
                        <span className="team-answer__spinner">⟳</span>
                      ) : (
                        <img src="/assets/trash-bin.svg" alt="Delete" />
                      )}
                    </button>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default TeamAnswer;
