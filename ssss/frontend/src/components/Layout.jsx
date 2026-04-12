import React from 'react'
import { Outlet } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'
import Sidebar from './Sidebar'
import Header from './Header'

function Layout() {
  const { user } = useAuthStore()

  return (
    <div className="min-h-screen bg-gray-950 flex">
      {/* Sidebar */}
      <Sidebar />
      
      {/* Main Content */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <Header user={user} />
        
        {/* Page Content */}
        <main className="flex-1 overflow-auto">
          <div className="p-6">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}

export default Layout
