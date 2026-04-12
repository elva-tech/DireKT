import React, { useState, useEffect } from 'react'
import { Bell, Search, Menu, X } from 'lucide-react'
import { useAuthStore } from '../stores/authStore'
import api from '../services/api'

function Header({ user }) {
  const [notifications, setNotifications] = useState([])
  const [showNotifications, setShowNotifications] = useState(false)
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false)
  const [currentTime, setCurrentTime] = useState(new Date())

  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentTime(new Date())
    }, 1000)

    return () => clearInterval(timer)
  }, [])

  useEffect(() => {
    // Fetch notifications
    const fetchNotifications = async () => {
      try {
        const response = await api.get('/notifications')
        setNotifications(response.data.notifications || [])
      } catch (error) {
        console.error('Failed to fetch notifications:', error)
      }
    }

    fetchNotifications()
    const interval = setInterval(fetchNotifications, 30000) // Every 30 seconds

    return () => clearInterval(interval)
  }, [])

  const formatTime = (date) => {
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })
  }

  const formatDate = (date) => {
    return date.toLocaleDateString('en-US', {
      weekday: 'short',
      month: 'short',
      day: 'numeric'
    })
  }

  return (
    <header className="bg-gray-900 border-b border-gray-800 px-6 py-4">
      <div className="flex items-center justify-between">
        {/* Left Section - Search */}
        <div className="flex items-center space-x-4 flex-1">
          <button
            onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
            className="lg:hidden p-2 text-gray-400 hover:text-white"
          >
            {isMobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
          
          <div className="relative max-w-md w-full">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              placeholder="Search symbols, orders..."
              className="input-field pl-10 pr-4 py-2 w-full text-sm"
            />
          </div>
        </div>

        {/* Right Section */}
        <div className="flex items-center space-x-4">
          {/* Time Display */}
          <div className="hidden md:block text-right">
            <div className="text-sm text-gray-400">{formatDate(currentTime)}</div>
            <div className="text-lg font-mono text-white">{formatTime(currentTime)}</div>
          </div>

          {/* Notifications */}
          <div className="relative">
            <button
              onClick={() => setShowNotifications(!showNotifications)}
              className="relative p-2 text-gray-400 hover:text-white transition-colors"
            >
              <Bell className="w-5 h-5" />
              {notifications.length > 0 && (
                <span className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 text-white text-xs rounded-full flex items-center justify-center">
                  {notifications.length}
                </span>
              )}
            </button>

            {/* Notifications Dropdown */}
            {showNotifications && (
              <div className="absolute right-0 mt-2 w-80 bg-gray-800 border border-gray-700 rounded-lg shadow-xl z-50">
                <div className="p-4 border-b border-gray-700">
                  <h3 className="font-medium text-white">Notifications</h3>
                </div>
                <div className="max-h-96 overflow-y-auto">
                  {notifications.length === 0 ? (
                    <div className="p-4 text-center text-gray-400">
                      No new notifications
                    </div>
                  ) : (
                    notifications.map((notification, index) => (
                      <div
                        key={index}
                        className="p-4 border-b border-gray-700 hover:bg-gray-750 transition-colors"
                      >
                        <div className="flex items-start space-x-3">
                          <div className={`w-2 h-2 rounded-full mt-2 ${
                            notification.type === 'success' ? 'bg-green-500' :
                            notification.type === 'error' ? 'bg-red-500' :
                            notification.type === 'warning' ? 'bg-yellow-500' :
                            'bg-blue-500'
                          }`}></div>
                          <div className="flex-1">
                            <p className="text-sm text-white">{notification.message}</p>
                            <p className="text-xs text-gray-400 mt-1">
                              {new Date(notification.timestamp).toLocaleTimeString()}
                            </p>
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            )}
          </div>

          {/* User Info */}
          <div className="hidden md:flex items-center space-x-3 pl-4 border-l border-gray-700">
            <div className="w-8 h-8 bg-green-600 rounded-full flex items-center justify-center">
              <span className="text-white text-sm font-medium">
                {user?.username?.charAt(0).toUpperCase()}
              </span>
            </div>
            <div>
              <p className="text-sm font-medium text-white">{user?.username}</p>
              <p className="text-xs text-green-400">Paper Mode</p>
            </div>
          </div>
        </div>
      </div>
    </header>
  )
}

export default Header
