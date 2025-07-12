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
  showFilename = true,
  className = '',
  size = 'normal', // 'normal', 'small', 'large'
  disabled = false, // Add disabled prop for Send button
  isSending = false, // Add isSending prop for loading state
  enableDrag = false // Add enableDrag prop for drag & drop functionality
}) => {
  const handleClick = () => {
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
    
    return classes.join(' ');
  };

  // Generate filename from video_name and frame_index
  const filename = `${frame.video_name}/${frame.frame_index}`;
  // Generate unique ID from video_name and frame_index
  const frameId = `${frame.video_name}-${frame.frame_index}`;

  return (
    <div
      className={getFrameClasses()}
      onClick={handleClick}
      onDoubleClick={handleDoubleClick}
      title={onDoubleClick ? "Double-click to play video" : filename}
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
      </div>
      
      {/* Action buttons - only show if handlers are provided */}
      {(onSubmit || onSend) && (
        <div className="frame-item__actions">
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
