import { create } from 'zustand'

const BACKEND_BASE = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000'
const INTEGRATION_BASE = import.meta.env.VITE_INTEGRATION_URL || 'http://localhost:8001'

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
  _userIdentityQuery: () => {
    const u = get().user || {}
    const params = new URLSearchParams()
    if (u.user_id) params.set('user_id', String(u.user_id))
    if (u.username) params.set('username', String(u.username))
    const qs = params.toString()
    return qs ? `?${qs}` : ''
  },

  login: async (credentials) => {
    try {
      set({ isLoading: true })

      const response = await fetch(`${BACKEND_BASE}/api/auth/login`, {
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

      const balanceAmount = Number(result?.balance || result?.user?.balance || 100000)
      const tradingStrategy = credentials.tradingStrategy || get().tradingStrategy || 'ml'

      set({
        user: result.user || {
          id: 1,
          username: credentials.username,
          name: credentials.username.charAt(0).toUpperCase() + credentials.username.slice(1),
          email: `${credentials.username}@mcxtrading.com`,
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
      localStorage.setItem('username', String(credentials.username || 'user'))

      try {
        await get().fetchSmartAllocation()
      } catch (e) {
        console.warn('Smart allocation after login:', e)
      }
      // Re-sync runtime engine status after auth to reflect already-running bots.
      try {
        await get().refreshAllTradingStatuses()
      } catch (e) {
        console.warn('Trading status sync after login:', e)
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

  register: async (credentials) => {
    try {
      set({ isLoading: true })
      const response = await fetch(`${BACKEND_BASE}/api/auth/register`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          username: credentials.username,
          password: credentials.password,
          role: 'paper_user',
          balance: Number(credentials.balanceAmount || 100000),
        }),
      })
      if (!response.ok) {
        const err = await response.json().catch(() => ({}))
        set({ isLoading: false })
        return { success: false, error: err?.detail || 'Registration failed' }
      }
      const result = await response.json().catch(() => ({}))
      set({ isLoading: false })
      return { success: !!result?.success, message: result?.message || 'Registration successful' }
    } catch (error) {
      set({ isLoading: false })
      return { success: false, error: error.message || 'Registration failed' }
    }
  },

  logout: async () => {
    try {
      // Intentionally DO NOT stop engines on logout.
      // Logging out should only clear local auth/session UI state.
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

  refreshAllTradingStatuses: async () => {
    const suffix = get()._userIdentityQuery()
    const readOne = async (strategy) => {
      try {
        const response = await fetch(`${INTEGRATION_BASE}/api/trading/status/${strategy}${suffix}`)
        const json = await response.json().catch(() => ({}))
        return Boolean(json?.active)
      } catch (_) {
        return false
      }
    }
    const [ml, llm, hybrid] = await Promise.all([
      readOne('ml'),
      readOne('llm'),
      readOne('hybrid'),
    ])
    set({
      mlSystemActive: ml,
      llmSystemActive: llm,
      hybridSystemActive: hybrid,
      tradingSystemActive: ml || llm || hybrid,
    })
    return { ml, llm, hybrid }
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

  updateBalancePersisted: async (newBalance) => {
    const amount = Number(newBalance || 0)
    if (!Number.isFinite(amount) || amount <= 0) {
      throw new Error('Balance must be greater than 0')
    }
    const sessionId = get().sessionId || localStorage.getItem('sessionId')
    if (!sessionId) throw new Error('Not authenticated')
    const response = await fetch(`${BACKEND_BASE}/api/user/balance`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${sessionId}`,
      },
      body: JSON.stringify({ balance: amount }),
    })
    const result = await response.json().catch(() => ({}))
    if (!response.ok || !result?.success) {
      throw new Error(result?.detail || result?.message || 'Failed to update balance')
    }
    set({ balanceAmount: amount })
    localStorage.setItem('userBalance', String(amount))
    await get().fetchSmartAllocation()
    return result
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
      const response = await fetch(`${INTEGRATION_BASE}/api/allocation/${balanceAmount}`)
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
      
      const response = await fetch(`${INTEGRATION_BASE}/api/trading/start`, {
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
          user_id: get().user?.user_id || undefined,
          username: get().user?.username || undefined,
        })
      })
      
      const result = await response.json()
      
      if (result.status) {
        const prev = get()
        const nextMl = strategy === 'ml' ? true : prev.mlSystemActive
        const nextLlm = strategy === 'llm' ? true : prev.llmSystemActive
        const nextHybrid = strategy === 'hybrid' ? true : prev.hybridSystemActive
        set({
          tradingSystemActive: nextMl || nextLlm || nextHybrid,
          mlSystemActive: nextMl,
          llmSystemActive: nextLlm,
          hybridSystemActive: nextHybrid,
        })
        return result
      } else {
        const ownerSuffix = result?.active_owner ? ` (Active owner: ${result.active_owner})` : ''
        throw new Error((result.message || 'Failed to start trading system') + ownerSuffix)
      }
    } catch (error) {
      console.error('Trading System Error:', error)
      throw error
    }
  },

  stopTradingSystem: async (strategy) => {
    try {
      const suffix = get()._userIdentityQuery()
      const response = await fetch(`${INTEGRATION_BASE}/api/trading/stop/${strategy}${suffix}`, {
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
    const suffix = get()._userIdentityQuery()
    const response = await fetch(`${INTEGRATION_BASE}/api/trading/emergency-exit/${strategy}${suffix}`, {
      method: 'POST'
    })
    const result = await response.json()
    if (!result.status) {
      throw new Error(result.message || 'Emergency exit failed')
    }
    return result
  },

  manualResetTradingSystem: async (strategy) => {
    const suffix = get()._userIdentityQuery()
    const response = await fetch(`${INTEGRATION_BASE}/api/trading/manual-reset/${strategy}${suffix}`, {
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
      const suffix = get()._userIdentityQuery()
      const response = await fetch(`${INTEGRATION_BASE}/api/trading/status/${strategy}${suffix}`)
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
