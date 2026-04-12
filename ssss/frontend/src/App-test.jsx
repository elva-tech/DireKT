import React from 'react'

function App() {
  return (
    <div style={{
      backgroundColor: '#0f172a',
      color: 'white',
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      fontFamily: 'Arial, sans-serif'
    }}>
      <div style={{ textAlign: 'center' }}>
        <h1 style={{ fontSize: '2rem', marginBottom: '20px' }}>
          🚀 MCX Trading Platform - Test Mode
        </h1>
        <p style={{ fontSize: '1.2rem', marginBottom: '30px' }}>
          Frontend is working! Let me check the services...
        </p>
        <div style={{ marginBottom: '20px' }}>
          <button 
            onClick={() => window.open('http://localhost:5000/health', '_blank')}
            style={{
              padding: '10px 20px',
              margin: '10px',
              backgroundColor: '#22c55e',
              color: 'white',
              border: 'none',
              borderRadius: '5px',
              cursor: 'pointer'
            }}
          >
            Test Smart Allocator API
          </button>
          <button 
            onClick={() => window.open('http://localhost:8001/health', '_blank')}
            style={{
              padding: '10px 20px',
              margin: '10px',
              backgroundColor: '#3b82f6',
              color: 'white',
              border: 'none',
              borderRadius: '5px',
              cursor: 'pointer'
            }}
          >
            Test Trading API
          </button>
        </div>
        <div style={{ marginTop: '30px', fontSize: '0.9rem', color: '#94a3b8' }}>
          <p>If you can see this page, React is working!</p>
          <p>Check the browser console (F12) for any errors.</p>
        </div>
      </div>
    </div>
  )
}

export default App
