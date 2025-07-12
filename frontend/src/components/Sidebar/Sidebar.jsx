import React, { useState, useRef, useEffect, useCallback } from 'react';
import { translatorService } from '../../services/TranslatorService';
import { QueryService, getErrorMessage } from '../../services';
import { TeamAnswerService, AnswerService } from '../../services';
import { useToast } from '../Toast/ToastProvider';
import { useApp } from '../../contexts/AppContext';
import { getSessionIdFromUrl, getStageFromUrl, getViewModeFromUrl, updateUrlParams } from '../../utils/urlParams';
import { exportTeamAnswersToZip, exportAnswersToZip } from '../../utils/exportUtils';
import ConfirmationModal from '../ConfirmationModal';
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
  const { stage, viewMode, round, queryIndex, setStage, setViewMode, setQueryIndex } = useApp();
  const toast = useToast();
  
  const [queries, setQueries] = useState([]);
  const [loading, setLoading] = useState(false);
  const [currentSession, setCurrentSession] = useState(null);
  const [currentStageQuery, setCurrentStageQuery] = useState(null);
  const [inputMessage, setInputMessage] = useState('');
  const [ocrText, setOcrText] = useState('');
  const [speechText, setSpeechText] = useState('');
  const [uploadedImage, setUploadedImage] = useState(null);
  const [uploadedImageFile, setUploadedImageFile] = useState(null);
  const [isRecording, setIsRecording] = useState(false);
  const [isTranslating, setIsTranslating] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState(null); // { queryIndex, mode }
  const [isDeleting, setIsDeleting] = useState(false);
  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);
  const textareaRef = useRef(null);
  const ocrTextareaRef = useRef(null);
  const speechTextareaRef = useRef(null);
  const hasInitialized = useRef(false);
  
  // Navigation state for input focus
  const [currentInputIndex, setCurrentInputIndex] = useState(-1); // -1: no focus, 0: OCR, 1: Speech, 2: Text
  const inputRefs = [ocrTextareaRef, speechTextareaRef, textareaRef]; // Order: OCR (top) -> Speech -> Text (bottom)

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

  // Load queries for current session
  const loadQueries = useCallback(async (sessionId = null) => {
    if (mode !== 'chat') return; // Only run in chat mode
    
    onFramesUpdate([]);
    const targetSessionId = sessionId || currentSession?.id;
    
    if (!targetSessionId) {
      return;
    }

    setLoading(true);
    try {
      const response = await QueryService.getQueriesBySession(targetSessionId, {
        page: 1,
        page_size: 100,
        // Remove stage filter - load all queries for the session
        viewmode: viewMode, // Add viewmode parameter
        // Don't trigger search_frames automatically when loading queries
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
  }, [currentSession, viewMode, onFramesUpdate, toast, mode]);

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

  // Auto-resize textarea
  const adjustTextareaHeight = () => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      textarea.style.height = Math.min(textarea.scrollHeight, 150) + 'px';
    }
  };

  // Auto-resize OCR textarea
  const adjustOcrTextareaHeight = () => {
    const textarea = ocrTextareaRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
    }
  };

  // Auto-resize Speech textarea
  const adjustSpeechTextareaHeight = () => {
    const textarea = speechTextareaRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
    }
  };

  useEffect(() => {
    adjustTextareaHeight();
  }, [inputMessage]);

  useEffect(() => {
    adjustOcrTextareaHeight();
  }, [ocrText]);

  useEffect(() => {
    adjustSpeechTextareaHeight();
  }, [speechText]);

  // Load query content when stage changes (for edit mode)
  useEffect(() => {
    const currentStageQuery = queries.find(q => q.stage === stage);
    setCurrentStageQuery(currentStageQuery);
    
    if (currentStageQuery) {
      // Edit mode - load existing query content
      // Use helper function to get clean values
      setInputMessage(hasValidValue(currentStageQuery.text) ? currentStageQuery.text : '');
      setOcrText(hasValidValue(currentStageQuery.ocr) ? currentStageQuery.ocr : '');
      setSpeechText(hasValidValue(currentStageQuery.speech) ? currentStageQuery.speech : '');
      
      // Handle image if exists
      if (hasValidValue(currentStageQuery.image)) {
        setUploadedImage(currentStageQuery.image);
        // Note: We don't set uploadedImageFile as it's for new uploads
      } else {
        setUploadedImage(null);
        setUploadedImageFile(null);
      }

      // Note: Frames will be loaded automatically when loadQueries is called
    } else {
      // Create mode - clear all inputs
      setInputMessage('');
      setOcrText('');
      setSpeechText('');
      setUploadedImage(null);
      setUploadedImageFile(null);
      
      // Reset file input
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  }, [stage, queries]); // Remove onFramesUpdate and viewMode to prevent infinite loop

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
      // Ctrl + Delete: Delete current stage query
      if (e.ctrlKey && e.key === 'Delete') {
        e.preventDefault();
        handleDeleteCurrentStageQuery();
        return;
      }
      
      // Ctrl + E: Translate focused input to English
      if (e.ctrlKey && e.key === 'e') {
        e.preventDefault();
        handleTranslateFocusedInput('en');
        return;
      }
      
      // Ctrl + Q: Translate focused input to Vietnamese
      if (e.ctrlKey && e.key === 'q') {
        e.preventDefault();
        handleTranslateFocusedInput('vi');
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
        // Prevent default scroll behavior
        e.preventDefault();
        e.stopPropagation();
        
        if (e.key === 'ArrowDown') {
          navigateInputs('down');
        } else {
          navigateInputs('up');
        }
      }
    };

    // Listen on document level to catch all keyboard events
    document.addEventListener('keydown', handleKeyDown, true);
    return () => document.removeEventListener('keydown', handleKeyDown, true);
  }, [currentInputIndex, ocrText, speechText, inputMessage, uploadedImage]);

  // Navigation function for input fields
  const navigateInputs = (direction) => {
    let nextIndex;
    
    if (direction === 'down') {
      if (currentInputIndex === -1) {
        // No focus -> go to top (OCR)
        nextIndex = 0;
      } else {
        // Move down cyclically: OCR(0) -> Speech(1) -> Text(2) -> OCR(0)
        nextIndex = (currentInputIndex + 1) % inputRefs.length;
      }
    } else if (direction === 'up') {
      if (currentInputIndex === -1) {
        // No focus -> go to bottom (Text)
        nextIndex = inputRefs.length - 1; // Text (index 2)
      } else {
        // Move up cyclically: Text(2) -> Speech(1) -> OCR(0) -> Text(2)
        nextIndex = currentInputIndex === 0 ? inputRefs.length - 1 : currentInputIndex - 1;
      }
    }
    
    // Focus on the target input
    if (inputRefs[nextIndex] && inputRefs[nextIndex].current) {
      inputRefs[nextIndex].current.focus();
      setCurrentInputIndex(nextIndex);
    }
  };

  // Handle send message
  const handleSendMessage = async () => {
    if (!inputMessage.trim() && !uploadedImage && !ocrText.trim() && !speechText.trim()) return;
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
        text: inputMessage.trim() || null,
        ocr: ocrText.trim() || null,
        speech: speechText.trim() || null,
        image: uploadedImageFile || null,
      };

      let response;
      
      // Check if we're in edit mode (current stage has existing query)
      if (currentStageQuery) {
        // Update existing query
        response = await QueryService.updateQuery(currentStageQuery.id, queryData);
      } else {
        // Create new query
        response = await QueryService.createQuery(queryData);
      }

      if (response.success) {
        // Clear inputs first
        setInputMessage('');
        setOcrText('');
        setSpeechText('');
        setUploadedImage(null);
        setUploadedImageFile(null);

        // Reset file input
        if (fileInputRef.current) {
          fileInputRef.current.value = '';
        }

        // Reload queries to get fresh data with proper formatting
        // This will also load frames automatically from backend
        await loadQueries(currentSession.id);

        toast.success(currentStageQuery ? 'Query updated successfully!' : 'Query created successfully!');
        
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
    const hasTextInput = inputMessage.trim().length > 0;
    const hasOcrInput = ocrText.trim().length > 0;
    const hasSpeechInput = speechText.trim().length > 0;
    const hasImageInput = uploadedImage !== null;

    if (hasTextInput || hasOcrInput || hasSpeechInput || hasImageInput) {
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
        
        // Clear inputs since the query was deleted
        setInputMessage('');
        setOcrText('');
        setSpeechText('');
        setUploadedImage(null);
        setUploadedImageFile(null);
        setCurrentStageQuery(null);
        
        // Reset file input
        if (fileInputRef.current) {
          fileInputRef.current.value = '';
        }

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
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleImageUpload = (e) => {
    const file = e.target.files[0];
    if (file) {
      setUploadedImageFile(file);
      const reader = new FileReader();
      reader.onload = (e) => {
        setUploadedImage(e.target.result);
      };
      reader.readAsDataURL(file);
    }
  };

  const handleRemoveImage = () => {
    setUploadedImage(null);
    setUploadedImageFile(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handlePaste = (e) => {
    const items = e.clipboardData.items;
    for (let item of items) {
      if (item.type.indexOf('image') !== -1) {
        const file = item.getAsFile();
        setUploadedImageFile(file);
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

  const handleTranslateOcr = async () => {
    if (!ocrText.trim()) return;
    
    setIsTranslating(true);
    try {
      // Detect if text is Vietnamese, then translate to English, otherwise to Vietnamese
      const detectedLang = await translatorService.detectLanguage(ocrText);
      const targetLang = (detectedLang === 'vi') ? 'en' : 'vi';
      
      const translated = await translatorService.translateText(ocrText, targetLang);
      if (translated && translated !== ocrText) {
        setOcrText(translated);
        toast.success('Text translated successfully!');
      }
    } catch (error) {
      toast.error('Failed to translate text');
    } finally {
      setIsTranslating(false);
    }
  };

  const handleTranslateSpeech = async () => {
    if (!speechText.trim()) return;
    
    setIsTranslating(true);
    try {
      // Detect if text is Vietnamese, then translate to English, otherwise to Vietnamese
      const detectedLang = await translatorService.detectLanguage(speechText);
      const targetLang = (detectedLang === 'vi') ? 'en' : 'vi';
      
      const translated = await translatorService.translateText(speechText, targetLang);
      if (translated && translated !== speechText) {
        setSpeechText(translated);
        toast.success('Text translated successfully!');
      }
    } catch (error) {
      toast.error('Failed to translate text');
    } finally {
      setIsTranslating(false);
    }
  };

  const handleTranslateText = async (targetLang) => {
    if (!inputMessage.trim()) return;
    
    setIsTranslating(true);
    try {
      const translated = await translatorService.translateText(inputMessage, targetLang);
      if (translated && translated !== inputMessage) {
        setInputMessage(translated);
        const langName = targetLang === 'en' ? 'English' : 'Vietnamese';
        toast.success(`Text translated to ${langName}!`);
      }
    } catch (error) {
      toast.error('Failed to translate text');
    } finally {
      setIsTranslating(false);
    }
  };

  // Handle translation for the currently focused input
  const handleTranslateFocusedInput = async (targetLang) => {
    if (currentInputIndex === -1) {
      toast.info('Please focus on an input field first');
      return;
    }

    let textToTranslate = '';
    let setTranslatedText = null;
    let fieldName = '';

    // Determine which input is focused
    switch (currentInputIndex) {
      case 0: // OCR
        textToTranslate = ocrText.trim();
        setTranslatedText = setOcrText;
        fieldName = 'OCR text';
        break;
      case 1: // Speech
        textToTranslate = speechText.trim();
        setTranslatedText = setSpeechText;
        fieldName = 'Speech text';
        break;
      case 2: // Text
        textToTranslate = inputMessage.trim();
        setTranslatedText = setInputMessage;
        fieldName = 'Text';
        break;
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
        setTranslatedText(translated);
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

  const handleMicrophoneClick = () => {
    if (isRecording) {
      // Stop recording
      setIsRecording(false);
      // Here you would implement actual recording stop logic
    } else {
      // Start recording
      setIsRecording(true);
      // Here you would implement actual recording start logic
    }
  };



  // Track focus changes to update currentInputIndex
  const handleInputFocus = (index) => {
    setCurrentInputIndex(index);
  };

  const handleInputBlur = () => {
    // Don't reset immediately, keep track for navigation
    // Only reset if no navigation happens within a short time
    setTimeout(() => {
      // Check if any input still has focus
      const anyInputFocused = inputRefs.some(ref => 
        ref.current && document.activeElement === ref.current
      );
      if (!anyInputFocused) {
        setCurrentInputIndex(-1);
      }
    }, 50);
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
  };

  // Handle viewMode change from external components  
  const handleInternalViewModeChange = (newViewMode) => {
    setViewMode(newViewMode);
    // Update URL params
    updateUrlParams({ viewmode: newViewMode });
  };

  // Filter queries by current stage for display
  // Show all queries in session, but highlight current stage query
  const filteredQueries = queries; // Show all queries instead of filtering by stage
  
  // Calculate max stage from existing queries + 1 for new stage
  const maxStageFromQueries = queries.length > 0 ? Math.max(...queries.map(q => q.stage)) : 0;
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
        await exportTeamAnswersToZip(allTeamAnswers, round);
        toast.success('Export completed successfully!', 2000);
        
      } else if (mode === 'answer') {
        if (!allAnswers || allAnswers.length === 0) {
          toast.warning('No answers to export', 3000);
          return;
        }
        
        toast.info('Generating export file...', 1000);
        await exportAnswersToZip(allAnswers, round);
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
                    console.log('DEBUG Sidebar: Clicking query index:', index);
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
                    console.log('DEBUG Sidebar: Setting queryIndex from input:', numValue);
                    setQueryIndex(numValue);
                  }
                }
              }}
              onBlur={(e) => {
                // If empty when focus is lost, set to 1
                if (e.target.value === '') {
                  console.log('DEBUG Sidebar: Setting queryIndex to 1 on blur');
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

      <div className="sidebar__chat" onPaste={handlePaste}>
        <div className="sidebar__messages">
          {loading ? (
            <div className="sidebar__loading">
              <div className="sidebar__spinner"></div>
              <span>Loading queries...</span>
            </div>
          ) : filteredQueries.length > 0 ? (
            filteredQueries.map((query) => (
              <div 
                key={query.id} 
                className={`sidebar__message sidebar__message--query ${
                  query.stage === stage ? 'sidebar__message--current-stage' : ''
                }`}
                onClick={() => {
                  // Switch to this query's stage when clicked
                  if (query.stage !== stage) {
                    handleInternalStageChange(query.stage);
                  }
                }}
                style={{ cursor: 'pointer' }}
              >
                <div className="sidebar__message-content">
                  {/* Text field */}
                  {hasValidValue(query.text) && (
                    <div className="sidebar__message-field">
                      <strong>Text:</strong> {query.text}
                    </div>
                  )}
                  
                  {/* OCR field */}
                  {hasValidValue(query.ocr) && (
                    <div className="sidebar__message-field">
                      <strong>OCR:</strong> {query.ocr}
                    </div>
                  )}
                  
                  {/* Speech field */}
                  {hasValidValue(query.speech) && (
                    <div className="sidebar__message-field">
                      <strong>Speech:</strong> {query.speech}
                    </div>
                  )}
                  
                  {/* Image field */}
                  {hasValidValue(query.image) && (
                    <div className="sidebar__message-field sidebar__message-image">
                      <img src={query.image} alt="Query image" className="sidebar__query-image" />
                    </div>
                  )}
                  
                  {/* Meta info */}
                  <div className="sidebar__message-meta">
                    <span className="sidebar__message-stage">Stage {query.stage}</span>
                    <span className="sidebar__message-date">
                      {(() => {
                        try {
                          const date = new Date(query.created_at);
                          return isNaN(date.getTime()) ? 
                            'Invalid Date' : 
                            date.toLocaleString('en-US', {
                              month: '2-digit',
                              day: '2-digit', 
                              year: 'numeric',
                              hour: '2-digit',
                              minute: '2-digit',
                              hour12: true
                            });
                        } catch (error) {
                          return 'Date Error';
                        }
                      })()}
                    </span>
                  </div>
                </div>

                {/* Delete button for individual query */}
                <button 
                  onClick={() => handleDeleteQuery(query.id)}
                  className="sidebar__delete-query"
                  title="Delete this query"
                >
                  <svg 
                    width="14" 
                    height="14" 
                    viewBox="0 0 24 24" 
                    fill="none" 
                    xmlns="http://www.w3.org/2000/svg"
                    className="sidebar__delete-query-icon"
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
            ))
          ) : (
            <div className="sidebar__empty">
              <p>No queries in Stage {stage}. Start by entering text, uploading an image, or using voice input.</p>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className="sidebar__input">
          {/* Stage Indicator */}
          {/* <div className="sidebar__stage-indicator">
            <span className="sidebar__stage-text">Creating query for Stage {stage}</span>
          </div> */}

          {/* Hidden file input for image paste */}
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            onChange={handleImageUpload}
            className="sidebar__file-input"
            id="image-upload"
            style={{ display: 'none' }}
          />

          {/* Image Preview - Moved to top */}
          {uploadedImage && (
            <div className="sidebar__image-preview">
              <img src={uploadedImage} alt="Uploaded" className="sidebar__preview-img" />
              <button onClick={handleRemoveImage} className="sidebar__remove-image">×</button>
            </div>
          )}

          {/* OCR Text Input Section */}
          <div className="sidebar__input-section">
            <label className="sidebar__input-label">OCR:</label>
            <div className="sidebar__input-container">
              <textarea
                ref={ocrTextareaRef}
                value={ocrText}
                onChange={(e) => setOcrText(e.target.value)}
                placeholder="OCR text from images..."
                className="sidebar__input-field"
                rows={1}
                onFocus={() => handleInputFocus(0)}
                onBlur={handleInputBlur}
              />
              {ocrText.trim() && (
                <button 
                  onClick={handleTranslateOcr}
                  disabled={isTranslating}
                  className="sidebar__translate-btn"
                  title="Translate to English"
                >
                  {isTranslating ? '...' : '🌐'}
                </button>
              )}
            </div>
          </div>

          {/* Speech Text Input Section */}
          <div className="sidebar__input-section">
            <label className="sidebar__input-label">Speech:</label>
            <div className="sidebar__input-container">
              <textarea
                ref={speechTextareaRef}
                value={speechText}
                onChange={(e) => setSpeechText(e.target.value)}
                placeholder="Speech to text result..."
                className="sidebar__input-field"
                rows={1}
                onFocus={() => handleInputFocus(1)}
                onBlur={handleInputBlur}
              />
              {speechText.trim() && (
                <button 
                  onClick={handleTranslateSpeech}
                  disabled={isTranslating}
                  className="sidebar__translate-btn"
                  title="Translate to English"
                >
                  {isTranslating ? '...' : '🌐'}
                </button>
              )}
            </div>
          </div>

          {/* Main Chat Input - Text input with Send and Mic only */}
          <div className="sidebar__input-container">
            <textarea
              ref={textareaRef}
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Type your query here..."
              className="sidebar__input-field"
              rows={1}
              onFocus={() => handleInputFocus(2)}
              onBlur={handleInputBlur}
            />
            
            <button
              onClick={handleMicrophoneClick}
              className={`sidebar__mic-btn ${isRecording ? 'recording' : ''}`}
              title={isRecording ? "Stop recording" : "Start recording"}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 1c-1.66 0-3 1.34-3 3v8c0 1.66 1.34 3 3 3s3-1.34 3-3V4c0-1.66-1.34-3-3-3zm5.91 9.38c0 3.45-2.79 6.26-6.26 6.26S5.39 13.83 5.39 10.38H3.61c0 4.7 3.41 8.6 7.87 9.48v2.05c0 .55.45 1 1 1s1-.45 1-1v-2.05c4.46-.88 7.87-4.78 7.87-9.48h-1.78z"/>
              </svg>
            </button>

            <button 
              onClick={handleSendMessage} 
              disabled={loading || (!inputMessage.trim() && !uploadedImage && !ocrText.trim() && !speechText.trim())}
              className="sidebar__send-btn"
            >
              <img src="/assets/send-alt-1-svgrepo-com.svg" alt="Send" />
            </button>
          </div>
        </div>
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
