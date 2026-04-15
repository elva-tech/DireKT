import React from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './stores/authStore'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard-enhanced'
import TestButton from './pages/TestButton'
import Trading from './pages/Trading-enhanced'
import Portfolio from './pages/Portfolio'
import Orders from './pages/Orders'
import Settings from './pages/Settings'
import History from './pages/History'
import Layout from './components/Layout-enhanced'

function App() {
  const { isAuthenticated, isLoading, initializeAuth } = useAuthStore()

  // Initialize auth on app mount
  React.useEffect(() => {
    initializeAuth()
  }, [])

  if (isLoading) {
    return (
      <div style={{ 
        backgroundColor: '#0f172a', 
        backgroundImage: 'linear-gradient(135deg, #1e293b 0%, #0f172a 100%)',
        color: 'white', 
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, sans-serif'
      }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{
            width: '40px',
            height: '40px',
            border: '4px solid rgba(255, 255, 255, 0.1)',
            borderTop: '4px solid #3b82f6',
            borderRadius: '50%',
            animation: 'spin 1s linear infinite',
            margin: '0 auto 20px'
          }}></div>
          <p style={{ color: '#94a3b8', fontSize: '1.1rem' }}>
            Initializing MCX Trading Platform...
          </p>
        </div>
        <style jsx>{`
          @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
          }
        `}</style>
      </div>
    )
  }

  return (
    <div style={{ 
      backgroundColor: '#0f172a', 
      backgroundImage: 'linear-gradient(135deg, #1e293b 0%, #0f172a 100%)',
      color: 'white', 
      minHeight: '100vh',
      fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, sans-serif'
    }}>
      <Routes>
        <Route 
          path="/login" 
          element={!isAuthenticated ? <Login /> : <Navigate to="/dashboard" replace />} 
        />
        <Route element={isAuthenticated ? <Layout /> : <Navigate to="/login" replace />}>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/test" element={<TestButton />} />
          <Route path="/trading" element={<Trading />} />
          <Route path="/history" element={<History />} />
          <Route path="/portfolio" element={<Portfolio />} />
          <Route path="/orders" element={<Orders />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
        </Route>
        <Route
          path="*"
          element={<Navigate to={isAuthenticated ? "/dashboard" : "/login"} replace />}
        />
      </Routes>
    </div>
  )
}

export default App
