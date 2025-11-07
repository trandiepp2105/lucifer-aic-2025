import React, { useRef, useEffect, useCallback } from 'react';
import { translatorService } from '../../services/TranslatorService';
import { useToast } from '../Toast/ToastProvider';
import { useSpeech } from '../../contexts/SpeechContext';
import { useApp } from '../../contexts/AppContext';
import './QueryInput.scss';

const QueryInput = ({
  currentLocalQuery,
  updateCurrentLocalQuery,
  isRecording,
  setIsRecording,
  isTranslating,
  setIsTranslating,
  currentInputIndex,
  setCurrentInputIndex,
  loading,
  onSendMessage,
}) => {
  const toast = useToast();
  const fileInputRef = useRef(null);
  
  // Access AppContext for temporal time
  const { temporalTime, setTemporalTime } = useApp();
  
  // Speech-to-text functionality using SpeechContext
  const {
    isRecording: isVoiceRecording,
    isInitializing: isVoiceInitializing,
    wsConnected,
    connectionStatus,
    finalTranscript,
    interimTranscript,
    getCombinedTranscript,
    startRecording: startVoiceRecording,
    stopRecording: stopVoiceRecording,
    clearTranscripts
  } = useSpeech();
  // Helper function to safely get string values, avoiding null/undefined display
  const getSafeValue = (value) => {
    if (value === null || value === undefined || value === 'null' || value === 'undefined') {
      return '';
    }
    return String(value);
  };

  const textareaRef = useRef(null);
  const ocrTextareaRef = useRef(null);
  const speechTextareaRef = useRef(null);

  // Input refs for navigation - Speech restored
  const inputRefs = [ocrTextareaRef, speechTextareaRef, textareaRef];

  // Auto-resize textarea
  const adjustTextareaHeight = useCallback(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      // Reset height to calculate scrollHeight properly
      textarea.style.height = 'auto';
      textarea.style.minHeight = '20px';
      
      // Calculate new height
      const newHeight = Math.min(textarea.scrollHeight, 150);
      
      // Set the new height with important to override CSS
      textarea.style.setProperty('height', newHeight + 'px', 'important');
      
      // Also adjust container height if needed
      const container = textarea.closest('.sidebar__main-input-container');
      if (container) {
        container.style.minHeight = 'auto';
        container.style.height = 'auto';
      }
    }
  }, []);

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
  }, [currentLocalQuery?.text, adjustTextareaHeight]);

  useEffect(() => {
    adjustOcrTextareaHeight();
  }, [currentLocalQuery?.ocr]);

  useEffect(() => {
    adjustSpeechTextareaHeight();
  }, [currentLocalQuery?.speech]);

  // Initial resize on mount
  useEffect(() => {
    adjustTextareaHeight();
    adjustOcrTextareaHeight();
    adjustSpeechTextareaHeight();
  }, [adjustTextareaHeight]);

  // Keyboard navigation between inputs
  useEffect(() => {
    const handleKeyDown = (e) => {
      // Ctrl + Arrow key navigation between inputs
      if ((e.key === 'ArrowDown' || e.key === 'ArrowUp') && e.ctrlKey) {
        // Prevent default scroll behavior
        e.preventDefault();
        e.stopPropagation();
        
        if (e.key === 'ArrowDown') {
          navigateInputs('down');
        } else {
          navigateInputs('up');
        }
      }

      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        // Use setTimeout to ensure any pending onChange events are processed first
        setTimeout(() => {
          onSendMessage();
        }, 0);
        return;
      }
    };

    document.addEventListener('keydown', handleKeyDown, true);
    
    return () => {
      document.removeEventListener('keydown', handleKeyDown, true);
    };
  }, [currentInputIndex, onSendMessage]); // Add onSendMessage as dependency

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
      }    // Focus on the target input
    if (inputRefs[nextIndex] && inputRefs[nextIndex].current) {
      inputRefs[nextIndex].current.focus();
      setCurrentInputIndex(nextIndex);
    }
  };

  const handleImageUpload = (e) => {
    const file = e.target.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (e) => {

        updateCurrentLocalQuery({
          image: e.target.result,
          imageFile: file,
          imageRemoved: false
        });
      };
      reader.readAsDataURL(file);
    }
  };

  const handleRemoveImage = () => {
    updateCurrentLocalQuery({
      image: null,
      imageFile: null,
      imageRemoved: true
    });
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
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

  // Auto-update text field with voice transcript in real-time
  useEffect(() => {
    if (isVoiceRecording) {
      const currentTranscript = getCombinedTranscript();
      if (currentTranscript) {
        // During recording, update text field instead of speech field
        updateCurrentLocalQuery({ 
          text: currentTranscript.trim()
        });
      }
    }
  }, [finalTranscript, interimTranscript, isVoiceRecording, getCombinedTranscript]);

  // Handle final transcript when recording completes
  useEffect(() => {
    if (!isVoiceRecording && finalTranscript) {
      // When recording stops and we have a final transcript, update text field
      updateCurrentLocalQuery({ 
        text: finalTranscript.trim(),
        baseText: undefined // Clear base text tracking
      });
    }
  }, [isVoiceRecording, finalTranscript]);

  // Voice recording functionality (new voice feature)
  const handleVoiceRecording = async () => {
    if (isVoiceRecording) {
      try {
        stopVoiceRecording();
        
        toast.success('Voice recording completed', 2000);
        
      } catch (error) {
        console.error('Error stopping voice recording:', error);
        toast.error('Failed to stop voice recording');
      }
    } else {
      try {
        if (!wsConnected) {
          toast.error('Speech service not connected. Please wait...');
          return;
        }
        
        // Clear the text field when starting new recording
        updateCurrentLocalQuery({ 
          text: '',
          baseText: undefined 
        });
        
        clearTranscripts(); // Clear previous transcripts
        await startVoiceRecording();
        toast.success('Voice recording started. Speak now...', 2000);
        
      } catch (error) {
        console.error('Error starting voice recording:', error);
        toast.error('Failed to start voice recording');
      }
    }
  };

  const handleTranslateOcr = async () => {
    const ocrValue = getSafeValue(currentLocalQuery?.ocr).trim();
    if (!ocrValue) return;
    
    setIsTranslating(true);
    try {
      // Detect if text is Vietnamese, then translate to English, otherwise to Vietnamese
      const detectedLang = await translatorService.detectLanguage(ocrValue);
      const targetLang = (detectedLang === 'vi') ? 'en' : 'vi';
      
      const translated = await translatorService.translateText(ocrValue, targetLang);
      if (translated && translated !== ocrValue) {
        updateCurrentLocalQuery({ ocr: translated });
        toast.success('Text translated successfully!');
      }
    } catch (error) {
      
      toast.error('Failed to translate text');
    } finally {
      setIsTranslating(false);
    }
  };

  // Speech translation function
  const handleTranslateSpeech = async () => {
    const speechValue = getSafeValue(currentLocalQuery?.speech).trim();
    if (!speechValue) return;
    
    setIsTranslating(true);
    try {
      // Detect if text is Vietnamese, then translate to English, otherwise to Vietnamese
      const detectedLang = await translatorService.detectLanguage(speechValue);
      const targetLang = (detectedLang === 'vi') ? 'en' : 'vi';
      
      const translated = await translatorService.translateText(speechValue, targetLang);
      if (translated && translated !== speechValue) {
        updateCurrentLocalQuery({ speech: translated });
        toast.success('Text translated successfully!');
      }
    } catch (error) {
      toast.error('Failed to translate text');
    } finally {
      setIsTranslating(false);
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

  // Handle image paste from clipboard (Ctrl+V)
  const handlePaste = (e) => {
    const items = e.clipboardData.items;
    for (let item of items) {
      if (item.type.indexOf('image') !== -1) {
        const file = item.getAsFile();
        if (file) {
          handleImageUpload({ target: { files: [file] } });
          e.preventDefault();
          break;
        }
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
      // Check if it's a frame drag from the main area
      const dragData = JSON.parse(e.dataTransfer.getData('application/json'));
      
      if (dragData.type === 'frame-image' && dragData.url) {
        // Convert frame URL to blob and set as uploaded image
        const response = await fetch(dragData.url);
        const blob = await response.blob();
        
        // Create file object from blob
        const file = new File([blob], `${dragData.frame.filename}.jpg`, { type: 'image/jpeg' });
        handleImageUpload({ target: { files: [file] } });
        
        toast.success(`Image from ${dragData.frame.filename} added to query`);
      }
    } catch (error) {
      // If JSON parsing fails, try to handle as file drop
      const files = Array.from(e.dataTransfer.files);
      const imageFiles = files.filter(file => file.type.startsWith('image/'));
      
      if (imageFiles.length > 0) {
        handleImageUpload({ target: { files: [imageFiles[0]] } });
        toast.success('Image added to query');
      } else {
        console.error('Error handling dropped item:', error);
        toast.error('Failed to add image from drop');
      }
    }
  };

  // Handle temporal time change
  const handleTemporalTimeChange = (value) => {
    // Round to nearest 5
    const roundedValue = Math.round(value / 5) * 5;
    setTemporalTime(roundedValue);
  };

  // Format temporal time display
  const formatTemporalTime = (seconds) => {
    if (seconds < 60) {
      return `${seconds}s`;
    } else {
      const minutes = Math.floor(seconds / 60);
      const remainingSeconds = seconds % 60;
      return `${minutes}m${remainingSeconds}s`;
    }
  };

  // Calculate progress for temporal time slider (min: 5, max: 180)
  const temporalTimeProgress = ((temporalTime - 5) / (180 - 5)) * 100;

  return (
    <div 
      className="sidebar__input sidebar__drop-zone"
      onPaste={handlePaste}
      onDragOver={handleDragOver}
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      {/* Temporal Time Slider */}
      <div className="sidebar__temporal-time-section">
        <label className="sidebar__temporal-time-label" htmlFor="temporal-time-slider" style={{ maxWidth: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          Temporal Time: {formatTemporalTime(temporalTime)}
        </label>
        <div className="sidebar__temporal-time">
          <div className="sidebar__custom-slider-track">
            <div className="sidebar__custom-slider-fill" style={{ width: `${temporalTimeProgress}%` }}></div>
            {/* Ticks/marks cho mỗi bước 5 giây */}
            <div className="sidebar__slider-ticks">
              {Array.from({ length: 36 }, (_, i) => {
                const value = i * 5 + 5;
                const min = 5;
                const max = 180;
                const percent = ((value - min) / (max - min)) * 100;
                return (
                  <div 
                    key={value} 
                    className="sidebar__slider-tick"
                    style={{ left: `${percent}%` }}
                  />
                );
              })}
            </div>
          </div>
          <input
            id="temporal-time-slider"
            type="range"
            className="sidebar__temporal-time-slider"
            min="5"
            max="180"
            step="5"
            value={temporalTime}
            onChange={(e) => handleTemporalTimeChange(parseInt(e.target.value, 10))}
          />
          <div className="sidebar__temporal-time-range">
            <span>5s</span>
            <span>3m</span>
          </div>
        </div>
      </div>

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
      {currentLocalQuery?.image && (
        <div className="sidebar__image-preview">
          <img src={currentLocalQuery.image} alt="Uploaded" className="sidebar__preview-img" />
          <button onClick={handleRemoveImage} className="sidebar__remove-image">×</button>
        </div>
      )}

      {/* OCR Text Input Section */}
      <div className="sidebar__input-section">
        <label className="sidebar__input-label">OCR:</label>
        <div className="sidebar__input-container">
          <textarea
            id="ocr-input"
            ref={ocrTextareaRef}
            value={getSafeValue(currentLocalQuery?.ocr)}
            onChange={(e) => updateCurrentLocalQuery({ ocr: e.target.value })}
            // onKeyDown={(e) => {
            //   if (e.key === 'Enter' && !e.shiftKey) {
            //     e.preventDefault();
            //     // Use setTimeout to ensure onChange is processed first
            //     setTimeout(() => {
            //       onSendMessage();
            //     }, 0);
            //   }
            // }}
            placeholder="OCR text from images..."
            className="sidebar__input-field"
            rows={1}
            onFocus={() => handleInputFocus(0)}
            onBlur={handleInputBlur}
          />
          {getSafeValue(currentLocalQuery?.ocr).trim() && (
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
        <label className="sidebar__input-label">Subtitle:</label>
        <div className="sidebar__input-container">
          <textarea
            id="speech-input"
            ref={speechTextareaRef}
            value={getSafeValue(currentLocalQuery?.speech)}
            onChange={(e) => updateCurrentLocalQuery({ speech: e.target.value })}
            // onKeyDown={(e) => {
            //   if (e.key === 'Enter' && !e.shiftKey) {
            //     e.preventDefault();
            //     // Use setTimeout to ensure onChange is processed first
            //     setTimeout(() => {
            //       onSendMessage();
            //     }, 0);
            //   }
            // }}
            placeholder="Speech to text result..."
            className="sidebar__input-field"
            rows={1}
            onFocus={() => handleInputFocus(1)}
            onBlur={handleInputBlur}
          />
          {getSafeValue(currentLocalQuery?.speech).trim() && (
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
      <div className="sidebar__input-container sidebar__main-input-container">
        <textarea
          id="text-input"
          ref={textareaRef}
          value={getSafeValue(currentLocalQuery?.text)}
          onChange={(e) => {
            updateCurrentLocalQuery({ text: e.target.value });
            // Trigger resize on next tick to ensure DOM is updated
            setTimeout(() => adjustTextareaHeight(), 0);
          }}
          onInput={() => {
            // Also trigger on input event for better responsiveness
            setTimeout(() => adjustTextareaHeight(), 0);
          }}
          // onKeyDown={(e) => {
          //   if (e.key === 'Enter' && !e.shiftKey) {
          //     e.preventDefault();
          //     // Use setTimeout to ensure onChange is processed first
          //     setTimeout(() => {
          //       onSendMessage();
          //     }, 0);
          //   }
          // }}
          placeholder="Type your query here..."
          className="sidebar__input-field"
          rows={1}
          onFocus={() => handleInputFocus(2)} // Updated from index 1 to 2 (Speech restored)
          onBlur={handleInputBlur}
        />
        <div className="sidebar__input-actions">
          {/* Voice recording button using mic button style */}
          <button
            onClick={handleVoiceRecording}
            disabled={isVoiceInitializing || !wsConnected}
            className={`sidebar__mic-btn ${isVoiceRecording ? 'recording' : ''} ${!wsConnected ? 'disconnected' : ''}`}
            title={
              !wsConnected ? 'Speech service disconnected' :
              isVoiceInitializing ? 'Initializing...' :
              isVoiceRecording ? 'Stop voice recording' : 'Start voice recording'
            }
          >
            {isVoiceInitializing ? (
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" className="sidebar__voice-loading">
                <path d="M12,4a8,8 0 0,1 7.89,6.7 1.53,1.53 0 0,0 1.49,1.3h0a1.5,1.5 0 0,0 1.48-1.75 11,11 0 0,0 -21.72,0A1.5,1.5 0 0,0 2.62,12h0a1.53,1.53 0 0,0 1.49-1.3A8,8 0 0,1 12,4Z"/>
              </svg>
            ) : (
              <img src="/assets/mic-solid-svgrepo-com.svg" alt="Microphone" width="16" height="16" />
            )}
          </button>

          <button 
            onClick={onSendMessage} 
            disabled={loading || (
              !getSafeValue(currentLocalQuery?.text).trim() && 
              !currentLocalQuery?.image && 
              !getSafeValue(currentLocalQuery?.ocr).trim() &&
              !getSafeValue(currentLocalQuery?.speech).trim()
            )}
            className="sidebar__send-btn"
          >
            <img src="/assets/send-alt-1-svgrepo-com.svg" alt="Send" />
          </button>
        </div>
      </div>

      {!wsConnected && (
        <div className="sidebar__voice-warning">
          <span>⚠️ Speech service disconnected</span>
        </div>
      )}
    </div>
  );
};

export default QueryInput;
