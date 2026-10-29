import React from 'react';
import { createRoot } from 'react-dom/client';
import { ErrorBoundary } from './core/runtime/ErrorBoundary';
import { Dashboard } from './Dashboard';
import './styles/global.css';

const root = document.getElementById('root');
if (!root) throw new Error('Frontend root element is missing.');

createRoot(root).render(
  <React.StrictMode>
    <ErrorBoundary>
      <Dashboard />
    </ErrorBoundary>
  </React.StrictMode>,
);
