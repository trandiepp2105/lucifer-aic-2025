import React from 'react';
import './PlaceholderPanel.scss';

const PlaceholderPanel = ({ title, icon, description }) => {
  return (
    <div className="placeholder-panel">
      <div className="placeholder-panel__content">
        <div className="placeholder-panel__icon">{icon}</div>
        <h3 className="placeholder-panel__title">{title}</h3>
        <p className="placeholder-panel__description">{description}</p>
      </div>
    </div>
  );
};

export default PlaceholderPanel;
