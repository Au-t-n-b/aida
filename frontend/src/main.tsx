import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { RouterProvider } from 'react-router-dom';
import { router } from './router';
import { AidaSessionProvider } from './lib/aida-session';
import { CurrentProjectProvider } from './lib/current-project';
import { AidaChatBridge } from './lib/aida-chat-bridge';
import './styles/globals.css';
import './styles/claw-rail.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AidaSessionProvider>
      <CurrentProjectProvider>
        <AidaChatBridge />
        <RouterProvider router={router} />
      </CurrentProjectProvider>
    </AidaSessionProvider>
  </StrictMode>,
);
