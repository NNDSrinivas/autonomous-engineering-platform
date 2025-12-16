import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from './App'
import { WorkspaceProvider } from './context/WorkspaceContext'
import './index.css'

// Create a React Query client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
})

// Check if we're in VS Code webview (iframe) and use appropriate router
const isInWebview = window.location.pathname.includes('/navi') || window.parent !== window;
const RouterComponent = isInWebview ? MemoryRouter : BrowserRouter;

// Set initial entries for MemoryRouter when in webview
const routerProps = isInWebview ? { initialEntries: ['/navi'], initialIndex: 0 } : {};

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <WorkspaceProvider>
        <RouterComponent {...routerProps}>
          <App />
        </RouterComponent>
      </WorkspaceProvider>
    </QueryClientProvider>
  </React.StrictMode>,
)