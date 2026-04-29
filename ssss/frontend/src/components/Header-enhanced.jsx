import React, { useState } from 'react'
import { useAuthStore } from '../stores/authStore'

const INTEGRATION_BASE = import.meta.env.VITE_INTEGRATION_URL || 'http://localhost:8001'

function Header({ user }) {
  const [currentTime, setCurrentTime] = useState(new Date())
  const [marketOpen, setMarketOpen] = useState(false)

  React.useEffect(() => {
    const timer = setInterval(() => {
      setCurrentTime(new Date())
    }, 1000)

    return () => clearInterval(timer)
  }, [])

  React.useEffect(() => {
    let mounted = true
    const syncMarketStatus = async () => {
      try {
        const res = await fetch(`${INTEGRATION_BASE}/api/market/status`)
        const json = await res.json().catch(() => ({}))
        if (!mounted) return
        setMarketOpen(Boolean(json?.data?.market_open))
      } catch (_) {
        if (!mounted) return
        setMarketOpen(false)
      }
    }
    syncMarketStatus()
    const timer = setInterval(syncMarketStatus, 15000)
    return () => {
      mounted = false
      clearInterval(timer)
    }
  }, [])

  return (
    <div style={{
      backgroundColor: 'rgba(255, 255, 255, 0.94)',
      borderBottom: '1px solid rgba(148, 163, 184, 0.25)',
      padding: '12px 20px',
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      gap: '16px',
      fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, sans-serif'
    }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '10px'
      }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          padding: '8px 10px',
          backgroundColor: 'rgba(248, 250, 252, 0.95)',
          borderRadius: '10px',
          border: '1px solid rgba(148, 163, 184, 0.12)'
        }}>
          <span style={{ fontSize: '0.85rem', color: '#64748b' }}>UTC</span>
          <div>
            <div style={{ color: '#0f172a', fontSize: '0.83rem', fontWeight: '600' }}>
              {currentTime.toLocaleTimeString('en-IN', { hour12: false })}
            </div>
            <div style={{ color: '#64748b', fontSize: '0.72rem' }}>
              {currentTime.toLocaleDateString('en-IN')}
            </div>
          </div>
        </div>

        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '7px',
          padding: '7px 10px',
          backgroundColor: marketOpen ? 'rgba(16, 185, 129, 0.12)' : 'rgba(239, 68, 68, 0.12)',
          borderRadius: '10px',
          border: marketOpen ? '1px solid rgba(16, 185, 129, 0.28)' : '1px solid rgba(239, 68, 68, 0.32)'
        }}>
          <div style={{
            width: '7px',
            height: '7px',
            backgroundColor: marketOpen ? '#34d399' : '#ef4444',
            borderRadius: '50%',
            animation: 'pulse 2s infinite'
          }}></div>
          <span style={{ color: marketOpen ? '#34d399' : '#fca5a5', fontSize: '0.78rem', fontWeight: '600' }}>
            {marketOpen ? 'MARKET OPEN' : 'MARKET CLOSED'}
          </span>
        </div>
      </div>

      <div style={{
        flex: 1
      }}>
        <div style={{ color: '#475569', fontSize: '0.8rem' }}>
          Real-time commodity execution dashboard
        </div>
      </div>

      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '10px'
      }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          padding: '7px 10px',
          backgroundColor: 'rgba(248, 250, 252, 0.95)',
          borderRadius: '10px',
          border: '1px solid rgba(148, 163, 184, 0.12)'
        }}>
          <div style={{
            width: '30px',
            height: '30px',
            background: 'linear-gradient(135deg, #dbeafe, #bfdbfe)',
            borderRadius: '8px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '13px',
            color: '#1e3a8a',
            fontWeight: 700,
          }}>
            U
          </div>
          <div>
            <div style={{ color: '#0f172a', fontSize: '0.8rem', fontWeight: '600' }}>
              {user?.username || 'Admin'}
            </div>
            <div style={{ color: '#64748b', fontSize: '0.7rem' }}>
              {user?.role || 'Operator'}
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
