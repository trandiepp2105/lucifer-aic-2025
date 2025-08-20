import React from 'react';
import './QueryItem.scss';

const QueryItem = ({ 
  query, 
  isCurrentStage, 
  onStageChange, 
  onDelete,
  onCreateQuery 
}) => {
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
      className={`sidebar__message sidebar__message--query ${
        isCurrentStage ? 'sidebar__message--current-stage' : ''
      }`}
      onClick={handleClick}
      style={{ cursor: 'pointer' }}
    >
      <div className="sidebar__message-content">
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
