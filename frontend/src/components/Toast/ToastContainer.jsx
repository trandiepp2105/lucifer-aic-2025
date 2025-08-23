import React from 'react';
import Toast from './Toast';
import './ToastContainer.scss';

const ToastContainer = ({ toasts, onRemoveToast }) => {
  if (!toasts || toasts.length === 0) {
    return null;
  }

  return (
    <div className="toast-container">
      {toasts.map((toast, index) => (
        <Toast
          key={toast.id}
          message={toast.message}
          type={toast.type}
          duration={toast.duration}
          onClose={() => onRemoveToast(toast.id)}
          style={{
            bottom: `${20 + index * 80}px`
          }}
        />
      ))}
    </div>
  );
};

export default ToastContainer;
