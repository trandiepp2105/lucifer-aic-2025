import React, { useState, useRef, useEffect, useCallback } from 'react';
import { translatorService } from '../../services/TranslatorService';
import { QueryService, getErrorMessage } from '../../services';
import { TeamAnswerService, AnswerService } from '../../services';
import { useToast } from '../Toast/ToastProvider';
import { useApp } from '../../contexts/AppContext';
import { getSessionIdFromUrl, getStageFromUrl, getViewModeFromUrl, updateUrlParams } from '../../utils/urlParams';
import { exportTeamAnswersToZip, exportAnswersToZip } from '../../utils/exportUtils';
import ConfirmationModal from '../ConfirmationModal';
import QueryInput from './QueryInput';
import SidebarQueries from './SidebarQueries';
import './Sidebar.scss';

const Sidebar = ({ 
  onFramesUpdate = () => {}, // Default empty function
  onAvailableStagesChange = () => {}, // Default empty function
  onSessionChange = () => {}, // Default empty function
  onLoadQueriesRegister = () => {}, // Default empty function
  mode = 'chat', // Default mode is chat
  queryIndexes = [], // For team-answer and answer modes
  isLoading = false, // Loading state for data
  onRefresh = null, // Refresh function for data
  allTeamAnswers = [], // All team answers data for export
  allAnswers = [], // All answers data for export
  csvFilenameFormat = 'query-{query_index}-{type}' // Custom CSV filename format
}) => {
  const { stage, viewMode, round, queryIndex, k, searchUrl, setStage, setViewMode, setQueryIndex } = useApp();
  const toast = useToast();
  
  // Local queries management - unified structure matching backend
  const [queries, setQueries] = useState([]); // Server queries
  const [localQueries, setLocalQueries] = useState([]); // Client-side query objects
  const [currentLocalQuery, setCurrentLocalQuery] = useState(null); // Current query being edited
  const [loading, setLoading] = useState(false);
  const [currentSession, setCurrentSession] = useState(null);
  const [currentStageQuery, setCurrentStageQuery] = useState(null);
  const [isRecording, setIsRecording] = useState(false);
  const [isTranslating, setIsTranslating] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState(null); // { queryIndex, mode }
  const [isDeleting, setIsDeleting] = useState(false);
  const [currentInputIndex, setCurrentInputIndex] = useState(-1); // Track focused input index
  const messagesEndRef = useRef(null);
  const hasInitialized = useRef(false);
  const hasLoadedQueries = useRef(false);

  // Create a new local query object matching backend structure
  const createLocalQuery = useCallback((overrides = {}) => {
    // For new queries (no id), start with empty strings for editing
    // For existing queries (with id), preserve null values for display
    const isNewQuery = !overrides.id;
    
    return {
      id: overrides.id || null,
      session: overrides.session || currentSession?.id || null,
      text: overrides.hasOwnProperty('text') ? overrides.text : (isNewQuery ? '' : null),
      ocr: overrides.hasOwnProperty('ocr') ? overrides.ocr : (isNewQuery ? '' : null),
      speech: overrides.hasOwnProperty('speech') ? overrides.speech : (isNewQuery ? '' : null),
      image: overrides.image || null,
      imageFile: overrides.imageFile || null, // Client-side file object
      imageRemoved: overrides.imageRemoved || false, // Track if user removed image
      time: overrides.time || new Date().toISOString(),
      background_sound: overrides.hasOwnProperty('background_sound') ? overrides.background_sound : (isNewQuery ? '' : null),
      stage: overrides.stage || stage || 1,
      created_at: overrides.created_at || new Date().toISOString(),
      updated_at: overrides.updated_at || new Date().toISOString(),
      ...overrides
    };
  }, [currentSession, stage]);

  // Initialize current local query for editing
  useEffect(() => {
    if (!currentLocalQuery) {
      setCurrentLocalQuery(createLocalQuery());
    }
  }, [currentLocalQuery, createLocalQuery]);

  // Map server queries to local queries
  const mapServerQueriesToLocal = (serverQueries) => {
    return serverQueries.map(query => createLocalQuery({
      id: query.id,
      session: query.session,
      text: query.text && query.text !== 'null' ? query.text : null,
      ocr: query.ocr && query.ocr !== 'null' ? query.ocr : null,
      speech: query.speech && query.speech !== 'null' ? query.speech : null,
      image: query.image && query.image !== 'null' ? query.image : null,
      time: query.time,
      background_sound: query.background_sound && query.background_sound !== 'null' ? query.background_sound : null,
      stage: query.stage,
      created_at: query.created_at,
      updated_at: query.updated_at
    }));
  };

  // Update local queries when server queries change
  useEffect(() => {
    if (queries.length > 0) {
      setLocalQueries(mapServerQueriesToLocal(queries));
    } else {
      setLocalQueries([]);
    }
  }, [queries]);

  // Update current stage query in localQueries directly
  const updateCurrentLocalQuery = useCallback((updates) => {
    setLocalQueries(prev => {
      const currentStageIndex = prev.findIndex(q => q.stage === stage);
      
      if (currentStageIndex >= 0) {
        // Update existing query for current stage
        const updatedQueries = [...prev];
        updatedQueries[currentStageIndex] = {
          ...updatedQueries[currentStageIndex],
          ...updates,
          updated_at: new Date().toISOString()
        };
        return updatedQueries;
      } else {
        // Create new query for current stage
        const newQuery = createLocalQuery({
          stage: stage,
          ...updates
        });
        return [...prev, newQuery];
      }
    });

    // Also update currentLocalQuery for input synchronization
    setCurrentLocalQuery(prev => ({
      ...prev,
      ...updates,
      updated_at: new Date().toISOString()
    }));
  }, [stage, createLocalQuery]);

  const updateUrlWithSession = (sessionId) => {
    updateUrlParams({ 
      session: sessionId,
      stage: stage,
      viewmode: viewMode 
    });
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  // Initialize new session
  const initializeSession = async () => {
    try {
      const response = await QueryService.createSession();
      if (response.success) {
        const sessionData = response.data.data; // Extract the actual session data
        setCurrentSession(sessionData);
        // Reset stage to 1 for new session
        handleInternalStageChange(1);
        // Update URL with new session and stage 1
        updateUrlParams({ 
          session: sessionData.id,
          stage: 1,
          viewmode: viewMode 
        });
        // Notify parent about session change
        if (onSessionChange) {
          onSessionChange(sessionData.id);
        }
        return sessionData;
      } else {
        toast.error('Failed to create session');
        return null;
      }
    } catch (error) {
      toast.error('Error creating session');
      return null;
    }
  };

  // Load session from URL or create new one
  const loadSessionFromUrl = async () => {
    const sessionIdFromUrl = getSessionIdFromUrl();
    
    if (sessionIdFromUrl) {
      // Try to validate the session exists by calling the session detail endpoint
      try {
        const response = await QueryService.validateSession(sessionIdFromUrl);
        
        if (response.success) {
          // Session exists, use it
          const sessionData = { id: parseInt(sessionIdFromUrl) };
          setCurrentSession(sessionData);
          // Notify parent about session change
          if (onSessionChange) {
            onSessionChange(sessionData.id);
          }
          return sessionData;
        } else if (response.status === 404) {
          // Session doesn't exist, create new one and update URL
          toast.info('Session not found, creating new session');
          updateUrlWithSession(null); // Remove invalid session from URL first
          return await initializeSession();
        } else {
          // Other error, create new session
          updateUrlWithSession(null); // Remove invalid session from URL
          return await initializeSession();
        }
      } catch (error) {
        // If validation fails, create new session
        updateUrlWithSession(null); // Remove invalid session from URL
        return await initializeSession();
      }
    } else {
      // No session in URL, create new one
      return await initializeSession();
    }
  };

  // Load queries
  const loadQueries = useCallback(async (sessionId = null) => {
    if (mode !== 'chat') return; // Only run in chat mode
    
    onFramesUpdate([]);
    const targetSessionId = sessionId || currentSession?.id;
    
    if (!targetSessionId) {
      return;
    }

    setLoading(true);
    try {
      const response = await QueryService.getQueries({
        session: targetSessionId,
        viewmode: viewMode,
        k: k,
        search_url: searchUrl, // Add search URL to params
      });

      if (response.success) {
        // API trả về {data: Array} hoặc trực tiếp Array
        const queriesArray = Array.isArray(response.data) ? response.data : (response.data.data || []);
        // Reverse to show newest queries at bottom (like chat messages)
        const reversedQueries = [...queriesArray].reverse();
        setQueries(reversedQueries);
        
        // Extract frames from GET response and update parent component
        if (response.data.frames && onFramesUpdate) {
          onFramesUpdate(response.data.frames);
        }
      } else {
        toast.error('Failed to load queries');
      }
    } catch (error) {
      toast.error('Error loading queries');
    } finally {
      setLoading(false);
    }
  }, [currentSession, viewMode, k, searchUrl, onFramesUpdate, toast, mode]);

  useEffect(() => {
    // Initialize session when component mounts
    const initializeApp = async () => {
      if (hasInitialized.current || mode !== 'chat') {
        return;
      }
      
      hasInitialized.current = true;
      
      // Load stage and viewMode from URL - AppContext handles this now
      // Just sync if there are differences
      const urlStage = getStageFromUrl();
      const urlViewMode = getViewModeFromUrl();
      
      if (urlStage !== stage) {
        setStage(urlStage);
      }
      
      if (urlViewMode !== viewMode) {
        setViewMode(urlViewMode);
      }
      
      const session = await loadSessionFromUrl();
      if (session) {
        await loadQueries(session.id);
      }
      hasLoadedQueries.current = true; // Mark that we've completed initial load
    };
    initializeApp();
  }, [mode]); // Add mode dependency

  useEffect(() => {
    scrollToBottom();
  }, [queries]);

  // Note: No need to reload queries when stage changes - it's just UI state
  // Only reload queries when:
  // 1. Page reload/session change
  // 2. After creating new query
  // 3. After editing existing query  
  // 4. After deleting query

  // Sync stage and viewMode with URL
  useEffect(() => {
    if (currentSession) {
      updateUrlParams({
        session: currentSession.id,
        stage: stage,
        viewmode: viewMode
      });
    }
  }, [stage, viewMode, currentSession]);

  // Reload queries when viewMode or k changes
  useEffect(() => {
    if (currentSession && mode === 'chat' && hasLoadedQueries.current) {
      loadQueries(currentSession.id);
    }
  }, [viewMode, k, currentSession, loadQueries, mode]);

  // Load query content when stage changes (for edit mode)
  // Sync currentLocalQuery with the corresponding item in localQueries
  useEffect(() => {
    const stageQuery = localQueries.find(q => q.stage === stage);
    setCurrentStageQuery(stageQuery);
    
    // Update currentLocalQuery to reference the same object in localQueries
    if (stageQuery) {
      // Load existing query for editing - create a copy for input binding
      setCurrentLocalQuery({ ...stageQuery });
    } else {
      // Create new query for this stage, but don't add to localQueries yet
      setCurrentLocalQuery(createLocalQuery({ stage: stage }));
    }
  }, [stage, localQueries, createLocalQuery]);

  // Notify parent about available stages when queries change
  useEffect(() => {
    const maxStageFromQueries = queries.length > 0 ? Math.max(...queries.map(q => q.stage)) : 0;
    const availableStages = maxStageFromQueries + 1;
    
    if (onAvailableStagesChange) {
      onAvailableStagesChange(availableStages);
    }
  }, [queries, onAvailableStagesChange]); // Re-add dependency now that it's useCallback

  // Register loadQueries function with parent component
  useEffect(() => {
    if (onLoadQueriesRegister) {
      onLoadQueriesRegister(loadQueries);
    }
  }, [onLoadQueriesRegister, loadQueries]);

  // Keyboard shortcuts for translation
  useEffect(() => {
    const handleKeyDown = (e) => {
      // Only handle keyboard events if we're in chat mode and no modals are open
      if (mode !== 'chat') return;
      
      // Check if any modal is open by looking for modal elements that are actually visible
      const modals = document.querySelectorAll('.team-answer-modal, .submission-modal, .confirmation-modal');
      if (modals.length > 0) {
        // If any modal exists in DOM (since they're conditionally rendered), don't handle keyboard events
        console.log('🚫 Sidebar: Modal detected, ignoring keyboard event');
        return;
      }
      
      // Ctrl + Delete: Delete current stage query
      if (e.ctrlKey && e.key === 'Delete') {
        e.preventDefault();
        handleDeleteCurrentStageQuery();
        return;
      }
      
      // Ctrl + E: Translate focused input to English
      if (e.ctrlKey && e.key === 'e') {
        e.preventDefault();
        handleTranslateFocusedInput('en'); // Direct call, no debounce
        return;
      }
      
      // Ctrl + Q: Translate focused input to Vietnamese
      if (e.ctrlKey && e.key === 'q') {
        e.preventDefault();
        handleTranslateFocusedInput('vi'); // Direct call, no debounce
        return;
      }

      // Enter key: Send query if any field has value
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSendQueryIfReady();
        return;
      }

      // Arrow key navigation between inputs - only when not typing in an input
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        // This navigation is now handled by QueryInput component
        return;
      }
    };

    // Listen on document level to catch all keyboard events only in chat mode
    if (mode === 'chat') {
      document.addEventListener('keydown', handleKeyDown, true);
    }
    
    return () => {
      if (mode === 'chat') {
        document.removeEventListener('keydown', handleKeyDown, true);
      }
    };
  }, [mode, currentInputIndex, currentLocalQuery?.ocr, currentLocalQuery?.text, currentLocalQuery?.image]); // Removed speech dependency

  // Check if any field has value and send query if ready
  const handleSendMessage = async () => {
    if (!currentLocalQuery) return;
    
    const hasText = currentLocalQuery.text?.trim();
    const hasOcr = currentLocalQuery.ocr?.trim();
    // const hasSpeech = currentLocalQuery.speech?.trim(); // Commented out - Speech disabled
    const hasImage = currentLocalQuery.image || currentLocalQuery.imageFile;
    
    if (!hasText && !hasOcr && !hasImage) return; // Removed hasSpeech check
    
    if (!currentSession) {
      toast.error('No active session. Please create a new session.');
      return;
    }

    setLoading(true);

    try {
      // Use stage from context
      const stageAtSendTime = stage;
      
      const queryData = {
        session: currentSession.id,
        stage: stageAtSendTime,
        text: hasText || null,
        ocr: hasOcr || null,
        // speech: hasSpeech || null, // Commented out - Speech disabled
        image: currentLocalQuery.imageFile || (currentLocalQuery.imageRemoved ? null : undefined), // Send null if explicitly removed, undefined if unchanged
      };

      let response;
      
      // Check if we're updating existing query or creating new one
      if (currentLocalQuery.id) {
        // Update existing query
        response = await QueryService.updateQuery(currentLocalQuery.id, queryData);
      } else {
        // Create new query
        response = await QueryService.createQuery(queryData);
      }

      if (response.success) {
        // Reset current local query for next input
        setCurrentLocalQuery(createLocalQuery());

        // Reload queries to get fresh data with proper formatting
        // This will also load frames automatically from backend
        await loadQueries(currentSession.id);

        toast.success(currentLocalQuery.id ? 'Query updated successfully!' : 'Query created successfully!');
        
        // Note: We don't change the current stage after creating a new query
        // The new stage is available for future use but we stay on current stage
        
        // Scroll to bottom to show new/updated query
        setTimeout(() => {
          if (messagesEndRef.current) {
            messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
          }
        }, 100);
      } else {
        const errorMessage = getErrorMessage(response);
        toast.error(`Failed to create query: ${errorMessage}`);
      }
    } catch (error) {
      toast.error('Network error occurred while creating query.');
    } finally {
      setLoading(false);
    }
  };

  // Check if any field has value and send query if ready
  const handleSendQueryIfReady = () => {
    if (!currentLocalQuery) return;
    
    const hasTextInput = currentLocalQuery.text?.trim()?.length > 0;
    const hasOcrInput = currentLocalQuery.ocr?.trim()?.length > 0;
    // const hasSpeechInput = currentLocalQuery.speech?.trim()?.length > 0; // Commented out - Speech disabled
    const hasImageInput = currentLocalQuery.image !== null || currentLocalQuery.imageFile !== null;

    if (hasTextInput || hasOcrInput || hasImageInput) { // Removed hasSpeechInput
      handleSendMessage();
    }
  };

  // Delete current stage query (Ctrl+Delete)
  const handleDeleteCurrentStageQuery = async () => {
    // Check if current stage has a query (not a temporary stage)
    if (!currentStageQuery) {
      toast.warning('No query to delete at current stage');
      return;
    }

    setLoading(true);
    try {
      // Delete the query
      const deleteResponse = await QueryService.deleteQuery(currentStageQuery.id);
      
      if (deleteResponse.success) {
        // Reload queries to get updated list with adjusted stages
        await loadQueries(currentSession.id);
        
        // Reset current local query to empty state
        setCurrentLocalQuery(createLocalQuery({ stage: stage }));
        setCurrentStageQuery(null);

        toast.success('Query deleted successfully!');
      } else {
        const errorMessage = getErrorMessage(deleteResponse);
        toast.error(`Failed to delete query: ${errorMessage}`);
      }
    } catch (error) {
      toast.error('Network error occurred while deleting query.');
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    // Only handle if no modals are open
    const modals = document.querySelectorAll('.team-answer-modal, .submission-modal, .confirmation-modal');
    if (modals.length > 0) {
      // If any modal exists in DOM (since they're conditionally rendered), don't handle keyboard events
      console.log('🚫 Sidebar: Modal detected in handleKeyPress, ignoring keyboard event');
      return;
    }
    
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handlePaste = (e) => {
    const items = e.clipboardData.items;
    for (let item of items) {
      if (item.type.indexOf('image') !== -1) {
        const file = item.getAsFile();
        setUploadedImageFile(file);
        setImageRemoved(false); // Reset flag when image is pasted
        const reader = new FileReader();
        reader.onload = (e) => {
          setUploadedImage(e.target.result);
        };
        reader.readAsDataURL(file);
        e.preventDefault();
        break;
      }
    }
  };

  // Handle drop events for drag & drop from frame items
  const handleDragOver = (e) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'copy';
  };

  const handleDragEnter = (e) => {
    e.preventDefault();
    // Add visual feedback for drop zone
    e.currentTarget.classList.add('sidebar__drop-zone--active');
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    // Remove visual feedback only if leaving the drop zone completely
    if (!e.currentTarget.contains(e.relatedTarget)) {
      e.currentTarget.classList.remove('sidebar__drop-zone--active');
    }
  };

  const handleDrop = async (e) => {
    e.preventDefault();
    e.currentTarget.classList.remove('sidebar__drop-zone--active');
    
    try {
      const dragData = JSON.parse(e.dataTransfer.getData('application/json'));
      
      if (dragData.type === 'frame-image' && dragData.url) {
        // Convert frame URL to blob and set as uploaded image
        const response = await fetch(dragData.url);
        const blob = await response.blob();
        
        // Create file object from blob
        const file = new File([blob], `${dragData.frame.filename}.jpg`, { type: 'image/jpeg' });
        setUploadedImageFile(file);
        setImageRemoved(false); // Reset flag when image is dragged from frame
        
        // Create data URL for preview
        const reader = new FileReader();
        reader.onload = (e) => {
          setUploadedImage(e.target.result);
        };
        reader.readAsDataURL(blob);
        
        toast.success(`Image from ${dragData.frame.filename} added to query`);
      }
    } catch (error) {
      console.error('Error handling dropped frame:', error);
      toast.error('Failed to add image from frame');
    }
  };

  const handleTranslateFocusedInput = async (targetLang) => {
    if (currentInputIndex === -1) {
      toast.info('Please focus on an input field first');
      return;
    }

    if (!currentLocalQuery) {
      toast.info('No query to translate');
      return;
    }

    let textToTranslate = '';
    let fieldKey = '';
    let fieldName = '';

    // Determine which input is focused
    switch (currentInputIndex) {
      case 0: // OCR
        textToTranslate = currentLocalQuery.ocr?.trim() || '';
        fieldKey = 'ocr';
        fieldName = 'OCR text';
        break;
      case 1: // Text (Speech removed, Text is now index 1)
        textToTranslate = currentLocalQuery.text?.trim() || '';
        fieldKey = 'text';
        fieldName = 'Text';
        break;
      // case 1: // Speech - COMMENTED OUT (Speech input disabled)
      //   textToTranslate = currentLocalQuery.speech?.trim() || '';
      //   fieldKey = 'speech';
      //   fieldName = 'Speech text';
      //   break;
      default:
        toast.info('Please focus on an input field first');
        return;
    }

    if (!textToTranslate) {
      toast.info(`${fieldName} is empty`);
      return;
    }

    setIsTranslating(true);
    try {
      const translated = await translatorService.translateText(textToTranslate, targetLang);
      if (translated && translated !== textToTranslate) {
        updateCurrentLocalQuery({ [fieldKey]: translated });
        const langName = targetLang === 'en' ? 'English' : 'Vietnamese';
        toast.success(`${fieldName} translated to ${langName}!`);
      } else {
        toast.info('Text is already in the target language or translation failed');
      }
    } catch (error) {
      toast.error(`Failed to translate ${fieldName.toLowerCase()}`);
    } finally {
      setIsTranslating(false);
    }
  };

  const handleDeleteAllQueries = async () => {
    if (!currentSession || queries.length === 0) return;
    
    // Show confirmation dialog
    const confirmed = window.confirm(
      `Are you sure you want to delete the current session with all ${queries.length} queries? This action cannot be undone.`
    );
    
    if (!confirmed) return;

    setLoading(true);
    try {
      const response = await QueryService.deleteSession(currentSession.id);
      
      if (response.success) {
        setQueries([]); // Clear local state
        // Create new session
        const newSession = await initializeSession();
        if (newSession) {
          toast.success('Session deleted and new session created!');
        } else {
          toast.success('Session deleted successfully!');
        }
      } else {
        const errorMessage = getErrorMessage(response);
        toast.error(`Failed to delete session: ${errorMessage}`);
      }
    } catch (error) {
      toast.error('Network error occurred while deleting session.');
    } finally {
      setLoading(false);
    }
  };

  // Delete individual query
  const handleDeleteQuery = async (queryId) => {
    try {
      const response = await QueryService.deleteQuery(queryId);
      
      if (response.success) {
        // Reload queries for current session to ensure consistency
        if (currentSession) {
          await loadQueries(currentSession.id);
        }
        toast.success('Query deleted successfully!');
      } else {
        const errorMessage = getErrorMessage(response);
        toast.error(`Failed to delete query: ${errorMessage}`);
      }
    } catch (error) {
      toast.error('Network error occurred while deleting query.');
    }
  };

  const formatTime = (timestamp) => {
    return timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  // Handle add session button
  const handleAddSession = async () => {
    try {
      // Don't use hasInitialized check for manual session creation
      const response = await QueryService.createSession();
      if (response.success) {
        const sessionData = response.data.data; // Extract the actual session data
        setCurrentSession(sessionData);
        // Reset stage to 1 for new session
        handleInternalStageChange(1);
        // Update URL with new session and stage 1
        updateUrlParams({ 
          session: sessionData.id,
          stage: 1,
          viewmode: viewMode 
        });
        // Notify parent about session change
        if (onSessionChange) {
          onSessionChange(sessionData.id);
        }
        // Clear current queries to show new empty session
        setQueries([]);
        toast.success('New session created!');
      } else {
        toast.error('Failed to create new session');
      }
    } catch (error) {
      toast.error('Failed to create new session');
    }
  };

  // Handle stage change from external components
  const handleInternalStageChange = (newStage) => {
    setStage(newStage);
    // Update URL params
    updateUrlParams({ stage: newStage });
    
    // Load the query for the new stage into currentLocalQuery
    const stageQuery = localQueries.find(q => q.stage === newStage);
    if (stageQuery) {
      // Load existing query for editing
      setCurrentLocalQuery({ ...stageQuery });
    } else {
      // Create new query for this stage
      setCurrentLocalQuery(createLocalQuery({ stage: newStage }));
    }
  };

  // Handle viewMode change from external components  
  const handleInternalViewModeChange = (newViewMode) => {
    setViewMode(newViewMode);
    // Update URL params
    updateUrlParams({ viewmode: newViewMode });
  };

  // Calculate max stage from existing queries + 1 for new stage
  const maxStageFromQueries = localQueries.length > 0 ? Math.max(...localQueries.map(q => q.stage)) : 0;
  const availableStages = maxStageFromQueries + 1; // Always allow one more stage for new query
  
  // Check if current stage has existing query (edit mode vs create mode)
  const isEditMode = !!currentStageQuery;

  // Helper function to check if a field has a valid value
  const hasValidValue = (value) => {
    return value && 
           value !== 'null' && 
           value !== null && 
           value !== undefined && 
           typeof value === 'string' && 
           value.trim() !== '';
  };

  // Render query index list for team-answer and answer modes
  // Handle export functionality
  const handleExport = async () => {
    try {
      if (mode === 'team-answer') {
        if (!allTeamAnswers || allTeamAnswers.length === 0) {
          toast.warning('No team answers to export', 3000);
          return;
        }
        
        toast.info('Generating export file...', 1000);
        await exportTeamAnswersToZip(allTeamAnswers, round, csvFilenameFormat);
        toast.success('Export completed successfully!', 2000);
        
      } else if (mode === 'answer') {
        if (!allAnswers || allAnswers.length === 0) {
          toast.warning('No answers to export', 3000);
          return;
        }
        
        toast.info('Generating export file...', 1000);
        await exportAnswersToZip(allAnswers, round, csvFilenameFormat);
        toast.success('Export completed successfully!', 2000);
      }
    } catch (error) {
      console.error('Export error:', error);
      toast.error(error.message || 'Failed to export data', 4000);
    }
  };

  // Handle delete query index items
  const handleDeleteQueryIndex = (queryIndex, mode) => {
    setDeleteTarget({ queryIndex, mode });
    setShowDeleteModal(true);
  };

  const confirmDeleteQueryIndex = async () => {
    if (!deleteTarget) return;
    
    const { queryIndex: targetQueryIndex, mode: targetMode } = deleteTarget;
    
    try {
      setIsDeleting(true);
      toast.info(`Deleting ${targetMode === 'team-answer' ? 'team answers' : 'answers'} for query ${targetQueryIndex}...`, 1000);
      
      if (targetMode === 'team-answer') {
        // Delete all team answers for this query index
        const response = await TeamAnswerService.deleteAllTeamAnswers({
          query_index: targetQueryIndex,
          round: round || 'prelims'
        });
        
        if (response.success) {
          toast.success(`All team answers for query ${targetQueryIndex} deleted successfully!`, 2000);
        } else {
          toast.error(response.error || `Failed to delete team answers for query ${targetQueryIndex}`, 4000);
        }
      } else if (targetMode === 'answer') {
        // Delete all answers for this query index
        const response = await AnswerService.deleteAllAnswers({
          query_index: targetQueryIndex,
          round: round || 'prelims'
        });
        
        if (response.success) {
          toast.success(`All answers for query ${targetQueryIndex} deleted successfully!`, 2000);
        } else {
          toast.error(response.error || `Failed to delete answers for query ${targetQueryIndex}`, 4000);
        }
      }
      
      // Refresh data after deletion
      if (onRefresh) {
        await onRefresh();
      }
      
    } catch (error) {
      console.error('Error deleting items:', error);
      toast.error(`Failed to delete ${targetMode === 'team-answer' ? 'team answers' : 'answers'}`, 4000);
    } finally {
      setIsDeleting(false);
      setShowDeleteModal(false);
      setDeleteTarget(null);
    }
  };

  const cancelDeleteQueryIndex = () => {
    setShowDeleteModal(false);
    setDeleteTarget(null);
  };

  const renderQueryIndexList = () => {
    if (mode !== 'team-answer' && mode !== 'answer') {
      return null;
    }

    return (
      <div className="sidebar__query-index-list">
        <div className="sidebar__header">
          <button 
            onClick={handleExport}
            disabled={isLoading || queryIndexes.length === 0}
            className="sidebar__export-btn"
            title="Export data"
          >
            <img src="/assets/export.svg" alt="Export" className="sidebar__action-icon" />
          </button>
          <h3>{mode === 'team-answer' ? 'Team Answers' : 'Final Answers'}</h3>
          {onRefresh && (
            <button 
              onClick={onRefresh}
              disabled={isLoading}
              className="sidebar__refresh-btn"
              title="Refresh data"
            >
              {isLoading ? (
                <span className="sidebar__loading-dots">...</span>
              ) : (
                <img src="/assets/reload.svg" alt="Reload" className="sidebar__action-icon" />
              )}
            </button>
          )}
        </div>
        
        <div className="sidebar__content">
          {isLoading ? (
            <div className="sidebar__loading">Loading...</div>
          ) : queryIndexes.length === 0 ? (
            <div className="sidebar__no-data">
              No {mode === 'team-answer' ? 'team answers' : 'answers'} found
            </div>
          ) : (
            <div className="sidebar__queries">
              {queryIndexes.map(index => (
                <div
                  key={index}
                  className={`sidebar__query-item ${queryIndex === index ? 'sidebar__query-item--active' : ''}`}
                  onClick={() => {
                    setQueryIndex(index);
                  }}
                >
                  <div className="sidebar__query-content">
                    <div className="sidebar__query-title">Query {index}</div>
                    <div className="sidebar__query-meta">
                      {mode === 'team-answer' ? 'Team Answer' : 'Final Answer'}
                    </div>
                  </div>
                  <button
                    className="sidebar__delete-btn"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteQueryIndex(index, mode);
                    }}
                    title={`Delete ${mode === 'team-answer' ? 'team answers' : 'answers'} for Query ${index}`}
                  >
                    <img src="/assets/trash-bin.svg" alt="Delete" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="sidebar">
      {/* Render query index list for team-answer and answer modes */}
      {(mode === 'team-answer' || mode === 'answer') ? (
        renderQueryIndexList()
      ) : (
        <>
          {/* Original chat sidebar content */}
          <div className="sidebar__header">
        {/* <button 
          className={`sidebar__action-btn sidebar__delete-btn ${!currentSession || filteredQueries.length === 0 ? 'sidebar__delete-btn--disabled' : ''}`}
          onClick={handleDeleteAllQueries}
          disabled={!currentSession || filteredQueries.length === 0}
          title={!currentSession ? "No active session" : filteredQueries.length === 0 ? `No queries in Stage ${stage}` : `Delete current session with ${queries.length} total queries`}
        >
          <svg 
            width="16" 
            height="16" 
            viewBox="0 0 24 24" 
            fill="none" 
            xmlns="http://www.w3.org/2000/svg"
            className="sidebar__delete-icon"
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
        </button> */}
        {round === 'final' ? (
          <h3>Query History</h3>
        ) : (
          <div className="sidebar__query-index">
            <label htmlFor="queryIndex">Index:</label>
            <input
              id="queryIndex"
              type="number"
              value={queryIndex}
              onChange={(e) => {
                const value = e.target.value;
                // Allow empty string for deletion
                if (value === '') {
                  setQueryIndex('');
                  return;
                }
                // Only allow numbers
                if (/^\d+$/.test(value)) {
                  const numValue = parseInt(value, 10);
                  if (numValue >= 1 && numValue <= 999) {
                    setQueryIndex(numValue);
                  }
                }
              }}
              onBlur={(e) => {
                // If empty when focus is lost, set to 1
                if (e.target.value === '') {
                  setQueryIndex(1);
                }
              }}
              onKeyDown={(e) => {
                // Prevent non-numeric characters (except backspace, delete, arrow keys, etc.)
                if (!/[\d]/.test(e.key) && 
                    !['Backspace', 'Delete', 'ArrowLeft', 'ArrowRight', 'Tab'].includes(e.key)) {
                  e.preventDefault();
                }
              }}
              min="1"
              max="999"
              className="sidebar__query-index-input"
            />
          </div>
        )}
        <button 
          className="sidebar__action-btn sidebar__add-btn"
          onClick={handleAddSession}
          title="Add new session"
        >
          <svg 
            width="16" 
            height="16" 
            viewBox="0 0 24 24" 
            fill="none" 
            xmlns="http://www.w3.org/2000/svg"
            className="sidebar__add-icon"
          >
            <path 
              d="M12 4V20M4 12H20" 
              stroke="currentColor" 
              strokeWidth="2" 
              strokeLinecap="round" 
              strokeLinejoin="round"
            />
          </svg>
        </button>
      </div>

      <div 
        className="sidebar__chat sidebar__drop-zone" 
        onPaste={handlePaste}
        onDragOver={handleDragOver}
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <SidebarQueries
          loading={loading}
          filteredQueries={localQueries}
          stage={stage}
          onStageChange={handleInternalStageChange}
          onDeleteQuery={handleDeleteQuery}
          messagesEndRef={messagesEndRef}
        />

          <QueryInput
            currentLocalQuery={currentLocalQuery}
            updateCurrentLocalQuery={updateCurrentLocalQuery}
            isRecording={isRecording}
            setIsRecording={setIsRecording}
            isTranslating={isTranslating}
            setIsTranslating={setIsTranslating}
            currentInputIndex={currentInputIndex}
            setCurrentInputIndex={setCurrentInputIndex}
            loading={loading}
            onSendMessage={handleSendMessage}
            onKeyPress={handleKeyPress}
            onPaste={handlePaste}
            onDragOver={handleDragOver}
            onDragEnter={handleDragEnter}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
          />

      </div>
        </>
      )}
      
      {/* Delete Confirmation Modal */}
      <ConfirmationModal
        isOpen={showDeleteModal}
        onClose={cancelDeleteQueryIndex}
        onConfirm={confirmDeleteQueryIndex}
        title={`Delete ${deleteTarget?.mode === 'team-answer' ? 'Team Answers' : 'Final Answers'}`}
        message={`Are you sure you want to delete all ${deleteTarget?.mode === 'team-answer' ? 'team answers' : 'final answers'} for Query ${deleteTarget?.queryIndex} in ${round || 'prelims'} round? This action cannot be undone.`}
        confirmText="Delete All"
        cancelText="Cancel"
        isLoading={isDeleting}
      />
    </div>
  );
};

export default Sidebar;
