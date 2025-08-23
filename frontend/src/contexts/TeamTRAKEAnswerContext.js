import React, { createContext, useContext, useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { useApp } from './AppContext';
import { useToast } from '../components/Toast/ToastProvider';
import { TeamTRAKEAnswerService } from '../services/TeamTRAKEAnswerService';
import { apiConfig } from '../services/apiConfig';

// Create the context
const TeamTRAKEAnswerContext = createContext();

// Custom hook to use the context
export const useTeamTRAKEAnswer = () => {
  const context = useContext(TeamTRAKEAnswerContext);
  if (!context) {
    throw new Error('useTeamTRAKEAnswer must be used within a TeamTRAKEAnswerProvider');
  }
  return context;
};

// Provider component
export const TeamTRAKEAnswerProvider = ({ children }) => {
  const { queryIndex, queryMode } = useApp();
  const toast = useToast();
  
  // TRAKE-specific state
  const [allTRAKEAnswers, setAllTRAKEAnswers] = useState([]);
  const [activeGroup, setActiveGroup] = useState(null);
  const [isLoadingTRAKEAnswers, setIsLoadingTRAKEAnswers] = useState(false);
  const [sseConnected, setSseConnected] = useState(false);

  // SSE reference
  const eventSourceRef = useRef(null);

  // Fetch TRAKE answers
  const fetchAllTRAKEAnswers = useCallback(async () => {
    console.log('🎯 Context fetchAllTRAKEAnswers called - fetching all TRAKE answers');
    
    if (queryMode !== 'tra') {
      console.log('❌ Not in tra mode, skipping fetch');
      return;
    }
    
    try {
      setIsLoadingTRAKEAnswers(true);
      console.log('📡 Making API call to fetch all TRAKE answers...');
      const response = await TeamTRAKEAnswerService.getTRAKEAnswers();
      console.log('📡 All TRAKE answers response:', response);
      
      if (response && response.data) {
        setAllTRAKEAnswers(response.data || []);
        console.log('✅ All TRAKE answers set:', response.data.length, 'groups');
      } else {
        console.error('Failed to fetch TRAKE answers:', response);
        toast.error('Failed to load TRAKE answers');
        setAllTRAKEAnswers([]);
      }
    } catch (error) {
      console.error('Error fetching TRAKE answers:', error);
      if (error.message?.includes('same video name')) {
        toast.error('All items must have the same video name');
      } else {
        toast.error('Error loading TRAKE answers');
      }
      setAllTRAKEAnswers([]);
    } finally {
      setIsLoadingTRAKEAnswers(false);
    }
  }, [queryMode, toast]);

  // Load TRAKE answers when queryMode changes
  useEffect(() => {
    console.log('🔄 useEffect triggered: queryMode =', queryMode);
    
    if (queryMode === 'tra') {
      console.log('🔄 Fetching all TRAKE answers');
      // Force clear old data first
      setAllTRAKEAnswers([]);
      // Then fetch new data
      fetchAllTRAKEAnswers();
    } else {
      // Clear TRAKE answers when not in 'tra' mode
      console.log('🧹 Clearing TRAKE answers - not in tra mode');
      setAllTRAKEAnswers([]);
    }
  }, [queryMode, fetchAllTRAKEAnswers]);

  // Reset activeGroup when switching query or mode
  useEffect(() => {
    setActiveGroup(null);
  }, [queryIndex, queryMode]);

  // Initialize SSE permanently (don't depend on queryMode)
  useEffect(() => {
    console.log('🚀 Starting TRAKE SSE permanently for mode detection');
    
    // Initialize SSE connection immediately
    const initializeSSE = () => {
      try {
        // Close existing connection if any
        if (eventSourceRef.current) {
          eventSourceRef.current.close();
          eventSourceRef.current = null;
        }

        // Create new EventSource connection
        const sseUrl = `${apiConfig.baseURL}/team-trake-answers/sse/`;
        console.log('🔗 Initializing TRAKE SSE connection to:', sseUrl);
        
        const eventSource = new EventSource(sseUrl);
        eventSourceRef.current = eventSource;

        // Handle incoming messages
        eventSource.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            console.log('📡 TRAKE SSE message received:', data);

            switch (data.type) {
              case 'connected':
                setSseConnected(true);
                toast.success('TRAKE real-time updates connected', 500);
                break;

              case 'create':
              case 'delete':
              case 'bulk_delete':
              case 'group_delete':
              case 'update_group':
              case 'group_update': // Add support for backend event type
                // Simply refresh all TRAKE answers when any changes happen
                if (queryMode === 'tra') {
                  console.log(`📡 SSE ${data.type} event - refreshing all TRAKE answers`, data);
                  fetchAllTRAKEAnswers();
                  
                  // Show appropriate toast message
                  switch (data.type) {
                    case 'create':
                      toast.success('New TRAKE items added', 500);
                      break;
                    case 'delete':
                      toast.info('TRAKE items removed', 500);
                      break;
                    case 'bulk_delete':
                      toast.info(`${data.count || 'Multiple'} TRAKE items deleted`, 500);
                      break;
                    case 'group_delete':
                      toast.info('TRAKE group deleted', 500);
                      break;
                    case 'update_group':
                    case 'group_update':
                      toast.info(`TRAKE group updated (${data.updated_count || 'items'} moved to group ${data.new_group || 'unknown'})`, 1000);
                      break;
                  }
                } else {
                  console.log(`📡 SSE ${data.type} event ignored - not in tra mode`);
                }
                break;

              case 'heartbeat':
                // Keep connection alive
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
          console.log('✅ TRAKE SSE connection opened');
          setSseConnected(true);
        };

        // Handle connection errors
        eventSource.onerror = (event) => {
          console.error('❌ TRAKE SSE connection error:', event);
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

    // Initialize immediately
    initializeSSE();

    // Cleanup only on unmount
    return () => {
      if (eventSourceRef.current) {
        console.log('🔌 Closing TRAKE SSE connection on unmount');
        eventSourceRef.current.close();
        eventSourceRef.current = null;
        setSseConnected(false);
      }
    };
  }, [toast, fetchAllTRAKEAnswers, queryMode]); // Add queryMode to capture current value

  // Manual refresh function that can be called from components
  const manualRefreshTRAKEAnswers = useCallback(() => {
    if (queryMode === 'tra') {
      console.log('🔄 Manual refresh all TRAKE answers');
      setAllTRAKEAnswers([]); // Clear first
      fetchAllTRAKEAnswers();
    }
  }, [queryMode, fetchAllTRAKEAnswers]);

  // Function to delete all TRAKE answers for current query
  const deleteAllTRAKEAnswers = useCallback(async () => {
    if (queryMode !== 'tra' || queryIndex === null || queryIndex === undefined) {
      console.log('❌ Cannot delete TRAKE answers - not in tra mode or no queryIndex');
      return;
    }

    try {
      setIsLoadingTRAKEAnswers(true);
      console.log('🗑️ Deleting all TRAKE answers for queryIndex:', queryIndex);
      const response = await TeamTRAKEAnswerService.deleteAllTRAKEAnswers(queryIndex);
      console.log('🗑️ Delete response:', response);
      
      if (response && response.success) {
        // Refresh all data to update the UI
        await fetchAllTRAKEAnswers();
        toast.success('All TRAKE answers deleted');
        return { success: true };
      } else {
        console.error('Failed to delete all TRAKE answers:', response);
        toast.error('Failed to delete TRAKE answers');
        return { success: false, error: response?.error || 'Failed to delete all TRAKE answers' };
      }
    } catch (error) {
      console.error('Error deleting all TRAKE answers:', error);
      toast.error('Failed to delete TRAKE answers');
      return { success: false, error: error.message || 'Error deleting all TRAKE answers' };
    } finally {
      setIsLoadingTRAKEAnswers(false);
    }
  }, [queryMode, queryIndex, toast, fetchAllTRAKEAnswers]);

  // Computed property to get TRAKE answers for current query index
  const currentQueryTRAKEAnswers = useMemo(() => {
    if (!allTRAKEAnswers || !Array.isArray(allTRAKEAnswers)) {
      return [];
    }
    
    console.log('🔍 Filtering TRAKE answers for queryIndex:', queryIndex);
    console.log('🔍 All TRAKE answers:', allTRAKEAnswers);
    
    // Find the query data that matches current queryIndex
    const currentQueryData = allTRAKEAnswers.find(queryData => 
      queryData.query_index === queryIndex
    );
    
    if (!currentQueryData || !currentQueryData.data || !Array.isArray(currentQueryData.data)) {
      console.log('🔍 No data found for queryIndex:', queryIndex);
      return [];
    }
    
    console.log('🔍 Found data for queryIndex:', queryIndex, currentQueryData.data);
    return currentQueryData.data;
  }, [allTRAKEAnswers, queryIndex]);

  const contextValue = {
    // State
    allTRAKEAnswers, // Keep original for internal use
    currentQueryTRAKEAnswers, // Filtered for current query
    setAllTRAKEAnswers,
    activeGroup,
    setActiveGroup,
    isLoadingTRAKEAnswers,
    sseConnected,
    
    // Actions
    fetchAllTRAKEAnswers,
    manualRefreshTRAKEAnswers,
    deleteAllTRAKEAnswers,
    
    // Helper function to toggle active group
    toggleActiveGroup: useCallback((groupNumber) => {
      setActiveGroup(current => current === groupNumber ? null : groupNumber);
    }, []),
    
    // Helper function to clear active group
    clearActiveGroup: useCallback(() => {
      setActiveGroup(null);
    }, [])
  };

  return (
    <TeamTRAKEAnswerContext.Provider value={contextValue}>
      {children}
    </TeamTRAKEAnswerContext.Provider>
  );
};

export default TeamTRAKEAnswerContext;
