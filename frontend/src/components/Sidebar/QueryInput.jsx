import React, { useRef, useEffect, useCallback } from 'react';
import { translatorService } from '../../services/TranslatorService';
import { useToast } from '../Toast/ToastProvider';
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
  onKeyPress,
  onPaste,
  onDragOver,
  onDragEnter,
  onDragLeave,
  onDrop
}) => {
  const toast = useToast();
  const fileInputRef = useRef(null);
  // Helper function to safely get string values, avoiding null/undefined display
  const getSafeValue = (value) => {
    if (value === null || value === undefined || value === 'null' || value === 'undefined') {
      return '';
    }
    return String(value);
  };

  const textareaRef = useRef(null);
  const ocrTextareaRef = useRef(null);
  // const speechTextareaRef = useRef(null); // Commented out - Speech input disabled for now

  // Input refs for navigation - Speech temporarily removed
  const inputRefs = [ocrTextareaRef, textareaRef]; // [ocrTextareaRef, speechTextareaRef, textareaRef];

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

  // Auto-resize Speech textarea - COMMENTED OUT (Speech input disabled)
  // const adjustSpeechTextareaHeight = () => {
  //   const textarea = speechTextareaRef.current;
  //   if (textarea) {
  //     textarea.style.height = 'auto';
  //     textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
  //   }
  // };

  useEffect(() => {
    adjustTextareaHeight();
  }, [currentLocalQuery?.text, adjustTextareaHeight]);

  useEffect(() => {
    adjustOcrTextareaHeight();
  }, [currentLocalQuery?.ocr]);

  // Speech auto-resize effect - COMMENTED OUT (Speech input disabled)
  // useEffect(() => {
  //   adjustSpeechTextareaHeight();
  // }, [currentLocalQuery?.speech]);

  // Initial resize on mount
  useEffect(() => {
    adjustTextareaHeight();
    adjustOcrTextareaHeight();
    // adjustSpeechTextareaHeight(); // Commented out - Speech input disabled
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
    };

    document.addEventListener('keydown', handleKeyDown, true);
    
    return () => {
      document.removeEventListener('keydown', handleKeyDown, true);
    };
  }, [currentInputIndex]);

  // Navigation function for input fields
  const navigateInputs = (direction) => {
    let nextIndex;
    
    if (direction === 'down') {
      if (currentInputIndex === -1) {
        // No focus -> go to top (OCR)
        nextIndex = 0;
      } else {
        // Move down cyclically: OCR(0) -> Text(1) -> OCR(0) (Speech removed)
        nextIndex = (currentInputIndex + 1) % inputRefs.length;
      }
    } else if (direction === 'up') {
      if (currentInputIndex === -1) {
        // No focus -> go to bottom (Text)
        nextIndex = inputRefs.length - 1; // Text (index 1)
      } else {
        // Move up cyclically: Text(1) -> OCR(0) -> Text(1) (Speech removed)
        nextIndex = currentInputIndex === 0 ? inputRefs.length - 1 : currentInputIndex - 1;
      }
    }
    
    // Focus on the target input
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
      console.log('Translation error:', error);
      toast.error('Failed to translate text');
    } finally {
      setIsTranslating(false);
    }
  };

  // Speech translation function - COMMENTED OUT (Speech input disabled)
  // const handleTranslateSpeech = async () => {
  //   const speechValue = getSafeValue(currentLocalQuery?.speech).trim();
  //   if (!speechValue) return;
  //   
  //   setIsTranslating(true);
  //   try {
  //     // Detect if text is Vietnamese, then translate to English, otherwise to Vietnamese
  //     const detectedLang = await translatorService.detectLanguage(speechValue);
  //     const targetLang = (detectedLang === 'vi') ? 'en' : 'vi';
  //     
  //     const translated = await translatorService.translateText(speechValue, targetLang);
  //     if (translated && translated !== speechValue) {
  //       updateCurrentLocalQuery({ speech: translated });
  //       toast.success('Text translated successfully!');
  //     }
  //   } catch (error) {
  //     console.log('Translation error:', error);
  //     toast.error('Failed to translate text');
  //   } finally {
  //     setIsTranslating(false);
  //   }
  // };

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

  return (
    <div 
      className="sidebar__input"
      onPaste={onPaste}
      onDragOver={onDragOver}
      onDragEnter={onDragEnter}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
    >
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
            ref={ocrTextareaRef}
            value={getSafeValue(currentLocalQuery?.ocr)}
            onChange={(e) => updateCurrentLocalQuery({ ocr: e.target.value })}
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

      {/* Speech Text Input Section - COMMENTED OUT (Speech input disabled for now) */}
      {/* 
      <div className="sidebar__input-section">
        <label className="sidebar__input-label">Speech:</label>
        <div className="sidebar__input-container">
          <textarea
            ref={speechTextareaRef}
            value={getSafeValue(currentLocalQuery?.speech)}
            onChange={(e) => updateCurrentLocalQuery({ speech: e.target.value })}
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
      */}

      {/* Main Chat Input - Text input with Send and Mic only */}
      <div className="sidebar__input-container sidebar__main-input-container">
        <textarea
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
          onKeyPress={onKeyPress}
          placeholder="Type your query here..."
          className="sidebar__input-field"
          rows={1}
          onFocus={() => handleInputFocus(1)} // Updated from index 2 to 1 (Speech removed)
          onBlur={handleInputBlur}
        />
        <div className="sidebar__input-actions">
          <button
            onClick={handleMicrophoneClick}
            className={`sidebar__mic-btn ${isRecording ? 'recording' : ''}`}
            title={isRecording ? "Stop recording" : "Start recording"}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 1c-1.66 0-3 1.34-3 3v8c0 1.66 1.34 3 3 3s3-1.34 3-3V4c0-1.66-1.34-3-3-3zm5.91 9.38c0 3.45-2.79 6.26-6.26 6.26S5.39 13.83 5.39 10.38H3.61c0 4.7 3.41 8.6 7.87 9.48v2.05c0 .55.45 1 1s1-.45 1-1v-2.05c4.46-.88 7.87-4.78 7.87-9.48h-1.78z"/>
            </svg>
          </button>

          <button 
            onClick={onSendMessage} 
            disabled={loading || (
              !getSafeValue(currentLocalQuery?.text).trim() && 
              !currentLocalQuery?.image && 
              !getSafeValue(currentLocalQuery?.ocr).trim()
              // !getSafeValue(currentLocalQuery?.speech).trim() // Commented out - Speech disabled
            )}
            className="sidebar__send-btn"
          >
            <img src="/assets/send-alt-1-svgrepo-com.svg" alt="Send" />
          </button>
        </div>
      </div>
    </div>
  );
};

export default QueryInput;
