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
      backgroundColor: '#f3f6fb',
      backgroundImage: 'radial-gradient(circle at 10% 0%, rgba(37, 99, 235, 0.08), transparent 35%), radial-gradient(circle at 90% 100%, rgba(14, 165, 233, 0.08), transparent 30%)',
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
          <div style={{ padding: '18px 20px 22px' }}>
            {children || <Outlet />}
          </div>
        </main>
      </div>
    </div>
  )
}

export default Layout
