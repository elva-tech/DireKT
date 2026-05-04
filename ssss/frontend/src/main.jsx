import React from 'react'
import ReactDOM from 'react-dom/client'
import './index.css'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from 'react-query'
import { Toaster } from 'react-hot-toast'
import App from './App.jsx'

function RootErrorFallback({ error }) {
  const msg = error?.message || String(error || 'Unknown error')
  return (
    <div
      style={{
        padding: 24,
        fontFamily: 'system-ui, sans-serif',
        maxWidth: 560,
        margin: '48px auto',
        color: '#0f172a',
      }}
    >
      <h1 style={{ fontSize: '1.25rem', marginBottom: 12 }}>App failed to load</h1>
      <pre
        style={{
          whiteSpace: 'pre-wrap',
          fontSize: 12,
          background: '#f1f5f9',
          padding: 12,
          borderRadius: 8,
          overflow: 'auto',
        }}
      >
        {msg}
      </pre>
      <p style={{ marginTop: 16, color: '#64748b', fontSize: 14 }}>
        Open DevTools (F12) → Console for details. Confirm the static site publishes the <code>dist</code> folder
        (not the repo root).
      </p>
    </div>
  )
}

class RootErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  render() {
    if (this.state.error) {
      return <RootErrorFallback error={this.state.error} />
    }
    return this.props.children
  }
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 10 * 60 * 1000, // 10 minutes
    },
  },
})

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <RootErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <App />
          <Toaster
            position="top-right"
            toastOptions={{
              duration: 4000,
              style: {
                background: '#363636',
                color: '#fff',
              },
              success: {
                duration: 3000,
                iconTheme: {
                  primary: '#22c55e',
                  secondary: '#fff',
                },
              },
              error: {
                duration: 5000,
                iconTheme: {
                  primary: '#ef4444',
                  secondary: '#fff',
                },
              },
            }}
          />
        </BrowserRouter>
      </QueryClientProvider>
    </RootErrorBoundary>
  </React.StrictMode>
)
