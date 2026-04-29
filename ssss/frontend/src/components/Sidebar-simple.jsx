import React from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'

function navButtonStyle(active) {
  return {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    padding: '10px 12px',
    borderRadius: '10px',
    fontSize: '0.88rem',
    fontWeight: '500',
    marginBottom: '6px',
    backgroundColor: active ? 'rgba(37, 99, 235, 0.14)' : 'transparent',
    color: active ? '#1d4ed8' : '#475569',
    border: active ? '1px solid rgba(59, 130, 246, 0.35)' : '1px solid rgba(148, 163, 184, 0.24)',
    cursor: 'pointer',
    width: '100%',
    textAlign: 'left',
    transition: 'all 0.2s ease',
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
      width: '272px',
      backgroundColor: 'rgba(255, 255, 255, 0.95)',
      borderRight: '1px solid rgba(148, 163, 184, 0.25)',
      display: 'flex',
      flexDirection: 'column',
      fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, sans-serif'
    }}>
      <div style={{
        padding: '22px 18px',
        borderBottom: '1px solid rgba(148, 163, 184, 0.14)'
      }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '10px'
        }}>
          <div style={{
            width: '36px',
            height: '36px',
            background: 'linear-gradient(135deg, #2563eb, #1d4ed8)',
            borderRadius: '10px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '18px'
          }}>
            ⟐
          </div>
          <div>
            <h1 style={{
              fontSize: '1.0rem',
              fontWeight: '700',
              color: '#0f172a',
              margin: 0,
              lineHeight: 1.2,
            }}>
              Direkt
            </h1>
            <p style={{ fontSize: '0.76rem', color: '#64748b', margin: '2px 0 0' }}>
              Execution Console
            </p>
          </div>
        </div>
      </div>

      <nav style={{ flex: 1, padding: '12px' }}>
        <button
          onClick={() => handleNavigation('/dashboard')}
          style={navButtonStyle(location.pathname === '/dashboard')}
        >
          <span style={{ fontSize: '1rem' }}>◫</span>
          <span>Dashboard</span>
        </button>

        <button
          onClick={() => handleNavigation('/trading')}
          style={navButtonStyle(location.pathname === '/trading')}
        >
          <span style={{ fontSize: '1rem' }}>◉</span>
          <span>Trading</span>
        </button>

        <button
          onClick={() => handleNavigation('/history')}
          style={navButtonStyle(location.pathname === '/history')}
        >
          <span style={{ fontSize: '1rem' }}>☰</span>
          <span>History</span>
        </button>

      </nav>

      <div style={{
        padding: '14px 12px',
        borderTop: '1px solid rgba(148, 163, 184, 0.14)'
      }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          marginBottom: '12px',
          padding: '10px',
          backgroundColor: 'rgba(248, 250, 252, 0.95)',
          borderRadius: '10px',
          border: '1px solid rgba(148, 163, 184, 0.24)',
        }}>
          <div style={{
            width: '34px',
            height: '34px',
            background: 'linear-gradient(135deg, #dbeafe, #bfdbfe)',
            borderRadius: '9px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '15px'
          }}>
            U
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ color: '#0f172a', fontSize: '0.83rem', fontWeight: '600' }}>
              {user?.username || 'Admin User'}
            </div>
            <div style={{ color: '#64748b', fontSize: '0.74rem' }}>
              {user?.role || 'Operator'}
            </div>
          </div>
        </div>

        <button
          onClick={handleLogout}
          style={{
            width: '100%',
            padding: '10px',
            backgroundColor: 'rgba(239, 68, 68, 0.12)',
            border: '1px solid rgba(239, 68, 68, 0.45)',
            borderRadius: '10px',
            color: '#b91c1c',
            fontSize: '0.82rem',
            fontWeight: '700',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '8px',
            transition: 'all 0.2s ease',
          }}
        >
          <span>↪</span>
          Sign out
        </button>
      </div>
    </div>
  )
}

export default Sidebar
