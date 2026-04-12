import React from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'

function Sidebar() {
  const { logout, user } = useAuthStore()
  const navigate = useNavigate()

  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }

  const handleNavigation = (path) => {
    navigate(path)
  }

  const navItems = [
    { path: '/dashboard', label: 'Dashboard', icon: '📊' },
    { path: '/test', label: 'Test Button', icon: '🧪' },
    { path: '/trading', label: 'Trading', icon: '💱' },
    { path: '/portfolio', label: 'Portfolio', icon: '💼' },
    { path: '/orders', label: 'Orders', icon: '📋' },
    { path: '/settings', label: 'Settings', icon: '⚙️' }
  ]

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
        {navItems.map((item) => (
          <button
            key={item.path}
            onClick={() => handleNavigation(item.path)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              padding: '12px 16px',
              borderRadius: '12px',
              textDecoration: 'none',
              fontSize: '0.9rem',
              fontWeight: '500',
              marginBottom: '8px',
              transition: 'all 0.2s ease',
              backgroundColor: 'transparent',
              color: '#9ca3af',
              border: '1px solid transparent',
              cursor: 'pointer',
              width: '100%',
              textAlign: 'left'
            }}
            onMouseEnter={(e) => {
              e.target.style.backgroundColor = 'rgba(255, 255, 255, 0.05)'
              e.target.style.color = 'white'
              e.target.style.borderColor = 'rgba(255, 255, 255, 0.1)'
            }}
            onMouseLeave={(e) => {
              e.target.style.backgroundColor = 'transparent'
              e.target.style.color = '#9ca3af'
              e.target.style.borderColor = 'transparent'
            }}
            onMouseDown={(e) => {
              e.target.style.backgroundColor = 'rgba(59, 130, 246, 0.2)'
              e.target.style.color = '#3b82f6'
              e.target.style.borderColor = 'rgba(59, 130, 246, 0.3)'
            }}
            onMouseUp={(e) => {
              e.target.style.backgroundColor = 'rgba(59, 130, 246, 0.2)'
              e.target.style.color = '#3b82f6'
              e.target.style.borderColor = 'rgba(59, 130, 246, 0.3)'
            }}
          >
            <span style={{ fontSize: '1.2rem' }}>{item.icon}</span>
            <span>{item.label}</span>
          </button>
        ))}
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
            transition: 'all 0.2s ease',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '8px'
          }}
          onMouseEnter={(e) => {
            e.target.style.backgroundColor = 'rgba(239, 68, 68, 0.2)'
            e.target.style.transform = 'translateY(-2px)'
          }}
          onMouseLeave={(e) => {
            e.target.style.backgroundColor = 'rgba(239, 68, 68, 0.1)'
            e.target.style.transform = 'translateY(0)'
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
