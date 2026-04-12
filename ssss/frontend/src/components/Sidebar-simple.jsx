import React from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'

function navButtonStyle(active) {
  return {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    padding: '12px 16px',
    borderRadius: '12px',
    fontSize: '0.9rem',
    fontWeight: '500',
    marginBottom: '8px',
    backgroundColor: active ? 'rgba(59, 130, 246, 0.25)' : 'transparent',
    color: active ? '#93c5fd' : '#9ca3af',
    border: active ? '1px solid rgba(59, 130, 246, 0.45)' : '1px solid transparent',
    cursor: 'pointer',
    width: '100%',
    textAlign: 'left',
  }
}

function Sidebar() {
  const { logout, user } = useAuthStore()
  const navigate = useNavigate()
  const location = useLocation()

  const handleLogout = async () => {
    console.log('Logout clicked')
    await logout()
    navigate('/login')
  }

  const handleNavigation = (path) => {
    console.log('Navigating to:', path)
    navigate(path)
  }

  return (
    <div style={{
      width: '280px',
      backgroundColor: 'rgba(15, 23, 42, 0.95)',
      backdropFilter: 'blur(16px)',
      borderRight: '1px solid rgba(255, 255, 255, 0.1)',
      display: 'flex',
      flexDirection: 'column',
      fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, sans-serif'
    }}>
      {/* Logo */}
      <div style={{
        padding: '24px',
        borderBottom: '1px solid rgba(255, 255, 255, 0.1)'
      }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '12px'
        }}>
          <div style={{
            width: '40px',
            height: '40px',
            background: 'linear-gradient(135deg, #3b82f6, #2563eb)',
            borderRadius: '12px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '20px'
          }}>
            📈
          </div>
          <div>
            <h1 style={{
              fontSize: '1.2rem',
              fontWeight: 'bold',
              color: 'white',
              marginBottom: '2px'
            }}>
              MCX Trading
            </h1>
            <p style={{ fontSize: '0.8rem', color: '#6b7280' }}>
              Professional Platform
            </p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav style={{ flex: 1, padding: '16px' }}>
        {/* Test Button */}
        <button
          onClick={() => {
            console.log('Test button clicked!')
            alert('Button works!')
          }}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            padding: '12px 16px',
            borderRadius: '12px',
            fontSize: '0.9rem',
            fontWeight: '500',
            marginBottom: '8px',
            backgroundColor: 'rgba(239, 68, 68, 0.1)',
            border: '1px solid rgba(239, 68, 68, 0.3)',
            color: '#ef4444',
            cursor: 'pointer',
            width: '100%',
            textAlign: 'left'
          }}
        >
          <span style={{ fontSize: '1.2rem' }}>🧪</span>
          <span>Test Alert</span>
        </button>

        {/* Navigation Buttons */}
        <button
          onClick={() => handleNavigation('/dashboard')}
          style={navButtonStyle(location.pathname === '/dashboard')}
        >
          <span style={{ fontSize: '1.2rem' }}>📊</span>
          <span>Dashboard</span>
        </button>

        <button
          onClick={() => handleNavigation('/test')}
          style={navButtonStyle(location.pathname === '/test')}
        >
          <span style={{ fontSize: '1.2rem' }}>🧪</span>
          <span>Test Page</span>
        </button>

        <button
          onClick={() => handleNavigation('/trading')}
          style={navButtonStyle(location.pathname === '/trading')}
        >
          <span style={{ fontSize: '1.2rem' }}>💱</span>
          <span>Trading</span>
        </button>

        <button
          onClick={() => handleNavigation('/history')}
          style={navButtonStyle(location.pathname === '/history')}
        >
          <span style={{ fontSize: '1.2rem' }}>📜</span>
          <span>History</span>
        </button>
      </nav>

      {/* User Section */}
      <div style={{
        padding: '16px',
        borderTop: '1px solid rgba(255, 255, 255, 0.1)'
      }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          marginBottom: '16px',
          padding: '12px',
          backgroundColor: 'rgba(255, 255, 255, 0.05)',
          borderRadius: '12px'
        }}>
          <div style={{
            width: '40px',
            height: '40px',
            background: 'linear-gradient(135deg, #8b5cf6, #6366f1)',
            borderRadius: '12px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '20px'
          }}>
            👤
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ color: 'white', fontSize: '0.9rem', fontWeight: '500' }}>
              {user?.username || 'Admin User'}
            </div>
            <div style={{ color: '#6b7280', fontSize: '0.8rem' }}>
              {user?.role || 'Administrator'}
            </div>
          </div>
        </div>

        <button
          onClick={handleLogout}
          style={{
            width: '100%',
            padding: '12px',
            backgroundColor: 'rgba(239, 68, 68, 0.1)',
            border: '1px solid rgba(239, 68, 68, 0.3)',
            borderRadius: '12px',
            color: '#ef4444',
            fontSize: '0.9rem',
            fontWeight: '500',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '8px'
          }}
        >
          <span>🚪</span>
          Logout
        </button>
      </div>
    </div>
  )
}

export default Sidebar
