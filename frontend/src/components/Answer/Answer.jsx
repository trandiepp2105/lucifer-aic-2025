import React, { useState, useEffect, useCallback, useRef } from 'react';
import FrameItem from '../FrameItem/FrameItem';
import { useApp } from '../../contexts/AppContext';
import './Answer.scss';

const Answer = ({ 
  selectedFrame, 
  isVisible, 
  onToggle, 
  onFrameSelect, 
  onFrameDoubleClick,
  allAnswers = [], // Get from props instead of local state
  onRefresh           // Refresh function from parent
}) => {
  const selectedFrameRef = useRef(null);
  const answerRef = useRef(null);
  
  const [loading, setLoading] = useState(false);
  
  // Get app context for queryIndex and round
  const { queryIndex, round } = useApp();

  // Filter answers based on current queryIndex and round
  const getFilteredAnswers = useCallback(() => {
    // Use queryIndex directly from AppContext (matches server query_index)
    const currentQueryIndex = queryIndex;
    const currentRound = round || 'prelims';
    
    const filtered = allAnswers.filter(answer => {
      return answer.query_index === currentQueryIndex && 
             answer.round === currentRound;
    });
    
    return filtered;
  }, [allAnswers, queryIndex, round]);

  // Scroll to selected frame when selection changes
  useEffect(() => {
    if (isVisible && selectedFrame && selectedFrameRef.current) {
      const timeout = setTimeout(() => {
        const container = answerRef.current;
        if (container) {
          const contentContainer = container.querySelector('.answer__content');
          if (contentContainer && selectedFrameRef.current) {
            const containerRect = contentContainer.getBoundingClientRect();
            const frameRect = selectedFrameRef.current.getBoundingClientRect();
            
            // Calculate relative position within the container
            const relativeTop = frameRect.top - containerRect.top + contentContainer.scrollTop;
            const relativeBottom = relativeTop + frameRect.height;
            
            // Check if frame is outside visible area
            const containerHeight = containerRect.height;
            const isAboveView = relativeTop < contentContainer.scrollTop;
            const isBelowView = relativeBottom > contentContainer.scrollTop + containerHeight;
            
            if (isAboveView || isBelowView) {
              // Calculate target scroll position to center the frame
              const targetScrollTop = relativeTop - (containerHeight / 2) + (frameRect.height / 2);
              
              // Scroll immediately without animation for instant response
              contentContainer.scrollTop = Math.max(0, targetScrollTop);
            }
          }
        }
      }, 100); // Small delay to ensure DOM is ready

      return () => clearTimeout(timeout);
    }
  }, [isVisible, selectedFrame?.video_name, selectedFrame?.frame_index]);

  if (!isVisible) {
    return (
      <div className="answer answer--collapsed">
        <button 
          className="answer__toggle"
          onClick={onToggle}
          title="Show final answers"
        >
          <img src="/assets/send.svg" alt="Show" />
        </button>
      </div>
    );
  }

  // Get filtered answers for current queryIndex and round
  const answers = getFilteredAnswers();

  return (
    <div className="answer" ref={answerRef}>
      <div className="answer__header">
        <button 
          className="answer__reload"
          onClick={onRefresh}
          disabled={loading}
          title="Reload final answers"
        >
          {loading ? (
            <span className="answer__spinner">⟳</span>
          ) : (
            <img src="/assets/reload.svg" alt="Reload" />
          )}
        </button>
        <button 
          className="answer__close"
          onClick={onToggle}
          title="Hide final answers"
        >
          <img src="/assets/send.svg" alt="Close" />
        </button>
      </div>
      
      <div className="answer__content">
        {loading && (
          <div className="answer__loading">
            <p>Loading final answers...</p>
          </div>
        )}
        
        {!loading && answers.length === 0 && (
          <div className="answer__empty">
            <p>No final answers found</p>
          </div>
        )}
        
        {!loading && answers.length > 0 && (
          <div className="answer__list">
            <div className="answer__grid">
              {answers.map((answer) => {
                const frameId = `${answer.video_name}-${answer.frame_index}`;
                const isSelected = selectedFrame && 
                  selectedFrame.video_name === answer.video_name && 
                  parseInt(selectedFrame.frame_index) === parseInt(answer.frame_index);
                
                return (
                  <div
                    key={answer.id}
                    ref={isSelected ? selectedFrameRef : null}
                    className="answer__item"
                    data-frame-id={frameId}
                    data-frame-index={answer.frame_index}
                  >
                    <FrameItem
                      frame={answer}
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
                      // No action buttons for view-only mode
                      showFilename={true}
                      size="small"
                      className="answer__frame"
                      readOnly={true} // Add read-only prop to disable actions
                    />
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

export default Answer;
