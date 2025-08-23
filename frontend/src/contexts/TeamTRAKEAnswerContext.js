import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
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
  const fetchAllTRAKEAnswers = useCallback(async (queryIdx = queryIndex) => {
    console.log('🎯 Context fetchAllTRAKEAnswers called with queryIndex:', queryIdx);
    
    if (queryMode !== 'tra') return;
    if (queryIdx === null || queryIdx === undefined) {
      console.log('❌ No queryIndex provided, skipping fetch');
      return;
    }
    
    try {
      setIsLoadingTRAKEAnswers(true);
      console.log('📡 Making API call to fetch TRAKE answers...');
      const response = await TeamTRAKEAnswerService.getTRAKEAnswers(queryIdx);
      console.log('📡 TRAKE answers response:', response);
      
      if (response && response.data) {
        setAllTRAKEAnswers(response.data || []);
        console.log('✅ TRAKE answers set:', response.data.length, 'groups');
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
  }, [queryIndex, queryMode, toast]);

  // Load TRAKE answers when queryIndex or queryMode changes
  useEffect(() => {
    if (queryMode === 'tra' && queryIndex !== null) {
      fetchAllTRAKEAnswers(queryIndex);
    }
  }, [queryIndex, queryMode, fetchAllTRAKEAnswers]);

  // Reset activeGroup when switching query or mode
  useEffect(() => {
    setActiveGroup(null);
  }, [queryIndex, queryMode]);

  // Initialize SSE connection for TRAKE answers
  const initializeTRAKESSE = useCallback(() => {
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
              // Refresh TRAKE answers when new items are created
              if (queryMode === 'tra' && queryIndex !== null) {
                fetchAllTRAKEAnswers(queryIndex);
              }
              toast.success('New TRAKE items added', 500);
              break;

            case 'delete':
              // Refresh TRAKE answers when items are deleted
              if (queryMode === 'tra' && queryIndex !== null) {
                fetchAllTRAKEAnswers(queryIndex);
              }
              toast.info('TRAKE items removed', 500);
              break;

            case 'bulk_delete':
              // Refresh TRAKE answers when bulk delete occurs
              if (queryMode === 'tra' && queryIndex !== null) {
                fetchAllTRAKEAnswers(queryIndex);
              }
              toast.info(`${data.count || 'Multiple'} TRAKE items deleted`, 500);
              break;

            case 'group_delete':
              // Refresh TRAKE answers when group is deleted
              if (queryMode === 'tra' && queryIndex !== null) {
                fetchAllTRAKEAnswers(queryIndex);
              }
              toast.info(`TRAKE group deleted`, 500);
              break;

            case 'update_group':
              // Refresh TRAKE answers when group is updated
              if (queryMode === 'tra' && queryIndex !== null) {
                fetchAllTRAKEAnswers(queryIndex);
              }
              toast.info('TRAKE group updated', 500);
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
  }, [queryMode, queryIndex, toast, fetchAllTRAKEAnswers]);

  // Cleanup SSE connection
  const cleanupTRAKESSE = useCallback(() => {
    if (eventSourceRef.current) {
      console.log('🔌 Closing TRAKE SSE connection');
      eventSourceRef.current.close();
      eventSourceRef.current = null;
      setSseConnected(false);
    }
  }, []);

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
                // Always refresh TRAKE answers when there are changes
                // This ensures the context data is up-to-date for mode detection
                const currentQueryIndex = queryIndex;
                if (currentQueryIndex !== null) {
                  fetchAllTRAKEAnswers(currentQueryIndex);
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
  }, []); // Empty dependency array - only run once on mount

  const contextValue = {
    // State
    allTRAKEAnswers,
    setAllTRAKEAnswers,
    activeGroup,
    setActiveGroup,
    isLoadingTRAKEAnswers,
    sseConnected,
    
    // Actions
    fetchAllTRAKEAnswers,
    
    // Delete all TRAKE answers for current query
    deleteAllTRAKEAnswers: useCallback(async (queryIdx = queryIndex) => {
      console.log('🗑️ Context deleteAllTRAKEAnswers called with queryIndex:', queryIdx);
      
      if (queryMode !== 'tra') return;
      if (queryIdx === null || queryIdx === undefined) {
        console.log('❌ No queryIndex provided, skipping delete');
        return;
      }
      
      try {
        console.log('📡 Making API call to delete all TRAKE answers...');
        const response = await TeamTRAKEAnswerService.deleteAllTRAKEAnswers(queryIdx);
        console.log('📡 Delete all TRAKE answers response:', response);
        
        if (response && response.success) {
          setAllTRAKEAnswers([]);
          console.log('✅ All TRAKE answers deleted successfully');
          return { success: true };
        } else {
          console.error('Failed to delete all TRAKE answers:', response);
          return { success: false, error: response?.error || 'Failed to delete all TRAKE answers' };
        }
      } catch (error) {
        console.error('Error deleting all TRAKE answers:', error);
        return { success: false, error: error.message || 'Error deleting all TRAKE answers' };
      }
    }, [queryIndex, queryMode]),
    
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
