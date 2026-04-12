import React, { useState, useEffect, useRef, useCallback } from 'react'
import { useAuthStore } from '../stores/authStore'

const INTEGRATION_BASE = 'http://localhost:8001'
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
  } = useAuthStore()

  const [liveQuote, setLiveQuote] = useState(null)
  const [priceHistory, setPriceHistory] = useState([])
  const [liveError, setLiveError] = useState(null)
  const [liveLoading, setLiveLoading] = useState(true)
  const intervalRef = useRef(null)

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

  // Mock portfolio data based on user balance
  const portfolioData = {
    portfolio: {
      total_value: balanceAmount || 100000,
      available_balance: Math.floor((balanceAmount || 100000) * 0.85),
      invested_amount: Math.floor((balanceAmount || 100000) * 0.15),
      today_pnl: Math.floor((balanceAmount || 100000) * 0.004), // 0.4% daily
      total_pnl: Math.floor((balanceAmount || 100000) * 0.025), // 2.5% total
      win_rate: tradingStrategy === 'ml' ? 65 : 58, // ML has better win rate
      strategy: tradingStrategy
    }
  }

  const performanceData = [
    { date: 'Mon', value: (balanceAmount || 100000) * 0.95 },
    { date: 'Tue', value: (balanceAmount || 100000) * 0.97 },
    { date: 'Wed', value: (balanceAmount || 100000) * 0.96 },
    { date: 'Thu', value: (balanceAmount || 100000) * 0.98 },
    { date: 'Fri', value: balanceAmount || 100000 }
  ]

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

  const getStrategyIcon = () => {
    return tradingStrategy === 'ml' ? '🤖' : '🧠'
  }

  const getStrategyName = () => {
    return tradingStrategy === 'ml' ? 'ML Model' : 'LLM Powered'
  }

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

  return (
    <div style={{
      backgroundColor: '#0f172a',
      backgroundImage: 'linear-gradient(135deg, #1e293b 0%, #0f172a 100%)',
      color: 'white',
      minHeight: '100vh',
      padding: '20px',
      fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, sans-serif'
    }}>
      {/* Header */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '32px',
        padding: '0 8px'
      }}>
        <div>
          <h1 style={{
            fontSize: '2.5rem',
            fontWeight: 'bold',
            color: 'white',
            marginBottom: '8px',
            letterSpacing: '-0.025em'
          }}>
            Trading Dashboard
          </h1>
          <p style={{ color: '#94a3b8', fontSize: '1rem' }}>
            Real-time market overview and portfolio management
          </p>
        </div>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          padding: '12px 20px',
          backgroundColor: 'rgba(34, 197, 94, 0.1)',
          border: '1px solid rgba(34, 197, 94, 0.3)',
          borderRadius: '12px',
          backdropFilter: 'blur(16px)'
        }}>
          <div style={{
            width: '8px',
            height: '8px',
            backgroundColor: '#22c55e',
            borderRadius: '50%',
            animation: 'pulse 2s infinite'
          }}></div>
          <span style={{ color: liveError ? '#f59e0b' : '#22c55e', fontSize: '0.9rem', fontWeight: '500' }}>
            {liveError ? 'Live (degraded)' : 'Live Market'}
          </span>
        </div>
      </div>

      {/* User Info Card */}
      <div style={{
        backgroundColor: 'rgba(255, 255, 255, 0.05)',
        backdropFilter: 'blur(16px)',
        border: '1px solid rgba(255, 255, 255, 0.1)',
        borderRadius: '20px',
        padding: '24px',
        marginBottom: '32px',
        boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)'
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
            color: 'white',
            display: 'flex',
            alignItems: 'center',
            gap: '12px'
          }}>
            <span style={{ fontSize: '1.5rem' }}>{getStrategyIcon()}</span>
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
            <span style={{ fontSize: '1.2rem' }}>{getStrategyIcon()}</span>
            <span style={{ color: 'white', fontSize: '0.9rem', fontWeight: '500' }}>
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
            <div style={{ color: '#94a3b8', fontSize: '0.9rem', marginBottom: '4px' }}>
              Trading Balance
            </div>
            <div style={{ fontSize: '1.8rem', fontWeight: 'bold', color: 'white' }}>
              ₹{balanceAmount.toLocaleString()}
            </div>
          </div>
          <div>
            <div style={{ color: '#94a3b8', fontSize: '0.9rem', marginBottom: '4px' }}>
              Strategy Type
            </div>
            <div style={{ fontSize: '1.2rem', fontWeight: 'bold', color: getStrategyColor() }}>
              {getStrategyName()}
            </div>
          </div>
          <div>
            <div style={{ color: '#94a3b8', fontSize: '0.9rem', marginBottom: '4px' }}>
              Max Position Size
            </div>
            <div style={{ fontSize: '1.2rem', fontWeight: 'bold', color: 'white' }}>
              {allocatedLots != null ? `${allocatedLots} lots` : '—'}
            </div>
          </div>
        </div>
      </div>

      {/* Market Overview */}
      <div style={{
        backgroundColor: 'rgba(255, 255, 255, 0.05)',
        backdropFilter: 'blur(16px)',
        border: '1px solid rgba(255, 255, 255, 0.1)',
        borderRadius: '20px',
        padding: '32px',
        boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)'
      }}>
        <h2 style={{
          fontSize: '1.5rem',
          fontWeight: '600',
          color: 'white',
          marginBottom: '8px',
          display: 'flex',
          alignItems: 'center',
          gap: '12px'
        }}>
          <span style={{ fontSize: '1.5rem' }}>📊</span>
          Market Overview
        </h2>
        <p style={{ color: '#94a3b8', fontSize: '0.85rem', marginBottom: '20px' }}>
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
            backgroundColor: 'rgba(31, 41, 55, 0.5)',
            padding: '20px',
            borderRadius: '12px',
            border: '1px solid rgba(75, 85, 99, 0.3)'
          }}>
            <div style={{ color: '#94a3b8', fontSize: '0.9rem', marginBottom: '8px' }}>
              LTP
            </div>
            <div style={{ fontSize: '1.8rem', fontWeight: 'bold', color: 'white', marginBottom: '8px' }}>
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
            backgroundColor: 'rgba(31, 41, 55, 0.5)',
            padding: '20px',
            borderRadius: '12px',
            border: '1px solid rgba(75, 85, 99, 0.3)'
          }}>
            <div style={{ color: '#94a3b8', fontSize: '0.9rem', marginBottom: '8px' }}>
              Volume
            </div>
            <div style={{ fontSize: '1.8rem', fontWeight: 'bold', color: 'white', marginBottom: '8px' }}>
              {liveQuote?.volume != null ? liveQuote.volume.toLocaleString('en-IN') : '—'}
            </div>
            <div style={{ color: '#6b7280', fontSize: '0.9rem' }}>
              last tick
            </div>
          </div>
          
          <div style={{
            backgroundColor: 'rgba(31, 41, 55, 0.5)',
            padding: '20px',
            borderRadius: '12px',
            border: '1px solid rgba(75, 85, 99, 0.3)'
          }}>
            <div style={{ color: '#94a3b8', fontSize: '0.9rem', marginBottom: '8px' }}>
              Open Interest
            </div>
            <div style={{ fontSize: '1.8rem', fontWeight: 'bold', color: 'white', marginBottom: '8px' }}>
              {liveQuote?.open_interest != null ? liveQuote.open_interest.toLocaleString('en-IN') : '—'}
            </div>
            <div style={{ color: '#6b7280', fontSize: '0.9rem' }}>
              from quote
            </div>
          </div>
          
          <div style={{
            backgroundColor: 'rgba(31, 41, 55, 0.5)',
            padding: '20px',
            borderRadius: '12px',
            border: '1px solid rgba(75, 85, 99, 0.3)'
          }}>
            <div style={{ color: '#94a3b8', fontSize: '0.9rem', marginBottom: '8px' }}>
              Session range (OHLC)
            </div>
            <div style={{ fontSize: '1.15rem', fontWeight: 'bold', color: 'white', marginBottom: '8px', lineHeight: 1.4 }}>
              {liveQuote?.low != null && liveQuote?.high != null
                ? `${formatInr(liveQuote.low)} – ${formatInr(liveQuote.high)}`
                : '—'}
            </div>
            <div style={{ color: '#6b7280', fontSize: '0.9rem' }}>
              O {formatInr(liveQuote?.open)} · C {formatInr(liveQuote?.close)}
            </div>
          </div>
        </div>

        {/* Simple Chart Representation */}
        <div style={{
          backgroundColor: 'rgba(31, 41, 55, 0.3)',
          padding: '20px',
          borderRadius: '12px',
          border: '1px solid rgba(75, 85, 99, 0.2)',
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
            color: '#6b7280',
            fontSize: '0.9rem'
          }}>
            LTP stream (last {priceHistory.length} ticks)
          </div>
          {priceHistory.length < 2 ? (
            <div style={{ color: '#6b7280', fontSize: '0.9rem' }}>
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
        marginBottom: '32px'
      }}>
        <div style={{
          backgroundColor: 'rgba(255, 255, 255, 0.05)',
          backdropFilter: 'blur(16px)',
          border: '1px solid rgba(255, 255, 255, 0.1)',
          borderRadius: '20px',
          padding: '24px',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
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
              fontSize: '24px'
            }}>
              💰
            </div>
            <div>
              <h3 style={{ fontSize: '0.9rem', color: '#9ca3af', marginBottom: '4px' }}>
                Portfolio Value
              </h3>
              <p style={{ fontSize: '1.8rem', fontWeight: 'bold', color: 'white' }}>
                ₹{portfolioData.portfolio.total_value.toLocaleString()}
              </p>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', color: '#22c55e', fontSize: '0.9rem' }}>
            <span style={{ marginRight: '8px' }}>↑</span>
            +₹{portfolioData.portfolio.today_pnl} today (+{((portfolioData.portfolio.today_pnl / portfolioData.portfolio.total_value) * 100).toFixed(2)}%)
          </div>
        </div>

        <div style={{
          backgroundColor: 'rgba(255, 255, 255, 0.05)',
          backdropFilter: 'blur(16px)',
          border: '1px solid rgba(255, 255, 255, 0.1)',
          borderRadius: '20px',
          padding: '24px',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
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
              fontSize: '24px'
            }}>
              💵
            </div>
            <div>
              <h3 style={{ fontSize: '0.9rem', color: '#9ca3af', marginBottom: '4px' }}>
                Available Balance
              </h3>
              <p style={{ fontSize: '1.8rem', fontWeight: 'bold', color: 'white' }}>
                ₹{portfolioData.portfolio.available_balance.toLocaleString()}
              </p>
            </div>
          </div>
          <div style={{ color: '#6b7280', fontSize: '0.9rem' }}>
            {((portfolioData.portfolio.available_balance / portfolioData.portfolio.total_value) * 100).toFixed(1)}% of portfolio
          </div>
        </div>

        <div style={{
          backgroundColor: 'rgba(255, 255, 255, 0.05)',
          backdropFilter: 'blur(16px)',
          border: '1px solid rgba(255, 255, 255, 0.1)',
          borderRadius: '20px',
          padding: '24px',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
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
              fontSize: '24px'
            }}>
              {getStrategyIcon()}
            </div>
            <div>
              <h3 style={{ fontSize: '0.9rem', color: '#9ca3af', marginBottom: '4px' }}>
                Win Rate
              </h3>
              <p style={{ fontSize: '1.8rem', fontWeight: 'bold', color: 'white' }}>
                {portfolioData.portfolio.win_rate}%
              </p>
            </div>
          </div>
          <div style={{ color: '#6b7280', fontSize: '0.9rem' }}>
            {tradingStrategy === 'ml' ? 'ML Model Performance' : 'LLM Performance'}
          </div>
        </div>
      </div>

      {/* Performance Chart */}
      <div style={{
        backgroundColor: 'rgba(255, 255, 255, 0.05)',
        backdropFilter: 'blur(16px)',
        border: '1px solid rgba(255, 255, 255, 0.1)',
        borderRadius: '20px',
        padding: '32px',
        boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)'
      }}>
        <h2 style={{
          fontSize: '1.5rem',
          fontWeight: '600',
          color: 'white',
          marginBottom: '24px',
          display: 'flex',
          alignItems: 'center',
          gap: '12px'
        }}>
          <span style={{ fontSize: '1.5rem' }}>📊</span>
          Portfolio Performance
        </h2>
        
        <div style={{
          backgroundColor: 'rgba(31, 41, 55, 0.3)',
          padding: '20px',
          borderRadius: '12px',
          border: '1px solid rgba(75, 85, 99, 0.2)',
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
            color: '#6b7280',
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
                <span style={{ color: '#6b7280', fontSize: '0.75rem' }}>
                  {data.date}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <style jsx>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
      `}</style>
    </div>
  )
}

export default Dashboard
