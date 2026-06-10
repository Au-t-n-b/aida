import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { RouterProvider } from 'react-router-dom';
import { router } from './router';
import { AidaSessionProvider } from './lib/aida-session';
import { AidaChatBridge } from './lib/aida-chat-bridge';
import './styles/globals.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AidaSessionProvider>
      <AidaChatBridge />
      <RouterProvider router={router} />
    </AidaSessionProvider>
  </StrictMode>,
);
