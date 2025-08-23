import React from 'react';
import HomePage from './pages/HomePage/HomePage';
import { ToastProvider } from './components/Toast/ToastProvider';
import { AppProvider } from './contexts/AppContext';
import { TeamTRAKEAnswerProvider } from './contexts/TeamTRAKEAnswerContext';
import './App.scss';

function App() {
  return (
    <AppProvider>
      <ToastProvider>
        <TeamTRAKEAnswerProvider>
          <div className="App">
            <HomePage />
          </div>
        </TeamTRAKEAnswerProvider>
      </ToastProvider>
    </AppProvider>
  );
}

export default App;