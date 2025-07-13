import React, { useState, useRef, useEffect } from 'react';
import './ActivityBar.scss';

const ActivityBar = ({ onSectionChange, activeSection, onRoundChange, onQueryModeChange, onCsvFormatChange, selectedRound = 'prelims', selectedQueryMode = 'kis', csvFilenameFormat = 'query-{query_index}-{type}' }) => {
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [currentRound, setCurrentRound] = useState(selectedRound);
  const [currentQueryMode, setCurrentQueryMode] = useState(selectedQueryMode);
  const [currentCsvFormat, setCurrentCsvFormat] = useState(csvFilenameFormat);
  const settingsRef = useRef(null);

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

  const handleQueryModeChange = (mode) => {
    setCurrentQueryMode(mode);
    // Notify parent component about query mode change
    if (onQueryModeChange) {
      onQueryModeChange(mode);
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
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ActivityBar;
