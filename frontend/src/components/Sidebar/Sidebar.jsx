import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { translatorService } from '../../services/TranslatorService';
import { QueryService, getErrorMessage } from '../../services';
import { TeamAnswerService, AnswerService } from '../../services';
import { useToast } from '../Toast/ToastProvider';
import { useApp } from '../../contexts/AppContext';
import { getSessionIdFromUrl, getStageFromUrl, getViewModeFromUrl, updateUrlParams } from '../../utils/urlParams';
import { exportTeamAnswersToZip, exportAnswersToZip } from '../../utils/exportUtils';
import { ExportTeamAnswerUtils } from '../../utils/exportTeamAnswerUtils';
import { QueryModeUtils } from '../../utils/queryModeUtils';
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
  allAnswers = [] // All answers data for export
}) => {
  const { stage, viewMode, round, queryIndex, k, searchUrl, session, sessionLoading, queryMode, csvFormat, temporalTime, setStage, setViewMode, setQueryIndex, setQueryMode, setSession } = useApp();
  const toast = useToast();
  
  // Local queries management - unified structure matching backend
  const [queries, setQueries] = useState([]); // Server queries
  const [localQueries, setLocalQueries] = useState([]); // Client-side query objects
  const [currentLocalQuery, setCurrentLocalQuery] = useState(null); // Current query being edited
  const [hiddenQueries, setHiddenQueries] = useState([]); // Hidden queries with original index: [{ query, originalIndex }]
  const [loading, setLoading] = useState(false);
  const [currentStageQuery, setCurrentStageQuery] = useState(null);
  const [isRecording, setIsRecording] = useState(false);
  const [isTranslating, setIsTranslating] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState(null); // { queryIndex, mode }
  const [isDeleting, setIsDeleting] = useState(false);
  const [currentInputIndex, setCurrentInputIndex] = useState(-1); // Track focused input index
  const [isSyncing, setIsSyncing] = useState(false);
  
  const messagesEndRef = useRef(null);
  const hasInitialized = useRef(false);
  const hasLoadedQueries = useRef(false);

  // Create a new local query object matching backend structure
  const createLocalQuery = useCallback((overrides = {}) => {
    const isNewQuery = !overrides.id;
    
    return {
      id: overrides.id || null,
      session: overrides.session || session || null,
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
  }, [session, stage]);

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
        const oldQuery = updatedQueries[currentStageIndex];
        updatedQueries[currentStageIndex] = {
          ...oldQuery,
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
    setCurrentLocalQuery(prev => {
      const updated = {
        ...prev,
        ...updates,
        updated_at: new Date().toISOString()
      };
      return updated;
    });
  }, [stage, createLocalQuery]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  // Load queries for current session
  const loadQueries = useCallback(async (sessionId = null) => {
    
    // reset local queries
    onFramesUpdate([])

    
    // Use sessionId parameter first, then session from AppContext
    const targetSessionId = sessionId || session;
    if (!targetSessionId) return;
    
    setLoading(true);
    try {
      const response = await QueryService.getQueries({
        session: targetSessionId,
        viewmode: viewMode,
        k: k,
        temporal_time: temporalTime,
        search_url: searchUrl
      });

      if (response.success) {
        const queriesArray = Array.isArray(response.data) ? response.data : (response.data.data || []);
        const reversedQueries = [...queriesArray].reverse();
        setQueries(reversedQueries);
        
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
  }, [session, viewMode, k, temporalTime, searchUrl, onFramesUpdate, toast, mode]);

  // Helper functions needed by keyboard navigation
  const handleInternalStageChange = (newStage) => {
    setStage(newStage);
    updateUrlParams({ stage: newStage });
    
    const stageQuery = localQueries.find(q => q.stage === newStage);
    if (stageQuery) {
      setCurrentLocalQuery({ ...stageQuery });
    } else {
      setCurrentLocalQuery(createLocalQuery({ stage: newStage }));
    }
    
    // Don't notify about available stages here - let useEffect handle it
    // The notification happens in useEffect when localQueries changes
  };

  // Check if query has content to allow operations
  const queryHasContent = useCallback((query) => {
    return (query.text && query.text.trim()) || 
           (query.ocr && query.ocr.trim()) || (query.speech && query.speech.trim()) ||
           (query.image);
  }, []);

  // Sync localQueries to backend
  const syncQueriesToBackend = useCallback(async () => {
    if (!session || sessionLoading || isSyncing) {
      return;
    }
    
    setIsSyncing(true);
    try {
      const queriesToSync = localQueries
        .filter(query => query.id || queryHasContent(query))
        .map(query => {
          
          const syncQuery = {
            stage: query.stage,
            time: query.time || new Date().toISOString()
          };
          
          if (query.id) {
            syncQuery.id = query.id;
          }
          
          syncQuery.text = query.text && query.text.trim() ? query.text : null;
          syncQuery.ocr = query.ocr && query.ocr.trim() ? query.ocr : null;
          syncQuery.speech = query.speech && query.speech.trim() ? query.speech : null;
          syncQuery.background_sound = query.background_sound && query.background_sound.trim() ? query.background_sound : null;
          
          if (query.imageFile) {
            // Don't send data URL, file will be sent separately in FormData
            syncQuery.image = null;
          } else if (query.imageRemoved) {
            // Explicitly remove image
            syncQuery.image = null;
          } else {
            // Don't include image field if no changes - let backend keep existing image
            // Only include if it's a new data URL (not a URL starting with http)
            if (query.image && !query.image.startsWith('http')) {
              syncQuery.image = query.image;
            }
            // If it's a URL (existing image), don't include the field to avoid changes
          }
          
          return syncQuery;
        });

      // Collect image files for FormData upload
      const imageFiles = localQueries
        .filter(q => q.imageFile)
        .map(q => ({
          stage: q.stage,
          file: q.imageFile
        }));

      const response = await QueryService.batchUpdateQueries(session, queriesToSync, imageFiles);
      
      if (response.success) {
        // No need for separate image uploads anymore - they're handled in batch request
        // Reload all queries from server to get fresh data
        await loadQueries(session);
      } else {
        console.error('Sync failed:', response.error);
        toast.error(response.error || 'Failed to sync queries', 4000);
      }
    } catch (error) {
      console.error('Sync error:', error);
      toast.error('Failed to sync queries', 4000);
    } finally {
      setIsSyncing(false);
    }
  }, [session, sessionLoading, localQueries, queries, isSyncing, queryHasContent, toast, loadQueries]);

  // Helper function to sync specific queries to backend
  const syncSpecificQueries = useCallback(async (queriesToUse) => {
    if (!session || sessionLoading || isSyncing) {
      return;
    }
    
    setIsSyncing(true);
    try {
      const queriesToSync = queriesToUse
        .filter(query => query.id || queryHasContent(query))
        .map(query => {
          const syncQuery = {
            stage: query.stage,
            time: query.time || new Date().toISOString()
          };
          
          if (query.id) {
            syncQuery.id = query.id;
          }
          
          syncQuery.text = query.text && query.text.trim() ? query.text : null;
          syncQuery.ocr = query.ocr && query.ocr.trim() ? query.ocr : null;
          syncQuery.speech = query.speech && query.speech.trim() ? query.speech : null;
          syncQuery.background_sound = query.background_sound && query.background_sound.trim() ? query.background_sound : null;
          
          if (query.imageFile) {
            // Don't send data URL, file will be sent separately in FormData
            syncQuery.image = null;
          } else if (query.imageRemoved) {
            // Explicitly remove image
            syncQuery.image = null;
          } else {
            // Don't include image field if no changes - let backend keep existing image
            // Only include if it's a new data URL (not a URL starting with http)
            if (query.image && !query.image.startsWith('http')) {
              syncQuery.image = query.image;
            }
            // If it's a URL (existing image), don't include the field to avoid changes
          }
          
          return syncQuery;
        });

      // Collect image files for FormData upload
      const imageFiles = queriesToUse
        .filter(q => q.imageFile)
        .map(q => ({
          stage: q.stage,
          file: q.imageFile
        }));

      const response = await QueryService.batchUpdateQueries(session, queriesToSync, imageFiles);
      
      if (response.success) {
        // No need for separate image uploads anymore - they're handled in batch request
        // Reload all queries from server to get fresh data
        await loadQueries(session);
        toast.success('Queries synced successfully', 2000);
      } else {
        console.error('Sync failed:', response.error);
        toast.error(response.error || 'Failed to sync queries', 4000);
      }
    } catch (error) {
      console.error('Sync error:', error);
      toast.error('Failed to sync queries', 4000);
    } finally {
      setIsSyncing(false);
    }
  }, [session, sessionLoading, isSyncing, queryHasContent, toast, loadQueries]);

  // Create new query after specified stage (insert mode)
  const handleCreateQuery = useCallback((afterStage) => {
    const newStage = afterStage + 1;
    
    // Check if stage already exists - if so, we need to shift stages
    const existingQuery = localQueries.find(q => q.stage === newStage);
    
    if (existingQuery) {
      // Shift all stages >= newStage up by 1 to make room for insertion
      setLocalQueries(prev => 
        prev.map(query => ({
          ...query,
          stage: query.stage >= newStage ? query.stage + 1 : query.stage
        }))
      );
    }
    
    // Create new query at the new stage
    const newQuery = createLocalQuery({ stage: newStage });
    setLocalQueries(prev => [...prev, newQuery]);
    
    // Navigate to the new stage
    handleInternalStageChange(newStage);
    
    // Note: No auto-sync here - sync happens when user sends the query
  }, [localQueries, createLocalQuery, handleInternalStageChange]);

  // Handle keyboard navigation (Ctrl + Left/Right)
  const handleStageNavigation = useCallback((direction) => {
    // Sort queries by stage to ensure correct navigation
    const sortedQueries = [...localQueries].sort((a, b) => a.stage - b.stage);
    const currentStageIndex = sortedQueries.findIndex(q => q.stage === stage);
    
    if (direction === 'left') {
      if (currentStageIndex > 0) {
        const prevStage = sortedQueries[currentStageIndex - 1].stage;
        handleInternalStageChange(prevStage);
      }
    } else if (direction === 'right') {
      if (currentStageIndex < sortedQueries.length - 1) {
        const nextStage = sortedQueries[currentStageIndex + 1].stage;
        handleInternalStageChange(nextStage);
      } else {
        // At the last stage - check if current query has content to create new one
        const currentQuery = sortedQueries[currentStageIndex];
        if (currentQuery && queryHasContent(currentQuery)) {
          handleCreateQuery(stage);
        }
      }
    }
  }, [localQueries, stage, handleInternalStageChange, handleCreateQuery, queryHasContent]);

  // Missing helper functions for keyboard navigation
  const handleDeleteCurrentStageQuery = async () => {
    const currentQuery = localQueries.find(q => q.stage === stage);
    if (currentQuery) {
      setLocalQueries(prev => prev.filter(q => q.stage !== stage));
      setCurrentLocalQuery(createLocalQuery({ stage: stage }));
      
      // Sync to backend immediately
      await syncQueriesToBackend();
      toast.success('Query deleted', 2000);
    }
  };

  const handleTranslateFocusedInput = async (targetLanguage) => {
    const activeElement = document.activeElement;
    if (!activeElement || activeElement.tagName !== 'TEXTAREA') return;
    
    const inputValue = activeElement.value;
    if (!inputValue.trim()) return;
    
    try {
      setIsTranslating(true);
      const translatedText = await translatorService.translateText(inputValue, targetLanguage);
      
      // Update the DOM element
      activeElement.value = translatedText;
      
      // Trigger React onChange event to sync state
      const event = new Event('input', { bubbles: true });
      activeElement.dispatchEvent(event);
      
      // Also update the local query directly
      if (activeElement.id === 'text-input') {
        updateCurrentLocalQuery({ text: translatedText });
      } else if (activeElement.id === 'ocr-input') {
        updateCurrentLocalQuery({ ocr: translatedText });
      } else if (activeElement.id === 'speech-input') {
        updateCurrentLocalQuery({ speech: translatedText });
      }
      
      toast.success(`Translated to ${targetLanguage === 'en' ? 'English' : 'Vietnamese'}`, 2000);
    } catch (error) {
      toast.error('Translation failed', 3000);
    } finally {
      setIsTranslating(false);
    }
  };



  // Send message function
  const handleSendMessage = async () => {
    // Get the most up-to-date query from localQueries instead of currentLocalQuery
    const currentQuery = localQueries.find(q => q.stage === stage) || currentLocalQuery;
    if (!currentQuery) return;
    
    const hasText = currentQuery.text?.trim();
    const hasOcr = currentQuery.ocr?.trim();
    const hasImage = currentQuery.image || currentQuery.imageFile;
    const hasSpeech = currentQuery.speech?.trim();
    if (!hasText && !hasOcr && !hasImage && !hasSpeech) return;

    if (!session || sessionLoading) {
      toast.error('No active session. Please wait for session to load.');
      return;
    }

    // Update current query
    updateCurrentLocalQuery({
      text: hasText || null,
      ocr: hasOcr || null,
      speech: hasSpeech || null,
      // Keep the data URL in image field, imageFile is handled separately
      image: currentQuery.imageRemoved ? null : currentQuery.image,
    });

    // Create next stage query
    const nextStage = stage + 1;
    const nextQuery = createLocalQuery({ stage: nextStage });
    setLocalQueries(prev => {
      const existing = prev.find(q => q.stage === nextStage);
      if (existing) {
        return prev;
      }
      return [...prev, nextQuery];
    });
    
    // Sync to backend immediately
    setTimeout(async () => {
      await syncQueriesToBackend();
      if (messagesEndRef.current) {
        messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
      }
    }, 0);
  };
  // const handleSendQueryIfReady = () => {
  //   // Get the most up-to-date query from localQueries instead of currentLocalQuery
  //   const currentQuery = localQueries.find(q => q.stage === stage) || currentLocalQuery;
  //   if (!currentQuery) return;
    
  //   const hasText = currentQuery.text?.trim();
  //   const hasOcr = currentQuery.ocr?.trim();
  //   const hasImage = currentQuery.image || currentQuery.imageFile;
  //   const hasSpeech = currentQuery.speech?.trim();
  //   if (!hasText && !hasOcr && !hasImage && !hasSpeech) return;

  //   handleSendMessage();
  // };
  // Initialize session when component mounts
  useEffect(() => {
    const initializeApp = async () => {
      // Only initialize once and only for chat mode
      if (hasInitialized.current || mode !== 'chat') {
        return;
      }
      
      hasInitialized.current = true;
      
      const urlStage = getStageFromUrl();
      const urlViewMode = getViewModeFromUrl();
      
      if (urlStage !== stage) {
        setStage(urlStage);
      }
      
      if (urlViewMode !== viewMode) {
        setViewMode(urlViewMode);
      }
      
      // Session is now managed by AppContext, just wait for it
      // No need to load session from URL here
      hasLoadedQueries.current = true;
    };
    initializeApp();
  }, [mode]);

  useEffect(() => {
    scrollToBottom();
  }, [queries]);
  
  // Load queries when session from AppContext changes
  useEffect(() => {
    const loadQueriesWhenSessionReady = async () => {      
      if (session && !sessionLoading && !hasLoadedQueries.current) {
        await loadQueries(session);
        hasLoadedQueries.current = true;
      }
    };
    
    loadQueriesWhenSessionReady();
  }, [session, sessionLoading]); // Depend on session and sessionLoading from AppContext

  // Sync stage and viewMode with URL
  useEffect(() => {
    if (session && !sessionLoading) {
      updateUrlParams({
        session: session,
        stage: stage,
        viewmode: viewMode
      });
    }
  }, [stage, viewMode, session, sessionLoading]);

  // Reload queries when viewMode or k changes
  useEffect(() => {
    if (session && !sessionLoading && mode === 'chat' && hasLoadedQueries.current) {
      loadQueries(session);
    }
  }, [viewMode, k, session, sessionLoading, loadQueries, mode]);

  // Load query content when stage changes
  useEffect(() => {
    const stageQuery = localQueries.find(q => q.stage === stage);
    setCurrentStageQuery(stageQuery);
    
    if (stageQuery) {
      setCurrentLocalQuery({ ...stageQuery });
    } else {
      setCurrentLocalQuery(createLocalQuery({ stage: stage }));
    }
  }, [stage, localQueries, createLocalQuery]);

  // Notify parent about available stages when queries change
  useEffect(() => {
    if (onAvailableStagesChange) {
      // Create array of available stages from 1 to max stage
      const maxStageFromQueries = queries.length > 0 ? Math.max(...queries.map(q => q.stage)) : 0;
      const maxStageFromLocal = localQueries.length > 0 ? Math.max(...localQueries.map(q => q.stage)) : 0;
      const maxStage = Math.max(maxStageFromQueries, maxStageFromLocal, 1); // At least stage 1
      
      const availableStages = Array.from({ length: maxStage }, (_, i) => i + 1);
      onAvailableStagesChange(availableStages);
    }
  }, [queries, localQueries, onAvailableStagesChange]);

  // Register loadQueries function with parent component
  useEffect(() => {
    if (onLoadQueriesRegister) {
      onLoadQueriesRegister(loadQueries);
    }
  }, [onLoadQueriesRegister, loadQueries]);

  // Keyboard shortcuts for translation
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (mode !== 'chat') return;
      
      const modals = document.querySelectorAll('.team-answer-modal, .submission-modal, .confirmation-modal');
      if (modals.length > 0) {
        return;
      }
      
      if (e.ctrlKey && e.key === 'Delete') {
        e.preventDefault();
        handleDeleteCurrentStageQuery();
        return;
      }
      
      if (e.ctrlKey && e.key === 'e') {
        e.preventDefault();
        handleTranslateFocusedInput('en');
        return;
      }
      
      if (e.ctrlKey && e.key === 'q') {
        e.preventDefault();
        handleTranslateFocusedInput('vi');
        return;
      }

      // Alt + R: Translate to English
      if (e.altKey && e.key === 'r') {
        e.preventDefault();
        handleTranslateFocusedInput('en');
        return;
      }
      
      // Alt + W: Translate to Vietnamese  
      if (e.altKey && e.key === 'w') {
        e.preventDefault();
        handleTranslateFocusedInput('vi');
        return;
      }



      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        return;
      }

      if (e.ctrlKey && (e.key === 'ArrowLeft' || e.key === 'ArrowRight')) {
        e.preventDefault();
        const direction = e.key === 'ArrowLeft' ? 'left' : 'right';
        handleStageNavigation(direction);
        return;
      }

      // Alt + Right: Navigate right (same as Ctrl + Right)
      if (e.altKey && e.key === 'ArrowRight') {
        e.preventDefault();
        handleStageNavigation('right');
        return;
      }
    };

    if (mode === 'chat') {
      document.addEventListener('keydown', handleKeyDown, true);
    }
    
    return () => {
      if (mode === 'chat') {
        document.removeEventListener('keydown', handleKeyDown, true);
      }
    };
  }, [mode, currentInputIndex, currentLocalQuery?.ocr, currentLocalQuery?.text, currentLocalQuery?.image]);

  // Track if there are unsaved changes
  useEffect(() => {
    const hasChanges = localQueries.some(localQuery => {
      const serverQuery = queries.find(q => q.id === localQuery.id);
      
      if (!localQuery.id) {
        return queryHasContent(localQuery);
      }
      
      if (!serverQuery) {
        return true;
      }
      
      return localQuery.text !== serverQuery.text ||
             localQuery.ocr !== serverQuery.ocr ||
             localQuery.speech !== serverQuery.speech ||
             localQuery.background_sound !== serverQuery.background_sound ||
             localQuery.stage !== serverQuery.stage ||
             localQuery.imageRemoved ||
             localQuery.imageFile;
    });
  }, [localQueries, queries, queryHasContent]);

  // Delete individual query
  const handleDeleteQuery = async (queryStage) => {
    // Calculate updated queries first
    const filteredQueries = localQueries.filter(q => q.stage !== queryStage);
    const updatedQueries = filteredQueries.map(query => ({
      ...query,
      stage: query.stage > queryStage ? query.stage - 1 : query.stage
    }));
    
    // Update local state
    setLocalQueries(updatedQueries);
    
    // Handle current stage logic
    if (queryStage === stage) {
      // If deleting current stage, navigate to a valid stage
      if (updatedQueries.length > 0) {
        // Navigate to the previous stage or the first available stage
        const targetStage = queryStage > 1 ? queryStage - 1 : 1;
        handleInternalStageChange(targetStage);
      } else {
        // No queries left, create a new one at stage 1
        setCurrentLocalQuery(createLocalQuery({ stage: 1 }));
        handleInternalStageChange(1);
      }
    } else if (queryStage < stage) {
      // If deleting a stage before current, adjust current stage down by 1
      handleInternalStageChange(stage - 1);
    }
    
    // Sync to backend immediately with updated queries
    setTimeout(async () => {
      // Use the updated queries directly instead of relying on state
      await syncSpecificQueries(updatedQueries);
      toast.success('Query deleted', 2000);
    }, 100);
  };

  // Handle reordering queries via drag & drop
  const handleReorderQueries = useCallback(async (reorderedQueries) => {
    // Separate hidden and non-hidden queries
    const nonHiddenQueries = [];
    const updatedHiddenQueries = [];
    
    reorderedQueries.forEach((query, index) => {
      if (query.isHidden) {
        // For hidden queries, calculate their originalIndex based on number of non-hidden queries before them
        const nonHiddenCountBefore = reorderedQueries.slice(0, index).filter(q => !q.isHidden).length;
        
        const existingHidden = hiddenQueries.find(hq => hq.query.stage === query.stage);
        if (existingHidden) {
          updatedHiddenQueries.push({
            ...existingHidden,
            originalIndex: nonHiddenCountBefore
          });
        }
      } else {
        // For non-hidden queries, keep them for reordering
        nonHiddenQueries.push(query);
      }
    });
    
    // Update stages for non-hidden queries based on their new order (excluding hidden slots)
    const updatedQueries = nonHiddenQueries.map((query, index) => ({
      ...query,
      stage: index + 1 // Reassign stages based on new order (1-based)
    }));
    
    // Update local state
    setLocalQueries(updatedQueries);
    
    // Update hidden queries with new original indices
    if (updatedHiddenQueries.length > 0) {
      setHiddenQueries(prev => {
        // Merge updated hidden queries with existing ones
        const result = [...prev];
        updatedHiddenQueries.forEach(updated => {
          const idx = result.findIndex(hq => hq.query.stage === updated.query.stage);
          if (idx !== -1) {
            result[idx] = updated;
          }
        });
        return result;
      });
    }
    
    // Update current local query if it was reordered
    if (currentLocalQuery) {
      const updatedCurrentQuery = updatedQueries.find(q => 
        q.id === currentLocalQuery.id || 
        (q.text === currentLocalQuery.text && q.ocr === currentLocalQuery.ocr && q.image === currentLocalQuery.image)
      );
      
      if (updatedCurrentQuery && updatedCurrentQuery.stage !== stage) {
        // Navigate to the new stage of the current query
        handleInternalStageChange(updatedCurrentQuery.stage);
        setCurrentLocalQuery({ ...updatedCurrentQuery });
      }
    }
    
    // Only sync to backend if local queries actually changed (not just hidden query reorder)
    if (nonHiddenQueries.length > 0 && updatedQueries.length > 0) {
      setTimeout(async () => {
        await syncSpecificQueries(updatedQueries);
        toast.success('Queries reordered', 2000);
      }, 100);
    } else if (updatedHiddenQueries.length > 0) {
      // Just hidden query reorder - no server sync needed
      toast.info('Hidden query position updated', 1000);
    }
  }, [currentLocalQuery, stage, handleInternalStageChange, syncSpecificQueries, toast, hiddenQueries]);

  // Handle toggle hidden query
  const handleToggleHidden = useCallback((queryToToggle) => {
    const queryStage = queryToToggle.stage;
    
    // Check if query is already hidden
    const hiddenIndex = hiddenQueries.findIndex(hq => hq.query.stage === queryStage);
    
    if (hiddenIndex !== -1) {
      // Unhide: remove from hiddenQueries and restore to localQueries at original position
      const hiddenItem = hiddenQueries[hiddenIndex];
      
      setHiddenQueries(prev => prev.filter((_, idx) => idx !== hiddenIndex));
      
      // Restore query to localQueries at its original index and shift subsequent queries
      setLocalQueries(prev => {
        const sortedQueries = [...prev].sort((a, b) => a.stage - b.stage);
        const insertIndex = hiddenItem.originalIndex;
        
        // Shift all queries at or after the insert position by incrementing their stage
        const updatedQueries = sortedQueries.map(q => {
          // Find the actual position in sorted array
          const currentIndex = sortedQueries.findIndex(sq => sq.stage === q.stage);
          if (currentIndex >= insertIndex) {
            return { ...q, stage: q.stage + 1 };
          }
          return q;
        });
        
        // Insert the unhidden query at its original position (keeping original stage)
        updatedQueries.splice(insertIndex, 0, hiddenItem.query);
        
        return updatedQueries;
      });
      
      toast.info('Query unhidden', 1000);
    } else {
      // Hide: move from localQueries to hiddenQueries
      const queryExists = localQueries.some(q => q.stage === queryStage);
      
      if (queryExists) {
        // Remove from localQueries
        setLocalQueries(prev => prev.filter(q => q.stage !== queryStage));
        
        // Add to hiddenQueries with original stage as the index
        setHiddenQueries(prev => [...prev, { 
          query: queryToToggle, 
          originalIndex: queryStage // Use stage number as originalIndex
        }]);
        
        toast.info('Query hidden', 1000);
      }
    }
  }, [hiddenQueries, localQueries, toast]);

  // Handle add session button
  const handleAddSession = async () => {
    try {
      const response = await QueryService.createSession();
      if (response.success) {
        const sessionData = response.data.data;
        setSession(sessionData.id); // Use AppContext to set session
        handleInternalStageChange(1);
        updateUrlParams({ 
          session: sessionData.id,
          stage: 1,
          viewmode: viewMode 
        });
        setLocalQueries([]);
        setCurrentLocalQuery(createLocalQuery());
        toast.success('New session created!');
      } else {
        toast.error('Failed to create new session');
      }
    } catch (error) {
      toast.error('Failed to create new session');
    }
  };

  // Handle export functionality
  const handleExport = async () => {
    try {
      if (mode === 'team-answer') {
        toast.info('Exporting team answers and TRAKE answers...', 1000);
        const result = await ExportTeamAnswerUtils.exportAllAnswers(csvFormat);
        toast.success(result.message || 'Export completed successfully!', 2000);
        
      } else if (mode === 'answer') {
        if (!allAnswers || allAnswers.length === 0) {
          toast.warning('No answers to export', 3000);
          return;
        }
        
        toast.info('Generating export file...', 1000);
        await exportAnswersToZip(allAnswers, round, csvFormat);
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

  // Handle export team answers functionality for chat section
  const handleExportTeamAnswers = async () => {
    try {
      toast.info('Exporting team answers and TRAKE answers...', 1000);
      const result = await ExportTeamAnswerUtils.exportAllAnswers(csvFormat);
      toast.success(result.message || 'Export completed successfully!', 2000);
    } catch (error) {
      console.error('Export error:', error);
      toast.error(error.message || 'Failed to export team answers', 4000);
    }
  };

  // Merge localQueries with hiddenQueries for display
  // Hidden queries are shown in their original stage positions with visual overlay
  const sortedLocalQueries = useMemo(() => {
    const sorted = [...localQueries].sort((a, b) => a.stage - b.stage);
    
    // If no hidden queries, return sorted local queries with displayStage = stage
    if (hiddenQueries.length === 0) {
      return sorted.map(q => ({ ...q, isHidden: false, displayStage: q.stage }));
    }
    
    // Combine all queries (visible + hidden) and sort by stage
    const allQueries = [
      ...sorted.map(q => ({ ...q, isHidden: false })),
      ...hiddenQueries.map(({ query }) => ({ ...query, isHidden: true }))
    ].sort((a, b) => a.stage - b.stage);
    
    // displayStage should match the original stage number
    return allQueries.map(q => ({
      ...q,
      displayStage: q.stage
    }));
  }, [localQueries, hiddenQueries]);

  // Render query index list for team-answer and answer modes
  const renderQueryIndexList = () => {
    return (
      <div className="sidebar__query-index-list">
        <div className="sidebar__header">
          <button 
            onClick={handleExport}
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

  // Auto-detect query mode when query index changes
  const handleQueryIndexChange = useCallback(async (newQueryIndex) => {
    try {
      // Set the new query index first
      setQueryIndex(newQueryIndex);
      
      // Only auto-detect for chat mode (not for team-answer/answer modes)
      if (mode === 'chat') {
        const detectedMode = await QueryModeUtils.detectQueryMode(newQueryIndex);
        
        if (detectedMode !== 'unknown' && detectedMode !== queryMode) {
          // Actually change the query mode
          setQueryMode(detectedMode);
          const modeName = QueryModeUtils.getModeName(detectedMode);
          toast.success(`Switched to ${modeName} mode for query ${newQueryIndex}`);
        } 
      }
    } catch (error) {
      console.error('Error in handleQueryIndexChange:', error);
      // Don't show error toast for auto-detection failures
    }
  }, [setQueryIndex, mode, toast, queryMode, setQueryMode]);

  return (
    <div className="sidebar">
      {/* Session loading indicator */}
      {sessionLoading && (
        <div className="sidebar__loading">
          <div className="sidebar__loading-spinner"></div>
          <p>Initializing session...</p>
        </div>
      )}
      
      {/* Main sidebar content - only show when session is ready */}
      {!sessionLoading && (
        <>
          {(mode === 'team-answer' || mode === 'answer') ? (
            renderQueryIndexList()
          ) : (
        <>
          <div className="sidebar__header">
            <button 
              onClick={handleExportTeamAnswers}
              className="sidebar__export-btn"
              title="Export Team Answers"
            >
              <img src="/assets/export.svg" alt="Export Team Answers" className="sidebar__action-icon" />
            </button>
            {round === 'final' ? (
              <h3>Query History</h3>
            ) : (
              <div className="sidebar__query-index">
                <label htmlFor="queryIndex">Index:</label>
                <div className="sidebar__query-index-controls">
                  <button 
                    className="sidebar__query-index-btn sidebar__query-index-btn--decrease"
                    onClick={() => {
                      const newValue = Math.max(1, (queryIndex || 1) - 1);
                      handleQueryIndexChange(newValue);
                    }}
                    title="Decrease query index"
                  >
                    -
                  </button>
                  <input
                    id="queryIndex"
                    type="number"
                    value={queryIndex}
                    onChange={(e) => {
                      const value = e.target.value;
                      if (value === '') {
                        setQueryIndex('');
                        return;
                      }
                      if (/^\d+$/.test(value)) {
                        const numValue = parseInt(value, 10);
                        if (numValue >= 1 && numValue <= 999) {
                          handleQueryIndexChange(numValue);
                        }
                      }
                    }}
                    onBlur={(e) => {
                      if (e.target.value === '') {
                        setQueryIndex(1);
                      }
                    }}
                    onKeyDown={(e) => {
                      if (!/[\d]/.test(e.key) && 
                          !['Backspace', 'Delete', 'ArrowLeft', 'ArrowRight', 'Tab'].includes(e.key)) {
                        e.preventDefault();
                      }
                    }}
                    min="1"
                    max="999"
                    className="sidebar__query-index-input"
                  />
                  <button 
                    className="sidebar__query-index-btn sidebar__query-index-btn--increase"
                    onClick={() => {
                      const newValue = Math.min(999, (queryIndex || 1) + 1);
                      handleQueryIndexChange(newValue);
                    }}
                    title="Increase query index"
                  >
                    +
                  </button>
                </div>
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

          <div className="sidebar__chat">
            <SidebarQueries
              loading={loading}
              filteredQueries={sortedLocalQueries}
              stage={stage}
              onStageChange={handleInternalStageChange}
              onDeleteQuery={handleDeleteQuery}
              onCreateQuery={handleCreateQuery}
              onReorderQueries={handleReorderQueries}
              onToggleHidden={handleToggleHidden}
              messagesEndRef={messagesEndRef}
            />
            
            <QueryInput
              loading={loading}
              currentLocalQuery={currentLocalQuery}
              updateCurrentLocalQuery={updateCurrentLocalQuery}
              onSendMessage={handleSendMessage}
              isRecording={isRecording}
              setIsRecording={setIsRecording}
              isTranslating={isTranslating}
              setIsTranslating={setIsTranslating}
              currentInputIndex={currentInputIndex}
              setCurrentInputIndex={setCurrentInputIndex}
            />
          </div>
        </>
      )}
      
      {showDeleteModal && (
        <ConfirmationModal
          isOpen={showDeleteModal}
          onClose={() => setShowDeleteModal(false)}
          onConfirm={() => {
            setShowDeleteModal(false);
            setDeleteTarget(null);
          }}
          title={`Delete ${deleteTarget?.mode === 'team-answer' ? 'Team Answers' : 'Final Answers'}`}
          message={`Are you sure you want to delete all ${deleteTarget?.mode === 'team-answer' ? 'team answers' : 'final answers'} for Query ${deleteTarget?.queryIndex}?`}
          confirmText="Delete All"
          cancelText="Cancel"
          isLoading={isDeleting}
        />
      )}
      </>
      )}
    </div>
  );
};

export default Sidebar;
