import React, { useState } from 'react'
import { useAuthStore } from '../stores/authStore'

function Header({ user }) {
  const [currentTime, setCurrentTime] = useState(new Date())
  const [searchQuery, setSearchQuery] = useState('')

  React.useEffect(() => {
    const timer = setInterval(() => {
      setCurrentTime(new Date())
    }, 1000)

    return () => clearInterval(timer)
  }, [])

  const handleSearch = (e) => {
    e.preventDefault()
    console.log('Searching for:', searchQuery)
    // Add search functionality here
  }

  const handleNotificationClick = () => {
    console.log('Notifications clicked')
    // Add notification functionality here
  }

  return (
    <div style={{
      backgroundColor: 'rgba(15, 23, 42, 0.95)',
      backdropFilter: 'blur(16px)',
      borderBottom: '1px solid rgba(255, 255, 255, 0.1)',
      padding: '16px 24px',
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, sans-serif'
    }}>
      {/* Left Section - Time */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '16px'
      }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          padding: '8px 16px',
          backgroundColor: 'rgba(255, 255, 255, 0.05)',
          borderRadius: '12px',
          border: '1px solid rgba(255, 255, 255, 0.1)'
        }}>
          <span style={{ fontSize: '1.2rem' }}>🕐</span>
          <div>
            <div style={{ color: 'white', fontSize: '0.9rem', fontWeight: '500' }}>
              {currentTime.toLocaleTimeString()}
            </div>
            <div style={{ color: '#6b7280', fontSize: '0.8rem' }}>
              {currentTime.toLocaleDateString()}
            </div>
          </div>
        </div>

        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          padding: '8px 16px',
          backgroundColor: 'rgba(34, 197, 94, 0.1)',
          borderRadius: '12px',
          border: '1px solid rgba(34, 197, 94, 0.3)'
        }}>
          <div style={{
            width: '8px',
            height: '8px',
            backgroundColor: '#22c55e',
            borderRadius: '50%',
            animation: 'pulse 2s infinite'
          }}></div>
          <span style={{ color: '#22c55e', fontSize: '0.9rem', fontWeight: '500' }}>
            Market Open
          </span>
        </div>
      </div>

      {/* Center Section - Search */}
      <div style={{
        flex: 1,
        maxWidth: '400px',
        margin: '0 32px'
      }}>
        <form onSubmit={handleSearch} style={{
          position: 'relative',
          display: 'flex',
          alignItems: 'center'
        }}>
          <span style={{
            position: 'absolute',
            left: '16px',
            color: '#6b7280',
            fontSize: '1.1rem',
            pointerEvents: 'none'
          }}>
            🔍
          </span>
          <input
            type="text"
            placeholder="Search symbols, strategies..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{
              width: '100%',
              padding: '12px 16px 12px 48px',
              backgroundColor: 'rgba(255, 255, 255, 0.05)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              borderRadius: '12px',
              color: 'white',
              fontSize: '0.9rem',
              outline: 'none',
              transition: 'all 0.2s ease'
            }}
            onFocus={(e) => {
              e.target.style.borderColor = '#3b82f6'
              e.target.style.boxShadow = '0 0 0 3px rgba(59, 130, 246, 0.1)'
            }}
            onBlur={(e) => {
              e.target.style.borderColor = 'rgba(255, 255, 255, 0.1)'
              e.target.style.boxShadow = 'none'
            }}
          />
        </form>
      </div>

      {/* Right Section - User Info */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '16px'
      }}>
        {/* Notifications */}
        <button
          onClick={handleNotificationClick}
          style={{
            position: 'relative',
            cursor: 'pointer',
            padding: '8px',
            borderRadius: '12px',
            backgroundColor: 'transparent',
            border: 'none',
            transition: 'all 0.2s ease',
            fontSize: '1.3rem'
          }}
          onMouseEnter={(e) => {
            e.target.style.backgroundColor = 'rgba(255, 255, 255, 0.05)'
          }}
          onMouseLeave={(e) => {
            e.target.style.backgroundColor = 'transparent'
          }}
        >
          🔔
          <div style={{
            position: 'absolute',
            top: '4px',
            right: '4px',
            width: '8px',
            height: '8px',
            backgroundColor: '#ef4444',
            borderRadius: '50%'
          }}></div>
        </button>

        {/* User Info */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          padding: '8px 16px',
          backgroundColor: 'rgba(255, 255, 255, 0.05)',
          borderRadius: '12px',
          border: '1px solid rgba(255, 255, 255, 0.1)'
        }}>
          <div style={{
            width: '36px',
            height: '36px',
            background: 'linear-gradient(135deg, #8b5cf6, #6366f1)',
            borderRadius: '10px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '18px'
          }}>
            👤
          </div>
          <div>
            <div style={{ color: 'white', fontSize: '0.9rem', fontWeight: '500' }}>
              {user?.username || 'Admin'}
            </div>
            <div style={{ color: '#6b7280', fontSize: '0.8rem' }}>
              {user?.role || 'Administrator'}
            </div>
          </div>
        </div>
      </div>

      <style jsx>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
      `}</style>
    </div>
  )
}

export default Header
