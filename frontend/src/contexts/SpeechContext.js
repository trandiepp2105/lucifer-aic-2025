import React, { createContext, useContext, useState, useEffect, useRef, useCallback } from 'react';
import { speechService } from '../services/SpeechService';

const SpeechContext = createContext();

export const SpeechProvider = ({ children }) => {
  // WebSocket connection state
  const [ws, setWs] = useState(null);
  const [wsConnected, setWsConnected] = useState(false);
  const [wsInfo, setWsInfo] = useState(null);
  
  // Recording state
  const [isRecording, setIsRecording] = useState(false);
  const [isInitializing, setIsInitializing] = useState(false);
  
  // Speech results
  const [currentTranscript, setCurrentTranscript] = useState('');
  const [finalTranscript, setFinalTranscript] = useState('');
  const [interimTranscript, setInterimTranscript] = useState('');
  
  // Audio recording resources
  const audioResourcesRef = useRef(null);
  const volumeLevel = useRef(0);
  
  // Connection status
  const [connectionStatus, setConnectionStatus] = useState('disconnected'); // disconnected, connecting, connected, error

  /**
   * Initialize WebSocket connection
   */
  const initializeWebSocket = useCallback(async () => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      return ws;
    }

    try {
      setConnectionStatus('connecting');
      
      // Get WebSocket info from backend
      const infoResponse = await speechService.getWebSocketInfo();
      if (!infoResponse.success) {
        throw new Error(infoResponse.error || 'Failed to get WebSocket info');
      }

      setWsInfo(infoResponse.data);
      const websocketUrl = infoResponse.data.websocket_url;
      // Create WebSocket connection
      const newWs = speechService.createWebSocketConnection(websocketUrl, {
        onOpen: () => {
          setWsConnected(true);
          setConnectionStatus('connected');
        },
        onMessage: (result) => {
          
          if (result.transcript) {
            if (result.is_final) {
              setFinalTranscript(prev => prev + result.transcript + ' ');
              setInterimTranscript('');
              // Don't accumulate in currentTranscript - it will be calculated by getCombinedTranscript
            } else {
              setInterimTranscript(result.transcript);
            }
          }
        },
        onClose: (event) => {
          setWsConnected(false);
          setConnectionStatus('disconnected');
          setWs(null);
        },
        onError: (error) => {
          console.error('🎤 Speech WebSocket error:', error);
          setConnectionStatus('error');
        }
      });

      setWs(newWs);
      return newWs;
      
    } catch (error) {
      console.error('Error initializing WebSocket:', error);
      setConnectionStatus('error');
      throw error;
    }
  }, [ws]);

  /**
   * Start voice recording
   */
  const startRecording = useCallback(async () => {
    if (isRecording) {
      return;
    }

    try {
      setIsInitializing(true);
      
      // Ensure WebSocket is connected
      let currentWs = ws;
      if (!currentWs || currentWs.readyState !== WebSocket.OPEN) {
        currentWs = await initializeWebSocket();
        
        // Wait a bit for connection to stabilize
        await new Promise(resolve => setTimeout(resolve, 500));
        
        if (!currentWs || currentWs.readyState !== WebSocket.OPEN) {
          throw new Error('Failed to establish WebSocket connection');
        }
      }

      // Start speech recognition on server
      speechService.startRecognition(currentWs);

      // Setup audio recording
      const audioResources = await speechService.setupAudioRecording(currentWs, {
        vadThreshold: 0.001,
        sampleRate: 16000,
        onVolumeUpdate: (percent) => {
          volumeLevel.current = percent;
        },
        onError: (error) => {
          console.error('Audio recording error:', error);
          stopRecording();
        }
      });

      audioResourcesRef.current = audioResources;
      setIsRecording(true);
      // Reset all transcripts for new recording session
      setCurrentTranscript('');
      setFinalTranscript('');
      setInterimTranscript('');
      
      
    } catch (error) {
      console.error('Error starting recording:', error);
      setIsRecording(false);
      throw error;
    } finally {
      setIsInitializing(false);
    }
  }, [isRecording, ws, initializeWebSocket]);

  /**
   * Stop voice recording
   */
  const stopRecording = useCallback(() => {
    if (!isRecording) {
      return;
    }

    try {
      // Stop speech recognition on server
      if (ws && ws.readyState === WebSocket.OPEN) {
        speechService.stopRecognition(ws);
      }

      // Cleanup audio resources
      if (audioResourcesRef.current) {
        audioResourcesRef.current.cleanup();
        audioResourcesRef.current = null;
      }

      setIsRecording(false);
      volumeLevel.current = 0;
      
      
    } catch (error) {
      console.error('Error stopping recording:', error);
    }
  }, [isRecording, ws]);

  /**
   * Clear transcripts
   */
  const clearTranscripts = useCallback(() => {
    setCurrentTranscript('');
    setFinalTranscript('');
    setInterimTranscript('');
  }, []);

  /**
   * Get combined transcript (final + interim)
   */
  const getCombinedTranscript = useCallback(() => {
    return finalTranscript + interimTranscript;
  }, [finalTranscript, interimTranscript]);

  /**
   * Get current volume level
   */
  const getVolumeLevel = useCallback(() => {
    return volumeLevel.current;
  }, []);

  /**
   * Disconnect WebSocket
   */
  const disconnectWebSocket = useCallback(() => {
    if (isRecording) {
      stopRecording();
    }

    if (ws) {
      ws.close();
      setWs(null);
      setWsConnected(false);
      setConnectionStatus('disconnected');
    }
  }, [ws, isRecording, stopRecording]);

  // Initialize WebSocket when component mounts
  useEffect(() => {
    let mounted = true;

    const initConnection = async () => {
      try {
        await initializeWebSocket();
      } catch (error) {
        if (mounted) {
          console.error('Failed to initialize speech WebSocket:', error);
        }
      }
    };

    initConnection();

    // Cleanup function
    return () => {
      mounted = false;
      if (isRecording) {
        stopRecording();
      }
      if (ws) {
        ws.close();
      }
    };
  }, []); // Empty dependency array for mount/unmount only

  // Auto-reconnect WebSocket if disconnected unexpectedly
  useEffect(() => {
    let reconnectTimer;

    if (!wsConnected && connectionStatus === 'disconnected' && !isInitializing) {
      // Only auto-reconnect if we were previously connected
      if (ws === null) {
        reconnectTimer = setTimeout(() => {
          initializeWebSocket().catch(error => {
            console.error('Auto-reconnect failed:', error);
          });
        }, 3000); // Retry after 3 seconds
      }
    }

    return () => {
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
      }
    };
  }, [wsConnected, connectionStatus, isInitializing, ws, initializeWebSocket]);

  const contextValue = {
    // Connection state
    wsConnected,
    wsInfo,
    connectionStatus,
    
    // Recording state
    isRecording,
    isInitializing,
    
    // Transcript state
    currentTranscript,
    finalTranscript,
    interimTranscript,
    
    // Methods
    startRecording,
    stopRecording,
    clearTranscripts,
    getCombinedTranscript,
    getVolumeLevel,
    disconnectWebSocket,
    initializeWebSocket
  };

  return (
    <SpeechContext.Provider value={contextValue}>
      {children}
    </SpeechContext.Provider>
  );
};

export const useSpeech = () => {
  const context = useContext(SpeechContext);
  if (!context) {
    throw new Error('useSpeech must be used within a SpeechProvider');
  }
  return context;
};

export default SpeechContext;
