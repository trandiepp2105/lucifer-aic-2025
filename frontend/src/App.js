import React from 'react';
import HomePage from './pages/HomePage/HomePage';
import { ToastProvider } from './components/Toast/ToastProvider';
import { AppProvider } from './contexts/AppContext';
import { TeamTRAKEAnswerProvider } from './contexts/TeamTRAKEAnswerContext';
import { SpeechProvider } from './contexts/SpeechContext';
import './App.scss';

function App() {
  return (
    <AppProvider>
      <ToastProvider>
        <SpeechProvider>
          <TeamTRAKEAnswerProvider>
            <div className="App">
              <HomePage />
            </div>
          </TeamTRAKEAnswerProvider>
        </SpeechProvider>
      </ToastProvider>
    </AppProvider>
  );
}

export default App;