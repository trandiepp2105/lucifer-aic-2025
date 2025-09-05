import React from 'react';
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragOverlay,
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import {
  restrictToVerticalAxis,
  restrictToParentElement,
} from '@dnd-kit/modifiers';
import QueryItem from './QueryItem';
import './SidebarQueries.scss';

const SidebarQueries = ({
  loading,
  filteredQueries,
  stage,
  onStageChange,
  onDeleteQuery,
  onCreateQuery,
  onReorderQueries,
  messagesEndRef
}) => {
  const [activeId, setActiveId] = React.useState(null);
  
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8, // Match TeamAnswer distance
      },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  const handleDragStart = (event) => {
    setActiveId(event.active.id);
  };

  const handleDragEnd = (event) => {
    const { active, over } = event;
    setActiveId(null);

    if (active.id !== over?.id) {
      const oldIndex = filteredQueries.findIndex((query) => 
        (query.id || `stage-${query.stage}`) === active.id
      );
      const newIndex = filteredQueries.findIndex((query) => 
        (query.id || `stage-${query.stage}`) === over.id
      );


      if (oldIndex !== -1 && newIndex !== -1) {
        const reorderedQueries = arrayMove(filteredQueries, oldIndex, newIndex);
        onReorderQueries(reorderedQueries);
      }
    }
  };
  return (
    <div className="sidebar__messages">
      {loading ? (
        <div className="sidebar__loading">
          <div className="sidebar__spinner"></div>
          <span>Loading queries...</span>
        </div>
      ) : filteredQueries.length > 0 ? (
        <DndContext 
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragStart={handleDragStart}
          onDragEnd={handleDragEnd}
          modifiers={[restrictToVerticalAxis, restrictToParentElement]}
        >
          <SortableContext 
            items={filteredQueries.map(query => query.id || `stage-${query.stage}`)}
            strategy={verticalListSortingStrategy}
          >
            {filteredQueries.map((query) => (
              <QueryItem
                key={query.id || `stage-${query.stage}`}
                query={query}
                isCurrentStage={query.stage === stage}
                onStageChange={onStageChange}
                onDelete={onDeleteQuery}
                onCreateQuery={onCreateQuery}
                isDraggable={true}
                isBeingDragged={activeId === (query.id || `stage-${query.stage}`)}
              />
            ))}
          </SortableContext>
          
          <DragOverlay>
            {activeId ? (
              <QueryItem
                query={filteredQueries.find(q => (q.id || `stage-${q.stage}`) === activeId)}
                isCurrentStage={false}
                isDraggable={false}
                isBeingDragged={true}
              />
            ) : null}
          </DragOverlay>
        </DndContext>
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
