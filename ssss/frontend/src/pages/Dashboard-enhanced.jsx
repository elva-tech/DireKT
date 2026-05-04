import React, { useState, useEffect, useRef, useCallback } from 'react'
import { useAuthStore } from '../stores/authStore'

const INTEGRATION_BASE = import.meta.env.VITE_INTEGRATION_URL || 'http://localhost:8001'
// Slightly slower polling reduces Angel API rate limits; integration also caches ~8s server-side.
const LIVE_POLL_MS = 6000
const CHART_MAX_POINTS = 48

function formatInr(n) {
  if (n == null || Number.isNaN(Number(n))) return '—'
  return `₹${Number(n).toLocaleString('en-IN', { maximumFractionDigits: 2 })}`
}

function Dashboard() {
  const {
    user,
    balanceAmount,
    tradingStrategy,
    instrumentToken,
    instrumentSymbol,
    lotAllocation,
    updateBalancePersisted,
  } = useAuthStore()

  const [liveQuote, setLiveQuote] = useState(null)
  const [priceHistory, setPriceHistory] = useState([])
  const [liveError, setLiveError] = useState(null)
  const [liveLoading, setLiveLoading] = useState(true)
  const [balanceInput, setBalanceInput] = useState(balanceAmount || 100000)
  const [balanceSaving, setBalanceSaving] = useState(false)
  const [balanceMsg, setBalanceMsg] = useState('')
  const [perfModels, setPerfModels] = useState([])
  const [runtimeByEngine, setRuntimeByEngine] = useState({ ml: null, llm: null, hybrid: null })
  const [weeklySeries, setWeeklySeries] = useState([])
  const intervalRef = useRef(null)

  useEffect(() => {
    setBalanceInput(balanceAmount || 100000)
  }, [balanceAmount])

  const fetchLive = useCallback(async () => {
    const requests = []

    // 1) Preferred dashboard contract: May/July SILVER path.
    const mayParams = new URLSearchParams()
    mayParams.set('symbol_family', 'SILVER')
    mayParams.set('prefer_may_jul', 'true')
    requests.push(`${INTEGRATION_BASE}/api/market/live?${mayParams.toString()}`)

    // 2) Fallback to exact allocated instrument token/symbol if available.
    if (instrumentToken) {
      const tokenParams = new URLSearchParams()
      tokenParams.set('token', String(instrumentToken))
      if (instrumentSymbol) tokenParams.set('tradingsymbol', String(instrumentSymbol))
      requests.push(`${INTEGRATION_BASE}/api/market/live?${tokenParams.toString()}`)
    }

    // 3) Fallback to allocation-based contract resolution from balance.
    if (balanceAmount) {
      const allocParams = new URLSearchParams()
      allocParams.set('use_allocation_token', 'true')
      allocParams.set('balance', String(balanceAmount))
      requests.push(`${INTEGRATION_BASE}/api/market/live?${allocParams.toString()}`)
    }

    try {
      let json = null
      let lastError = null
      for (const url of requests) {
        const res = await fetch(url, { method: 'GET' })
        json = await res.json().catch(() => ({}))
        if (res.ok && json?.status && json?.data) {
          lastError = null
          break
        }
        const detail = json?.detail
        lastError =
          typeof detail === 'string'
            ? detail
            : Array.isArray(detail)
              ? detail.map((d) => d.msg || d).join('; ')
              : detail
                ? JSON.stringify(detail)
                : json?.message || `HTTP ${res.status}`
        json = null
      }

      if (!json?.data) {
        setLiveError(lastError || 'Live quote unavailable')
        setLiveLoading(false)
        return
      }
      setLiveError(null)
      setLiveQuote(json.data)
      const ltp = json.data.ltp
      if (ltp != null && ltp > 0) {
        const label = new Date().toLocaleTimeString('en-IN', {
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
          hour12: false,
        })
        setPriceHistory((prev) => {
          const next = [...prev, { t: label, price: ltp }]
          return next.length > CHART_MAX_POINTS ? next.slice(-CHART_MAX_POINTS) : next
        })
      }
    } catch (e) {
      setLiveError(e.message || 'Network error')
    } finally {
      setLiveLoading(false)
    }
  }, [balanceAmount, instrumentSymbol, instrumentToken])

  useEffect(() => {
    fetchLive()
    intervalRef.current = window.setInterval(fetchLive, LIVE_POLL_MS)
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [fetchLive])

  useEffect(() => {
    let mounted = true
    const refreshStats = async () => {
      const params = new URLSearchParams()
      if (user?.user_id) params.set('user_id', String(user.user_id))
      if (user?.username) params.set('username', String(user.username))
      const qs = params.toString() ? `?${params.toString()}` : ''
      try {
        const [perfRes, histRes, mlRes, llmRes, hybridRes] = await Promise.all([
          fetch(`${INTEGRATION_BASE}/api/trading/performance-summary${qs}`),
          fetch(`${INTEGRATION_BASE}/api/trading/history?limit=1000${qs ? `&${params.toString()}` : ''}`),
          fetch(`${INTEGRATION_BASE}/api/trading/metrics/ml${qs}`),
          fetch(`${INTEGRATION_BASE}/api/trading/metrics/llm${qs}`),
          fetch(`${INTEGRATION_BASE}/api/trading/metrics/hybrid${qs}`),
        ])
        const [perfJson, histJson, mlJson, llmJson, hybridJson] = await Promise.all([
          perfRes.json().catch(() => ({})),
          histRes.json().catch(() => ({})),
          mlRes.json().catch(() => ({})),
          llmRes.json().catch(() => ({})),
          hybridRes.json().catch(() => ({})),
        ])
        if (!mounted) return
        if (Array.isArray(perfJson?.models)) setPerfModels(perfJson.models)
        setRuntimeByEngine({
          ml: mlJson?.metrics || null,
          llm: llmJson?.metrics || null,
          hybrid: hybridJson?.metrics || null,
        })
        const closed = (histJson?.events || []).filter((e) => String(e?.lifecycle || '').toUpperCase() === 'CLOSED')
        const sorted = closed
          .slice()
          .sort((a, b) => new Date(a?.close_timestamp || a?.timestamp || 0) - new Date(b?.close_timestamp || b?.timestamp || 0))
          .slice(-5)
        let running = Number(balanceAmount || 0)
        const trend = sorted.map((row, idx) => {
          running += Number(row?.pnl || 0)
          return {
            date: `T${idx + 1}`,
            value: running,
          }
        })
        if (trend.length > 0) setWeeklySeries(trend)
      } catch (_) {}
    }
    refreshStats()
    const id = setInterval(refreshStats, 10000)
    return () => {
      mounted = false
      clearInterval(id)
    }
  }, [user?.user_id, user?.username, balanceAmount])

  const performanceData = weeklySeries.length > 0
    ? weeklySeries
    : [{ date: 'Now', value: Number(balanceAmount || 0) }]

  const perfValues = performanceData.map((d) => d.value)
  const perfMin = Math.min(...perfValues)
  const perfMax = Math.max(...perfValues)
  const perfSpan = perfMax - perfMin || 1
  const WEEKLY_BAR_MAX = 104
  const WEEKLY_BAR_MIN = 14
  const weeklyBarHeight = (value) =>
    WEEKLY_BAR_MIN + ((value - perfMin) / perfSpan) * (WEEKLY_BAR_MAX - WEEKLY_BAR_MIN)

  const getStrategyColor = () => {
    return tradingStrategy === 'ml' ? '#3b82f6' : '#8b5cf6'
  }

  const getStrategyName = () => {
    return tradingStrategy === 'ml' ? 'ML Model' : 'LLM Powered'
  }

  const selectedEngine = tradingStrategy === 'llm' ? 'llm' : tradingStrategy === 'hybrid' ? 'hybrid' : 'ml'
  const selectedPerf = perfModels.find((m) => String(m.engine || '').toLowerCase() === selectedEngine) || { win_rate: 0 }
  const selectedRuntime = runtimeByEngine[selectedEngine] || {}
  const totalValue = Number(balanceAmount || 0)
  const availableBalance = Number(lotAllocation?.summary?.remaining_cash ?? (totalValue - Math.max(0, Number(lotAllocation?.summary?.total_margin_used || 0))))
  const usedMargin = Math.max(0, totalValue - Math.max(0, availableBalance))
  const todayPnl = Number(selectedRuntime?.total_pnl ?? 0)
  const todayPct = totalValue > 0 ? (todayPnl / totalValue) * 100 : 0

  const chartPrices = priceHistory.map((p) => p.price)
  const chartMin = chartPrices.length ? Math.min(...chartPrices) : 0
  const chartMax = chartPrices.length ? Math.max(...chartPrices) : 1
  const chartSpan = chartMax - chartMin || 1

  const displaySymbol =
    liveQuote?.tradingsymbol ||
    instrumentSymbol ||
    lotAllocation?.buy_orders?.[0]?.contract ||
    'MCX Silver'

  const allocatedLots = lotAllocation?.summary?.total_lots
  const marketOpen = Boolean(liveQuote?.market_open)
  const marketReason = liveQuote?.market_reason

  return (
    <div style={{
      backgroundColor: 'transparent',
      color: '#0f172a',
      minHeight: '100vh',
      padding: '12px',
      fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, sans-serif'
    }}>
      {/* Header */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '16px',
        padding: '18px 20px',
        borderRadius: '16px',
        background: 'linear-gradient(135deg, rgba(15,23,42,0.95), rgba(30,41,59,0.92))',
        border: '1px solid rgba(148,163,184,0.22)',
        boxShadow: '0 18px 36px rgba(2, 6, 23, 0.25)'
      }}>
        <div>
          <h1 style={{
            fontSize: '2rem',
            fontWeight: '700',
            color: '#f8fafc',
            marginBottom: '4px',
            letterSpacing: '-0.025em'
          }}>
            Trading Dashboard
          </h1>
          <p style={{ color: '#94a3b8', fontSize: '0.9rem' }}>
            Real-time market overview and portfolio management
          </p>
        </div>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          padding: '12px 20px',
          backgroundColor: marketOpen ? 'rgba(34, 197, 94, 0.14)' : 'rgba(239, 68, 68, 0.14)',
          border: marketOpen ? '1px solid rgba(34, 197, 94, 0.45)' : '1px solid rgba(239, 68, 68, 0.45)',
          borderRadius: '12px',
          backdropFilter: 'blur(10px)'
        }}>
          <div style={{
            width: '8px',
            height: '8px',
            backgroundColor: marketOpen ? '#22c55e' : '#ef4444',
            borderRadius: '50%',
            animation: 'dashboard-pulse 2s infinite'
          }}></div>
          <span style={{ color: marketOpen ? '#4ade80' : '#f87171', fontSize: '0.82rem', fontWeight: '700', letterSpacing: '0.03em' }}>
            {marketOpen ? 'Market Open' : 'Market Closed'}
          </span>
        </div>
      </div>

      {/* User Info Card */}
      <div style={{
        background: 'linear-gradient(140deg, rgba(255,255,255,0.95), rgba(248,250,252,0.9))',
        border: '1px solid rgba(148, 163, 184, 0.2)',
        borderRadius: '16px',
        padding: '24px',
        marginBottom: '16px',
        boxShadow: '0 12px 28px rgba(15, 23, 42, 0.12)'
      }}>
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '16px'
        }}>
          <h2 style={{
            fontSize: '1.3rem',
            fontWeight: '600',
            color: '#0f172a',
            display: 'flex',
            alignItems: 'center',
            gap: '12px'
          }}>
            <span style={{ width: '10px', height: '10px', borderRadius: '50%', backgroundColor: getStrategyColor(), display: 'inline-block' }}></span>
            Your Trading Profile
          </h2>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '8px 16px',
            backgroundColor: `${getStrategyColor()}20`,
            borderRadius: '12px',
            border: `1px solid ${getStrategyColor()}`
          }}>
            <span style={{ color: '#0f172a', fontSize: '0.82rem', fontWeight: '700', letterSpacing: '0.02em' }}>
              {getStrategyName()}
            </span>
          </div>
        </div>
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: '16px'
        }}>
          <div>
            <div style={{ color: '#64748b', fontSize: '0.9rem', marginBottom: '4px' }}>
              Trading Balance
            </div>
            <div style={{ fontSize: '1.7rem', fontWeight: '700', color: '#0f172a' }}>
              ₹{balanceAmount.toLocaleString()}
            </div>
          </div>
          <div>
            <div style={{ color: '#64748b', fontSize: '0.9rem', marginBottom: '4px' }}>
              Strategy Type
            </div>
            <div style={{ fontSize: '1.2rem', fontWeight: 'bold', color: getStrategyColor() }}>
              {getStrategyName()}
            </div>
          </div>
          <div>
            <div style={{ color: '#64748b', fontSize: '0.9rem', marginBottom: '4px' }}>
              Max Position Size
            </div>
            <div style={{ fontSize: '1.2rem', fontWeight: 'bold', color: '#0f172a' }}>
              {allocatedLots != null ? `${allocatedLots} lots` : '—'}
            </div>
          </div>
        </div>
        <div style={{ marginTop: '14px', display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
          <input
            type="number"
            min="1000"
            step="1000"
            value={balanceInput}
            onChange={(e) => setBalanceInput(Number(e.target.value || 0))}
            style={{
              width: '220px',
              backgroundColor: 'rgba(31, 41, 55, 0.5)',
              border: '1px solid rgba(75, 85, 99, 0.5)',
              borderRadius: '10px',
              padding: '10px 12px',
              color: 'white',
              fontSize: '0.95rem',
            }}
          />
          <button
            type="button"
            disabled={balanceSaving}
            onClick={async () => {
              setBalanceSaving(true)
              setBalanceMsg('')
              try {
                await updateBalancePersisted(balanceInput)
                setBalanceMsg('Balance updated.')
              } catch (e) {
                setBalanceMsg(e?.message || 'Update failed')
              } finally {
                setBalanceSaving(false)
              }
            }}
            style={{
              background: 'linear-gradient(135deg, #3b82f6, #2563eb)',
              color: 'white',
              border: 'none',
              borderRadius: '10px',
              padding: '10px 14px',
              cursor: balanceSaving ? 'not-allowed' : 'pointer',
              opacity: balanceSaving ? 0.7 : 1,
            }}
          >
            {balanceSaving ? 'Saving...' : 'Update Balance'}
          </button>
          {balanceMsg ? <span style={{ color: '#475569', fontSize: '0.85rem' }}>{balanceMsg}</span> : null}
        </div>
      </div>

      {/* Market Overview */}
      <div style={{
        background: 'linear-gradient(140deg, rgba(255,255,255,0.95), rgba(248,250,252,0.9))',
        border: '1px solid rgba(148, 163, 184, 0.2)',
        borderRadius: '16px',
        padding: '32px',
        boxShadow: '0 12px 28px rgba(15, 23, 42, 0.12)'
      }}>
        <h2 style={{
          fontSize: '1.5rem',
          fontWeight: '600',
          color: '#0f172a',
          marginBottom: '8px',
          display: 'flex',
          alignItems: 'center',
          gap: '12px'
        }}>
          <span style={{ width: '10px', height: '10px', borderRadius: '50%', backgroundColor: '#2563eb', display: 'inline-block' }}></span>
          Market Overview
        </h2>
        <p style={{ color: '#64748b', fontSize: '0.85rem', marginBottom: '20px' }}>
          {liveQuote?.tradingsymbol || displaySymbol}
          {liveQuote?.contract_selection ? (
            <> · {liveQuote.contract_selection === 'may_or_july' ? 'May/Jul expiry series' : liveQuote.contract_selection.replace(/_/g, ' ')}</>
          ) : null}
          {liveQuote?.expiry_month ? (
            <> · expiry month {liveQuote.expiry_month}</>
          ) : null}
          {liveQuote?.as_of ? (
            <> · Updated {new Date(liveQuote.as_of).toLocaleString('en-IN')} · refresh ~{LIVE_POLL_MS / 1000}s</>
          ) : liveLoading ? (
            <> · Loading…</>
          ) : null}
          {marketReason ? <> · {marketReason}</> : null}
        </p>
        {liveError && (
          <div style={{
            marginBottom: '16px',
            padding: '12px',
            borderRadius: '10px',
            backgroundColor: 'rgba(245, 158, 11, 0.12)',
            border: '1px solid rgba(245, 158, 11, 0.35)',
            color: '#fcd34d',
            fontSize: '0.9rem',
          }}>
            {liveError}
          </div>
        )}

        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: '20px',
          marginBottom: '24px'
        }}>
          <div style={{
            backgroundColor: 'rgba(248, 250, 252, 0.98)',
            padding: '20px',
            borderRadius: '12px',
            border: '1px solid rgba(148, 163, 184, 0.22)'
          }}>
            <div style={{ color: '#334155', fontSize: '0.9rem', marginBottom: '8px', fontWeight: 600 }}>
              LTP
            </div>
            <div style={{ fontSize: '1.8rem', fontWeight: 'bold', color: '#0f172a', marginBottom: '8px' }}>
              {formatInr(liveQuote?.ltp)}
            </div>
            <div style={{
              color: liveQuote?.change_pct == null ? '#6b7280' : liveQuote.change_pct >= 0 ? '#22c55e' : '#ef4444',
              fontSize: '0.9rem',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
            }}>
              {liveQuote?.change_pct != null ? (
                <>
                  <span>{liveQuote.change_pct >= 0 ? '↑' : '↓'}</span>
                  {liveQuote.change_pct >= 0 ? '+' : ''}{liveQuote.change_pct}% vs prev close
                </>
              ) : (
                <span>—</span>
              )}
            </div>
          </div>
          
          <div style={{
            backgroundColor: 'rgba(255, 255, 255, 0.98)',
            padding: '20px',
            borderRadius: '12px',
            border: '1px solid rgba(148, 163, 184, 0.28)'
          }}>
            <div style={{ color: '#334155', fontSize: '0.9rem', marginBottom: '8px', fontWeight: 600 }}>
              Volume
            </div>
            <div style={{ fontSize: '1.8rem', fontWeight: 'bold', color: '#0f172a', marginBottom: '8px' }}>
              {liveQuote?.volume != null ? liveQuote.volume.toLocaleString('en-IN') : '—'}
            </div>
            <div style={{ color: '#475569', fontSize: '0.9rem' }}>
              last tick
            </div>
          </div>
          
          <div style={{
            backgroundColor: 'rgba(255, 255, 255, 0.98)',
            padding: '20px',
            borderRadius: '12px',
            border: '1px solid rgba(148, 163, 184, 0.28)'
          }}>
            <div style={{ color: '#334155', fontSize: '0.9rem', marginBottom: '8px', fontWeight: 600 }}>
              Open Interest
            </div>
            <div style={{ fontSize: '1.8rem', fontWeight: 'bold', color: '#0f172a', marginBottom: '8px' }}>
              {liveQuote?.open_interest != null ? liveQuote.open_interest.toLocaleString('en-IN') : '—'}
            </div>
            <div style={{ color: '#475569', fontSize: '0.9rem' }}>
              from quote
            </div>
          </div>
          
          <div style={{
            backgroundColor: 'rgba(255, 255, 255, 0.98)',
            padding: '20px',
            borderRadius: '12px',
            border: '1px solid rgba(148, 163, 184, 0.28)'
          }}>
            <div style={{ color: '#334155', fontSize: '0.9rem', marginBottom: '8px', fontWeight: 600 }}>
              Session range (OHLC)
            </div>
            <div style={{ fontSize: '1.15rem', fontWeight: 'bold', color: '#0f172a', marginBottom: '8px', lineHeight: 1.4 }}>
              {liveQuote?.low != null && liveQuote?.high != null
                ? `${formatInr(liveQuote.low)} – ${formatInr(liveQuote.high)}`
                : '—'}
            </div>
            <div style={{ color: '#334155', fontSize: '0.9rem', fontWeight: 500 }}>
              O {formatInr(liveQuote?.open)} · C {formatInr(liveQuote?.close)}
            </div>
          </div>
        </div>

        {/* Simple Chart Representation */}
        <div style={{
          backgroundColor: 'rgba(248, 250, 252, 0.98)',
          padding: '20px',
          borderRadius: '12px',
          border: '1px solid rgba(148, 163, 184, 0.22)',
          height: '200px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          position: 'relative'
        }}>
          <div style={{
            position: 'absolute',
            top: '10px',
            left: '10px',
            color: '#334155',
            fontSize: '0.9rem'
          }}>
            LTP stream (last {priceHistory.length} ticks)
          </div>
          {priceHistory.length < 2 ? (
            <div style={{ color: '#475569', fontSize: '0.9rem' }}>
              Collecting live prices… stay on this page a few seconds.
            </div>
          ) : (
            <div style={{
              display: 'flex',
              alignItems: 'end',
              gap: '4px',
              height: '120px',
              width: '100%',
              paddingLeft: '8px',
              paddingRight: '8px',
              boxSizing: 'border-box',
            }}>
              {priceHistory.map((pt, index) => {
                const h = 8 + ((pt.price - chartMin) / chartSpan) * 104
                const prev = index > 0 ? priceHistory[index - 1].price : pt.price
                const up = pt.price >= prev
                return (
                  <div
                    key={`${pt.t}-${index}`}
                    title={`${pt.t} ${pt.price}`}
                    style={{
                      flex: 1,
                      minWidth: '3px',
                      maxWidth: '12px',
                      height: `${h}px`,
                      backgroundColor: up ? '#22c55e' : '#ef4444',
                      borderRadius: '3px 3px 0 0',
                      opacity: 0.85,
                    }}
                  />
                )
              })}
            </div>
          )}
        </div>
      </div>

      {/* Portfolio Summary */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
        gap: '24px',
        marginBottom: '16px'
      }}>
        <div style={{
          background: 'linear-gradient(135deg, rgba(15,23,42,0.92), rgba(30,41,59,0.86))',
          border: '1px solid rgba(96, 165, 250, 0.24)',
          borderRadius: '14px',
          padding: '24px',
          boxShadow: '0 14px 30px rgba(2, 6, 23, 0.3)',
          transition: 'all 0.3s ease'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', marginBottom: '16px' }}>
            <div style={{
              width: '48px',
              height: '48px',
              background: 'linear-gradient(135deg, #3b82f6, #2563eb)',
              borderRadius: '12px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              marginRight: '16px',
              fontSize: '11px',
              fontWeight: 700,
              color: '#dbeafe'
            }}>
              VAL
            </div>
            <div>
              <h3 style={{ fontSize: '0.82rem', color: '#94a3b8', marginBottom: '4px' }}>
                Portfolio Value
              </h3>
              <p style={{ fontSize: '1.7rem', fontWeight: '700', color: '#f8fafc' }}>
                ₹{Number(totalValue || 0).toLocaleString('en-IN', { maximumFractionDigits: 2 })}
              </p>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', color: '#22c55e', fontSize: '0.9rem' }}>
            <span style={{ marginRight: '8px' }}>↑</span>
            {todayPnl >= 0 ? '+' : '-'}₹{Math.abs(todayPnl).toLocaleString('en-IN', { maximumFractionDigits: 2 })} today ({todayPct >= 0 ? '+' : ''}{todayPct.toFixed(2)}%)
          </div>
        </div>

        <div style={{
          background: 'linear-gradient(135deg, rgba(15,23,42,0.92), rgba(30,41,59,0.86))',
          border: '1px solid rgba(74, 222, 128, 0.22)',
          borderRadius: '14px',
          padding: '24px',
          boxShadow: '0 14px 30px rgba(2, 6, 23, 0.3)',
          transition: 'all 0.3s ease'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', marginBottom: '16px' }}>
            <div style={{
              width: '48px',
              height: '48px',
              background: 'linear-gradient(135deg, #22c55e, #16a34a)',
              borderRadius: '12px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              marginRight: '16px',
              fontSize: '11px',
              fontWeight: 700,
              color: '#dcfce7'
            }}>
              BAL
            </div>
            <div>
              <h3 style={{ fontSize: '0.82rem', color: '#94a3b8', marginBottom: '4px' }}>
                Available Balance
              </h3>
              <p style={{ fontSize: '1.7rem', fontWeight: '700', color: '#f8fafc' }}>
                ₹{Math.max(0, availableBalance).toLocaleString('en-IN', { maximumFractionDigits: 2 })}
              </p>
            </div>
          </div>
          <div style={{ color: '#cbd5e1', fontSize: '0.9rem' }}>
            {(totalValue > 0 ? (Math.max(0, availableBalance) / totalValue) * 100 : 0).toFixed(1)}% of portfolio
          </div>
          <div style={{ color: '#94a3b8', fontSize: '0.82rem', marginTop: '6px' }}>
            Used margin: ₹{usedMargin.toLocaleString('en-IN', { maximumFractionDigits: 2 })}
          </div>
        </div>

        <div style={{
          background: 'linear-gradient(135deg, rgba(15,23,42,0.92), rgba(30,41,59,0.86))',
          border: '1px solid rgba(167, 139, 250, 0.22)',
          borderRadius: '14px',
          padding: '24px',
          boxShadow: '0 14px 30px rgba(2, 6, 23, 0.3)',
          transition: 'all 0.3s ease'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', marginBottom: '16px' }}>
            <div style={{
              width: '48px',
              height: '48px',
              background: `linear-gradient(135deg, ${getStrategyColor()}, ${tradingStrategy === 'ml' ? '#2563eb' : '#6366f1'})`,
              borderRadius: '12px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              marginRight: '16px',
              fontSize: '11px',
              fontWeight: 700,
              color: '#ede9fe'
            }}>
              WIN
            </div>
            <div>
              <h3 style={{ fontSize: '0.82rem', color: '#94a3b8', marginBottom: '4px' }}>
                Win Rate
              </h3>
              <p style={{ fontSize: '1.7rem', fontWeight: '700', color: '#f8fafc' }}>
                {Number(selectedPerf?.win_rate || 0).toFixed(2)}%
              </p>
            </div>
          </div>
          <div style={{ color: '#cbd5e1', fontSize: '0.9rem' }}>
            {getStrategyName()} performance from persisted closed trades
          </div>
        </div>
      </div>

      {/* Performance Chart */}
      <div style={{
        background: 'linear-gradient(135deg, rgba(15,23,42,0.92), rgba(30,41,59,0.86))',
        border: '1px solid rgba(96, 165, 250, 0.2)',
        borderRadius: '14px',
        padding: '32px',
        boxShadow: '0 14px 30px rgba(2, 6, 23, 0.3)'
      }}>
        <h2 style={{
          fontSize: '1.5rem',
          fontWeight: '600',
          color: '#f8fafc',
          marginBottom: '24px',
          display: 'flex',
          alignItems: 'center',
          gap: '12px'
        }}>
          <span style={{ width: '10px', height: '10px', borderRadius: '50%', backgroundColor: '#2563eb', display: 'inline-block' }}></span>
          Portfolio Performance
        </h2>
        
        <div style={{
          backgroundColor: 'rgba(2, 6, 23, 0.38)',
          padding: '20px',
          borderRadius: '12px',
          border: '1px solid rgba(148, 163, 184, 0.22)',
          height: '250px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          position: 'relative'
        }}>
          <div style={{
            position: 'absolute',
            top: '10px',
            left: '10px',
            color: '#94a3b8',
            fontSize: '0.9rem'
          }}>
            Weekly Performance
          </div>
          <div style={{
            display: 'flex',
            alignItems: 'end',
            justifyContent: 'center',
            gap: '10px',
            height: '140px',
            width: '100%',
            maxWidth: '420px',
            margin: '0 auto',
            marginTop: '28px',
          }}>
            {performanceData.map((data, index) => (
              <div key={index} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '6px', flex: '0 0 auto' }}>
                <div
                  style={{
                    width: '22px',
                    height: `${weeklyBarHeight(data.value)}px`,
                    backgroundColor: '#3b82f6',
                    borderRadius: '4px 4px 0 0',
                    opacity: 0.85,
                    maxHeight: `${WEEKLY_BAR_MAX}px`,
                  }}
                ></div>
                <span style={{ color: '#94a3b8', fontSize: '0.75rem' }}>
                  {data.date}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <style>
        {`
        @keyframes dashboard-pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
      `}
      </style>
    </div>
  )
}

export default Dashboard
