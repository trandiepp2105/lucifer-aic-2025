import React from 'react';
import {
  useSortable
} from '@dnd-kit/sortable';
import {
  CSS,
} from '@dnd-kit/utilities';
import './QueryItem.scss';

const QueryItem = ({ 
  query, 
  isCurrentStage, 
  onStageChange, 
  onDelete,
  onCreateQuery,
  isDraggable = false,
  isBeingDragged = false
}) => {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ 
    id: query.id || `stage-${query.stage}`,
    disabled: !isDraggable
  });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };
  // Helper function to check if a field has a valid value
  const hasValidValue = (value) => {
    return value !== null && 
           value !== undefined && 
           value !== 'null' && 
           value !== 'undefined' &&
           typeof value === 'string' && 
           value.trim() !== '';
  };

  // Check if query has content to allow creating new query after it
  const hasContent = () => {
    return hasValidValue(query.text) || hasValidValue(query.ocr) || hasValidValue(query.image);
  };

  const handleClick = () => {
    // Don't change stage when dragging
    if (isDragging) return;
    
    if (query.stage !== isCurrentStage && onStageChange) {
      onStageChange(query.stage);
    }
  };

  const handleDelete = (e) => {
    e.stopPropagation();
    if (onDelete) {
      onDelete(query.stage); // Pass stage instead of ID for local management
    }
  };

  return (
    <div 
      ref={setNodeRef}
      style={style}
      className={`sidebar__message sidebar__message--query ${
        isCurrentStage ? 'sidebar__message--current-stage' : ''
      } ${isDragging || isBeingDragged ? 'sidebar__message--dragging' : ''}`}
      onClick={handleClick}
      data-draggable={isDraggable}
      {...(isDraggable ? attributes : {})}
      {...(isDraggable ? listeners : {})}
    >
      {/* Drag handle - visual indicator only */}
      {isDraggable && (
        <div className="sidebar__drag-handle">
          <svg 
            width="16" 
            height="16" 
            viewBox="0 0 24 24" 
            fill="none" 
            xmlns="http://www.w3.org/2000/svg"
          >
            <path 
              d="M8 6C8 6.55228 7.55228 7 7 7C6.44772 7 6 6.55228 6 6C6 5.44772 6.44772 5 7 5C7.55228 5 8 5.44772 8 6Z" 
              fill="currentColor"
            />
            <path 
              d="M8 12C8 12.5523 7.55228 13 7 13C6.44772 13 6 12.5523 6 12C6 11.4477 6.44772 11 7 11C7.55228 11 8 11.4477 8 12Z" 
              fill="currentColor"
            />
            <path 
              d="M8 18C8 18.5523 7.55228 19 7 19C6.44772 19 6 18.5523 6 18C6 17.4477 6.44772 17 7 17C7.55228 17 8 17.4477 8 18Z" 
              fill="currentColor"
            />
            <path 
              d="M14 6C14 6.55228 13.5523 7 13 7C12.4477 7 12 6.55228 12 6C12 5.44772 12.4477 5 13 5C13.5523 5 14 5.44772 14 6Z" 
              fill="currentColor"
            />
            <path 
              d="M14 12C14 12.5523 13.5523 13 13 13C12.4477 13 12 12.5523 12 12C12 11.4477 12.4477 11 13 11C13.5523 11 14 11.4477 14 12Z" 
              fill="currentColor"
            />
            <path 
              d="M14 18C14 18.5523 13.5523 19 13 19C12.4477 19 12 18.5523 12 18C12 17.4477 12.4477 17 13 17C13.5523 17 14 17.4477 14 18Z" 
              fill="currentColor"
            />
          </svg>
        </div>
      )}

      <div className="sidebar__message-content">
        {/* Stage indicator */}
        <div className="sidebar__stage-indicator">
          Stage {query.stage}
        </div>
        
        {/* Check if query has any content */}
        {(() => {
          const hasText = hasValidValue(query.text);
          const hasOcr = hasValidValue(query.ocr);
          const hasImage = hasValidValue(query.image);
          const hasAnyContent = hasText || hasOcr || hasImage;

          return (
            <>
              {/* Text field - always show if has content, or show empty if no other content */}
              {(hasText || !hasAnyContent) && (
                <div className="sidebar__message-field">
                  <strong>Text:</strong> {hasText ? query.text : <span className="sidebar__empty-field">Enter your query...</span>}
                </div>
              )}
              
              {/* OCR field */}
              {hasOcr && (
                <div className="sidebar__message-field">
                  <strong>OCR:</strong> {query.ocr}
                </div>
              )}
              
              {/* Speech field - COMMENTED OUT (Speech input disabled) */}
              {/* 
              {hasValidValue(query.speech) && (
                <div className="sidebar__message-field">
                  <strong>Speech:</strong> {query.speech}
                </div>
              )}
              */}
              
              {/* Image field */}
              {hasImage && (
                <div className="sidebar__message-field sidebar__message-image">
                  <img src={query.image} alt="Query image" className="sidebar__query-image" />
                </div>
              )}
            </>
          );
        })()}

        {/* Action buttons - shown on hover */}
        <div className="sidebar__message-actions">
          <button 
            onClick={(e) => {
              e.stopPropagation();
              if (hasContent() && onCreateQuery) {
                onCreateQuery(query.stage);
              }
            }}
            className={`sidebar__action-btn sidebar__action-btn--create ${!hasContent() ? 'disabled' : ''}`}
            title={hasContent() ? "Create new query after this" : "Add content to create new query"}
            disabled={!hasContent()}
          >
            <svg 
              width="12" 
              height="12" 
              viewBox="0 0 24 24" 
              fill="none" 
              xmlns="http://www.w3.org/2000/svg"
            >
              <path 
                d="M12 4V20M20 12H4" 
                stroke="currentColor" 
                strokeWidth="2" 
                strokeLinecap="round" 
                strokeLinejoin="round"
              />
            </svg>
          </button>
          <button 
            onClick={handleDelete}
            className="sidebar__action-btn sidebar__action-btn--delete"
            title="Delete this query"
          >
            <svg 
              width="12" 
              height="12" 
              viewBox="0 0 24 24" 
              fill="none" 
              xmlns="http://www.w3.org/2000/svg"
            >
              <path 
                d="M3 6.52381C3 6.12932 3.32671 5.80952 3.72973 5.80952H8.51787C8.52437 4.9683 8.61554 3.81504 9.45037 3.01668C10.1074 2.38839 11.0081 2 12 2C12.9919 2 13.8926 2.38839 14.5496 3.01668C15.3844 3.81504 15.4756 4.9683 15.4821 5.80952H20.2703C20.6733 5.80952 21 6.12932 21 6.52381C21 6.9183 20.6733 7.2381 20.2703 7.2381H3.72973C3.32671 7.2381 3 6.9183 3 6.52381Z" 
                fill="currentColor"
              />
              <path 
                fillRule="evenodd" 
                clipRule="evenodd" 
                d="M11.5956 22H12.4044C15.1871 22 16.5785 22 17.4831 21.1141C18.3878 20.2281 18.4803 18.7749 18.6654 15.8685L18.9321 11.6806C19.0326 10.1036 19.0828 9.31511 18.6289 8.81545C18.1751 8.31579 17.4087 8.31579 15.876 8.31579H8.12404C6.59127 8.31579 5.82488 8.31579 5.37105 8.81545C4.91722 9.31511 4.96744 10.1036 5.06788 11.6806L5.33459 15.8685C5.5197 18.7749 5.61225 20.2281 6.51689 21.1141C7.42153 22 8.81289 22 11.5956 22ZM10.2463 12.1885C10.2051 11.7546 9.83753 11.4381 9.42537 11.4815C9.01321 11.5249 8.71251 11.9117 8.75372 12.3456L9.25372 17.6087C9.29494 18.0426 9.66247 18.3591 10.0746 18.3157C10.4868 18.2724 10.7875 17.8855 10.7463 17.4516L10.2463 12.1885ZM14.5746 11.4815C14.9868 11.5249 15.2875 11.9117 15.2463 12.3456L14.7463 17.6087C14.7051 18.0426 14.3375 18.3591 13.9254 18.3157C13.5132 18.2724 13.2125 17.8855 13.2537 17.4516L13.7537 12.1885C13.7949 11.7546 14.1625 11.4381 14.5746 11.4815Z" 
                fill="currentColor"
              />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
};

export default QueryItem;
