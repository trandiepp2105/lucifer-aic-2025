import React from 'react';
import QueryItem from './QueryItem';
import './SidebarQueries.scss';

const SidebarQueries = ({
  loading,
  filteredQueries,
  stage,
  onStageChange,
  onDeleteQuery,
  onCreateQuery,
  messagesEndRef
}) => {
  return (
    <div className="sidebar__messages">
      {loading ? (
        <div className="sidebar__loading">
          <div className="sidebar__spinner"></div>
          <span>Loading queries...</span>
        </div>
      ) : filteredQueries.length > 0 ? (
        filteredQueries.map((query) => (
          <QueryItem
            key={query.id || `stage-${query.stage}`}
            query={query}
            isCurrentStage={query.stage === stage}
            onStageChange={onStageChange}
            onDelete={onDeleteQuery}
            onCreateQuery={onCreateQuery}
          />
        ))
      ) : (
        <div className="sidebar__empty">
          <p>No queries in Stage {stage}. Start by entering text, uploading an image, or using voice input.</p>
        </div>
      )}
      <div ref={messagesEndRef} />
    </div>
  );
};

export default SidebarQueries;
