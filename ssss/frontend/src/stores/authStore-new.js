import { create } from 'zustand'

const useAuthStore = create((set, get) => ({
  // State
  user: null,
  sessionId: null,
  isAuthenticated: false,
  isLoading: false,
  balanceAmount: 100000,
  tradingStrategy: 'ml',
  tradingSystemActive: false,
  lotAllocation: null,

  // Actions
  login: async (credentials) => {
    try {
      set({ isLoading: true })
      
      // Mock authentication - accept any username/password for demo
      if (credentials.username && credentials.password) {
        const userData = {
          id: 1,
          username: credentials.username,
          name: credentials.username.charAt(0).toUpperCase() + credentials.username.slice(1),
          email: `${credentials.username}@mcxtrading.com`,
          balanceAmount: credentials.balanceAmount || 100000,
          tradingStrategy: credentials.tradingStrategy || 'ml'
        }
        
        set({
          user: userData,
          sessionId: 'mock-session-' + Date.now(),
          isAuthenticated: true,
          balanceAmount: credentials.balanceAmount || 100000,
          tradingStrategy: credentials.tradingStrategy || 'ml',
          isLoading: false,
        })
        localStorage.setItem('sessionId', 'mock-session-' + Date.now())
        localStorage.setItem('userBalance', credentials.balanceAmount || 100000)
        localStorage.setItem('tradingStrategy', credentials.tradingStrategy || 'ml')
        return { success: true }
      } else {
        set({ isLoading: false })
        return { success: false, error: 'Invalid credentials' }
      }
    } catch (error) {
      set({ isLoading: false })
      return { 
        success: false, 
        error: error.message || 'Login failed'
      }
    }
  },

  logout: async () => {
    try {
      // Stop trading system if active
      const { tradingSystemActive } = get()
      if (tradingSystemActive) {
        try {
          await fetch('http://localhost:8001/api/trading/stop/ml', {
            method: 'POST'
          })
        } catch (err) {
          console.log('Error stopping ML system:', err)
        }
        
        try {
          await fetch('http://localhost:8001/api/trading/stop/llm', {
            method: 'POST'
          })
        } catch (err) {
          console.log('Error stopping LLM system:', err)
        }
      }

      // No logout endpoint in backend, just clear local state
      set({
        user: null,
        sessionId: null,
        isAuthenticated: false,
        balanceAmount: 100000,
        tradingStrategy: 'ml',
        tradingSystemActive: false,
        lotAllocation: null,
      })
      localStorage.removeItem('sessionId')
      localStorage.removeItem('userBalance')
      localStorage.removeItem('tradingStrategy')
    } catch (error) {
      console.error('Logout error:', error)
    }
  },

  initializeAuth: () => {
    const sessionId = localStorage.getItem('sessionId')
    const balanceAmount = localStorage.getItem('userBalance')
    const tradingStrategy = localStorage.getItem('tradingStrategy')
    
    if (sessionId) {
      set({ 
        sessionId, 
        isAuthenticated: true,
        user: {
          id: 1,
          username: 'user',
          name: 'User',
          email: 'user@mcxtrading.com',
        },
        balanceAmount: balanceAmount ? parseFloat(balanceAmount) : 100000,
        tradingStrategy: tradingStrategy || 'ml',
        isLoading: false 
      })
    } else {
      set({ isLoading: false })
    }
  },

  updateBalance: (newBalance) => {
    set({ balanceAmount: newBalance })
    localStorage.setItem('userBalance', newBalance)
  },

  updateStrategy: (newStrategy) => {
    set({ tradingStrategy: newStrategy })
    localStorage.setItem('tradingStrategy', newStrategy)
  },

  setTradingSystemActive: (active) => {
    set({ tradingSystemActive: active })
  },

  setLotAllocation: (allocation) => {
    set({ lotAllocation: allocation })
  },

  // Smart Allocation API
  getSmartAllocation: async (balance) => {
    try {
      const response = await fetch('http://localhost:5000/api/smart-allocate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          available_amount: balance,
          product_type: 'CARRYFORWARD'
        })
      })
      
      const result = await response.json()
      
      if (result.status) {
        set({ lotAllocation: result })
        return result
      } else {
        throw new Error(result.message || 'Smart allocation failed')
      }
    } catch (error) {
      console.error('Smart Allocation Error:', error)
      throw error
    }
  },

  // Trading System Integration
  startTradingSystem: async (strategy) => {
    try {
      const { balanceAmount } = get()
      
      const response = await fetch('http://localhost:8001/api/trading/start', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          strategy: strategy,
          balance: balanceAmount,
          symbol: 'SILVER'
        })
      })
      
      const result = await response.json()
      
      if (result.status) {
        set({ tradingSystemActive: true })
        return result
      } else {
        throw new Error(result.message || 'Failed to start trading system')
      }
    } catch (error) {
      console.error('Trading System Error:', error)
      throw error
    }
  },

  stopTradingSystem: async (strategy) => {
    try {
      const response = await fetch(`http://localhost:8001/api/trading/stop/${strategy}`, {
        method: 'POST'
      })
      
      const result = await response.json()
      
      if (result.status) {
        set({ tradingSystemActive: false })
        return result
      } else {
        throw new Error(result.message || 'Failed to stop trading system')
      }
    } catch (error) {
      console.error('Stop Trading System Error:', error)
      throw error
    }
  },

  getTradingSystemStatus: async (strategy) => {
    try {
      const response = await fetch(`http://localhost:8001/api/trading/status/${strategy}`)
      const result = await response.json()
      return result
    } catch (error) {
      console.error('Get Trading Status Error:', error)
      throw error
    }
  }
}))

export default useAuthStore
