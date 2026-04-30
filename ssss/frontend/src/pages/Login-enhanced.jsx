import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'

function Login() {
  const [authMode, setAuthMode] = useState('login')
  const [credentials, setCredentials] = useState({
    username: '',
    password: '',
    balanceAmount: 100000,
  })
  const [isLoading, setIsLoading] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const [authMessage, setAuthMessage] = useState('')
  const [authError, setAuthError] = useState('')
  
  const navigate = useNavigate()
  const { login, register } = useAuthStore()

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (authMode !== 'login') return
    setIsLoading(true)
    setAuthError('')
    setAuthMessage('')
    
    const result = await login({
      username: credentials.username,
      password: credentials.password,
      tradingStrategy: credentials.tradingStrategy
    })
    
    if (result.success) {
      navigate('/dashboard')
    } else {
      setAuthError(result.error || 'Login failed')
    }
    
    setIsLoading(false)
  }

  const handleRegister = async () => {
    setIsLoading(true)
    setAuthError('')
    setAuthMessage('')
    const result = await register({
      username: credentials.username,
      password: credentials.password,
      balanceAmount: credentials.balanceAmount,
    })
    if (result.success) {
      setAuthMessage('Registration successful. Please log in now.')
      setAuthMode('login')
    } else {
      setAuthError(result.error || 'Registration failed')
    }
    setIsLoading(false)
  }

  const handleChange = (e) => {
    const { name, value } = e.target
    setCredentials(prev => ({
      ...prev,
      [name]: name === 'balanceAmount' ? parseFloat(value) || 0 : value
    }))
  }

  return (
    <div style={{
      minHeight: '100vh',
      background: 'radial-gradient(circle at 20% 10%, #0f2b5f 0%, rgba(15, 23, 42, 0.98) 35%), radial-gradient(circle at 80% 100%, #072334 0%, #061a2b 45%, #051420 100%)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '24px',
      position: 'relative',
      overflow: 'hidden',
      fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, sans-serif'
    }}>
      <div style={{
        maxWidth: '420px',
        width: '100%',
        position: 'relative',
        zIndex: '2'
      }}>
        <div style={{ textAlign: 'center', marginBottom: '20px' }}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: '46px',
            height: '46px',
            background: 'linear-gradient(135deg, #0ea5e9, #2563eb)',
            borderRadius: '12px',
            margin: '0 auto 14px',
            boxShadow: '0 10px 24px rgba(14,165,233,0.35)'
          }}>
            <div style={{ width: '20px', height: '3px', backgroundColor: '#e0f2fe', borderRadius: '8px' }} />
          </div>
          <h1 style={{
            fontSize: '2rem',
            fontWeight: '700',
            color: '#f8fafc',
            marginBottom: '6px'
          }}>
            MCX Trading Platform
          </h1>
          <p style={{ fontSize: '0.9rem', color: '#94a3b8' }}>
            Institutional-style paper desk for Silver allocation.
          </p>
        </div>

        <div style={{
          backgroundColor: 'rgba(8, 25, 42, 0.72)',
          backdropFilter: 'blur(12px)',
          border: '1px solid rgba(148, 163, 184, 0.24)',
          borderRadius: '16px',
          padding: '18px',
          boxShadow: '0 18px 44px rgba(2, 6, 23, 0.4)'
        }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginBottom: '14px' }}>
            <button
              type="button"
              onClick={() => { setAuthMode('login'); setAuthError(''); setAuthMessage('') }}
              style={{
                flex: 1,
                padding: '10px 12px',
                borderRadius: '9px',
                border: authMode === 'login' ? '1px solid rgba(34,197,189,0.7)' : '1px solid rgba(71,85,105,0.5)',
                background: authMode === 'login' ? 'rgba(20,184,166,0.15)' : 'rgba(15,23,42,0.55)',
                color: '#e2e8f0',
                cursor: 'pointer',
                fontWeight: 600
              }}
            >
              Login
            </button>
            <button
              type="button"
              onClick={() => { setAuthMode('signup'); setAuthError(''); setAuthMessage('') }}
              style={{
                flex: 1,
                padding: '10px 12px',
                borderRadius: '9px',
                border: authMode === 'signup' ? '1px solid rgba(34,197,189,0.7)' : '1px solid rgba(71,85,105,0.5)',
                background: authMode === 'signup' ? 'rgba(20,184,166,0.15)' : 'rgba(15,23,42,0.55)',
                color: '#e2e8f0',
                cursor: 'pointer',
                fontWeight: 600
              }}
            >
              Sign Up
            </button>
          </div>
          <form onSubmit={handleSubmit}>
            <div style={{ marginBottom: '14px' }}>
              <label style={{
                display: 'block',
                fontSize: '0.82rem',
                fontWeight: '500',
                color: '#cbd5e1',
                marginBottom: '6px'
              }}>
                Username
              </label>
              <input
                type="text"
                name="username"
                value={credentials.username}
                onChange={handleChange}
                placeholder="Enter your username"
                required
                style={{
                  width: '100%',
                  backgroundColor: 'rgba(2, 6, 23, 0.58)',
                  border: '1px solid rgba(71, 85, 105, 0.6)',
                  borderRadius: '10px',
                  padding: '12px',
                  color: '#f8fafc',
                  fontSize: '0.92rem',
                  outline: 'none'
                }}
              />
            </div>

            <div style={{ marginBottom: '14px' }}>
              <label style={{
                display: 'block',
                fontSize: '0.82rem',
                fontWeight: '500',
                color: '#cbd5e1',
                marginBottom: '6px'
              }}>
                Password
              </label>
              <div style={{ position: 'relative' }}>
                <input
                  type={showPassword ? "text" : "password"}
                  name="password"
                  value={credentials.password}
                  onChange={handleChange}
                  placeholder="Enter your password"
                  required
                  style={{
                    width: '100%',
                    backgroundColor: 'rgba(2, 6, 23, 0.58)',
                    border: '1px solid rgba(71, 85, 105, 0.6)',
                    borderRadius: '10px',
                    padding: '12px 54px 12px 12px',
                    color: '#f8fafc',
                    fontSize: '0.92rem',
                    outline: 'none'
                  }}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  style={{
                    position: 'absolute',
                    right: '16px',
                    top: '50%',
                    transform: 'translateY(-50%)',
                    background: 'none',
                    border: 'none',
                    color: '#22d3ee',
                    cursor: 'pointer',
                    fontSize: '0.78rem',
                    fontWeight: 700
                  }}
                >
                  {showPassword ? 'HIDE' : 'SHOW'}
                </button>
              </div>
            </div>

            {authMode === 'signup' && (
            <div style={{ marginBottom: '14px' }}>
              <label style={{
                display: 'block',
                fontSize: '0.82rem',
                fontWeight: '500',
                color: '#cbd5e1',
                marginBottom: '6px'
              }}>
                Trading Balance (₹)
              </label>
              <input
                type="number"
                name="balanceAmount"
                value={credentials.balanceAmount}
                onChange={handleChange}
                placeholder="Enter your trading balance"
                min="10000"
                max="10000000"
                step="1000"
                required
                style={{
                  width: '100%',
                  backgroundColor: 'rgba(2, 6, 23, 0.58)',
                  border: '1px solid rgba(71, 85, 105, 0.6)',
                  borderRadius: '10px',
                  padding: '12px',
                  color: '#f8fafc',
                  fontSize: '0.92rem',
                  outline: 'none'
                }}
              />
              <div style={{
                marginTop: '6px',
                fontSize: '0.75rem',
                color: '#94a3b8'
              }}>
                Min: ₹10,000 | Max: ₹1,00,00,000
              </div>
            </div>
            )}

            <button
              type={authMode === 'login' ? 'submit' : 'button'}
              onClick={authMode === 'signup' ? handleRegister : undefined}
              disabled={isLoading}
              style={{
                width: '100%',
                background: 'linear-gradient(135deg, #14b8a6, #06b6d4)',
                color: '#ecfeff',
                border: 'none',
                padding: '12px 20px',
                borderRadius: '10px',
                fontSize: '0.95rem',
                fontWeight: '600',
                cursor: isLoading ? 'not-allowed' : 'pointer',
                opacity: isLoading ? 0.7 : 1,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}
            >
              {isLoading ? (
                <>
                  <div style={{
                    width: '20px',
                    height: '20px',
                    border: '2px solid rgba(255, 255, 255, 0.3)',
                    borderTop: '2px solid white',
                    borderRadius: '50%',
                    animation: 'spin 1s linear infinite'
                  }}></div>
                  Processing
                </>
              ) : (
                <>{authMode === 'login' ? 'Log In' : 'Create Account'}</>
              )}
            </button>
            {authError ? (
              <div style={{ marginTop: '10px', fontSize: '0.85rem', color: '#fca5a5' }}>
                {authError}
              </div>
            ) : null}
            {authMessage ? (
              <div style={{ marginTop: '10px', fontSize: '0.85rem', color: '#86efac' }}>
                {authMessage}
              </div>
            ) : null}
          </form>
        </div>
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

export default Login
