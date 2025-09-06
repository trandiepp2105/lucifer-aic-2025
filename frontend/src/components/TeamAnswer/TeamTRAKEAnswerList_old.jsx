import React, { useState, useCallback } from 'react';
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import {
  useSortable,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { restrictToVerticalAxis, restrictToParentElement } from '@dnd-kit/modifiers';
import FrameItem from '../FrameItem/FrameItem';
import ConfirmationModal from '../ConfirmationModal';
import { useToast } from '../Toast/ToastProvider';
import { useApp } from '../../contexts/AppContext';
import { TeamTRAKEAnswerService } from '../../services/TeamTRAKEAnswerService';
import './TeamTRAKEAnswerList.scss';

// Sortable Group Item Component
const SortableGroupItem = ({ group, onDeleteItem, onFrameSelect, onFrameDoubleClick, selectedFrame }) => {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: group.group });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  const [deletingItem, setDeletingItem] = useState(null);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const toast = useToast();

  const handleDeleteClick = (item, event) => {
    event.stopPropagation();
    setDeletingItem(item);
    setShowDeleteModal(true);
  };

  const handleConfirmDelete = async () => {
    if (!deletingItem) return;

    try {
      await TeamTRAKEAnswerService.deleteTRAKEAnswersByIds([deletingItem.id]);
      onDeleteItem(deletingItem.id);
      toast.success('TRAKE answer deleted successfully');
    } catch (error) {
      console.error('Error deleting TRAKE answer:', error);
      toast.error('Failed to delete TRAKE answer');
    } finally {
      setShowDeleteModal(false);
      setDeletingItem(null);
    }
  };

  const handleCancelDelete = () => {
    setShowDeleteModal(false);
    setDeletingItem(null);
  };

  return (
    <>
      <div
        ref={setNodeRef}
        style={style}
        className={`team-trake-group ${isDragging ? 'dragging' : ''}`}
        {...attributes}
      >
        <div className="team-trake-group__header" {...listeners}>
          <div className="team-trake-group__title">
            <span className="team-trake-group__icon">≡</span>
            Group {group.group} ({group.items.length} items)
          </div>
          <div className="team-trake-group__drag-handle">
            <span>⋮⋮</span>
          </div>
        </div>
        
        <div className="team-trake-group__items">
          {group.items.map((item) => {
            const isSelected = selectedFrame && 
              selectedFrame.video_name === item.video_name && 
              parseInt(selectedFrame.frame_index) === parseInt(item.frame_index);
            
            return (
              <div key={item.id} className="team-trake-group__item">
                <FrameItem
                  frame={item}
                  isSelected={isSelected}
                  onClick={onFrameSelect}
                  onDoubleClick={onFrameDoubleClick}
                  showFilename={true}
                  size="small"
                  className="team-trake-group__frame"
                />
                <button
                  className="team-trake-group__delete-btn"
                  onClick={(e) => handleDeleteClick(item, e)}
                  title="Delete this item"
                >
                  ×
                </button>
              </div>
            );
          })}
        </div>
      </div>

      <ConfirmationModal
        isOpen={showDeleteModal}
        onConfirm={handleConfirmDelete}
        onCancel={handleCancelDelete}
        title="Delete TRAKE Answer"
        message={`Are you sure you want to delete this TRAKE answer?`}
        confirmText="Delete"
        cancelText="Cancel"
      />
    </>
  );
};

const TeamTRAKEAnswerList = ({ 
  selectedFrame, 
  isVisible, 
  onToggle, 
  onFrameSelect, 
  onFrameDoubleClick,
  allTRAKEAnswers = [],
  setAllTRAKEAnswers, // Add setter for TRAKE answers
  onRefresh
}) => {
  const toast = useToast();
  const { queryIndex } = useApp();
  const [dragging, setDragging] = useState(false);
  const [sseConnected, setSseConnected] = useState(false);
  
  // SSE connection ref
  const eventSourceRef = useRef(null);

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  // Convert allTRAKEAnswers to grouped format if needed
  const groupedAnswers = React.useMemo(() => {
    if (!Array.isArray(allTRAKEAnswers)) return [];
    
    // If already grouped (array of objects with group and items)
    if (allTRAKEAnswers.length > 0 && allTRAKEAnswers[0].hasOwnProperty('group') && allTRAKEAnswers[0].hasOwnProperty('items')) {
      return allTRAKEAnswers.sort((a, b) => a.group - b.group);
    }
    
    // If flat array, group by group field
    const groups = {};
    allTRAKEAnswers.forEach(item => {
      const groupId = item.group || 1;
      if (!groups[groupId]) {
        groups[groupId] = { group: groupId, items: [] };
      }
      groups[groupId].items.push(item);
    });
    
    // Sort items within each group by frame_index
    Object.values(groups).forEach(group => {
      group.items.sort((a, b) => (a.frame_index || 0) - (b.frame_index || 0));
    });
    
    return Object.values(groups).sort((a, b) => a.group - b.group);
  }, [allTRAKEAnswers]);

  const handleDragStart = () => {
    setDragging(true);
  };

  const handleDragEnd = async (event) => {
    setDragging(false);
    const { active, over } = event;

    if (!over || active.id === over.id) {
      return;
    }

    const oldIndex = groupedAnswers.findIndex(group => group.group === active.id);
    const newIndex = groupedAnswers.findIndex(group => group.group === over.id);

    if (oldIndex === -1 || newIndex === -1) return;

    try {
      // Calculate new group assignments
      const reorderedGroups = arrayMove(groupedAnswers, oldIndex, newIndex);
      const groupUpdates = [];

      // Prepare updates for each moved group
      reorderedGroups.forEach((group, index) => {
        const newGroupId = index + 1;
        if (group.group !== newGroupId) {
          groupUpdates.push({
            oldGroup: group.group,
            newGroup: newGroupId,
            items: group.items
          });
        }
      });

      // Apply updates to backend
      for (const update of groupUpdates) {
        // Update all items in this group to new group number
        const itemIds = update.items.map(item => item.id);
        await TeamTRAKEAnswerService.updateGroupForItems(itemIds, update.newGroup);
      }

      // Refresh data to reflect changes
      if (onRefresh) {
        onRefresh();
      }

      toast.success('Group order updated successfully');
    } catch (error) {
      console.error('Error updating group order:', error);
      toast.error('Failed to update group order');
    }
  };

  const handleDeleteItem = useCallback((itemId) => {
    // Refresh data after delete
    if (onRefresh) {
      onRefresh();
    }
  }, [onRefresh]);

  // Initialize SSE connection for TRAKE answers
  const initializeSSE = () => {
    try {
      // Close existing connection if any
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }

      // Create new EventSource connection
      const sseUrl = `${apiConfig.baseURL}/team-trake-answers/sse/`;
      
      const eventSource = new EventSource(sseUrl);
      eventSourceRef.current = eventSource;

      // Handle incoming messages
      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          switch (data.type) {
            case 'connected':
              setSseConnected(true);
              toast.success('TRAKE real-time updates connected', 500);
              break;

            case 'create':
              // Refresh data when new TRAKE answers are created
              if (onRefresh) {
                onRefresh();
              }
              toast.success('New TRAKE answers added', 500);
              break;

            case 'bulk_delete':
              // Refresh data when TRAKE answers are deleted
              if (onRefresh) {
                onRefresh();
              }
              toast.info(`${data.deleted_count} TRAKE answer(s) removed`, 500);
              break;

            case 'group_delete':
              // Refresh data when entire group is deleted
              if (onRefresh) {
                onRefresh();
              }
              toast.info(`Group ${data.group} deleted (${data.deleted_count} items)`, 500);
              break;

            case 'group_update':
              // Refresh data when group assignments are updated
              if (onRefresh) {
                onRefresh();
              }
              toast.success('Group order updated', 500);
              break;

            case 'heartbeat':
              // Ignore heartbeat messages
              break;

            case 'error':
              console.error('❌ TRAKE SSE Error:', data.message);
              toast.error(data.message, 500);
              break;

            default:
              console.log('Unknown TRAKE SSE message type:', data.type);
              break;
          }
        } catch (error) {
          console.error('Error parsing TRAKE SSE message:', error, event.data);
        }
      };

      // Handle connection open
      eventSource.onopen = (event) => {
        setSseConnected(true);
      };

      // Handle connection errors
      eventSource.onerror = (event) => {
        setSseConnected(false);
        
        if (eventSource.readyState === EventSource.CLOSED) {
          toast.warning('TRAKE real-time connection lost', 500);
        }
      };

    } catch (error) {
      console.error('Failed to initialize TRAKE SSE:', error);
      setSseConnected(false);
    }
  };

  // Close SSE connection
  const closeSSE = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
      setSseConnected(false);
    }
  };

  // Initialize SSE connection when component mounts and when queryIndex changes
  useEffect(() => {
    
    if (isVisible && queryIndex) {
      initializeSSE();
      
      // Also fetch initial data
      if (onRefresh) {
        onRefresh();
      }
    }

    return () => {
      closeSSE();
    };
  }, [isVisible, queryIndex]);

  if (!isVisible) {
    return null;
  }

  return (
    <div className="team-trake-answer-list">
      <div className="team-trake-answer-list__header">
        <div className="team-trake-answer-list__status">
          <span 
            className={`team-trake-answer-list__sse-indicator ${sseConnected ? 'connected' : 'disconnected'}`}
            title={sseConnected ? 'TRAKE real-time updates connected' : 'TRAKE real-time updates disconnected'}
          >
            {sseConnected ? '🟢' : '🔴'}
          </span>
        </div>
        <h3 className="team-trake-answer-list__title">
          <span className="team-trake-answer-list__icon">🎯</span>
          TRAKE Answers ({groupedAnswers.length} groups)
        </h3>
        <button
          className="team-trake-answer-list__refresh"
          onClick={() => {
            if (onRefresh) {
              onRefresh();
            }
          }}
          title="Refresh TRAKE answers"
        >
          🔄
        </button>
        <button
          className="team-trake-answer-list__toggle"
          onClick={onToggle}
          title="Toggle TRAKE answers"
        >
          {isVisible ? '▼' : '▲'}
        </button>
      </div>

      <div className="team-trake-answer-list__content">
        {groupedAnswers.length > 0 ? (
          <DndContext
            sensors={sensors}
            collisionDetection={closestCenter}
            onDragStart={handleDragStart}
            onDragEnd={handleDragEnd}
            modifiers={[restrictToVerticalAxis, restrictToParentElement]}
          >
            <SortableContext
              items={groupedAnswers.map(group => group.group)}
              strategy={verticalListSortingStrategy}
            >
              <div className="team-trake-answer-list__groups">
                {groupedAnswers.map((group) => (
                  <SortableGroupItem
                    key={group.group}
                    group={group}
                    onDeleteItem={handleDeleteItem}
                    onFrameSelect={onFrameSelect}
                    onFrameDoubleClick={onFrameDoubleClick}
                    selectedFrame={selectedFrame}
                  />
                ))}
              </div>
            </SortableContext>
          </DndContext>
        ) : (
          <div className="team-trake-answer-list__empty">
            <div className="team-trake-answer-list__empty-icon">🎯</div>
            <p className="team-trake-answer-list__empty-text">
              No TRAKE answers yet
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

export default TeamTRAKEAnswerList;
