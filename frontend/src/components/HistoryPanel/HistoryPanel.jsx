import React, { useState, useEffect } from 'react';
// Direct import to avoid cache issues
import SessionService from '../../services/SessionService';
import './HistoryPanel.scss';

const HistoryPanel = () => {
  const [sessions, setSessions] = useState([]);
  const [currentSessionId, setCurrentSessionId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [newSessionName, setNewSessionName] = useState('');
  const [showCreateForm, setShowCreateForm] = useState(false);

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
      
      // Set first session as current if none selected
      if (sessionList.length > 0 && !currentSessionId) {
        setCurrentSessionId(sessionList[0].id);
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
    setCurrentSessionId(sessionId);
    setError(null);
  };

  const handleDeleteSession = async (sessionId, e) => {
    e.stopPropagation(); // Prevent selecting session when deleting
    
    if (!window.confirm('Are you sure you want to delete this session?')) {
      return;
    }

    try {
      await SessionService.deleteSession(sessionId);
      setSessions(prev => prev.filter(session => session.id !== sessionId));
      
      // If deleted session was current, clear current session
      if (currentSessionId === sessionId) {
        setCurrentSessionId(null);
        // Set first remaining session as current
        setSessions(prev => {
          if (prev.length > 0) {
            setCurrentSessionId(prev[0].id);
          }
          return prev;
        });
      }
    } catch (err) {
      setError('Failed to delete session');
    }
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
        ) : sessions.length === 0 ? (
          <div className="history-panel__empty">
            <p>No sessions found.</p>
            <p>Create a new session to get started.</p>
          </div>
        ) : (
          <div className="history-panel__list">
            {sessions.map((session) => (
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
