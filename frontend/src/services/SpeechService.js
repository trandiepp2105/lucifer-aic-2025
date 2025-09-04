class SpeechService {
  constructor() {
    this.baseUrl = process.env.REACT_APP_BASE_URL || '';
  }

  /**
   * Get WebSocket connection information from backend
   */
  async getWebSocketInfo() {
    try {
      const response = await fetch(`${this.baseUrl}/speech/info/`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      return {
        success: true,
        data: data
      };
    } catch (error) {
      console.error('Error fetching WebSocket info:', error);
      return {
        success: false,
        error: error.message
      };
    }
  }

  /**
   * Create WebSocket connection to speech recognition service
   */
  createWebSocketConnection(websocketUrl, callbacks = {}) {
    try {
      const ws = new WebSocket(websocketUrl);

      ws.onopen = () => {
        if (callbacks.onOpen) {
          callbacks.onOpen();
        }
      };

      ws.onmessage = (event) => {
        try {
          const result = JSON.parse(event.data);
          
          if (callbacks.onMessage) {
            callbacks.onMessage(result);
          }
        } catch (error) {
          console.error('Error parsing speech result:', error);
          if (callbacks.onError) {
            callbacks.onError(error);
          }
        }
      };

      ws.onclose = (event) => {
        if (callbacks.onClose) {
          callbacks.onClose(event);
        }
      };

      ws.onerror = (error) => {
        console.error('🎤 Speech WebSocket error:', error);
        if (callbacks.onError) {
          callbacks.onError(error);
        }
      };

      return ws;
    } catch (error) {
      console.error('Error creating WebSocket connection:', error);
      throw error;
    }
  }

  /**
   * Send start recognition command
   */
  startRecognition(ws) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      const command = { command: "start_recognition" };
      ws.send(JSON.stringify(command));
    } else {
      throw new Error('WebSocket is not connected');
    }
  }

  /**
   * Send stop recognition command
   */
  stopRecognition(ws) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      const command = { command: "stop_recognition" };
      ws.send(JSON.stringify(command));
    } else {
      console.warn('WebSocket is not connected - cannot stop recognition');
    }
  }

  /**
   * Send audio data to WebSocket
   */
  sendAudioData(ws, audioData) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(audioData);
    } else {
      console.warn('WebSocket is not connected - cannot send audio data');
    }
  }

  /**
   * Convert Float32Array to 16-bit PCM
   */
  floatTo16BitPCM(input) {
    const output = new Int16Array(input.length);
    for (let i = 0; i < input.length; i++) {
      let s = Math.max(-1, Math.min(1, input[i]));
      output[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
    }
    return output;
  }

  /**
   * Calculate RMS volume for VAD (Voice Activity Detection)
   */
  calculateRMS(data) {
    let sum = 0;
    for (let i = 0; i < data.length; i++) {
      sum += data[i] * data[i];
    }
    return Math.sqrt(sum / data.length);
  }

  /**
   * Setup audio recording with WebSocket integration
   */
  async setupAudioRecording(ws, options = {}) {
    const {
      vadThreshold = 0.001,
      sampleRate = 16000,
      onVolumeUpdate = null,
      onError = null
    } = options;

    try {


      // Check browser compatibility for getUserMedia
      if (!navigator) {
        throw new Error('Navigator not available');
      }

      // Polyfill for mediaDevices if not available
      if (!navigator.mediaDevices) {
        
        // Check for legacy getUserMedia
        const legacyGetUserMedia = navigator.getUserMedia || 
                                  navigator.webkitGetUserMedia || 
                                  navigator.mozGetUserMedia || 
                                  navigator.msGetUserMedia;
        
        if (legacyGetUserMedia) {
          
          // Create polyfill for mediaDevices
          navigator.mediaDevices = {};
          navigator.mediaDevices.getUserMedia = function(constraints) {
            return new Promise((resolve, reject) => {
              legacyGetUserMedia.call(navigator, constraints, resolve, reject);
            });
          };
        } else {
          throw new Error('No microphone API available. This might be due to:\n' +
                         '• Browser security settings blocking media access\n' +
                         '• Enterprise policies restricting microphone access\n' +
                         '• Private browsing mode with strict settings\n' +
                         '• Browser extensions blocking media APIs\n\n' +
                         'For Edge: Check Settings > Privacy & Security > Camera/Microphone permissions\n' +
                         'Try: edge://settings/content/microphone');
        }
      }

      if (!navigator.mediaDevices.getUserMedia) {
        throw new Error('getUserMedia not available. Please check your browser settings and permissions.');
      }

      // Check if running in secure context (HTTPS required for getUserMedia)
      if (!window.isSecureContext && location.protocol !== 'https:' && location.hostname !== 'localhost') {
        throw new Error('Microphone access requires HTTPS or localhost. Please use a secure connection.');
      }


      // Request microphone access
      const stream = await navigator.mediaDevices.getUserMedia({ 
        audio: {
          sampleRate: sampleRate,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        }
      });

      // Create audio context
      const audioContext = new (window.AudioContext || window.webkitAudioContext)({ 
        sampleRate: sampleRate 
      });
      
      const input = audioContext.createMediaStreamSource(stream);
      const processor = audioContext.createScriptProcessor(4096, 1, 1);

      processor.onaudioprocess = (e) => {
        const data = e.inputBuffer.getChannelData(0);
        
        // Calculate volume for visual feedback
        const rms = this.calculateRMS(data);
        if (onVolumeUpdate) {
          const percent = Math.min(100, Math.floor(rms * 500));
          onVolumeUpdate(percent);
        }

        // Voice Activity Detection - only send if volume above threshold
        if (rms > vadThreshold) {
          const pcmData = this.floatTo16BitPCM(data);
          this.sendAudioData(ws, pcmData.buffer);
        }
      };

      input.connect(processor);
      processor.connect(audioContext.destination);

      return {
        stream,
        audioContext,
        input,
        processor,
        cleanup: () => {
          if (processor) {
            processor.disconnect();
            processor.onaudioprocess = null;
          }
          if (input) input.disconnect();
          if (audioContext) {
            audioContext.close();
          }
          if (stream) {
            stream.getTracks().forEach(track => track.stop());
          }
        }
      };
    } catch (error) {
      console.error('Error setting up audio recording:', error);
      
      // Provide user-friendly error messages
      let userMessage = 'Failed to access microphone';
      
      if (error.name === 'NotAllowedError' || error.name === 'PermissionDeniedError') {
        userMessage = 'Microphone permission denied. Please allow microphone access and try again.';
      } else if (error.name === 'NotFoundError' || error.name === 'DevicesNotFoundError') {
        userMessage = 'No microphone found. Please connect a microphone and try again.';
      } else if (error.name === 'NotReadableError' || error.name === 'TrackStartError') {
        userMessage = 'Microphone is being used by another application. Please close other apps using the microphone.';
      } else if (error.name === 'OverconstrainedError' || error.name === 'ConstraintNotSatisfiedError') {
        userMessage = 'Microphone does not support the required audio settings.';
      } else if (error.message) {
        userMessage = error.message;
      }
      
      const enhancedError = new Error(userMessage);
      enhancedError.originalError = error;
      
      if (onError) {
        onError(enhancedError);
      }
      throw enhancedError;
    }
  }
}

// Export singleton instance
export const speechService = new SpeechService();
export default speechService;
