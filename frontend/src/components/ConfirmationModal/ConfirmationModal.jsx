import React from 'react';
import './ConfirmationModal.scss';

const ConfirmationModal = ({ 
  isOpen, 
  onClose, 
  onConfirm, 
  title = "Confirm Action", 
  message = "Are you sure you want to proceed?",
  confirmText = "Confirm",
  cancelText = "Cancel",
  confirmButtonClass = "confirmation-modal__confirm",
  isLoading = false
}) => {
  if (!isOpen) return null;

  const handleBackdropClick = (e) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  const handleConfirm = () => {
    if (!isLoading) {
      onConfirm();
    }
  };

  const handleCancel = () => {
    if (!isLoading) {
      onClose();
    }
  };

  return (
    <div className="confirmation-modal__backdrop" onClick={handleBackdropClick}>
      <div className="confirmation-modal">
        <div className="confirmation-modal__header">
          <h3 className="confirmation-modal__title">{title}</h3>
          <button 
            className="confirmation-modal__close"
            onClick={handleCancel}
            disabled={isLoading}
            type="button"
          >
            ×
          </button>
        </div>
        
        <div className="confirmation-modal__content">
          <p className="confirmation-modal__message">{message}</p>
        </div>
        
        <div className="confirmation-modal__actions">
          <button 
            className="confirmation-modal__cancel"
            onClick={handleCancel}
            disabled={isLoading}
            type="button"
          >
            {cancelText}
          </button>
          <button 
            className={`${confirmButtonClass} ${isLoading ? 'confirmation-modal__loading' : ''}`}
            onClick={handleConfirm}
            disabled={isLoading}
            type="button"
          >
            {isLoading ? (
              <>
                <span className="confirmation-modal__spinner">⟳</span>
                Processing...
              </>
            ) : (
              confirmText
            )}
          </button>
        </div>
      </div>
    </div>
  );
};

export default ConfirmationModal;
