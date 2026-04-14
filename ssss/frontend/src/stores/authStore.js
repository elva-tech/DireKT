import { create } from 'zustand'

// Resilient API URL selection with multiple fallbacks
const API_URL = import.meta.env.VITE_API_URL || 
                'https://direkt-backend-koop.onrender.com' || 
                'https://direkt-backend.onrender.com' ||
                'http://localhost:8000';

export const useAuthStore = create((set, get) => ({
  // State
  user: null,
  sessionId: null,
  isAuthenticated: false,
  isLoading: false,
  balanceAmount: 100000,
  tradingStrategy: 'ml',
  tradingSystemActive: false,
  mlSystemActive: false,
  llmSystemActive: false,
  hybridSystemActive: false,
  lotAllocation: null,
  /** From allocator: live Angel instrument for quotes + paper sizing */
  instrumentSymbol: null,
  instrumentToken: null,
  allocationSymbolType: null,

  // Actions
  register: async (credentials) => {
    try {
      set({ isLoading: true })
      const response = await fetch(`${API_URL}/api/auth/register`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          username: credentials.username,
          password: credentials.password,
          balance: credentials.balance || 100000.0
        }),
      })

      const result = await response.json()
      set({ isLoading: false })
      
      if (response.ok && result.success) {
        return { success: true, message: result.message }
      } else {
        return { success: false, error: result.message || 'Registration failed' }
      }
    } catch (error) {
      set({ isLoading: false })
      console.error('Registration error:', error)
      return { success: false, error: 'Network error or server unavailable' }
    }
  },

  login: async (credentials) => {
    try {
      set({ isLoading: true })
      const response = await fetch(`${API_URL}/api/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          username: credentials.username,
          password: credentials.password,
        }),
      })

      if (!response.ok) {
        const err = await response.json().catch(() => ({}))
        set({ isLoading: false })
        return { success: false, error: err?.detail || 'Login failed' }
      }

      const result = await response.json()
      if (!result?.success || !result?.session_id) {
        set({ isLoading: false })
        return { success: false, error: result?.message || 'Login failed' }
      }

      const balanceAmount = credentials.balanceAmount || 100000
      const tradingStrategy = credentials.tradingStrategy || get().tradingStrategy || 'ml'

      set({
        user: {
          id: result.user.user_id,
          username: result.user.username,
          role: result.user.role,
          name: result.user.username.charAt(0).toUpperCase() + result.user.username.slice(1),
        },
        sessionId: result.session_id,
        isAuthenticated: true,
        balanceAmount,
        tradingStrategy,
        isLoading: false,
      })

      localStorage.setItem('sessionId', result.session_id)
      localStorage.setItem('userBalance', String(balanceAmount))
      localStorage.setItem('tradingStrategy', String(tradingStrategy))
      localStorage.setItem('username', String(result.user.username || 'user'))

      try {
        await get().fetchSmartAllocation()
      } catch (e) {
        console.warn('Smart allocation after login:', e)
      }

      return { success: true }
    } catch (error) {
      set({ isLoading: false })
      return { 
        success: false, 
        error: error.message || 'Login failed'
      }
    }
  },

  signup: async (credentials) => {
    try {
      set({ isLoading: true })
      const response = await fetch(`${API_URL}/api/auth/signup`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          username: credentials.username,
          password: credentials.password,
        }),
      })

      const result = await response.json()
      set({ isLoading: false })

      if (!response.ok) {
        return { success: false, error: result?.detail || 'Signup failed' }
      }

      return { success: true, message: result?.message }
    } catch (error) {
      set({ isLoading: false })
      return { 
        success: false, 
        error: error.message || 'Signup failed'
      }
    }
  },

  logout: async () => {
    try {
      // Stop trading system if active
      const { tradingSystemActive } = get()
      if (tradingSystemActive) {
        try {
          await fetch(`${API_URL}/api/trading/stop/ml`, {
            method: 'POST'
          })
        } catch (err) {
          console.log('Error stopping ML system:', err)
        }
        
        try {
          await fetch(`${API_URL}/api/trading/stop/llm`, {
            method: 'POST'
          })
        } catch (err) {
          console.log('Error stopping LLM system:', err)
        }

        try {
          await fetch(`${API_URL}/api/trading/stop/hybrid`, {
            method: 'POST'
          })
        } catch (err) {
          console.log('Error stopping Hybrid system:', err)
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
        mlSystemActive: false,
        llmSystemActive: false,
        hybridSystemActive: false,
        lotAllocation: null,
        instrumentSymbol: null,
        instrumentToken: null,
        allocationSymbolType: null,
        isLoading: false,
      })
      localStorage.removeItem('sessionId')
      localStorage.removeItem('userBalance')
      localStorage.removeItem('tradingStrategy')
      localStorage.removeItem('instrumentSymbol')
      localStorage.removeItem('instrumentToken')
      localStorage.removeItem('allocationSymbolType')
    } catch (error) {
      console.error('Logout error:', error)
    }
  },

  initializeAuth: () => {
    const sessionId = localStorage.getItem('sessionId')
    const balanceAmount = localStorage.getItem('userBalance')
    const tradingStrategy = localStorage.getItem('tradingStrategy')
    const username = localStorage.getItem('username')
    
    if (sessionId) {
      const instrumentSymbol = localStorage.getItem('instrumentSymbol') || null
      const instrumentToken = localStorage.getItem('instrumentToken') || null
      const allocationSymbolType = localStorage.getItem('allocationSymbolType') || null
      set({ 
        sessionId, 
        isAuthenticated: true,
        user: {
          id: 1,
          username: username || 'user',
          name: 'User',
          email: 'user@mcxtrading.com',
        },
        balanceAmount: balanceAmount ? parseFloat(balanceAmount) : 100000,
        tradingStrategy: tradingStrategy || 'ml',
        instrumentSymbol: instrumentSymbol || null,
        instrumentToken: instrumentToken || null,
        allocationSymbolType: allocationSymbolType || null,
        isLoading: false 
      })
      get().fetchSmartAllocation().catch(() => {})
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
    const { mlSystemActive, llmSystemActive, hybridSystemActive } = get()
    set({
      tradingSystemActive: active,
      mlSystemActive: active ? mlSystemActive : false,
      llmSystemActive: active ? llmSystemActive : false,
      hybridSystemActive: active ? hybridSystemActive : false,
    })
  },

  setLotAllocation: (allocation) => {
    set({ lotAllocation: allocation })
  },

  // Smart Allocator Integration
  fetchSmartAllocation: async () => {
    try {
      const { balanceAmount } = get()
      // Use integration service as a stable gateway to allocator.
      const response = await fetch(`${API_URL}/api/allocation/${balanceAmount}`)
      const result = await response.json().catch(() => ({}))

      if (!response.ok) {
        throw new Error(result?.detail || `Allocation API failed (${response.status})`)
      }

      if (!result?.status) {
        throw new Error(result?.error || result?.message || 'Failed to fetch smart allocation')
      }

      const allocation = result.data || result
      const bo = allocation.buy_orders?.[0] || {}
      const instrumentSymbol = bo.contract || null
      const instrumentToken = bo.symbol_token || null
      const allocationSymbolType = allocation.summary?.allocation_symbol_type || null
      if (instrumentSymbol) localStorage.setItem('instrumentSymbol', instrumentSymbol)
      else localStorage.removeItem('instrumentSymbol')
      if (instrumentToken) localStorage.setItem('instrumentToken', instrumentToken)
      else localStorage.removeItem('instrumentToken')
      if (allocationSymbolType) localStorage.setItem('allocationSymbolType', allocationSymbolType)
      else localStorage.removeItem('allocationSymbolType')
      set({
        lotAllocation: allocation,
        instrumentSymbol,
        instrumentToken,
        allocationSymbolType,
      })
      return allocation
    } catch (error) {
      console.error('Smart Allocation Error:', error)
      throw error
    }
  },

  // Trading System Integration
  startTradingSystem: async (strategy) => {
    try {
      const {
        balanceAmount,
        allocationSymbolType,
        instrumentSymbol,
        instrumentToken,
        lotAllocation,
      } = get()
      const maxLots = Number(lotAllocation?.buy_orders?.[0]?.lots || lotAllocation?.summary?.total_lots || 0)
      
      const response = await fetch(`${API_URL}/api/trading/start`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          strategy,
          balance: balanceAmount,
          symbol: allocationSymbolType || 'SILVER',
          tradingsymbol: instrumentSymbol || undefined,
          symbol_token: instrumentToken || undefined,
          max_lots: maxLots > 0 ? maxLots : undefined,
        })
      })
      
      const result = await response.json()
      
      if (result.status) {
        set({
          tradingSystemActive: true,
          mlSystemActive: strategy === 'ml',
          llmSystemActive: strategy === 'llm',
          hybridSystemActive: strategy === 'hybrid',
        })
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
      const response = await fetch(`${API_URL}/api/trading/stop/${strategy}`, {
        method: 'POST'
      })
      
      const result = await response.json()
      
      if (result.status) {
        const nextMl = strategy === 'ml' ? false : get().mlSystemActive
        const nextLlm = strategy === 'llm' ? false : get().llmSystemActive
        const nextHybrid = strategy === 'hybrid' ? false : get().hybridSystemActive
        set({
          mlSystemActive: nextMl,
          llmSystemActive: nextLlm,
          hybridSystemActive: nextHybrid,
          tradingSystemActive: nextMl || nextLlm || nextHybrid,
        })
        return result
      } else {
        throw new Error(result.message || 'Failed to stop trading system')
      }
    } catch (error) {
      console.error('Stop Trading System Error:', error)
      throw error
    }
  },

  emergencyExitTradingSystem: async (strategy) => {
    const response = await fetch(`${API_URL}/api/trading/emergency-exit/${strategy}`, {
      method: 'POST'
    })
    const result = await response.json()
    if (!result.status) {
      throw new Error(result.message || 'Emergency exit failed')
    }
    return result
  },

  manualResetTradingSystem: async (strategy) => {
    const response = await fetch(`${API_URL}/api/trading/manual-reset/${strategy}`, {
      method: 'POST'
    })
    const result = await response.json()
    if (!result.status) {
      throw new Error(result.message || 'Manual reset failed')
    }
    return result
  },

  getTradingSystemStatus: async (strategy) => {
    try {
      const response = await fetch(`${API_URL}/api/trading/status/${strategy}`)
      const result = await response.json()
      const active = Boolean(result?.active)
      if (strategy === 'ml') {
        set({
          mlSystemActive: active,
          tradingSystemActive: active || get().llmSystemActive || get().hybridSystemActive,
        })
      } else if (strategy === 'llm') {
        set({
          llmSystemActive: active,
          tradingSystemActive: get().mlSystemActive || active || get().hybridSystemActive,
        })
      } else if (strategy === 'hybrid') {
        set({
          hybridSystemActive: active,
          tradingSystemActive: get().mlSystemActive || get().llmSystemActive || active,
        })
      }
      return result
    } catch (error) {
      console.error('Get Trading Status Error:', error)
      throw error
    }
  }
}))

export default useAuthStore
