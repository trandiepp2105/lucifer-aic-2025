import React, { useEffect, useRef, useState, useCallback } from 'react';
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
import TeamAnswerModal from '../TeamAnswerModal/TeamAnswerModal';
import ImageZoomModal from '../ImageZoomModal/ImageZoomModal';
import VideoPlayer from '../VideoPlayer/VideoPlayer';
import SubmissionModal from '../SubmissionModal/SubmissionModal';
import { useApp } from '../../contexts/AppContext';
import { useTeamTRAKEAnswer } from '../../contexts/TeamTRAKEAnswerContext';
import { useToast } from '../Toast/ToastProvider';
import { useSubmission } from '../../hooks/useSubmission';
import { TeamAnswerService } from '../../services';
import { apiConfig } from '../../services/apiConfig';
import './TeamAnswer.scss';
import TeamTRAKEAnswerList from './TeamTRAKEAnswerList';

const TeamAnswer = ({ 
  selectedFrame, 
  isVisible, 
  onToggle, 
  onFrameSelect, 
  onFrameDoubleClick, 
  onSubmit,
  allTeamAnswers = [], // Get from props instead of local state
  setAllTeamAnswers,  // Setter from parent
  onRefresh,          // Refresh function from parent
  isCompact = false,  // Add compact mode prop
  className = ''      // Add className prop
}) => {
  const selectedFrameRef = useRef(null);
  
  // Use TRAKE context for TRAKE-related state
  const {
    currentQueryTRAKEAnswers, // Use filtered TRAKE answers for current query
    setAllTRAKEAnswers,
    activeGroup,
    setActiveGroup,
    isLoadingTRAKEAnswers,
    fetchAllTRAKEAnswers,
    deleteAllTRAKEAnswers
  } = useTeamTRAKEAnswer();
  
  // Submission logic with confirmation modal
  const {
    submissionModal,
    openSubmissionModal,
    closeSubmissionModal,
    handleSubmissionConfirm,
    submitKISAnswer,
    submitQAAnswer,
    submitTRAKEAnswer
  } = useSubmission();
  
  const teamAnswerRef = useRef(null);
  
  const [loading, setLoading] = useState(false);
  const [deletingFrames, setDeletingFrames] = useState(new Set());
  const [deletingAll, setDeletingAll] = useState(false);
  const [showDeleteAllModal, setShowDeleteAllModal] = useState(false);
  const [editingItem, setEditingItem] = useState(null); // For edit modal
  const [sseConnected, setSseConnected] = useState(false);
  const [traKEsseConnected, setTRAKEsseConnected] = useState(false); // Add TRAKE SSE state
  
  // Image zoom state
  const [zoomImageUrl, setZoomImageUrl] = useState('');
  const [zoomImageAlt, setZoomImageAlt] = useState('');
  const [zoomFrame, setZoomFrame] = useState(null);
  const [isImageZoomOpen, setIsImageZoomOpen] = useState(false);
  
  // VideoPlayer state
  const [isVideoPlayerOpen, setIsVideoPlayerOpen] = useState(false);
  
  // Drag & Drop state
  const [sortingItems, setSortingItems] = useState(new Set());
  
  // DnD Kit sensors with vertical-only constraint
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8, // Minimum distance before drag starts
      },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );
  
  // SSE connection ref
  const eventSourceRef = useRef(null);
  const trakeEventSourceRef = useRef(null); // Add TRAKE SSE ref
  
  // Get app context for queryIndex, round and queryMode
  const { queryIndex, round, queryMode, removeTempTrakeItem } = useApp();
  const toast = useToast();

  // Initialize SSE connection
  const initializeSSE = () => {
    try {
      // Close existing connection if any
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }

      // Create new EventSource connection
      const sseUrl = `${apiConfig.baseURL}/team-answers/sse/`;
      
      const eventSource = new EventSource(sseUrl);
      eventSourceRef.current = eventSource;

      // Handle incoming messages
      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          switch (data.type) {
            case 'connected':
              setSseConnected(true);
              toast.success('Real-time updates connected', 500);
              break;

            case 'create':
              // Add new team answer to the list
              setAllTeamAnswers(prevAnswers => [data.data, ...prevAnswers]);
              toast.success('New team answer added', 500);
              break;

            case 'delete':
              // Remove team answers from the list
              const deletedIds = Array.isArray(data.data) ? data.data : [data.data];
              setAllTeamAnswers(prevAnswers => 
                prevAnswers.filter(answer => !deletedIds.includes(answer.id))
              );
              toast.info(`${deletedIds.length} team answer(s) removed`, 500);
              break;

            case 'edit':
              // Update existing team answer in the list
              setAllTeamAnswers(prevAnswers => 
                prevAnswers.map(answer => 
                  answer.id === data.data.id ? data.data : answer
                )
              );
              toast.success('Team answer updated', 500);
              break;

            case 'sort':
              // Update both source and target team answers in the list
              setAllTeamAnswers(prevAnswers => 
                prevAnswers.map(answer => {
                  if (answer.id === data.data.source.id) {
                    return data.data.source;
                  } else if (answer.id === data.data.target.id) {
                    return data.data.target;
                  }
                  return answer;
                })
              );
              toast.info('Team answers reordered', 500);
              break;

            case 'heartbeat':
              // Ignore heartbeat messages
              break;

            case 'error':
              console.error('❌ SSE Error:', data.message);
              toast.error(data.message, 500);
              break;

            default:
              // Ignore unknown message types
              break;
          }
        } catch (error) {
          console.error('Error parsing SSE message:', error, event.data);
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
          toast.warning('Real-time connection lost', 500);
        }
      };

    } catch (error) {
      console.error('Failed to initialize SSE:', error);
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

  // Initialize TRAKE SSE connection
  const initializeTRAKESSE = () => {
    try {
      // Close existing connection if any
      if (trakeEventSourceRef.current) {
        trakeEventSourceRef.current.close();
        trakeEventSourceRef.current = null;
      }

      // Create new EventSource connection for TRAKE
      const sseUrl = `${apiConfig.baseURL}/team-trake-answers/sse/`;
      
      const eventSource = new EventSource(sseUrl);
      trakeEventSourceRef.current = eventSource;

      // Handle incoming messages
      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          switch (data.type) {
            case 'connected':
              setTRAKEsseConnected(true);
              toast.success('TRAKE real-time updates connected', 500);
              break;

            case 'create':
              // Refresh TRAKE data when new answers are created
              if (onRefresh) {
                onRefresh();
              }
              toast.success('New TRAKE answers added', 500);
              break;

            case 'bulk_delete':
              // Refresh TRAKE data when answers are deleted
              if (onRefresh) {
                onRefresh();
              }
              toast.info(`${data.deleted_count} TRAKE answer(s) removed`, 500);
              break;

            case 'group_delete':
              // Refresh TRAKE data when entire group is deleted
              if (onRefresh) {
                onRefresh();
              }
              toast.info(`Group ${data.group} deleted (${data.deleted_count} items)`, 500);
              break;

            case 'group_update':
              // Refresh TRAKE data when group assignments are updated
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
              break;
          }
        } catch (error) {
          console.error('Error parsing TRAKE SSE message:', error, event.data);
        }
      };

      // Handle connection open
      eventSource.onopen = (event) => {
        setTRAKEsseConnected(true);
        // Fetch initial TRAKE data when connection is established
        if (onRefresh) {
          // Call onRefresh with no parameters - the context will handle fetching all data
          onRefresh();
        }
      };

      // Handle connection errors
      eventSource.onerror = (event) => {
        setTRAKEsseConnected(false);
        
        if (eventSource.readyState === EventSource.CLOSED) {
          toast.warning('TRAKE real-time connection lost', 500);
        }
      };

    } catch (error) {
      console.error('Failed to initialize TRAKE SSE:', error);
      setTRAKEsseConnected(false);
    }
  };

  // Close TRAKE SSE connection
  const closeTRAKESSE = () => {
    if (trakeEventSourceRef.current) {
      trakeEventSourceRef.current.close();
      trakeEventSourceRef.current = null;
      setTRAKEsseConnected(false);
    }
  };

  // Filter team answers based on current queryIndex and round
  const getFilteredTeamAnswers = useCallback(() => {
    // Use queryIndex directly from AppContext (matches server query_index)
    const currentQueryIndex = queryIndex;
    const currentRound = round || 'prelims';
    
    const filtered = allTeamAnswers.filter(teamAnswer => {
      return teamAnswer.query_index === currentQueryIndex && 
             teamAnswer.round === currentRound;
    });
    
    // Sort by created_at descending (newest first)
    return filtered.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
  }, [allTeamAnswers, queryIndex, round]);

  // Handle delete team answer
  const handleDeleteTeamAnswer = async (teamAnswer) => {
    const frameId = `${teamAnswer.video_name}-${teamAnswer.frame_index}`;
    
    // Check if already deleting
    if (deletingFrames.has(frameId)) {
      return;
    }

    try {
      // Add frame to deleting set
      setDeletingFrames(prev => new Set(prev).add(frameId));
      
      const response = await TeamAnswerService.deleteTeamAnswer(teamAnswer.id);
      
      if (response.success) {
        toast.success('Team answer deleted successfully!', 500);
        // Refresh the list
        if (onRefresh) onRefresh();
      } else {
        console.error('Delete failed:', response.error);
        toast.error(response.error || 'Failed to delete team answer', 500);
      }
    } catch (error) {
      console.error('Error deleting team answer:', error);
      toast.error('An error occurred while deleting team answer', 500);
    } finally {
      // Remove frame from deleting set
      setDeletingFrames(prev => {
        const newSet = new Set(prev);
        newSet.delete(frameId);
        return newSet;
      });
    }
  };

  // Handle delete all team answers for current query index
  const handleDeleteAllTeamAnswers = async () => {
    if (deletingAll) {
      return;
    }

    // Show confirmation modal instead of alert
    setShowDeleteAllModal(true);
  };

  // Handle delete all TRAKE answers for TRA mode
  const handleDeleteAllTRAKEAnswers = async () => {
    if (deletingAll) {
      return;
    }

    // Show confirmation modal for TRAKE answers
    setShowDeleteAllModal(true);
  };

  // Handle confirmed delete all team answers
  const handleConfirmDeleteAll = async () => {
    // Use queryIndex directly from AppContext (matches server query_index)
    const currentQueryIndex = queryIndex;
    
    try {
      setDeletingAll(true);
      setShowDeleteAllModal(false);
      
      if (queryMode === 'tra') {
        // Delete all TRAKE answers
        toast.info('Deleting all TRAKE answers...', 500);
        
        const result = await deleteAllTRAKEAnswers(currentQueryIndex);
        
        if (result.success) {
          toast.success('All TRAKE answers deleted successfully!', 500);
        } else {
          console.error('Delete all TRAKE failed:', result.error);
          toast.error(result.error || 'Failed to delete all TRAKE answers', 500);
        }
      } else {
        // Delete all team answers
        toast.info('Deleting all team answers...', 500);
        
        const response = await TeamAnswerService.deleteAllTeamAnswers({
          query_index: currentQueryIndex,
          round: round || 'prelims'
        });
        
        if (response.success) {
          toast.success('All team answers deleted successfully!', 500);
          // Refresh the list
          if (onRefresh) onRefresh();
        } else {
          console.error('Delete all failed:', response.error);
          toast.error(response.error || 'Failed to delete all team answers', 500);
        }
      }
    } catch (error) {
      console.error(`Error deleting all ${queryMode === 'tra' ? 'TRAKE' : 'team'} answers:`, error);
      toast.error(`An error occurred while deleting all ${queryMode === 'tra' ? 'TRAKE' : 'team'} answers`, 500);
    } finally {
      setDeletingAll(false);
    }
  };

  // Handle edit team answer
  const handleEditTeamAnswer = (teamAnswer) => {
    setEditingItem(teamAnswer);
  };

  // Handle edit modal close
  const handleEditModalClose = () => {
    setEditingItem(null);
  };

  // Handle VideoPlayer open/close
  const handleFrameDoubleClickInternal = (frame) => {
    setIsVideoPlayerOpen(true);
    // Also call the parent's onFrameDoubleClick if provided
    if (onFrameDoubleClick) {
      onFrameDoubleClick(frame);
    }
  };

  const handleCloseVideoPlayer = () => {
    setIsVideoPlayerOpen(false);
  };

  // Handle send frame (delegate to onSubmit if available)
  const handleSendFrame = (frame) => {
    if (onSubmit) {
      onSubmit(frame);
    }
  };

  // Handle edit modal submit
  const handleEditModalSubmit = async (qaData) => {
    if (!editingItem) return;
    
    try {
      const response = await TeamAnswerService.updateTeamAnswer(editingItem.id, {
        video_name: editingItem.video_name,
        frame_index: editingItem.frame_index,
        url: editingItem.url,
        qa: qaData.qaText.trim(),
        query_index: editingItem.query_index,
        round: editingItem.round
      });
      
      if (response.success) {
        toast.success('Team answer updated successfully!', 500);
        handleEditModalClose();
        // SSE will handle the update automatically
      } else {
        toast.error(response.error || 'Failed to update team answer', 4000);
      }
    } catch (error) {
      console.error('Error updating team answer:', error);
      toast.error('An error occurred while updating team answer', 4000);
    }
  };

  // Handle frame zoom
  const handleFrameZoom = (frame) => {
    if (frame && frame.url) {
      setZoomImageUrl(frame.url);
      setZoomImageAlt(frame.video_name ? `${frame.video_name} - Frame ${frame.frame_index}` : 'Frame image');
      setZoomFrame(frame);
      setIsImageZoomOpen(true);
    }
  };

  // Handle close image zoom
  const handleCloseImageZoom = () => {
    setIsImageZoomOpen(false);
    setZoomImageUrl('');
    setZoomImageAlt('');
    setZoomFrame(null);
  };

  // Handle video play
  const handleVideoPlay = (frame) => {
    if (frame && frame.url) {
      setVideoPlayerUrl(frame.url);
      setVideoPlayerFrame(frame);
      setIsVideoPlayerOpen(true);
    }
  };

  // Sửa hàm onSubmit cho QA mode
  const handleFrameSubmit = useCallback((frame) => {
    if (queryMode === 'qa') {
      submitQAAnswer(frame, frame.qa || '');
    } else if (queryMode === 'kis') {
      submitKISAnswer(frame);
    } else if (queryMode === 'trake') {
      submitTRAKEAnswer([frame]);
    }
  }, [queryMode, submitQAAnswer, submitKISAnswer, submitTRAKEAnswer]);

  // DnD Kit drag handlers
  const handleDragEnd = async (event) => {
    const { active, over } = event;

    if (!over || active.id === over.id) {
      return;
    }

    const sourceId = active.id;
    const targetId = over.id;

    // Check if already sorting
    if (sortingItems.has(sourceId) || sortingItems.has(targetId)) {
      return;
    }

    try {
      // Add items to sorting set
      setSortingItems(prev => new Set(prev).add(sourceId).add(targetId));
      
      const response = await TeamAnswerService.sortTeamAnswer(sourceId, targetId);
      
      if (response.success) {
        toast.success('Team answers reordered successfully!', 500);
        // SSE will handle the update automatically
      } else {
        toast.error(response.error || 'Failed to reorder team answers', 2000);
      }
    } catch (error) {
      console.error('Error sorting team answers:', error);
      toast.error('An error occurred while reordering team answers', 2000);
    } finally {
      // Remove items from sorting set
      setSortingItems(prev => {
        const newSet = new Set(prev);
        newSet.delete(sourceId);
        newSet.delete(targetId);
        return newSet;
      });
    }
  };

  // Fetch team answers when component becomes visible (only once)
  useEffect(() => {
    if (isVisible && onRefresh) {
      onRefresh();
    }
  }, [isVisible, queryIndex, round]); // Remove onRefresh dependency to prevent infinite calls

  // Auto scroll to selected frame when component becomes visible
  useEffect(() => {
    if (isVisible && selectedFrameRef.current && teamAnswerRef.current) {
      const timeout = setTimeout(() => {
        const contentContainer = teamAnswerRef.current.querySelector('.team-answer__content');
        const centerFrameWrapper = selectedFrameRef.current;
        
        if (centerFrameWrapper && contentContainer) {
          // Get all frame wrappers to find the index of center frame
          const allFrameWrappers = contentContainer.querySelectorAll('.team-answer__frame-wrapper');
          const centerFrameIndex = Array.from(allFrameWrappers).indexOf(centerFrameWrapper);
          
          if (centerFrameIndex >= 0) {
            // Use fixed height for simple and accurate calculation
            const frameHeight = 160; // Fixed height from CSS
            const gap = 12.8; // 0.8rem gap (0.8 * 16px)
            const itemHeight = frameHeight + gap;
            const containerHeight = contentContainer.clientHeight;
            
            // Calculate scroll to center the specific frame
            const targetScrollTop = (centerFrameIndex * itemHeight) - (containerHeight / 2) + (frameHeight / 2);
            
            // Scroll immediately without animation for instant response
            contentContainer.scrollTop = Math.max(0, targetScrollTop);
          }
        }
      }, 100); // Small delay to ensure DOM is ready

      return () => clearTimeout(timeout);
    }
  }, [isVisible, selectedFrame?.video_name, selectedFrame?.frame_index]);

  // Initialize SSE connection when component mounts
  useEffect(() => {
    // Always initialize regular TeamAnswer SSE
    initializeSSE();

    // Cleanup on unmount
    return () => {
      closeSSE();
    };
  }, []); // Empty dependency array - only run on mount/unmount

  // Initialize TRAKE SSE connection based on queryMode
  useEffect(() => {
    if (queryMode === 'tra') {
      initializeTRAKESSE();
    } else {
      closeTRAKESSE();
    }

    // Cleanup when queryMode changes or component unmounts
    return () => {
      if (queryMode === 'tra') {
        closeTRAKESSE();
      }
    };
  }, [queryMode]); // Re-run when queryMode changes

  if (!isVisible) {
    return (
      <div className="team-answer team-answer--collapsed">
        <button 
          className="team-answer__toggle"
          onClick={onToggle}
          title="Show team answers"
        >
          <img src="/assets/team.svg" alt="Show" />
        </button>
      </div>
    );
  }

  // Get filtered team answers for current queryIndex and round
  const teamAnswers = getFilteredTeamAnswers();
  
  // Get current query info for modal message
  const currentQueryIndex = queryIndex;
  const currentRound = round || 'prelims';

  return (
    <div className={`team-answer ${isCompact ? 'team-answer--compact' : ''} ${className}`} ref={teamAnswerRef}>
      <ConfirmationModal
        isOpen={showDeleteAllModal}
        onClose={() => setShowDeleteAllModal(false)}
        onConfirm={handleConfirmDeleteAll}
        title={queryMode === 'tra' ? "Delete All TRAKE Answers" : "Delete All Team Answers"}
        message={queryMode === 'tra' ? 
          `Are you sure you want to delete all TRAKE answers for query ${queryIndex}? This action cannot be undone.` :
          `Are you sure you want to delete all team answers for query ${queryIndex} in ${round || 'prelims'} round? This action cannot be undone.`
        }
        confirmText="Delete All"
        cancelText="Cancel"
        isLoading={deletingAll}
      />
      <div className="team-answer__header">
        <div className="team-answer__status">
          {queryMode === 'tra' ? (
            <span 
              className={`team-answer__sse-indicator ${traKEsseConnected ? 'connected' : 'disconnected'}`}
              title={traKEsseConnected ? 'TRAKE real-time updates connected' : 'TRAKE real-time updates disconnected'}
            >
              {traKEsseConnected ? '🟢' : '🔴'}
            </span>
          ) : (
            <span 
              className={`team-answer__sse-indicator ${sseConnected ? 'connected' : 'disconnected'}`}
              title={sseConnected ? 'Real-time updates connected' : 'Real-time updates disconnected'}
            >
              {sseConnected ? '🟢' : '🔴'}
            </span>
          )}
        </div>
        {/* <div className="team-answer__title">
          {queryMode === 'tra' ? (
            <span>
              <span className="team-answer__icon">🎯</span>
              TRAKE Answers ({Array.isArray(currentQueryTRAKEAnswers) ? 
                (currentQueryTRAKEAnswers.length > 0 && currentQueryTRAKEAnswers[0].hasOwnProperty('group') ? 
                  currentQueryTRAKEAnswers.length : 
                  Object.keys(currentQueryTRAKEAnswers.reduce((groups, item) => ({ ...groups, [item.group || 1]: true }), {})).length
                ) : 0
              } groups)
            </span>
          ) : (
            <span>
              <span className="team-answer__icon">👥</span>
              Team Answers ({teamAnswers.length})
            </span>
          )}
        </div> */}
        <button 
          className="team-answer__reload"
          onClick={onRefresh}
          disabled={loading}
          title={queryMode === 'tra' ? "Reload TRAKE answers" : "Reload team answers"}
        >
          {loading ? (
            <span className="team-answer__spinner">⟳</span>
          ) : (
            <img src="/assets/reload.svg" alt="Reload" />
          )}
        </button>
        <button 
          className="team-answer__delete-all"
          onClick={queryMode === 'tra' ? handleDeleteAllTRAKEAnswers : handleDeleteAllTeamAnswers}
          disabled={deletingAll || loading}
          title={queryMode === 'tra' ? "Delete all TRAKE answers" : "Delete all team answers"}
        >
          {deletingAll ? (
            <span className="team-answer__spinner">⟳</span>
          ) : (
            <img src="/assets/trash-bin.svg" alt="Delete All" />
          )}
        </button>
        <button 
          className="team-answer__close"
          onClick={onToggle}
          title="Hide team answers"
        >
          <img src="/assets/team.svg" alt="Close" />
        </button>
      </div>
      
      <div className="team-answer__content">
        {queryMode === 'tra' ? (
          // Render TRAKE answers for TRA mode
          <TeamTRAKEAnswerList
            selectedFrame={selectedFrame}
            isVisible={true}
            onToggle={onToggle}
            onFrameSelect={onFrameSelect}
            onFrameDoubleClick={onFrameDoubleClick}
            allTRAKEAnswers={currentQueryTRAKEAnswers}
            setAllTRAKEAnswers={setAllTRAKEAnswers}
            onRefresh={fetchAllTRAKEAnswers}
            activeGroup={activeGroup}
            onSetActiveGroup={setActiveGroup}
            isCompact={isCompact}
          />
        ) : (
          // Render regular team answers for KIS/QA modes
          <>
            {loading && (
              <div className="team-answer__loading">
                <p>Loading team answers...</p>
              </div>
            )}
            
            {!loading && teamAnswers.length === 0 && (
              <div className="team-answer__empty">
                <p>No team answers found</p>
              </div>
            )}
             {!loading && teamAnswers.length > 0 && (
              <div className="team-answer__list">
                <DndContext
                  sensors={sensors}
                  collisionDetection={closestCenter}
                  onDragEnd={handleDragEnd}
                  modifiers={[restrictToVerticalAxis, restrictToParentElement]}
                >
                  <SortableContext
                    items={teamAnswers.map(item => item.id)}
                    strategy={verticalListSortingStrategy}
                  >
                    <div className="team-answer__grid">
                      {teamAnswers.map((teamAnswer) => {
                        const isSelected = selectedFrame && 
                          selectedFrame.video_name === teamAnswer.video_name && 
                          parseInt(selectedFrame.frame_index) === parseInt(teamAnswer.frame_index);
                        
                        return (
                          <SortableTeamAnswerItem
                            key={teamAnswer.id}
                            teamAnswer={teamAnswer}
                            isSelected={isSelected}
                            selectedFrameRef={isSelected ? selectedFrameRef : null}
                            onFrameSelect={onFrameSelect}
                            onFrameDoubleClick={handleFrameDoubleClickInternal}
                            onSubmit={handleFrameSubmit} // Sửa lại ở đây
                            queryMode={queryMode}
                            handleEditTeamAnswer={handleEditTeamAnswer}
                            handleDeleteTeamAnswer={handleDeleteTeamAnswer}
                            handleFrameZoom={handleFrameZoom}
                            deletingFrames={deletingFrames}
                            sortingItems={sortingItems}
                          />
                        );
                      })}
                    </div>
                  </SortableContext>
                </DndContext>
              </div>
            )}
          </>
        )}
      </div>

      {/* Edit Modal for team answers */}
      <TeamAnswerModal
        isOpen={!!editingItem}
        onClose={handleEditModalClose}
        onSubmit={handleEditModalSubmit}
        frame={editingItem}
        allTeamAnswers={allTeamAnswers}
        isEditMode={true}
      />

      {/* Image Zoom Modal */}
      <ImageZoomModal
        isOpen={isImageZoomOpen}
        onClose={handleCloseImageZoom}
        imageUrl={zoomImageUrl}
        imageAlt={zoomImageAlt}
        frame={zoomFrame}
      />

      {/* Video Player Modal */}
      {isVideoPlayerOpen && (
        <VideoPlayer
          isOpen={isVideoPlayerOpen}
          onClose={handleCloseVideoPlayer}
          currentFrame={selectedFrame}
          onFrameSelect={onFrameSelect}
          onSubmit={onSubmit}
          onSend={handleSendFrame}
          sendingFrames={new Set()} // TeamAnswer doesn't track sending frames
          allTeamAnswers={allTeamAnswers}
        />
      )}

      {/* Submission Modal */}
      <SubmissionModal
        isOpen={submissionModal.isOpen}
        onClose={closeSubmissionModal}
        onConfirm={handleSubmissionConfirm}
        submissionType={submissionModal.type}
        frameData={submissionModal.frameData}
        qaText={submissionModal.qaText}
        isSubmitting={submissionModal.isSubmitting}
        onRemoveTrakeItem={removeTempTrakeItem}
      />
    </div>
  );
};

// Sortable Item Component
const SortableTeamAnswerItem = ({
  teamAnswer,
  isSelected,
  selectedFrameRef,
  onFrameSelect,
  onFrameDoubleClick,
  onSubmit,
  queryMode,
  handleEditTeamAnswer,
  handleDeleteTeamAnswer,
  handleFrameZoom,
  handleVideoPlay,
  deletingFrames,
  sortingItems
}) => {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: teamAnswer.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.8 : 1,
    zIndex: isDragging ? 1000 : 1,
  };

  const frameId = `${teamAnswer.video_name}-${teamAnswer.frame_index}`;
  const isSorting = sortingItems.has(teamAnswer.id);

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`team-answer__item ${isSorting ? 'team-answer__item--sorting' : ''} ${isDragging ? 'team-answer__item--dragging' : ''}`}
      data-frame-id={frameId}
      data-frame-index={teamAnswer.frame_index}
      data-team-answer-id={teamAnswer.id}
      data-dragging={isDragging}
      {...attributes}
      {...listeners}
    >
      <div ref={isSelected ? selectedFrameRef : null}>
        <FrameItem
          frame={teamAnswer}
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
          onSubmit={onSubmit}
          onZoom={handleFrameZoom}
          showFilename={true}
          size="small"
          className="team-answer__frame"
        />
        {/* Edit button - only show for QA mode */}
        {queryMode === 'qa' && (
          <button
            className="team-answer__edit-btn"
            onClick={(e) => {
              e.stopPropagation();
              handleEditTeamAnswer(teamAnswer);
            }}
            title="Edit Q&A text"
          >
            <img src="/assets/edit.svg" alt="Edit" />
          </button>
        )}
        <button
          className={`team-answer__delete-btn ${
            deletingFrames.has(frameId) ? 'team-answer__delete-btn--loading' : ''
          }`}
          onClick={(e) => {
            e.stopPropagation();
            handleDeleteTeamAnswer(teamAnswer);
          }}
          disabled={deletingFrames.has(frameId)}
          title="Delete team answer"
        >
          {deletingFrames.has(frameId) ? (
            <span className="team-answer__spinner">⟳</span>
          ) : (
            <img src="/assets/trash-bin.svg" alt="Delete" />
          )}
        </button>

        {/* Image Zoom button
        <button
          className="team-answer__zoom-btn"
          onClick={(e) => {
            e.stopPropagation();
            // Set zoom image data
            setZoomImageUrl(teamAnswer.url);
            setZoomImageAlt(`Zoomed image for ${teamAnswer.video_name}`);
            setZoomFrame(teamAnswer);
            setIsImageZoomOpen(true);
          }}
          title="Zoom image"
        >
          <img src="/assets/zoom-in.svg" alt="Zoom" />
        </button> */}
      </div>
    </div>
  );
};

export default TeamAnswer;
