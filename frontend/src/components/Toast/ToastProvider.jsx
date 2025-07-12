import React, { createContext, useContext, useState, useCallback, useMemo } from 'react';
import Toast from './Toast';

const ToastContext = createContext();

export const useToast = () => {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return context;
};

export const ToastProvider = ({ children }) => {
  const [toasts, setToasts] = useState([]);
  const MAX_TOASTS = 3;

  const showToast = useCallback((message, type = 'info', duration = 3000) => {
    const id = Date.now();
    const newToast = { id, message, type, duration };
    
    setToasts(prev => {
      const newToasts = [...prev, newToast];
      // Keep only the last MAX_TOASTS toasts
      return newToasts.slice(-MAX_TOASTS);
    });
  }, []);

  const removeToast = useCallback((id) => {
    setToasts(prev => prev.filter(toast => toast.id !== id));
  }, []);

  const value = useMemo(() => ({
    showToast,
    success: (message, duration) => showToast(message, 'success', duration),
    error: (message, duration) => showToast(message, 'error', duration),
    warning: (message, duration) => showToast(message, 'warning', duration),
    info: (message, duration) => showToast(message, 'info', duration),
  }), [showToast]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="toast-container">
        {toasts.map((toast, index) => {
          // Calculate position from bottom
          // Newest toast (highest index) should be at bottom
          const fromBottom = toasts.length - 1 - index;
          const bottomOffset = 20 + fromBottom * 70; // 70px spacing between toasts
          
          return (
            <Toast
              key={toast.id}
              message={toast.message}
              type={toast.type}
              duration={toast.duration}
              onClose={() => removeToast(toast.id)}
              style={{ bottom: `${bottomOffset}px` }}
            />
          );
        })}
      </div>
    </ToastContext.Provider>
  );
};
