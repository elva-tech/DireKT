import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'

const Login = () => {
  const [isRegister, setIsRegister] = useState(false)
  const [credentials, setCredentials] = useState({
    username: '',
    password: '',
    confirmPassword: '',
    balanceAmount: 100000,
  })
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(null)
  const [showPassword, setShowPassword] = useState(false)
  const [backendStatus, setBackendStatus] = useState('checking') // 'checking', 'online', 'offline'
  
  const navigate = useNavigate()
  const { login, register } = useAuthStore()

  // Background animation state
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 })
  
  useEffect(() => {
    const handleMouseMove = (e) => {
      setMousePos({
        x: (e.clientX / window.innerWidth - 0.5) * 20,
        y: (e.clientY / window.innerHeight - 0.5) * 20,
      })
    }
    window.addEventListener('mousemove', handleMouseMove)
    return () => window.removeEventListener('mousemove', handleMouseMove)
  }, [])

  // Check backend health
  useEffect(() => {
    const checkHealth = async () => {
      try {
        // We use the same API_URL logic as the store
        const API_URL = import.meta.env.VITE_API_URL || 
                        'https://direkt-backend-koop.onrender.com' || 
                        'https://direkt-backend.onrender.com' ||
                        'http://localhost:8000';
        
        const response = await fetch(`${API_URL}/api/v1/ping`);
        if (response.ok) {
          setBackendStatus('online');
        } else {
          setBackendStatus('offline');
        }
      } catch (e) {
        setBackendStatus('offline');
      }
    };
    checkHealth();
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault()
    setIsLoading(true)
    setError(null)
    setSuccess(null)

    if (isRegister) {
      if (credentials.password !== credentials.confirmPassword) {
        setError("Passwords do not match");
        setIsLoading(false)
        return;
      }
      
      const res = await register({
        username: credentials.username,
        password: credentials.password,
        balance: parseFloat(credentials.balanceAmount) || 100000
      });
      
      if (res.success) {
        // Auto-login after successful registration
        const loginRes = await login({
          username: credentials.username,
          password: credentials.password,
          balanceAmount: parseFloat(credentials.balanceAmount) || 100000
        });
        
        if (loginRes.success) {
          navigate('/dashboard');
        } else {
          setError("Account created, but auto-login failed. Please sign in manually.");
          setIsRegister(false);
          setCredentials(prev => ({ ...prev, password: '', confirmPassword: '' }));
        }
      } else {
        setError(res.error || "Registration failed");
      }
    } else {
      const res = await login({
        username: credentials.username,
        password: credentials.password,
        balanceAmount: credentials.balanceAmount
      })
      
      if (res.success) {
        navigate('/dashboard')
      } else {
        setError(res.error)
      }
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

  const styles = {
    container: {
      minHeight: '100vh',
      width: '100%',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      position: 'relative',
      background: '#0f172a',
      color: '#f8fafc',
      fontFamily: "'Inter', sans-serif",
      overflow: 'hidden',
      padding: '20px',
    },
    backgroundGlow: {
      position: 'absolute',
      width: '60vw',
      height: '60vw',
      borderRadius: '50%',
      background: 'radial-gradient(circle, rgba(59, 130, 246, 0.15) 0%, transparent 70%)',
      top: '50%',
      left: '50%',
      transform: `translate(calc(-50% + ${mousePos.x}px), calc(-50% + ${mousePos.y}px))`,
      zIndex: 0,
      filter: 'blur(80px)',
      pointerEvents: 'none',
    },
    accentGlow: {
      position: 'absolute',
      width: '40vw',
      height: '40vw',
      borderRadius: '50%',
      background: 'radial-gradient(circle, rgba(168, 85, 247, 0.1) 0%, transparent 70%)',
      top: '20%',
      right: '10%',
      transform: `translate(${mousePos.x * -0.5}px, ${mousePos.y * -0.5}px)`,
      zIndex: 0,
      filter: 'blur(60px)',
      pointerEvents: 'none',
    },
    card: {
      width: '100%',
      maxWidth: '480px',
      background: 'rgba(30, 41, 59, 0.7)',
      backdropFilter: 'blur(20px)',
      WebkitBackdropFilter: 'blur(20px)',
      border: '1px solid rgba(255, 255, 255, 0.1)',
      borderRadius: '24px',
      padding: '40px',
      boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)',
      position: 'relative',
      zIndex: 10,
      transition: 'transform 0.3s ease, box-shadow 0.3s ease',
    },
    header: {
      textAlign: 'center',
      marginBottom: '32px',
    },
    logo: {
      width: '64px',
      height: '64px',
      background: 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)',
      borderRadius: '16px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      fontSize: '32px',
      margin: '0 auto 20px',
      boxShadow: '0 10px 20px rgba(59, 130, 246, 0.3)',
    },
    title: {
      fontSize: '28px',
      fontWeight: '700',
      marginBottom: '8px',
      letterSpacing: '-0.5px',
    },
    subtitle: {
      fontSize: '15px',
      color: '#94a3b8',
    },
    form: {
      display: 'flex',
      flexDirection: 'column',
      gap: '20px',
    },
    inputGroup: {
      display: 'flex',
      flexDirection: 'column',
      gap: '8px',
    },
    label: {
      fontSize: '14px',
      fontWeight: '500',
      color: '#cbd5e1',
      marginLeft: '4px',
    },
    inputWrapper: {
      position: 'relative',
    },
    icon: {
      position: 'absolute',
      left: '16px',
      top: '50%',
      transform: 'translateY(-50%)',
      color: '#64748b',
      fontSize: '18px',
    },
    input: {
      width: '100%',
      background: 'rgba(15, 23, 42, 0.4)',
      border: '1px solid rgba(255, 255, 255, 0.1)',
      borderRadius: '12px',
      padding: '14px 16px 14px 48px',
      color: 'white',
      fontSize: '16px',
      outline: 'none',
      transition: 'all 0.2s ease',
    },
    button: {
      width: '100%',
      background: 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)',
      color: 'white',
      border: 'none',
      borderRadius: '12px',
      padding: '16px',
      fontSize: '16px',
      fontWeight: '600',
      cursor: 'pointer',
      transition: 'all 0.2s ease',
      marginTop: '10px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      gap: '10px',
      boxShadow: '0 10px 15px -3px rgba(59, 130, 246, 0.3)',
    },
    toggleText: {
      textAlign: 'center',
      marginTop: '24px',
      fontSize: '14px',
      color: '#94a3b8',
    },
    toggleLink: {
      color: '#3b82f6',
      fontWeight: '600',
      cursor: 'pointer',
      textDecoration: 'none',
      marginLeft: '5px',
    },
    errorMsg: {
      padding: '12px',
      background: 'rgba(239, 68, 68, 0.1)',
      border: '1px solid rgba(239, 68, 68, 0.2)',
      borderRadius: '10px',
      color: '#f87171',
      fontSize: '14px',
      textAlign: 'center',
    },
    successMsg: {
      padding: '12px',
      background: 'rgba(34, 197, 94, 0.1)',
      border: '1px solid rgba(34, 197, 94, 0.2)',
      borderRadius: '10px',
      color: '#4ade80',
      fontSize: '14px',
      textAlign: 'center',
    },
    spinner: {
      width: '20px',
      height: '20px',
      border: '3px solid rgba(255,255,255,0.3)',
      borderTop: '3px solid white',
      borderRadius: '50%',
      animation: 'spin 0.8s linear infinite',
    }
  }

  return (
    <div style={styles.container}>
      <style>{`
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        input:focus { border-color: #3b82f6 !important; box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.1); background: rgba(15, 23, 42, 0.6) !important; }
        .btn:hover { transform: translateY(-2px); box-shadow: 0 20px 25px -5px rgba(59, 130, 246, 0.4); opacity: 0.95; }
        .btn:active { transform: translateY(0); }
      `}</style>
      
      <div style={styles.backgroundGlow} />
      <div style={styles.accentGlow} />

      {/* Connection Indicator */}
      <div style={{
        position: 'fixed',
        bottom: '20px',
        right: '20px',
        padding: '8px 12px',
        background: 'rgba(15, 23, 42, 0.8)',
        borderRadius: '20px',
        border: '1px solid rgba(255, 255, 255, 0.1)',
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        fontSize: '12px',
        color: '#94a3b8',
        zIndex: 1000,
        backdropFilter: 'blur(8px)',
      }}>
        <div style={{
          width: '8px',
          height: '8px',
          borderRadius: '50%',
          background: backendStatus === 'online' ? '#22c55e' : backendStatus === 'offline' ? '#ef4444' : '#f59e0b',
          boxShadow: `0 0 10px ${backendStatus === 'online' ? '#22c55e' : backendStatus === 'offline' ? '#ef4444' : '#f59e0b'}`,
        }} />
        Server: {backendStatus === 'online' ? 'Connected' : backendStatus === 'offline' ? 'Disconnected' : 'Checking...'}
      </div>

      <div style={styles.card}>
        <div style={styles.header}>
          <div style={styles.logo}>📈</div>
          <h1 style={styles.title}>{isRegister ? 'Join DireKT' : 'Welcome Back'}</h1>
          <p style={styles.subtitle}>
            {isRegister ? 'Create your professional trading account' : 'Access your advanced trading terminal'}
          </p>
        </div>

        {error && <div style={styles.errorMsg}>{error}</div>}
        {success && <div style={styles.successMsg}>{success}</div>}

        <form style={styles.form} onSubmit={handleSubmit}>
          <div style={styles.inputGroup}>
            <label style={styles.label}>Username</label>
            <div style={styles.inputWrapper}>
              <span style={styles.icon}>👤</span>
              <input 
                style={styles.input}
                type="text"
                name="username"
                placeholder="Enter username"
                required
                value={credentials.username}
                onChange={handleChange}
              />
            </div>
          </div>

          <div style={styles.inputGroup}>
            <label style={styles.label}>Password</label>
            <div style={styles.inputWrapper}>
              <span style={styles.icon}>🔒</span>
              <input 
                style={styles.input}
                type={showPassword ? "text" : "password"}
                name="password"
                placeholder="••••••••"
                required
                value={credentials.password}
                onChange={handleChange}
              />
              <span 
                style={{...styles.icon, left: 'auto', right: '16px', cursor: 'pointer'}}
                onClick={() => setShowPassword(!showPassword)}
              >
                {showPassword ? '👁️' : '👁️‍🗨️'}
              </span>
            </div>
          </div>

          {isRegister && (
            <div style={styles.inputGroup}>
              <label style={styles.label}>Confirm Password</label>
              <div style={styles.inputWrapper}>
                <span style={styles.icon}>🛡️</span>
                <input 
                  style={styles.input}
                  type={showPassword ? "text" : "password"}
                  name="confirmPassword"
                  placeholder="••••••••"
                  required
                  value={credentials.confirmPassword}
                  onChange={handleChange}
                />
              </div>
            </div>
          )}

          {isRegister && (
            <div style={styles.inputGroup}>
              <label style={styles.label}>Initial Balance for Paper Trading (₹)</label>
              <div style={styles.inputWrapper}>
                <span style={styles.icon}>💰</span>
                <input 
                  style={styles.input}
                  type="number"
                  name="balanceAmount"
                  value={credentials.balanceAmount}
                  onChange={handleChange}
                  min="10000"
                />
              </div>
            </div>
          )}

          <button className="btn" style={styles.button} disabled={isLoading}>
            {isLoading ? <div style={styles.spinner} /> : (isRegister ? 'Create Account' : 'Sign In')}
            {!isLoading && <span style={{marginLeft: '4px'}}>→</span>}
          </button>
        </form>

        <div style={styles.toggleText}>
          {isRegister ? 'Already have an account?' : "Don't have an account?"}
          <span 
            style={styles.toggleLink} 
            onClick={() => {
              setIsRegister(!isRegister)
              setError(null)
              setSuccess(null)
            }}
          >
            {isRegister ? 'Sign In' : 'Create Account'}
          </span>
        </div>
      </div>
    </div>
  )
}

export default Login
