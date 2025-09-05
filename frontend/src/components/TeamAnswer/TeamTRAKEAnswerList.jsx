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
import SubmissionModal from '../SubmissionModal/SubmissionModal';
import { useToast } from '../Toast/ToastProvider';
import { useApp } from '../../contexts/AppContext';
import { useSubmission } from '../../hooks/useSubmission';
import { TeamTRAKEAnswerService } from '../../services/TeamTRAKEAnswerService';
import './TeamTRAKEAnswerList.scss';

// Sortable Group Item Component
const SortableGroupItem = ({ group, onDeleteItem, onDeleteGroup, onFrameSelect, onFrameDoubleClick, selectedFrame, activeGroup, onSetActiveGroup, openSubmissionModal }) => {
  const { queryIndex } = useApp(); // Get queryIndex from App context
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
  const [showDeleteGroupModal, setShowDeleteGroupModal] = useState(false);
  const [deletingGroup, setDeletingGroup] = useState(false);
  const toast = useToast();

  const handleDeleteClick = (item, event) => {
    event.stopPropagation();
    setDeletingItem(item);
    setShowDeleteModal(true);
  };

  // Direct delete without confirmation modal
  const handleDirectDeleteClick = async (item, event) => {
    event.stopPropagation();
    
    try {
      await TeamTRAKEAnswerService.deleteTRAKEAnswersByIds([item.id]);
      if (onDeleteItem) {
        onDeleteItem(item.id);
      }
      toast.success(`TRAKE answer deleted from ${item.video_name} frame ${item.frame_index}`);
    } catch (error) {
      console.error('Error deleting TRAKE answer:', error);
      toast.error('Failed to delete TRAKE answer');
    }
  };

  const handleDeleteGroupClick = (event) => {
    event.stopPropagation();
    setShowDeleteGroupModal(true);
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

  const handleConfirmDeleteGroup = async () => {
    if (!group || !group.group) return;

    try {
      setDeletingGroup(true);
      await TeamTRAKEAnswerService.deleteGroupTRAKEAnswers(group.group, queryIndex);
      if (onDeleteGroup) {
        onDeleteGroup(group.group);
      }
      toast.success(`Group ${group.group} deleted successfully`);
    } catch (error) {
      console.error('Error deleting group:', error);
      toast.error('Failed to delete group');
    } finally {
      setDeletingGroup(false);
      setShowDeleteGroupModal(false);
    }
  };

  const handleCancelDelete = () => {
    setShowDeleteModal(false);
    setDeletingItem(null);
  };

  const handleCancelDeleteGroup = () => {
    setShowDeleteGroupModal(false);
  };

  const handleActiveGroupChange = (event) => {
    const isChecked = event.target.checked;
    if (onSetActiveGroup) {
      onSetActiveGroup(isChecked ? group.group : null);
    }
  };

  const handleSubmitGroup = () => {
    const frameList = group.items.map(item => ({
      video_name: item.video_name,
      frame_index: item.frame_index,
      group: group.group,
      url: item.frame_url || item.url // Add url for modal preview
    }));
    if (!frameList.length) {
      toast.error('No frames to submit in this group');
      return;
    }
    // Open submission modal instead of calling callback
    openSubmissionModal('trake', frameList);
  };

  return (
    <>
      <div
        ref={setNodeRef}
        style={style}
        className={`team-trake-group ${isDragging ? 'dragging' : ''} ${activeGroup === group.group ? 'active' : ''}`}
        {...attributes}
      >
        <div className="team-trake-group__header">
          {/* Left side - controls */}
          <div className="team-trake-group__left">
            <input
              type="checkbox"
              className="team-trake-group__checkbox"
              checked={activeGroup === group.group}
              onChange={handleActiveGroupChange}
              title={activeGroup === group.group ? "Active group for new submissions" : "Set as active group"}
            />
            {/* <span className="team-trake-group__title">
              Group {group.group} ({group.items.length})
            </span> */}
          </div>
          
          {/* Middle - drag area */}
          <div 
            className="team-trake-group__drag-area"
            {...listeners}
            style={{ cursor: isDragging ? 'grabbing' : 'grab' }}
            title="Drag to reorder groups"
          >
            <div className="team-trake-group__drag-indicator">
              <img src="/assets/drag.svg" alt="Drag to reorder" />
            </div>
          </div>
          
          {/* Right side - action buttons */}
          <div className="team-trake-group__actions">
            <button 
              className="team-trake-group__submit"
              onClick={handleSubmitGroup}
              title={`Submit Group ${group.group} (${group.items.length} items)`}
            >
              <img src="/assets/send.svg" alt="Submit Group" />
            </button>
            <button 
              className="team-trake-group__delete"
              onClick={handleDeleteGroupClick}
              disabled={deletingGroup}
              title="Delete entire group"
            >
              {deletingGroup ? (
                <span className="team-trake-group__spinner">⟳</span>
              ) : (
                <img src="/assets/trash-bin.svg" alt="Delete Group" />
              )}
            </button>
          </div>
        </div>
        
        <div className="team-trake-group__items">
          {group.items.map((item) => {
            const isSelected = selectedFrame && 
              selectedFrame.video_name === item.video_name && 
              parseInt(selectedFrame.frame_index) === parseInt(item.frame_index);
            
            return (
              <div key={`${group.group}-${item.id}-${item.frame_index}`} className="team-trake-group__item">
                <FrameItem
                  frame={{
                    ...item,
                    url: item.frame_url || item.url,
                    video_name: item.video_name,
                    frame_index: item.frame_index
                  }}
                  onClick={() => onFrameSelect && onFrameSelect({
                    ...item,
                    url: item.frame_url || item.url,
                    video_name: item.video_name,
                    frame_index: item.frame_index
                  })}
                  onDoubleClick={() => onFrameDoubleClick && onFrameDoubleClick({
                    ...item,
                    url: item.frame_url || item.url,
                    video_name: item.video_name,
                    frame_index: item.frame_index
                  })}
                  isSelected={isSelected}
                  showDelete={true}
                  onDeleteClick={(event) => handleDirectDeleteClick(item, event)}
                />
              </div>
            );
          })}
        </div>
      </div>

      <ConfirmationModal
        isOpen={showDeleteModal}
        onClose={handleCancelDelete}
        onConfirm={handleConfirmDelete}
        title="Delete TRAKE Answer"
        message={`Are you sure you want to delete this TRAKE answer from ${deletingItem?.video_name} frame ${deletingItem?.frame_index}?`}
        confirmText="Delete"
        cancelText="Cancel"
      />
      
      <ConfirmationModal
        isOpen={showDeleteGroupModal}
        onClose={handleCancelDeleteGroup}
        onConfirm={handleConfirmDeleteGroup}
        title="Delete Entire Group"
        message={`Are you sure you want to delete Group ${group.group} and all ${group.items.length} items in it? This action cannot be undone.`}
        confirmText="Delete Group"
        cancelText="Cancel"
        isLoading={deletingGroup}
      />
    </>
  );
};

// Main Component
const TeamTRAKEAnswerList = ({ 
  selectedFrame, 
  isVisible = true, 
  onToggle, 
  onFrameSelect, 
  onFrameDoubleClick,
  allTRAKEAnswers = [],
  setAllTRAKEAnswers,
  onRefresh,
  activeGroup,      // Add activeGroup prop
  onSetActiveGroup, // Add onSetActiveGroup prop
  isCompact = false // Add compact mode prop
}) => {
  const toast = useToast();
  const { queryIndex } = useApp();
  const [dragging, setDragging] = useState(false);
  
  // Use submission hook for modal management
  const {
    submissionModal,
    openSubmissionModal,
    closeSubmissionModal,
    handleSubmissionConfirm
  } = useSubmission();

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
      return allTRAKEAnswers.sort((a, b) => b.group - a.group); // Sort descending (largest group first)
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
    
    return Object.values(groups).sort((a, b) => b.group - a.group); // Sort descending (largest group first)
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
      // Calculate new group assignments with descending order logic
      const reorderedGroups = arrayMove(groupedAnswers, oldIndex, newIndex);
      const groupUpdates = [];

      // Since we're sorting descending, assign groups in reverse order
      // Index 0 = highest group number, Index n = lowest group number
      const maxGroup = Math.max(...groupedAnswers.map(g => g.group));
      
      reorderedGroups.forEach((group, index) => {
        // Calculate new group ID: maxGroup for index 0, decreasing as index increases
        const newGroupId = maxGroup - index;
        if (group.group !== newGroupId) {
          groupUpdates.push({
            oldGroup: group.group,
            newGroup: newGroupId,
            items: group.items
          });
        }
      });

      // Apply updates to backend - each will trigger SSE events
      for (const update of groupUpdates) {
        // Update all items in this group to new group number
        const itemIds = update.items.map(item => item.id);
        await TeamTRAKEAnswerService.updateGroupForItems(itemIds, update.newGroup);
      }

      // Let SSE handle data refresh automatically
      // If no SSE, fallback to manual refresh after a short delay
      setTimeout(() => {
        if (onRefresh) {
          onRefresh();
        }
      }, 500);

      toast.success('Group order updated successfully');
    } catch (error) {
      console.error('Error updating group order:', error);
      toast.error('Failed to update group order');
      
      // On error, definitely refresh to get correct state
      if (onRefresh) {
        onRefresh();
      }
    }
  };

  const handleDeleteGroup = useCallback(async (groupNumber) => {
    try {
      // Optimistic update - remove group from UI
      const updatedAnswers = allTRAKEAnswers.filter(group => group.group !== groupNumber);
      if (setAllTRAKEAnswers) {
        setAllTRAKEAnswers(updatedAnswers);
      }
      
      // Refresh data from server to ensure consistency
      if (onRefresh) {
        setTimeout(() => onRefresh(), 100);
      }
    } catch (error) {
      console.error('Error in handleDeleteGroup:', error);
      // Refresh data on error to restore consistent state
      if (onRefresh) {
        onRefresh();
      }
    }
  }, [allTRAKEAnswers, setAllTRAKEAnswers, onRefresh]);

  const handleDeleteItem = useCallback((itemId) => {
    // Refresh data after delete
    if (onRefresh) {
      onRefresh();
    }
  }, [onRefresh]);

  if (!isVisible) {
    return null;
  }

  return (
    <div className={`team-trake-answer-list ${isCompact ? 'team-trake-answer-list--compact' : ''}`}>
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
                    onDeleteGroup={handleDeleteGroup}
                    onFrameSelect={onFrameSelect}
                    onFrameDoubleClick={onFrameDoubleClick}
                    selectedFrame={selectedFrame}
                    activeGroup={activeGroup}
                    onSetActiveGroup={onSetActiveGroup}
                    openSubmissionModal={openSubmissionModal}
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
      
      {/* Submission Modal */}
      <SubmissionModal
        isOpen={submissionModal.isOpen}
        onClose={closeSubmissionModal}
        onConfirm={handleSubmissionConfirm}
        submissionType={submissionModal.type}
        frameData={submissionModal.frameData}
        qaText={submissionModal.qaText}
        isSubmitting={submissionModal.isSubmitting}
      />
    </div>
  );
};

export default TeamTRAKEAnswerList;
