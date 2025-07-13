import React, { useEffect, useCallback } from 'react';
import './ImageZoomModal.scss';

const ImageZoomModal = ({ 
  isOpen, 
  onClose, 
  imageUrl, 
  imageAlt = 'Zoomed image',
  frame = null // Optional frame data for additional info
}) => {
  // Close modal on Escape key
  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Escape') {
      onClose();
    }
  }, [onClose]);

  // Close modal on click outside image
  const handleBackdropClick = (e) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  // Add event listeners when modal opens
  useEffect(() => {
    if (isOpen) {
      document.addEventListener('keydown', handleKeyDown);
      document.body.style.overflow = 'hidden'; // Prevent background scroll
      
      return () => {
        document.removeEventListener('keydown', handleKeyDown);
        document.body.style.overflow = 'auto'; // Restore scroll
      };
    }
  }, [isOpen, handleKeyDown]);

  if (!isOpen) return null;

  return (
    <div className="image-zoom-modal" onClick={handleBackdropClick}>
      <div className="image-zoom-modal__container">

        
        {/* Zoomed image */}
        <img 
          src={imageUrl} 
          alt={imageAlt}
          className="image-zoom-modal__image"
          onClick={(e) => e.stopPropagation()} // Prevent close on image click
        />
        
        {/* Optional frame info */}
        {frame && (
          <div className="image-zoom-modal__info">
            {frame.video_name && (
              <span className="image-zoom-modal__video">
                {frame.video_name}
              </span>
            )}
            {frame.frame_index !== undefined && (
              <span className="image-zoom-modal__frame">
                Frame: {frame.frame_index}
              </span>
            )}
            {frame.text && (
              <div className="image-zoom-modal__text">
                {frame.text}
              </div>
            )}
          </div>
        )}
        
        {/* Instructions */}
        <div className="image-zoom-modal__instructions">
          Press ESC or click outside to close
        </div>
      </div>
    </div>
  );
};

export default ImageZoomModal;
