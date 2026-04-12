import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'

function Login() {
  const [credentials, setCredentials] = useState({
    username: '',
    password: '',
    balanceAmount: 100000,
  })
  const [isLoading, setIsLoading] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  
  const navigate = useNavigate()
  const { login } = useAuthStore()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setIsLoading(true)
    
    // Store user data in localStorage for later use
    localStorage.setItem('userBalance', credentials.balanceAmount)
    localStorage.setItem('tradingStrategy', credentials.tradingStrategy)
    
    const result = await login({
      username: credentials.username,
      password: credentials.password,
      balanceAmount: credentials.balanceAmount,
      tradingStrategy: credentials.tradingStrategy
    })
    
    if (result.success) {
      navigate('/dashboard')
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

  const calculateLotSize = () => {
    const silverPrice = 65000 // Current MCX Silver price
    const lotSize = 30 // MCX Silver lot size in kg
    const marginPerLot = silverPrice * lotSize * 0.12 // 12% margin
    const maxLots = Math.floor(credentials.balanceAmount / marginPerLot)
    
    return {
      maxLots: Math.min(maxLots, 5), // Max 5 lots for risk management
      marginPerLot: marginPerLot,
      totalMargin: maxLots * marginPerLot,
      recommendedLots: Math.min(Math.floor(maxLots * 0.6), 3) // 60% of max, max 3 lots
    }
  }

  const lotInfo = calculateLotSize()

  return (
    <div style={{
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '20px',
      position: 'relative',
      overflow: 'hidden',
      fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, sans-serif'
    }}>
      {/* Background decoration */}
      <div style={{
        position: 'absolute',
        top: '0',
        left: '0',
        right: '0',
        bottom: '0',
        background: 'linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, transparent 50%, rgba(168, 85, 247, 0.1) 100%)'
      }}></div>
      <div style={{
        position: 'absolute',
        top: '80px',
        left: '80px',
        width: '288px',
        height: '288px',
        background: 'rgba(59, 130, 246, 0.1)',
        borderRadius: '50%',
        filter: 'blur(96px)'
      }}></div>
      <div style={{
        position: 'absolute',
        bottom: '80px',
        right: '80px',
        width: '288px',
        height: '288px',
        background: 'rgba(168, 85, 247, 0.1)',
        borderRadius: '50%',
        filter: 'blur(96px)'
      }}></div>
      
      <div style={{
        maxWidth: '600px',
        width: '100%',
        position: 'relative',
        zIndex: '10'
      }}>
        {/* Logo Section */}
        <div style={{ textAlign: 'center', marginBottom: '32px' }}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: '80px',
            height: '80px',
            background: 'linear-gradient(135deg, #3b82f6, #2563eb)',
            borderRadius: '16px',
            margin: '0 auto 24px',
            boxShadow: '0 25px 50px -12px rgba(59, 130, 246, 0.25)'
          }}>
            <span style={{ fontSize: '40px' }}>📈</span>
          </div>
          <h1 style={{
            fontSize: '2.5rem',
            fontWeight: 'bold',
            color: 'white',
            marginBottom: '8px',
            letterSpacing: '-0.025em'
          }}>
            MCX Trading Platform
          </h1>
          <p style={{ fontSize: '1.1rem', color: '#94a3b8' }}>
            Paper trading — balance sets Silver / Mini / Micro; choose ML or LLM on Trading
          </p>
        </div>

        {/* Login Form */}
        <div style={{
          backgroundColor: 'rgba(255, 255, 255, 0.05)',
          backdropFilter: 'blur(16px)',
          border: '1px solid rgba(255, 255, 255, 0.1)',
          borderRadius: '20px',
          padding: '32px',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)'
        }}>
          <form onSubmit={handleSubmit}>
            {/* Traditional Login Fields */}
            <div style={{ marginBottom: '24px' }}>
              <label style={{
                display: 'block',
                fontSize: '0.9rem',
                fontWeight: '500',
                color: '#e5e7eb',
                marginBottom: '8px'
              }}>
                Username
              </label>
              <div style={{ position: 'relative' }}>
                <span style={{
                  position: 'absolute',
                  left: '16px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  color: '#6b7280',
                  fontSize: '20px'
                }}>👤</span>
                <input
                  type="text"
                  name="username"
                  value={credentials.username}
                  onChange={handleChange}
                  placeholder="Enter your username"
                  required
                  style={{
                    width: '100%',
                    backgroundColor: 'rgba(31, 41, 55, 0.5)',
                    border: '1px solid rgba(75, 85, 99, 0.5)',
                    borderRadius: '12px',
                    padding: '16px 16px 16px 48px',
                    color: 'white',
                    fontSize: '1rem',
                    transition: 'all 0.2s ease',
                    outline: 'none'
                  }}
                  onFocus={(e) => {
                    e.target.style.borderColor = '#3b82f6'
                    e.target.style.boxShadow = '0 0 0 3px rgba(59, 130, 246, 0.1)'
                  }}
                  onBlur={(e) => {
                    e.target.style.borderColor = 'rgba(75, 85, 99, 0.5)'
                    e.target.style.boxShadow = 'none'
                  }}
                />
              </div>
            </div>

            <div style={{ marginBottom: '24px' }}>
              <label style={{
                display: 'block',
                fontSize: '0.9rem',
                fontWeight: '500',
                color: '#e5e7eb',
                marginBottom: '8px'
              }}>
                Password
              </label>
              <div style={{ position: 'relative' }}>
                <span style={{
                  position: 'absolute',
                  left: '16px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  color: '#6b7280',
                  fontSize: '20px'
                }}>🔒</span>
                <input
                  type={showPassword ? "text" : "password"}
                  name="password"
                  value={credentials.password}
                  onChange={handleChange}
                  placeholder="Enter your password"
                  required
                  style={{
                    width: '100%',
                    backgroundColor: 'rgba(31, 41, 55, 0.5)',
                    border: '1px solid rgba(75, 85, 99, 0.5)',
                    borderRadius: '12px',
                    padding: '16px 48px 16px 48px',
                    color: 'white',
                    fontSize: '1rem',
                    transition: 'all 0.2s ease',
                    outline: 'none'
                  }}
                  onFocus={(e) => {
                    e.target.style.borderColor = '#3b82f6'
                    e.target.style.boxShadow = '0 0 0 3px rgba(59, 130, 246, 0.1)'
                  }}
                  onBlur={(e) => {
                    e.target.style.borderColor = 'rgba(75, 85, 99, 0.5)'
                    e.target.style.boxShadow = 'none'
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
                    color: '#6b7280',
                    cursor: 'pointer',
                    fontSize: '20px'
                  }}
                >
                  {showPassword ? '👁️' : '👁️‍🗨️'}
                </button>
              </div>
            </div>

            {/* Balance Amount */}
            <div style={{ marginBottom: '24px' }}>
              <label style={{
                display: 'block',
                fontSize: '0.9rem',
                fontWeight: '500',
                color: '#e5e7eb',
                marginBottom: '8px'
              }}>
                Trading Balance (₹)
              </label>
              <div style={{ position: 'relative' }}>
                <span style={{
                  position: 'absolute',
                  left: '16px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  color: '#6b7280',
                  fontSize: '20px'
                }}>💰</span>
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
                    backgroundColor: 'rgba(31, 41, 55, 0.5)',
                    border: '1px solid rgba(75, 85, 99, 0.5)',
                    borderRadius: '12px',
                    padding: '16px 16px 16px 48px',
                    color: 'white',
                    fontSize: '1rem',
                    transition: 'all 0.2s ease',
                    outline: 'none'
                  }}
                  onFocus={(e) => {
                    e.target.style.borderColor = '#3b82f6'
                    e.target.style.boxShadow = '0 0 0 3px rgba(59, 130, 246, 0.1)'
                  }}
                  onBlur={(e) => {
                    e.target.style.borderColor = 'rgba(75, 85, 99, 0.5)'
                    e.target.style.boxShadow = 'none'
                  }}
                />
              </div>
              <div style={{
                marginTop: '8px',
                fontSize: '0.8rem',
                color: '#6b7280'
              }}>
                Min: ₹10,000 | Max: ₹1,00,00,000
              </div>
            </div>

            {/* Lot Calculation Preview */}
            <div style={{
              padding: '16px',
              backgroundColor: 'rgba(34, 197, 94, 0.1)',
              border: '1px solid rgba(34, 197, 94, 0.3)',
              borderRadius: '12px',
              marginBottom: '24px'
            }}>
              <h3 style={{
                fontSize: '1rem',
                fontWeight: '500',
                color: '#22c55e',
                marginBottom: '12px',
                textAlign: 'center'
              }}>
                📊 Lot Allocation Preview
              </h3>
              <div style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gap: '12px',
                fontSize: '0.9rem'
              }}>
                <div>
                  <div style={{ color: '#6b7280', marginBottom: '4px' }}>Max Lots:</div>
                  <div style={{ color: 'white', fontSize: '1.1rem', fontWeight: 'bold' }}>
                    {lotInfo.maxLots} lots
                  </div>
                </div>
                <div>
                  <div style={{ color: '#6b7280', marginBottom: '4px' }}>Recommended:</div>
                  <div style={{ color: 'white', fontSize: '1.1rem', fontWeight: 'bold' }}>
                    {lotInfo.recommendedLots} lots
                  </div>
                </div>
              </div>
              <div style={{
                marginTop: '8px',
                fontSize: '0.8rem',
                color: '#6b7280',
                textAlign: 'center'
              }}>
                Based on ₹{credentials.balanceAmount.toLocaleString()} balance at ₹65,000/kg with 12% margin
              </div>
            </div>

            <button
              type="submit"
              disabled={isLoading}
              style={{
                width: '100%',
                background: 'linear-gradient(135deg, #3b82f6, #2563eb)',
                color: 'white',
                border: 'none',
                padding: '16px 24px',
                borderRadius: '12px',
                fontSize: '1rem',
                fontWeight: '500',
                cursor: isLoading ? 'not-allowed' : 'pointer',
                boxShadow: '0 10px 25px -5px rgba(59, 130, 246, 0.25)',
                transition: 'all 0.2s ease',
                opacity: isLoading ? 0.7 : 1,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '8px'
              }}
              onMouseOver={(e) => {
                if (!isLoading) {
                  e.target.style.background = 'linear-gradient(135deg, #2563eb, #1d4ed8)'
                  e.target.style.transform = 'translateY(-2px)'
                  e.target.style.boxShadow = '0 20px 25px -5px rgba(59, 130, 246, 0.35)'
                }
              }}
              onMouseOut={(e) => {
                if (!isLoading) {
                  e.target.style.background = 'linear-gradient(135deg, #3b82f6, #2563eb)'
                  e.target.style.transform = 'translateY(0)'
                  e.target.style.boxShadow = '0 10px 25px -5px rgba(59, 130, 246, 0.25)'
                }
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
                  Initializing Trading System...
                </>
              ) : (
                <>
                  <span>🚀</span>
                  Log in and load allocation
                </>
              )}
            </button>
          </form>
        </div>

        {/* Demo Credentials */}
        <div style={{
          marginTop: '24px',
          padding: '20px',
          background: 'linear-gradient(135deg, rgba(34, 197, 94, 0.1), rgba(16, 185, 129, 0.1))',
          border: '1px solid rgba(34, 197, 94, 0.3)',
          borderRadius: '16px',
          backdropFilter: 'blur(16px)'
        }}>
          <h3 style={{
            fontSize: '1rem',
            fontWeight: '500',
            color: '#22c55e',
            marginBottom: '12px',
            textAlign: 'center'
          }}>
            🎯 Demo Credentials
          </h3>
          <div style={{ fontSize: '0.9rem', color: '#94a3b8', lineHeight: '1.5' }}>
            <div style={{ marginBottom: '8px' }}>
              <strong style={{ color: '#e5e7eb' }}>Username:</strong> admin
            </div>
            <div style={{ marginBottom: '8px' }}>
              <strong style={{ color: '#e5e7eb' }}>Password:</strong> admin123
            </div>
            <div style={{ marginTop: '12px', fontSize: '0.8rem', color: '#6b7280' }}>
              💡 After login, open Trading to pick ML or LLM and start the paper bot
            </div>
          </div>
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
