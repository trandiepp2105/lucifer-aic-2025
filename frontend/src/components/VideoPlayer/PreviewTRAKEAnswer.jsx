import React from 'react';
import FrameItem from '../FrameItem/FrameItem';
import { useApp } from '../../contexts/AppContext';
import './PreviewTRAKEAnswer.scss';

const PreviewTRAKEAnswer = ({ 
  isVisible = true,
  className = '',
  allTeamAnswers = [],
  allTRAKEAnswers = [], // Add TRAKE answers prop
  onFrameSelect,
  onFrameDoubleClick,
  onSubmit,
  selectedFrame,
  searchResults = [], // Add search results for TRAKE mode
}) => {
  const { 
    queryMode, 
    queryIndex, 
    round, 
    tempTrakeItems, 
    addTempTrakeItem, 
    removeTempTrakeItem 
  } = useApp();

  if (!isVisible) {
    return null;
  }

  // Filter and sort team answers based on current context, only if queryMode is not 'tra'
  const teamAnswers = React.useMemo(() => {
    if (queryMode === 'tra') {
      // For TRA mode, use TRAKE answers data
      if (!allTRAKEAnswers || !Array.isArray(allTRAKEAnswers)) {
        return [];
      }
      
      // TRAKE answers are already grouped and sorted by backend
      // Extract all items from all groups
      const allItems = [];
      allTRAKEAnswers.forEach(group => {
        if (group.items && Array.isArray(group.items)) {
          allItems.push(...group.items);
        }
      });
      
      return allItems;
    }

    const currentQueryIndex = queryIndex;
    const currentRound = round || 'prelims';
    
    const filtered = allTeamAnswers.filter(teamAnswer => {
      return teamAnswer.query_index === currentQueryIndex && 
             teamAnswer.round === currentRound;
    });
    
    // Sort by created_at descending (newest first)
    return filtered.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
  }, [allTeamAnswers, allTRAKEAnswers, queryIndex, round, queryMode]);

  // Check if a frame is in temp TRAKE items
  const isFrameInTempTrake = React.useCallback((frame) => {
    return tempTrakeItems.some(item => 
      item.video_name === frame.video_name && 
      item.frame_index === frame.frame_index
    );
  }, [tempTrakeItems]);

  // Handle checkbox change for TRAKE mode
  const handleCheckboxChange = React.useCallback((frame, isChecked) => {
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

  const handleFrameClick = (frame) => {
    if (onFrameSelect) {
      onFrameSelect(frame);
    }
  };

  const handleFrameDoubleClick = (frame) => {
    if (onFrameDoubleClick) {
      onFrameDoubleClick(frame);
    }
  };

  return (
    <div className={`preview-trake ${className}`}>
      <div className="preview-trake__content">
        {queryMode === 'tra' ? (
          // Show search results for TRA mode with checkboxes
          <>
            {searchResults && searchResults.length > 0 ? (
              <div className="preview-trake__items">
                <div className="preview-trake__section-title">Search Results</div>
                {searchResults.map((frame, index) => {
                  const isSelected = selectedFrame && 
                    selectedFrame.video_name === frame.video_name && 
                    parseInt(selectedFrame.frame_index) === parseInt(frame.frame_index);
                  
                  const isChecked = isFrameInTempTrake(frame);
                  
                  return (
                    <div
                      key={`search-${frame.video_name}-${frame.frame_index}-${index}`}
                      className="preview-trake__item"
                    >
                      <FrameItem
                        frame={frame}
                        isSelected={isSelected}
                        onClick={handleFrameClick}
                        onDoubleClick={handleFrameDoubleClick}
                        showFilename={true}
                        size="small"
                        className="preview-trake__frame"
                        showCheckbox={true}
                        isChecked={isChecked}
                        onCheckboxChange={handleCheckboxChange}
                      />
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="preview-trake__placeholder">
                <div className="preview-trake__placeholder-icon">�</div>
                <p className="preview-trake__placeholder-text">
                  Search results will be displayed here for TRAKE selection
                </p>
              </div>
            )}
            
            {/* Show TRAKE answers if available */}
            {teamAnswers.length > 0 && (
              <div className="preview-trake__items">
                <div className="preview-trake__section-title">Previous TRAKE Answers</div>
                {teamAnswers.map((teamAnswer) => {
                  const isSelected = selectedFrame && 
                    selectedFrame.video_name === teamAnswer.video_name && 
                    parseInt(selectedFrame.frame_index) === parseInt(teamAnswer.frame_index);
                  
                  return (
                    <div
                      key={`trake-${teamAnswer.id || `${teamAnswer.video_name}-${teamAnswer.frame_index}`}`}
                      className="preview-trake__item"
                    >
                      <FrameItem
                        frame={teamAnswer}
                        isSelected={isSelected}
                        onClick={handleFrameClick}
                        onDoubleClick={handleFrameDoubleClick}
                        showFilename={true}
                        size="small"
                        className="preview-trake__frame"
                      />
                    </div>
                  );
                })}
              </div>
            )}
          </>
        ) : (
          // Show team answers for KIS/QA modes
          <>
            {teamAnswers.length > 0 ? (
              <div className="preview-trake__items">
                {teamAnswers.map((teamAnswer) => {
                  const isSelected = selectedFrame && 
                    selectedFrame.video_name === teamAnswer.video_name && 
                    parseInt(selectedFrame.frame_index) === parseInt(teamAnswer.frame_index);
                  
                  return (
                    <div
                      key={teamAnswer.id}
                      className="preview-trake__item"
                    >
                      <FrameItem
                        frame={teamAnswer}
                        isSelected={isSelected}
                        onClick={handleFrameClick}
                        onDoubleClick={handleFrameDoubleClick}
                        onSubmit={onSubmit}
                        showFilename={true}
                        size="small"
                        className="preview-trake__frame"
                      />
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="preview-trake__empty">
                <div className="preview-trake__empty-icon">📋</div>
                <p className="preview-trake__empty-text">
                  No team answers for query {queryIndex}
                </p>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};

export default PreviewTRAKEAnswer;
