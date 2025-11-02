import React, { useState, useRef, useEffect } from 'react';
import { useApp } from '../../contexts/AppContext';
import { useToast } from '../Toast/ToastProvider';
import { QueryModeUtils } from '../../utils/queryModeUtils';
import { DresLoginService, DresSessionService } from '../../services/DresLoginService';
import './ActivityBar.scss';

const ActivityBar = ({ onSectionChange, activeSection, onRoundChange, onQueryModeChange, onKChange, selectedRound = 'prelims', selectedQueryMode = 'kis', selectedK = 50 }) => {
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isDresLoginOpen, setIsDresLoginOpen] = useState(false);
  const [dresLoginData, setDresLoginData] = useState({ username: '', password: '' });
  const [dresLoginLoading, setDresLoginLoading] = useState(false);
  const [evaluationIdLoading, setEvaluationIdLoading] = useState(false);
  const [currentRound, setCurrentRound] = useState(selectedRound);
  const [currentQueryMode, setCurrentQueryMode] = useState(selectedQueryMode);
  const [currentK, setCurrentK] = useState(selectedK);
  const settingsRef = useRef(null);
  const dresLoginRef = useRef(null);
  
  // Use AppContext for search URL, queryIndex, and csvFormat
  const { searchUrl, setSearchUrl, dresSession, setDresSession, evaluationId, setEvaluationId, queryIndex, csvFormat, setCsvFormat } = useApp();
  const toast = useToast();

  // Update internal state when props change
  useEffect(() => {
    setCurrentRound(selectedRound);
  }, [selectedRound]);

  useEffect(() => {
    setCurrentQueryMode(selectedQueryMode);
  }, [selectedQueryMode]);

  useEffect(() => {
    setCurrentK(selectedK);
  }, [selectedK]);


  const allSections = [
    { id: 'chat', icon: '/assets/chat.svg', title: 'Chat' },
    { id: 'history', icon: '/assets/history.svg', title: 'Chat History' },
    { id: 'team-answer', icon: '/assets/team.svg', title: 'Team Answer' },
    { id: 'answer', icon: '/assets/send.svg', title: 'Answer' },
  ];

  // Filter sections based on round - only team-answer is hidden for final round
  const sections = allSections.filter(section => {
    if (currentRound === 'final' && section.id === 'team-answer') {
      return false;
    }
    return true;
  });

  // Auto-switch section when round changes - only switch from team-answer when round becomes final
  useEffect(() => {
    if (currentRound === 'final' && activeSection === 'team-answer') {
      onSectionChange('chat');
    }
  }, [currentRound, activeSection, onSectionChange]);

  // Close settings dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      // Close settings dropdown only if clicked outside settings AND outside dres login popup
      if (settingsRef.current && !settingsRef.current.contains(event.target) &&
          (!dresLoginRef.current || !dresLoginRef.current.contains(event.target))) {
        setIsSettingsOpen(false);
      }
      // Close dres login popup if clicked outside of it
      if (dresLoginRef.current && !dresLoginRef.current.contains(event.target)) {
        setIsDresLoginOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  const handleSettingsClick = () => {
    setIsSettingsOpen(!isSettingsOpen);
  };

  const handleRoundChange = (round) => {
    setCurrentRound(round);
    // Notify parent component about round change
    if (onRoundChange) {
      onRoundChange(round);
    }
  };

  const handleLabelClick = (round) => {
    handleRoundChange(round);
  };

  const handleQueryModeChange = async (mode) => {
    try {
      // Validate mode switch against current query index data
      const validation = await QueryModeUtils.validateModeSwitch(mode, queryIndex);
      
      if (validation.allowed) {
        setCurrentQueryMode(mode);
        // Notify parent component about query mode change
        if (onQueryModeChange) {
          onQueryModeChange(mode);
        }
        if (validation.message) {
          toast.success(validation.message);
        }
      } else {
        // Keep current mode, show error
        if (validation.message) {
          toast.error(validation.message);
        }
        console.warn(`Mode switch blocked: ${validation.message}`);
      }
    } catch (error) {
      console.error('Error validating mode switch:', error);
      toast.error('Error validating mode switch');
    }
  };

  const handleQueryModeClick = (mode) => {
    handleQueryModeChange(mode);
  };

  const handleCsvFormatChange = (format) => {
    setCsvFormat(format);
  };

  const handleKChange = (k) => {
    setCurrentK(k);
    // Notify parent component about k change
    if (onKChange) {
      onKChange(k);
    }
  };

  const handleSearchUrlChange = (url) => {
    setSearchUrl(url);
  };

  const handleDresSessionChange = (session) => {
    setDresSession(session);
  };

  const handleEvaluationIdChange = (id) => {
    setEvaluationId(id);
  };

  const handleDresLoginToggle = () => {
    setIsDresLoginOpen(!isDresLoginOpen);
  };

  const handleDresLoginInputChange = (field, value) => {
    setDresLoginData(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const handleDresLogin = async () => {
    if (!dresLoginData.username || !dresLoginData.password) {
      toast.error('Please enter both username and password');
      return;
    }

    setDresLoginLoading(true);
    try {
      const response = await DresLoginService.login({
        username: dresLoginData.username,
        password: dresLoginData.password
      });

      if (response.success && response.data) {
        const { session_id, evaluation_id } = response.data;
        if (session_id) {
          setDresSession(session_id);
          // Update evaluation_id if available
          if (evaluation_id) {
            setEvaluationId(evaluation_id);
            console.log('DRES login successful with evaluation_id:', evaluation_id);
          } else {
            console.log('DRES login successful but no active evaluation found');
          }
          toast.success('DRES login successful');
          setIsDresLoginOpen(false);
          setDresLoginData({ username: '', password: '' });
        } else {
          toast.error('No session ID received from server');
        }
      } else {
        toast.error(response.error || 'Login failed');
      }
    } catch (error) {
      console.error('DRES login error:', error);
      toast.error('Login failed: ' + error.message);
    } finally {
      setDresLoginLoading(false);
    }
  };

  const handleDresLoginKeyDown = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      e.stopPropagation();
      handleDresLogin();
    }
  };

  const handleEvaluationIdApply = async () => {
    setEvaluationIdLoading(true);
    try {
      const response = await DresSessionService.updateEvaluationId(evaluationId);
      
      if (response.success) {
        toast.success('Evaluation ID updated successfully');
        console.log('Evaluation ID updated:', evaluationId);
      } else {
        toast.error('Failed to update Evaluation ID: ' + response.error);
        console.error('Evaluation ID update failed:', response.error);
      }
    } catch (error) {
      toast.error('Failed to update Evaluation ID: ' + error.message);
      console.error('Evaluation ID update error:', error);
    } finally {
      setEvaluationIdLoading(false);
    }
  };

  // Update CSS variable for slider progress
  const progress = ((currentK - 1) / (500 - 1)) * 100;

  return (
    <div className="activity-bar">
      <div className="activity-bar__sections">
        {sections.map((section) => (
          <button
            key={section.id}
            className={`activity-bar__item ${activeSection === section.id ? 'activity-bar__item--active' : ''}`}
            onClick={() => onSectionChange(section.id)}
            title={section.title}
          >
            <img 
              src={section.icon} 
              alt={section.title}
              className="activity-bar__icon"
            />
          </button>
        ))}
      </div>

      <div className="activity-bar__bottom">
        <div className="activity-bar__query-mode">
          <div className="activity-bar__query-mode-tabs">
            <button
              className={`activity-bar__query-mode-tab ${currentQueryMode === 'kis' ? 'activity-bar__query-mode-tab--active' : ''}`}
              onClick={() => handleQueryModeClick('kis')}
              title="KIS Mode"
            >
              KIS
            </button>
            <button
              className={`activity-bar__query-mode-tab ${currentQueryMode === 'qa' ? 'activity-bar__query-mode-tab--active' : ''}`}
              onClick={() => handleQueryModeClick('qa')}
              title="Q&A Mode"
            >
              Q&A
            </button>
            <button
              className={`activity-bar__query-mode-tab ${currentQueryMode === 'tra' ? 'activity-bar__query-mode-tab--active' : ''}`}
              onClick={() => handleQueryModeClick('tra')}
              title="TRAKE Mode"
            >
              TRA
            </button>
          </div>
        </div>
        
        <div className="activity-bar__settings" ref={settingsRef}>
          <button
            className="activity-bar__item"
            onClick={handleSettingsClick}
            title="Settings"
          >
            <img 
              src="/assets/setting.svg" 
              alt="Settings"
              className="activity-bar__icon"
            />
          </button>
          
          {isSettingsOpen && (
            <div className="activity-bar__settings-dropdown">
              <div className="activity-bar__settings-header">
                <h3>Settings</h3>
                <button
                  className="activity-bar__dres-login-toggle"
                  onClick={handleDresLoginToggle}
                  title="DRES Login"
                >
                  DRES
                </button>
              </div>
              
              <div className="activity-bar__settings-section">
                <label className="activity-bar__settings-label" style={{ maxWidth: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  Round
                </label>
                <div className="activity-bar__round-selector">
                  <div className="activity-bar__round-tabs">
                    <button
                      className={`activity-bar__round-tab ${currentRound === 'prelims' ? 'activity-bar__round-tab--active' : ''}`}
                      onClick={() => handleLabelClick('prelims')}
                    >
                      PRELIMS
                    </button>
                    <button
                      className={`activity-bar__round-tab ${currentRound === 'final' ? 'activity-bar__round-tab--active' : ''}`}
                      onClick={() => handleLabelClick('final')}
                    >
                      FINAL
                    </button>
                  </div>
                </div>
              </div>

              <div className="activity-bar__settings-section">
                <label className="activity-bar__settings-label" htmlFor="csv-format-input" style={{ maxWidth: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  CSV Filename Format
                </label>
                <div className="activity-bar__csv-format">
                  <input
                    id="csv-format-input"
                    type="text"
                    className="activity-bar__csv-format-input"
                    value={csvFormat}
                    onChange={(e) => handleCsvFormatChange(e.target.value)}
                    placeholder="query-{query_index}-{type}"
                  />
                  <div className="activity-bar__csv-format-help">
                    Use {'{query_index}'} and {'{type}'} as placeholders
                  </div>
                </div>
              </div>

              <div className="activity-bar__settings-section">
                <label className="activity-bar__settings-label" htmlFor="search-url-input" style={{ maxWidth: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  Search URL
                </label>
                <div className="activity-bar__search-url">
                  <textarea
                    id="search-url-input"
                    className="activity-bar__search-url-input"
                    value={searchUrl}
                    onChange={(e) => handleSearchUrlChange(e.target.value)}
                    placeholder="Enter search server endpoint URL..."
                    rows={3}
                  />
                  <div className="activity-bar__search-url-help">
                    URL endpoint for search server
                  </div>
                </div>
              </div>

              <div className="activity-bar__settings-section">
                <label className="activity-bar__settings-label" htmlFor="dres-url-input" style={{ maxWidth: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  DRES Session
                </label>
                <div className="activity-bar__search-url">
                  {/* don't allow textarea to edit*/}
                  <textarea
                    id="dres-url-input"
                    className="activity-bar__search-url-input"
                    // readOnly
                    value={dresSession}
                    onChange={(e) => handleDresSessionChange(e.target.value)}
                    placeholder="DRES session will appear here after login..."
                    rows={3}
                  />
                  <div className="activity-bar__search-url-help">
                    DRES session ID from server
                  </div>
                </div>
              </div>

              <div className="activity-bar__settings-section">
                <label className="activity-bar__settings-label" htmlFor="evaluation-id-input" style={{ maxWidth: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  Evaluation ID
                </label>
                <div className="activity-bar__search-url">
                  <textarea
                    id="evaluation-id-input"
                    className="activity-bar__search-url-input"
                    value={evaluationId}
                    onChange={(e) => handleEvaluationIdChange(e.target.value)}
                    placeholder="Enter DRES evaluation ID..."
                    rows={2}
                  />
                  <div className="activity-bar__search-url-help">
                    DRES evaluation/competition ID
                  </div>
                  <button
                    className="activity-bar__apply-button"
                    onClick={handleEvaluationIdApply}
                    disabled={evaluationIdLoading}
                  >
                    {evaluationIdLoading ? 'Applying...' : 'Apply'}
                  </button>
                </div>
              </div>

              <div className="activity-bar__settings-section">
                <label className="activity-bar__settings-label" htmlFor="top-k-slider" style={{ maxWidth: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  Top K Results: {currentK}
                </label>
                <div className="activity-bar__top-k">
                  <div className="activity-bar__custom-slider-track">
                    <div className="activity-bar__custom-slider-fill" style={{ width: `${progress}%` }}></div>
                  </div>
                  <input
                    id="top-k-slider"
                    type="range"
                    className="activity-bar__top-k-slider"
                    min="1"
                    max="500"
                    value={currentK}
                    onChange={(e) => handleKChange(parseInt(e.target.value, 10))}
                  />
                  <div className="activity-bar__top-k-range">
                    <span>1</span>
                    <span>500</span>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* DRES Login Popup */}
        {isDresLoginOpen && (
          <div className="activity-bar__dres-login-popup" ref={dresLoginRef}>
            <div className="activity-bar__dres-login-header">
              <h3>DRES Login</h3>
            </div>
            <div className="activity-bar__dres-login-form">
              <div className="activity-bar__dres-login-field">
                <label htmlFor="dres-username">Username</label>
                <input
                  id="dres-username"
                  type="text"
                  value={dresLoginData.username}
                  onChange={(e) => handleDresLoginInputChange('username', e.target.value)}
                  onKeyDown={handleDresLoginKeyDown}
                  placeholder="Enter username"
                  disabled={dresLoginLoading}
                  autoFocus
                />
              </div>
              <div className="activity-bar__dres-login-field">
                <label htmlFor="dres-password">Password</label>
                <input
                  id="dres-password"
                  type="password"
                  value={dresLoginData.password}
                  onChange={(e) => handleDresLoginInputChange('password', e.target.value)}
                  onKeyDown={handleDresLoginKeyDown}
                  placeholder="Enter password"
                  disabled={dresLoginLoading}
                />
              </div>
              <div className="activity-bar__dres-login-actions">
                <button
                  className="activity-bar__dres-login-btn activity-bar__dres-login-btn--cancel"
                  onClick={() => setIsDresLoginOpen(false)}
                  disabled={dresLoginLoading}
                >
                  Cancel
                </button>
                <button
                  className="activity-bar__dres-login-btn activity-bar__dres-login-btn--login"
                  onClick={handleDresLogin}
                  disabled={dresLoginLoading || !dresLoginData.username || !dresLoginData.password}
                >
                  {dresLoginLoading ? 'Logging in...' : 'Login'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default ActivityBar;
