import React from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { 
  TrendingUp, 
  BarChart3, 
  Briefcase, 
  Receipt, 
  History as HistoryIcon,
  Settings, 
  LogOut,
  Bot,
  Shield
} from 'lucide-react'
import { useAuthStore } from '../stores/authStore'

const sidebarItems = [
  {
    name: 'Dashboard',
    path: '/dashboard',
    icon: BarChart3,
    description: 'Market overview'
  },
  {
    name: 'Trading',
    path: '/trading',
    icon: TrendingUp,
    description: 'Place trades'
  },
  {
    name: 'History',
    path: '/history',
    icon: HistoryIcon,
    description: 'Bot trade log'
  },
  {
    name: 'Portfolio',
    path: '/portfolio',
    icon: Briefcase,
    description: 'Holdings & P&L'
  },
  {
    name: 'Orders',
    path: '/orders',
    icon: Receipt,
    description: 'Order history'
  },
  {
    name: 'Settings',
    path: '/settings',
    icon: Settings,
    description: 'Configuration'
  }
]

function Sidebar() {
  const location = useLocation()
  const { user, logout } = useAuthStore()

  const handleLogout = () => {
    logout()
  }

  return (
    <div className="w-64 bg-gray-900 border-r border-gray-800 flex flex-col">
      {/* Logo */}
      <div className="p-6 border-b border-gray-800">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 bg-blue-600 rounded-lg flex items-center justify-center">
            <Bot className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-white">MCX Trading</h1>
            <p className="text-xs text-gray-400">Paper Trading</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4">
        <ul className="space-y-2">
          {sidebarItems.map((item) => {
            const Icon = item.icon
            const isActive = location.pathname === item.path
            
            return (
              <li key={item.name}>
                <NavLink
                  to={item.path}
                  className={`flex items-center space-x-3 px-4 py-3 rounded-lg transition-all duration-200 ${
                    isActive
                      ? 'bg-blue-600 text-white shadow-lg'
                      : 'text-gray-400 hover:bg-gray-800 hover:text-white'
                  }`}
                >
                  <Icon className="w-5 h-5" />
                  <div className="flex-1">
                    <div className="font-medium">{item.name}</div>
                    <div className="text-xs opacity-75">{item.description}</div>
                  </div>
                </NavLink>
              </li>
            )
          })}
        </ul>
      </nav>

      {/* User Section */}
      <div className="p-4 border-t border-gray-800">
        <div className="bg-gray-800 rounded-lg p-3">
          <div className="flex items-center space-x-3 mb-3">
            <div className="w-8 h-8 bg-green-600 rounded-full flex items-center justify-center">
              <Shield className="w-4 h-4 text-white" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-white truncate">
                {user?.username || 'User'}
              </p>
              <p className="text-xs text-gray-400">Paper Mode</p>
            </div>
          </div>
          
          <button
            onClick={handleLogout}
            className="w-full flex items-center justify-center space-x-2 px-3 py-2 text-sm text-gray-400 hover:text-white hover:bg-gray-700 rounded-lg transition-colors duration-200"
          >
            <LogOut className="w-4 h-4" />
            <span>Logout</span>
          </button>
        </div>
      </div>
    </div>
  )
}

export default Sidebar
