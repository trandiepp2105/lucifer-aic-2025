import React, { useState, useEffect } from 'react';
// Direct import to avoid cache issues
import SessionService from '../../services/SessionService';
import { useApp } from '../../contexts/AppContext';
import ConfirmationModal from '../ConfirmationModal';
import './HistoryPanel.scss';

const HistoryPanel = () => {
  const { session: currentSessionId, setSession } = useApp();
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [newSessionName, setNewSessionName] = useState('');
  const [showCreateForm, setShowCreateForm] = useState(false);
  
  // Confirmation modal states
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [sessionToDelete, setSessionToDelete] = useState(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // Load sessions on component mount
  useEffect(() => {
    loadSessions();
  }, []);

  const loadSessions = async () => {
    try {
      if (!SessionService || typeof SessionService.getSessions !== 'function') {
        throw new Error('SessionService.getSessions is not available');
      }
      
      setLoading(true);
      const sessionList = await SessionService.getSessions();
      setSessions(sessionList);
      setError(null);
      
      // Set first session as current if none selected (but only from non-current sessions)
      const availableSessions = sessionList.filter(session => session.id !== currentSessionId);
      if (availableSessions.length > 0 && !currentSessionId) {
        setSession(availableSessions[0].id);
      }
    } catch (err) {
      setError('Failed to load sessions');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateSession = async (e) => {
    e.preventDefault();
    if (!newSessionName.trim()) return;

    try {
      const newSession = await SessionService.createSession(newSessionName.trim());
      setSessions(prev => [newSession, ...prev]);
      setNewSessionName('');
      setShowCreateForm(false);
      
      // Auto-select the new session
      setCurrentSessionId(newSession.id);
    } catch (err) {
      setError('Failed to create session');
    }
  };

  const handleSelectSession = (sessionId) => {
    setSession(sessionId);
    setError(null);
  };

  const handleDeleteSession = (sessionId, e) => {
    e.stopPropagation(); // Prevent selecting session when deleting
    
    // Find session to show in confirmation
    const session = sessions.find(s => s.id === sessionId);
    setSessionToDelete(session);
    setShowDeleteModal(true);
  };

  const handleConfirmDelete = async () => {
    if (!sessionToDelete) return;

    try {
      setIsDeleting(true);
      await SessionService.deleteSession(sessionToDelete.id);
      setSessions(prev => prev.filter(session => session.id !== sessionToDelete.id));
      
      // Since we filter out current session, we don't need to handle deleting current session
      // Just reload the sessions list
      loadSessions();
    } catch (err) {
      setError('Failed to delete session');
    } finally {
      setIsDeleting(false);
      setShowDeleteModal(false);
      setSessionToDelete(null);
    }
  };

  const handleCancelDelete = () => {
    setShowDeleteModal(false);
    setSessionToDelete(null);
  };

  const formatTime = (dateString) => {
    if (!dateString) return 'Unknown';
    
    try {
      const date = new Date(dateString);
      const now = new Date();
      const diffMs = now - date;
      const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
      const diffDays = Math.floor(diffHours / 24);

      if (diffHours < 1) {
        return 'Just now';
      } else if (diffHours < 24) {
        return `${diffHours} hour${diffHours !== 1 ? 's' : ''} ago`;
      } else if (diffDays === 1) {
        return 'Yesterday';
      } else if (diffDays < 7) {
        return `${diffDays} days ago`;
      } else {
        return date.toLocaleDateString();
      }
    } catch (err) {
      return 'Unknown';
    }
  };

  return (
    <div className="history-panel">
      <ConfirmationModal
        isOpen={showDeleteModal}
        onClose={handleCancelDelete}
        onConfirm={handleConfirmDelete}
        title="Delete Session"
        message={`Are you sure you want to delete "${sessionToDelete?.name || `Session ${sessionToDelete?.id}`}"? This action cannot be undone.`}
        confirmText="Delete"
        cancelText="Cancel"
        isLoading={isDeleting}
      />
      
      <div className="history-panel__header">
        <h3>Session Manager</h3>
        <button 
          className="history-panel__add-btn"
          onClick={() => setShowCreateForm(!showCreateForm)}
          title="Create new session"
        >
          +
        </button>
      </div>
      
      <div className="history-panel__content">
        {error && (
          <div className="history-panel__error">
            {error}
          </div>
        )}

        {showCreateForm && (
          <form className="history-panel__create-form" onSubmit={handleCreateSession}>
            <input
              type="text"
              value={newSessionName}
              onChange={(e) => setNewSessionName(e.target.value)}
              placeholder="Enter session name..."
              className="history-panel__input"
              autoFocus
            />
            <div className="history-panel__form-actions">
              <button type="submit" className="history-panel__btn history-panel__btn--primary">
                Create
              </button>
              <button 
                type="button" 
                className="history-panel__btn history-panel__btn--secondary"
                onClick={() => {
                  setShowCreateForm(false);
                  setNewSessionName('');
                }}
              >
                Cancel
              </button>
            </div>
          </form>
        )}

        {loading ? (
          <div className="history-panel__loading">
            Loading sessions...
          </div>
        ) : sessions.filter(session => session.id !== currentSessionId).length === 0 ? (
          <div className="history-panel__empty">
            <p>No other sessions found.</p>
            <p>Create a new session to get started.</p>
          </div>
        ) : (
          <div className="history-panel__list">
            {sessions
              .filter(session => session.id !== currentSessionId)
              .map((session) => (
              <div
                key={session.id}
                className={`history-panel__item ${
                  currentSessionId === session.id 
                    ? 'history-panel__item--active' 
                    : ''
                }`}
                onClick={() => handleSelectSession(session.id)}
              >
                <div className="history-panel__item-content">
                  <div className="history-panel__title">
                    {session.name || `Session ${session.id}`}
                  </div>
                  <div className="history-panel__time">
                    {formatTime(session.created_at)}
                  </div>
                  {session.description && (
                    <div className="history-panel__description">
                      {session.description}
                    </div>
                  )}
                </div>
                <button
                  className="history-panel__delete-btn"
                  onClick={(e) => handleDeleteSession(session.id, e)}
                  title="Delete session"
                >
                  <img src="/assets/trash-bin.svg" alt="Delete" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default HistoryPanel;
