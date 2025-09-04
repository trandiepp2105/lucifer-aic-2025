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
    
    if (queryMode !== 'tra') {
      return;
    }
    
    try {
      setIsLoadingTRAKEAnswers(true);
      const response = await TeamTRAKEAnswerService.getTRAKEAnswers();
      
      if (response && response.data) {
        setAllTRAKEAnswers(response.data || []);
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
    
    if (queryMode === 'tra') {
      // Force clear old data first
      setAllTRAKEAnswers([]);
      // Then fetch new data
      fetchAllTRAKEAnswers();
    } else {
      // Clear TRAKE answers when not in 'tra' mode
      setAllTRAKEAnswers([]);
    }
  }, [queryMode, fetchAllTRAKEAnswers]);

  // Reset activeGroup when switching query or mode
  useEffect(() => {
    setActiveGroup(null);
  }, [queryIndex, queryMode]);

  // Initialize SSE permanently (don't depend on queryMode)
  useEffect(() => {
    
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
              case 'delete':
              case 'bulk_delete':
              case 'group_delete':
              case 'update_group':
              case 'group_update': // Add support for backend event type
                // Simply refresh all TRAKE answers when any changes happen
                if (queryMode === 'tra') {
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

    // Initialize immediately
    initializeSSE();

    // Cleanup only on unmount
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
        setSseConnected(false);
      }
    };
  }, [toast, fetchAllTRAKEAnswers, queryMode]); // Add queryMode to capture current value

  // Manual refresh function that can be called from components
  const manualRefreshTRAKEAnswers = useCallback(() => {
    if (queryMode === 'tra') {
      setAllTRAKEAnswers([]); // Clear first
      fetchAllTRAKEAnswers();
    }
  }, [queryMode, fetchAllTRAKEAnswers]);

  // Function to delete all TRAKE answers for current query
  const deleteAllTRAKEAnswers = useCallback(async () => {
    if (queryMode !== 'tra' || queryIndex === null || queryIndex === undefined) {
      return;
    }

    try {
      setIsLoadingTRAKEAnswers(true);
      const response = await TeamTRAKEAnswerService.deleteAllTRAKEAnswers(queryIndex);
      
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
    

    
    // Find the query data that matches current queryIndex
    const currentQueryData = allTRAKEAnswers.find(queryData => 
      queryData.query_index === queryIndex
    );
    
    if (!currentQueryData || !currentQueryData.data || !Array.isArray(currentQueryData.data)) {
      return [];
    }
    
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
