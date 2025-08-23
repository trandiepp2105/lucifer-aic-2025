import React, { useState, useRef, useEffect } from 'react';
import { useApp } from '../../contexts/AppContext';
import { useToast } from '../Toast/ToastProvider';
import { QueryModeUtils } from '../../utils/queryModeUtils';
import './ActivityBar.scss';

const ActivityBar = ({ onSectionChange, activeSection, onRoundChange, onQueryModeChange, onCsvFormatChange, onKChange, selectedRound = 'prelims', selectedQueryMode = 'kis', csvFilenameFormat = 'query-{query_index}-{type}', selectedK = 50 }) => {
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [currentRound, setCurrentRound] = useState(selectedRound);
  const [currentQueryMode, setCurrentQueryMode] = useState(selectedQueryMode);
  const [currentCsvFormat, setCurrentCsvFormat] = useState(csvFilenameFormat);
  const [currentK, setCurrentK] = useState(selectedK);
  const settingsRef = useRef(null);
  
  // Use AppContext for search URL and queryIndex
  const { searchUrl, setSearchUrl, queryIndex } = useApp();
  const toast = useToast();

  // Update internal state when props change
  useEffect(() => {
    setCurrentRound(selectedRound);
  }, [selectedRound]);

  useEffect(() => {
    setCurrentQueryMode(selectedQueryMode);
  }, [selectedQueryMode]);

  useEffect(() => {
    setCurrentCsvFormat(csvFilenameFormat);
  }, [csvFilenameFormat]);

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
      if (settingsRef.current && !settingsRef.current.contains(event.target)) {
        setIsSettingsOpen(false);
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
    setCurrentCsvFormat(format);
    // Notify parent component about CSV format change
    if (onCsvFormatChange) {
      onCsvFormatChange(format);
    }
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

  // Update CSS variable for slider progress
  const progress = ((currentK - 1) / (200 - 1)) * 100;

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
              </div>
              
              <div className="activity-bar__settings-section">
                <label className="activity-bar__settings-label">
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
                <label className="activity-bar__settings-label" htmlFor="csv-format-input">
                  CSV Filename Format
                </label>
                <div className="activity-bar__csv-format">
                  <input
                    id="csv-format-input"
                    type="text"
                    className="activity-bar__csv-format-input"
                    value={currentCsvFormat}
                    onChange={(e) => handleCsvFormatChange(e.target.value)}
                    placeholder="query-{query_index}-{type}"
                  />
                  <div className="activity-bar__csv-format-help">
                    Use {'{query_index}'} and {'{type}'} as placeholders
                  </div>
                </div>
              </div>

              <div className="activity-bar__settings-section">
                <label className="activity-bar__settings-label" htmlFor="search-url-input">
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
                <label className="activity-bar__settings-label" htmlFor="top-k-slider">
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
                    max="200"
                    value={currentK}
                    onChange={(e) => handleKChange(parseInt(e.target.value, 10))}
                  />
                  <div className="activity-bar__top-k-range">
                    <span>1</span>
                    <span>200</span>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ActivityBar;
