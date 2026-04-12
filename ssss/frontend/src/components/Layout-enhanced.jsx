import React from 'react'
import { Outlet } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'
import Sidebar from './Sidebar-simple'
import Header from './Header-enhanced'

function Layout({ children }) {
  const { user } = useAuthStore()

  return (
    <div style={{
      minHeight: '100vh',
      backgroundColor: '#0f172a',
      backgroundImage: 'linear-gradient(135deg, #1e293b 0%, #0f172a 100%)',
      display: 'flex',
      fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, sans-serif'
    }}>
      {/* Sidebar */}
      <Sidebar />
      
      {/* Main Content */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        {/* Header */}
        <Header user={user} />
        
        {/* Page Content */}
        <main style={{ flex: 1, overflow: 'auto' }}>
          <div style={{ padding: '24px' }}>
            {children || <Outlet />}
          </div>
        </main>
      </div>
    </div>
  )
}

export default Layout
