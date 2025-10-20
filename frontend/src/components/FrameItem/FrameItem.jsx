import React from 'react';
import './FrameItem.scss';

const FrameItem = ({ 
  frame, 
  isSelected = false, 
  isCenter = false,
  onClick, 
  onDoubleClick, 
  onSubmit,
  onSend,
  onZoom, // Add onZoom prop for zoom functionality
  showFilename = true,
  className = '',
  size = 'normal', // 'normal', 'small', 'large'
  disabled = false, // Add disabled prop for Send button
  isSending = false, // Add isSending prop for loading state
  enableDrag = false, // Add enableDrag prop for drag & drop functionality
  showCheckbox = false, // Add checkbox support for TRAKE mode
  isChecked = false, // Checkbox state
  onCheckboxChange, // Checkbox change handler
  showDelete = false, // Add delete button support
  onDeleteClick, // Delete button click handler
  isPeakFrame = false, // Add isPeakFrame prop to highlight peak frames
  peakStage = -1, // Add peakStage prop to show which stage this is the peak for
}) => {
  const handleClick = (e) => {
    // Check for Ctrl+Click to trigger zoom
    if (e.ctrlKey && onZoom) {
      e.preventDefault();
      e.stopPropagation();
      onZoom(frame);
      return;
    }
    
    if (onClick) {
      onClick(frame);
    }
  };

  const handleDoubleClick = () => {
    if (onDoubleClick) {
      onDoubleClick(frame);
    }
  };

  const handleSubmit = (e) => {
    e.stopPropagation();
    if (onSubmit) {
      onSubmit(frame);
    }
  };

  const handleSend = (e) => {
    e.stopPropagation();
    if (onSend && !disabled && !isSending) {
      onSend(frame);
    }
  };

  const handleCheckboxChange = (e) => {
    e.stopPropagation();
    if (onCheckboxChange) {
      onCheckboxChange(frame, e.target.checked);
    }
  };

  const handleDelete = (e) => {
    e.stopPropagation();
    if (onDeleteClick) {
      onDeleteClick(e);
    }
  };

  // Handle drag start for image drag & drop
  const handleDragStart = (e) => {
    if (!enableDrag) return;
    
    // Set drag data with frame image URL and metadata
    const dragData = {
      type: 'frame-image',
      url: frame.url,
      frame: {
        video_name: frame.video_name,
        frame_index: frame.frame_index,
        filename: `${frame.video_name}/${frame.frame_index}`
      }
    };
    
    e.dataTransfer.setData('application/json', JSON.stringify(dragData));
    e.dataTransfer.effectAllowed = 'copy';
    
    // Add dragging class for visual feedback
    e.target.classList.add('frame-item--dragging');
  };

  const handleDragEnd = (e) => {
    if (!enableDrag) return;
    
    // Remove dragging class
    e.target.classList.remove('frame-item--dragging');
  };

  const getFrameClasses = () => {
    let classes = ['frame-item'];
    
    if (className) {
      classes.push(className);
    }
    
    if (isSelected) {
      classes.push('frame-item--selected');
    }
    
    if (isCenter) {
      classes.push('frame-item--center');
    }
    
    if (size !== 'normal') {
      classes.push(`frame-item--${size}`);
    }
    
    // Add classes for checkbox state
    if (showCheckbox) {
      classes.push('frame-item--has-checkbox');
      if (isChecked) {
        classes.push('frame-item--checked');
      }
    }
    
    // Add class for peak frame highlighting
    if (isPeakFrame) {
      classes.push('frame-item--peak');
      console.log('🎯 Applying peak class to:', frame.video_name, frame.frame_index, 'stage:', peakStage);
    }
    
    return classes.join(' ');
  };

  // Generate filename from video_name and frame_index
  const filename = `${frame.video_name}/${frame.frame_index}`;
  // Generate unique ID from video_name and frame_index
  const frameId = `${frame.video_name}-${frame.frame_index}`;

  // Generate title with instructions
  const getTitle = () => {
    let title = filename;
    if (isPeakFrame && peakStage >= 0) {
      title = `[Peak Stage ${peakStage + 1}] ${title}`;
    }
    if (onDoubleClick) {
      title += " | Double-click to play video";
    }
    if (onZoom) {
      title += " | Ctrl+Click to zoom";
    }
    return title;
  };

  return (
    <div
      className={getFrameClasses()}
      onClick={handleClick}
      onDoubleClick={handleDoubleClick}
      title={getTitle()}
      draggable={enableDrag}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
    >
      <div className="frame-item__thumbnail">
        <img 
          src={frame.url} 
          alt={`Frame ${frame.video_name}-${frame.frame_index}`}
          loading="lazy"
        />
        {/* Peak stage badge */}
        {isPeakFrame && peakStage >= 0 && (
          <div className="frame-item__peak-badge" title={`Highest scoring frame for Stage ${peakStage + 1}`}>
            S{peakStage + 1}
          </div>
        )}
      </div>
      
      {/* Action buttons - only show if handlers are provided */}
      {(onSubmit || onSend || showCheckbox || showDelete) && (
        <div className="frame-item__actions">
          {showCheckbox ? (
            <label className="frame-item__checkbox-wrapper">
              <input
                type="checkbox"
                className="frame-item__checkbox"
                checked={isChecked}
                onChange={handleCheckboxChange}
              />
              <span className="frame-item__checkbox-custom"></span>
            </label>
          ) : (
            <>
              {onSend && (
                <button 
                  className={`frame-item__action-btn frame-item__action-btn--send ${disabled || isSending ? 'frame-item__action-btn--disabled' : ''}`}
                  onClick={handleSend}
                  title={isSending ? "Sending..." : "Send this frame"}
                  disabled={disabled || isSending}
                >
                  {isSending ? (
                    <span className="frame-item__spinner">⟳</span>
                  ) : (
                    <img src="/assets/team.svg" alt="Send" />
                  )}
                </button>
              )}
              {onSubmit && (
                <button 
                  className="frame-item__action-btn frame-item__action-btn--submit"
                  onClick={handleSubmit}
                  title="Submit this frame"
                >
                  <img src="/assets/submit.svg" alt="Submit" />
                </button>
              )}
              {showDelete && (
                <button 
                  className="frame-item__action-btn frame-item__action-btn--delete"
                  onClick={handleDelete}
                  title="Delete this frame"
                >
                  <img src="/assets/trash-bin.svg" alt="Delete" />
                </button>
              )}
            </>
          )}
        </div>
      )}
      
      {showFilename && (
        <div className="frame-item__info">
          <span className="frame-item__filename">{filename}</span>
        </div>
      )}
    </div>
  );
};

export default FrameItem;
