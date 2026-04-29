import React from 'react'

function App() {
  console.log('App component is rendering!')
  
  return (
    <div style={{
      backgroundColor: '#0f172a',
      color: 'white',
      minHeight: '100vh',
      padding: '20px',
      fontFamily: 'Arial, sans-serif'
    }}>
      <h1>🚀 React App is Working!</h1>
      <p>Current time: {new Date().toLocaleTimeString()}</p>
      <p>If you can see this, React is rendering correctly.</p>
      
      <div style={{
        backgroundColor: 'rgba(255, 255, 255, 0.1)',
        padding: '20px',
        borderRadius: '10px',
        marginTop: '20px'
      }}>
        <h2>Service Status:</h2>
        <p>Smart Allocator: <span style={{color: '#22c55e'}}>✅ Running on port 5000</span></p>
        <p>Trading Integration: <span style={{color: '#22c55e'}}>✅ Running on port 8001</span></p>
        <p>Frontend: <span style={{color: '#22c55e'}}>✅ Running on port 3000</span></p>
      </div>
      
      <button 
        onClick={() => alert('Button clicked! React is working!')}
        style={{
          padding: '10px 20px',
          backgroundColor: '#3b82f6',
          color: 'white',
          border: 'none',
          borderRadius: '5px',
          cursor: 'pointer',
          marginTop: '20px'
        }}
      >
        Test JavaScript
      </button>
    </div>
  )
}

export default App
