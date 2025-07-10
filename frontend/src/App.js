import React from 'react';
import HomePage from './pages/HomePage/HomePage';
import { ToastProvider } from './components/Toast/ToastProvider';
import { AppProvider } from './contexts/AppContext';
import './App.scss';

function App() {
  return (
    <AppProvider>
      <ToastProvider>
        <div className="App">
          <HomePage />
        </div>
      </ToastProvider>
    </AppProvider>
  );
}

export default App;