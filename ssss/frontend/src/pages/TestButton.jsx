import React from 'react'
import { useNavigate } from 'react-router-dom'

function TestButton() {
  const navigate = useNavigate()

  const handleClick = () => {
    console.log('Button clicked!')
    alert('Button is working!')
    navigate('/dashboard')
  }

  return (
    <div style={{
      padding: '20px',
      backgroundColor: '#0f172a',
      color: 'white',
      minHeight: '100vh',
      fontFamily: 'Arial, sans-serif'
    }}>
      <h1>Button Test Page</h1>
      <button
        onClick={handleClick}
        style={{
          padding: '12px 24px',
          backgroundColor: '#3b82f6',
          color: 'white',
          border: 'none',
          borderRadius: '8px',
          cursor: 'pointer',
          fontSize: '16px'
        }}
      >
        Click Me!
      </button>
    </div>
  )
}

export default TestButton
