import React, { useState, useEffect } from 'react'
import { useAuthStore } from '../stores/authStore'
const raw_api_url = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const INTEGRATION_BASE = raw_api_url.replace(/\/$/, '')

function Trading() {
  const {
    balanceAmount,
    tradingStrategy,
    user,
    lotAllocation,
    fetchSmartAllocation,
    startTradingSystem,
    stopTradingSystem,
    emergencyExitTradingSystem,
    manualResetTradingSystem,
    getTradingSystemStatus,
    updateStrategy,
    mlSystemActive,
    llmSystemActive,
    hybridSystemActive,
  } = useAuthStore()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [loadingStrategy, setLoadingStrategy] = useState(null)
  const [mlMetrics, setMlMetrics] = useState(null)
  const [llmMetrics, setLlmMetrics] = useState(null)
  const [hybridMetrics, setHybridMetrics] = useState(null)
  const [modelPerf, setModelPerf] = useState([
    { engine: 'ml', trades: 0, win_rate: 0, profit: 0, loss: 0 },
    { engine: 'llm', trades: 0, win_rate: 0, profit: 0, loss: 0 },
    { engine: 'hybrid', trades: 0, win_rate: 0, profit: 0, loss: 0 },
  ])

  // LLM Trading System Integration
  const startLLMTrading = async () => {
    try {
      setLoading(true)
      setLoadingStrategy('llm')
      setError(null)
      updateStrategy('llm')
      await startTradingSystem('llm')
      alert('LLM Trading System Started Successfully!')
    } catch (err) {
      setError(`LLM Trading Error: ${err.message || err}`)
      console.error('LLM Trading Error:', err)
    } finally {
      setLoading(false)
      setLoadingStrategy(null)
    }
  }

  // ML Trading System Integration
  const startHybridTrading = async () => {
    try {
      setLoading(true)
      setLoadingStrategy('hybrid')
      setError(null)
      updateStrategy('hybrid')
      await startTradingSystem('hybrid')
      alert('Hybrid Trading System Started Successfully! (ML proposes → LLM verifies)')
    } catch (err) {
      setError(`Hybrid Trading Error: ${err.message || err}`)
      console.error('Hybrid Trading Error:', err)
    } finally {
      setLoading(false)
      setLoadingStrategy(null)
    }
  }

  const stopHybridTrading = async () => {
    try {
      setLoading(true)
      setLoadingStrategy('hybrid-stop')
      setError(null)
      await stopTradingSystem('hybrid')
      alert('Hybrid Trading System Stopped')
    } catch (err) {
      setError(err?.message || 'Error stopping Hybrid Trading System')
      console.error('Stop Hybrid Trading Error:', err)
    } finally {
      setLoading(false)
      setLoadingStrategy(null)
    }
  }

  const startMLTrading = async () => {
    try {
      setLoading(true)
      setLoadingStrategy('ml')
      setError(null)
      updateStrategy('ml')
      await startTradingSystem('ml')
      alert('ML Trading System Started Successfully!')
    } catch (err) {
      setError(`ML Trading Error: ${err.message || err}`)
      console.error('ML Trading Error:', err)
    } finally {
      setLoading(false)
      setLoadingStrategy(null)
    }
  }

  const stopMLTrading = async () => {
    try {
      setLoading(true)
      setLoadingStrategy('ml-stop')
      setError(null)
      await stopTradingSystem('ml')
      alert('ML Trading System Stopped')
    } catch (err) {
      setError(err?.message || 'Error stopping ML Trading System')
      console.error('Stop ML Trading Error:', err)
    } finally {
      setLoading(false)
      setLoadingStrategy(null)
    }
  }

  const stopLLMTrading = async () => {
    try {
      setLoading(true)
      setLoadingStrategy('llm-stop')
      setError(null)
      await stopTradingSystem('llm')
      alert('LLM Trading System Stopped')
    } catch (err) {
      setError(err?.message || 'Error stopping LLM Trading System')
      console.error('Stop LLM Trading Error:', err)
    } finally {
      setLoading(false)
      setLoadingStrategy(null)
    }
  }

  const emergencyExitEngine = async (strategy) => {
    try {
      setLoading(true)
      setLoadingStrategy(`${strategy}-emergency`)
      setError(null)
      await emergencyExitTradingSystem(strategy)
      alert(`${strategy.toUpperCase()} emergency exit triggered`)
    } catch (err) {
      setError(err?.message || 'Emergency exit failed')
    } finally {
      setLoading(false)
      setLoadingStrategy(null)
    }
  }

  const resetEngineBlock = async (strategy) => {
    try {
      setLoading(true)
      setLoadingStrategy(`${strategy}-reset`)
      setError(null)
      await manualResetTradingSystem(strategy)
      alert(`${strategy.toUpperCase()} state machine reset`)
    } catch (err) {
      setError(err?.message || 'Manual reset failed')
    } finally {
      setLoading(false)
      setLoadingStrategy(null)
    }
  }

  useEffect(() => {
    fetchSmartAllocation().catch((err) => {
      setError(err?.message || 'Unable to fetch smart lot allocation')
    })
  }, [balanceAmount])

  // Sync UI with backend after refresh and poll periodically.
  useEffect(() => {
    let mounted = true
    const refreshStatus = async () => {
      try {
        const [ml, llm, hybrid] = await Promise.all([
          getTradingSystemStatus('ml'),
          getTradingSystemStatus('llm'),
          getTradingSystemStatus('hybrid'),
        ])
        if (!mounted) return
      } catch (_) {}
    }
    refreshStatus()
    const id = setInterval(refreshStatus, 5000)
    return () => {
      mounted = false
      clearInterval(id)
    }
  }, [])

  useEffect(() => {
    let mounted = true
    const refreshMetrics = async () => {
      try {
        const [mlRes, llmRes, hybridRes] = await Promise.all([
          fetch(`${INTEGRATION_BASE}/api/trading/metrics/ml`),
          fetch(`${INTEGRATION_BASE}/api/trading/metrics/llm`),
          fetch(`${INTEGRATION_BASE}/api/trading/metrics/hybrid`),
        ])
        const [mlJson, llmJson, hybridJson] = await Promise.all([
          mlRes.json().catch(() => ({})),
          llmRes.json().catch(() => ({})),
          hybridRes.json().catch(() => ({})),
        ])
        if (!mounted) return
        setMlMetrics(mlJson?.metrics || null)
        setLlmMetrics(llmJson?.metrics || null)
        setHybridMetrics(hybridJson?.metrics || null)
      } catch (_) {}
    }
    refreshMetrics()
    const id = setInterval(refreshMetrics, 5000)
    return () => {
      mounted = false
      clearInterval(id)
    }
  }, [])

  useEffect(() => {
    let mounted = true
    const refreshModelPerformance = async () => {
      try {
        const resp = await fetch(`${INTEGRATION_BASE}/api/trading/performance-summary`)
        const data = await resp.json().catch(() => ({}))
        if (!mounted) return
        if (resp.ok && Array.isArray(data?.models)) {
          setModelPerf(data.models)
        }
      } catch (_) {}
    }
    refreshModelPerformance()
    const id = setInterval(refreshModelPerformance, 10000)
    return () => {
      mounted = false
      clearInterval(id)
    }
  }, [])

  const activeEngineLabel = hybridSystemActive
    ? 'Hybrid (ML + LLM) Active'
    : mlSystemActive
      ? 'ML Model Active'
      : llmSystemActive
        ? 'LLM Powered Active'
        : 'No Engine Active'
  const fmtTime = (val) => (val ? new Date(val).toLocaleTimeString('en-IN', { hour12: false }) : '—')

  const getStrategyColor = () => {
    if (tradingStrategy === 'hybrid') return '#10b981'
    return tradingStrategy === 'ml' ? '#3b82f6' : '#8b5cf6'
  }

  const getStrategyIcon = () => {
    if (tradingStrategy === 'hybrid') return '🔀'
    return tradingStrategy === 'ml' ? '🤖' : '🧠'
  }

  const blockML = llmSystemActive || hybridSystemActive
  const blockLLM = mlSystemActive || hybridSystemActive
  const blockHybrid = mlSystemActive || llmSystemActive

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
            Trading System
          </h1>
          <p style={{ color: '#94a3b8', fontSize: '1rem' }}>
            Balance sets Silver / SilverM / SilverMIC via allocator; live Angel quotes feed ML, LLM, or Hybrid—ML proposes, LLM verifies (paper only)
          </p>
        </div>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          padding: '12px 20px',
          backgroundColor: `${getStrategyColor()}20`,
          borderRadius: '12px',
          border: `1px solid ${getStrategyColor()}`
        }}>
          <span style={{ fontSize: '1.2rem' }}>{getStrategyIcon()}</span>
          <span style={{ color: 'white', fontSize: '0.9rem', fontWeight: '500' }}>
            {activeEngineLabel}
          </span>
        </div>
      </div>

      {/* Error Display */}
      {error && (
        <div style={{
          backgroundColor: 'rgba(239, 68, 68, 0.1)',
          border: '1px solid rgba(239, 68, 68, 0.3)',
          borderRadius: '12px',
          padding: '16px',
          marginBottom: '24px',
          color: '#ef4444'
        }}>
          <strong>Error:</strong> {error}
        </div>
      )}

      {/* Model Comparison (ML vs LLM vs Hybrid) */}
      <div style={{
        backgroundColor: 'rgba(255, 255, 255, 0.05)',
        backdropFilter: 'blur(16px)',
        border: '1px solid rgba(255, 255, 255, 0.1)',
        borderRadius: '20px',
        padding: '20px',
        marginBottom: '24px',
      }}>
        <h3 style={{ color: 'white', fontSize: '1.1rem', marginBottom: '12px' }}>
          📊 Model Performance Comparison
        </h3>
        <p style={{ color: '#94a3b8', fontSize: '0.88rem', marginBottom: '14px' }}>
          Win%, total profit and total loss from closed trades (persisted history).
        </p>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '14px' }}>
          {modelPerf.map((m) => (
            <div key={m.engine} style={{
              backgroundColor: 'rgba(31, 41, 55, 0.5)',
              border: '1px solid rgba(75, 85, 99, 0.3)',
              borderRadius: '12px',
              padding: '14px',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '10px' }}>
                <strong style={{ color: 'white', textTransform: 'uppercase' }}>{m.engine}</strong>
                <span style={{ color: '#94a3b8', fontSize: '0.82rem' }}>Trades: {m.trades || 0}</span>
              </div>
              <div style={{ color: '#94a3b8', fontSize: '0.86rem', lineHeight: 1.75 }}>
                <div>Win%: <strong style={{ color: '#22c55e' }}>{Number(m.win_rate || 0).toFixed(2)}%</strong></div>
                <div>Profit: <strong style={{ color: '#22c55e' }}>₹{Number(m.profit || 0).toLocaleString('en-IN', { maximumFractionDigits: 2 })}</strong></div>
                <div>Loss: <strong style={{ color: '#ef4444' }}>₹{Number(m.loss || 0).toLocaleString('en-IN', { maximumFractionDigits: 2 })}</strong></div>
              </div>
              <div style={{ marginTop: '10px' }}>
                <div style={{ color: '#64748b', fontSize: '0.78rem', marginBottom: '4px' }}>Win%</div>
                <div style={{ height: '8px', backgroundColor: 'rgba(148, 163, 184, 0.2)', borderRadius: '999px', overflow: 'hidden' }}>
                  <div style={{
                    width: `${Math.max(0, Math.min(100, Number(m.win_rate || 0)))}%`,
                    height: '100%',
                    background: 'linear-gradient(90deg, #22c55e, #16a34a)',
                  }} />
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Live Engine Activity */}
      <div style={{
        backgroundColor: 'rgba(255, 255, 255, 0.05)',
        backdropFilter: 'blur(16px)',
        border: '1px solid rgba(255, 255, 255, 0.1)',
        borderRadius: '20px',
        padding: '20px',
        marginBottom: '24px',
      }}>
        <h3 style={{ color: 'white', fontSize: '1.1rem', marginBottom: '14px' }}>📡 Engine Activity (Live)</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '14px' }}>
          {[
            { key: 'ml', title: 'ML Engine', active: mlSystemActive, m: mlMetrics },
            { key: 'llm', title: 'LLM Engine', active: llmSystemActive, m: llmMetrics },
            { key: 'hybrid', title: 'Hybrid (ML → LLM verify)', active: hybridSystemActive, m: hybridMetrics },
          ].map((engine) => (
            <div
              key={engine.key}
              style={{
                backgroundColor: 'rgba(31, 41, 55, 0.5)',
                border: '1px solid rgba(75, 85, 99, 0.3)',
                borderRadius: '12px',
                padding: '14px',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '10px' }}>
                <strong style={{ color: 'white' }}>{engine.title}</strong>
                <span style={{ color: engine.active ? '#22c55e' : '#6b7280', fontSize: '0.8rem' }}>
                  {engine.active ? 'ACTIVE' : 'INACTIVE'}
                </span>
              </div>
              <div style={{ color: '#94a3b8', fontSize: '0.86rem', lineHeight: 1.65 }}>
                <div>Trade state: <strong style={{ color: 'white' }}>{engine.m?.trade_state || 'IDLE'}</strong></div>
                <div>Block reason: <strong style={{ color: 'white' }}>{engine.m?.block_reason || '—'}</strong></div>
                <div>Cooldown: <strong style={{ color: 'white' }}>
                  {engine.m?.cooldown_remaining_secs == null ? '—' : `${engine.m.cooldown_remaining_secs}s`}
                </strong></div>
                <div>Quote failures: <strong style={{ color: 'white' }}>{engine.m?.consecutive_quote_failures ?? 0}</strong></div>
                <div>Engine failures: <strong style={{ color: 'white' }}>{engine.m?.consecutive_engine_failures ?? 0}</strong></div>
                <div>Quotes processed: <strong style={{ color: 'white' }}>{engine.m?.quote_count ?? 0}</strong></div>
                <div>Signals generated: <strong style={{ color: 'white' }}>{engine.m?.signal_count ?? 0}</strong></div>
                <div>Last quote: <strong style={{ color: 'white' }}>{fmtTime(engine.m?.last_quote_at)}</strong></div>
                <div>Last signal: <strong style={{ color: 'white' }}>{fmtTime(engine.m?.last_signal_at)}</strong></div>
                <div>Last LTP: <strong style={{ color: 'white' }}>
                  {engine.m?.last_quote_ltp ? `₹${Number(engine.m.last_quote_ltp).toLocaleString('en-IN', { maximumFractionDigits: 2 })}` : '—'}
                </strong></div>
                <div>Signal action: <strong style={{ color: 'white' }}>{engine.m?.last_signal_action || '—'}</strong></div>
                <div>Last engine action: <strong style={{ color: 'white' }}>{engine.m?.last_engine_action || '—'}</strong></div>
                <div>Engine conf: <strong style={{ color: 'white' }}>
                  {engine.m?.last_engine_confidence == null
                    ? '—'
                    : engine.m?.engine === 'llm'
                      ? `${Number(engine.m.last_engine_confidence).toFixed(1)}%`
                      : `${(Number(engine.m.last_engine_confidence)*100).toFixed(1)}%`}
                </strong></div>
                <div>Engine reason: <strong style={{ color: 'white' }}>{engine.m?.last_engine_reason || '—'}</strong></div>
                <div>Engine reject: <strong style={{ color: 'white' }}>{engine.m?.last_engine_reject_reason || '—'}</strong></div>
                <div>Entry price: <strong style={{ color: 'white' }}>
                  {engine.m?.open_entry_price ? `₹${Number(engine.m.open_entry_price).toLocaleString('en-IN', { maximumFractionDigits: 2 })}` : '—'}
                </strong></div>
                <div>SL price: <strong style={{ color: 'white' }}>
                  {engine.m?.open_sl_price ? `₹${Number(engine.m.open_sl_price).toLocaleString('en-IN', { maximumFractionDigits: 2 })}` : '—'}
                </strong></div>
                <div>Target price: <strong style={{ color: 'white' }}>
                  {engine.m?.open_target_price ? `₹${Number(engine.m.open_target_price).toLocaleString('en-IN', { maximumFractionDigits: 2 })}` : '—'}
                </strong></div>
                <div>Price change vs entry: <strong style={{ color: (Number(engine.m?.price_change_since_entry ?? 0) >= 0 ? '#22c55e' : '#ef4444') }}>
                  ₹{Number(engine.m?.price_change_since_entry ?? 0).toLocaleString('en-IN', { maximumFractionDigits: 2 })}
                </strong></div>
                <div>Entries: <strong style={{ color: 'white' }}>{engine.m?.entries_count ?? 0}</strong></div>
                <div>Exits: <strong style={{ color: 'white' }}>{engine.m?.exits_count ?? 0}</strong></div>
                <div>State machine trades: <strong style={{ color: 'white' }}>{engine.m?.state_machine_history_count ?? 0}</strong></div>
                <div>Realized P&L: <strong style={{ color: (Number(engine.m?.realized_pnl ?? 0) >= 0 ? '#22c55e' : '#ef4444') }}>
                  ₹{Number(engine.m?.realized_pnl ?? 0).toLocaleString('en-IN', { maximumFractionDigits: 2 })}
                </strong></div>
                <div>Open P&L: <strong style={{ color: (Number(engine.m?.unrealized_pnl ?? 0) >= 0 ? '#22c55e' : '#ef4444') }}>
                  ₹{Number(engine.m?.unrealized_pnl ?? 0).toLocaleString('en-IN', { maximumFractionDigits: 2 })}
                </strong></div>
                <div>Total P&L: <strong style={{ color: (Number(engine.m?.total_pnl ?? 0) >= 0 ? '#22c55e' : '#ef4444') }}>
                  ₹{Number(engine.m?.total_pnl ?? 0).toLocaleString('en-IN', { maximumFractionDigits: 2 })}
                </strong></div>
                {engine.m?.state_machine_trade && (
                  <div style={{ marginTop: '8px', paddingTop: '8px', borderTop: '1px solid rgba(148, 163, 184, 0.15)' }}>
                    <div>Trade ID: <strong style={{ color: 'white' }}>{engine.m.state_machine_trade.id}</strong></div>
                    <div>Trade dir: <strong style={{ color: 'white' }}>{engine.m.state_machine_trade.direction}</strong></div>
                    <div>Trade status: <strong style={{ color: 'white' }}>{engine.m.state_machine_trade.status}</strong></div>
                    <div>Trade notes: <strong style={{ color: 'white' }}>
                      {(engine.m.state_machine_trade.notes || []).slice(-2).join(' | ') || '—'}
                    </strong></div>
                  </div>
                )}
                {engine.active && (
                  <div style={{ display: 'flex', gap: '8px', marginTop: '10px', flexWrap: 'wrap' }}>
                    <button
                      onClick={() => emergencyExitEngine(engine.key)}
                      disabled={loading}
                      style={{
                        padding: '8px 10px',
                        background: 'linear-gradient(135deg, #f97316, #ea580c)',
                        color: 'white',
                        border: 'none',
                        borderRadius: '8px',
                        cursor: loading ? 'not-allowed' : 'pointer',
                        opacity: loading ? 0.7 : 1,
                      }}
                    >
                      {loading && loadingStrategy === `${engine.key}-emergency` ? 'Exiting...' : 'Emergency Exit'}
                    </button>
                    <button
                      onClick={() => resetEngineBlock(engine.key)}
                      disabled={loading || engine.m?.trade_state !== 'BLOCKED'}
                      style={{
                        padding: '8px 10px',
                        background: 'linear-gradient(135deg, #14b8a6, #0f766e)',
                        color: 'white',
                        border: 'none',
                        borderRadius: '8px',
                        cursor: (loading || engine.m?.trade_state !== 'BLOCKED') ? 'not-allowed' : 'pointer',
                        opacity: (loading || engine.m?.trade_state !== 'BLOCKED') ? 0.7 : 1,
                      }}
                    >
                      {loading && loadingStrategy === `${engine.key}-reset` ? 'Resetting...' : 'Manual Reset'}
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Smart Allocation Results */}
      {lotAllocation && (
        <div style={{
          backgroundColor: 'rgba(255, 255, 255, 0.05)',
          backdropFilter: 'blur(16px)',
          border: '1px solid rgba(255, 255, 255, 0.1)',
          borderRadius: '20px',
          padding: '32px',
          marginBottom: '32px',
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
            <span style={{ fontSize: '1.5rem' }}>🎯</span>
            Smart Lot Allocation
          </h2>
          {(lotAllocation.summary?.allocation_symbol_type || lotAllocation.buy_orders?.[0]?.contract) && (
            <p style={{ color: '#94a3b8', fontSize: '0.9rem', marginTop: '-16px', marginBottom: '20px' }}>
              Instrument: <strong style={{ color: '#e2e8f0' }}>{lotAllocation.buy_orders?.[0]?.contract || '—'}</strong>
              {lotAllocation.summary?.allocation_symbol_type ? (
                <> · Tier: <strong style={{ color: '#e2e8f0' }}>{lotAllocation.summary.allocation_symbol_type}</strong></>
              ) : null}
              {lotAllocation.summary?.symbol_cascade_note ? (
                <span style={{ display: 'block', marginTop: '8px', fontSize: '0.85rem' }}>{lotAllocation.summary.symbol_cascade_note}</span>
              ) : null}
            </p>
          )}
          
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
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
                Available Capital
              </div>
              <div style={{ fontSize: '1.8rem', fontWeight: 'bold', color: 'white', marginBottom: '8px' }}>
                ₹{lotAllocation.summary.available_capital.toLocaleString()}
              </div>
              <div style={{ color: '#6b7280', fontSize: '0.8rem' }}>
                Total trading capital
              </div>
            </div>
            
            <div style={{
              backgroundColor: 'rgba(31, 41, 55, 0.5)',
              padding: '20px',
              borderRadius: '12px',
              border: '1px solid rgba(75, 85, 99, 0.3)'
            }}>
              <div style={{ color: '#94a3b8', fontSize: '0.9rem', marginBottom: '8px' }}>
                Volatility Level
              </div>
              <div style={{ 
                fontSize: '1.8rem', 
                fontWeight: 'bold', 
                color: lotAllocation.summary.volatility_level === 'HIGH' ? '#ef4444' : 
                        lotAllocation.summary.volatility_level === 'NORMAL' ? '#f59e0b' : '#22c55e',
                marginBottom: '8px' 
              }}>
                {lotAllocation.summary.volatility_level}
              </div>
              <div style={{ color: '#6b7280', fontSize: '0.8rem' }}>
                Risk assessment
              </div>
            </div>
            
            <div style={{
              backgroundColor: 'rgba(31, 41, 55, 0.5)',
              padding: '20px',
              borderRadius: '12px',
              border: '1px solid rgba(75, 85, 99, 0.3)'
            }}>
              <div style={{ color: '#94a3b8', fontSize: '0.9rem', marginBottom: '8px' }}>
                Risk Percentage
              </div>
              <div style={{ fontSize: '1.8rem', fontWeight: 'bold', color: 'white', marginBottom: '8px' }}>
                {lotAllocation.summary.risk_pct_used}
              </div>
              <div style={{ color: '#6b7280', fontSize: '0.8rem' }}>
                Of capital deployed
              </div>
            </div>
            
            <div style={{
              backgroundColor: 'rgba(31, 41, 55, 0.5)',
              padding: '20px',
              borderRadius: '12px',
              border: '1px solid rgba(75, 85, 99, 0.3)'
            }}>
              <div style={{ color: '#94a3b8', fontSize: '0.9rem', marginBottom: '8px' }}>
                Total Lots
              </div>
              <div style={{ fontSize: '1.8rem', fontWeight: 'bold', color: 'white', marginBottom: '8px' }}>
                {lotAllocation.summary.total_lots}
              </div>
              <div style={{ color: '#6b7280', fontSize: '0.8rem' }}>
                Across all contracts
              </div>
            </div>
          </div>

          {/* Buy Orders */}
          <div style={{ marginBottom: '24px' }}>
            <h3 style={{
              fontSize: '1.2rem',
              fontWeight: '500',
              color: 'white',
              marginBottom: '16px'
            }}>
              📋 Recommended Positions
            </h3>
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
              gap: '16px'
            }}>
              {lotAllocation.buy_orders.map((order, index) => (
                <div key={index} style={{
                  backgroundColor: 'rgba(34, 197, 94, 0.1)',
                  border: '1px solid rgba(34, 197, 94, 0.3)',
                  borderRadius: '12px',
                  padding: '16px'
                }}>
                  <div style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    marginBottom: '12px'
                  }}>
                    <span style={{
                      fontSize: '1.1rem',
                      fontWeight: '500',
                      color: 'white'
                    }}>
                      {order.contract}
                    </span>
                    <span style={{
                      fontSize: '0.9rem',
                      color: '#22c55e',
                      backgroundColor: 'rgba(34, 197, 94, 0.2)',
                      padding: '4px 8px',
                      borderRadius: '6px'
                    }}>
                      {order.lots} lots
                    </span>
                  </div>
                  <div style={{ fontSize: '0.9rem', color: '#94a3b8', marginBottom: '8px' }}>
                    <div>Price: ₹{order.ltp.toLocaleString()}</div>
                    <div>Margin: ₹{order.margin_per_lot.toLocaleString()}/lot</div>
                    <div>Exposure: ₹{order.exposure_value.toLocaleString()}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Summary */}
          <div style={{
            backgroundColor: 'rgba(59, 130, 246, 0.1)',
            border: '1px solid rgba(59, 130, 246, 0.3)',
            borderRadius: '12px',
            padding: '16px',
            fontSize: '0.9rem',
            color: '#94a3b8',
            lineHeight: '1.6'
          }}>
            <strong>💡 Reasoning:</strong> {lotAllocation.summary.reasoning}
          </div>
        </div>
      )}

      {/* Trading System Controls */}
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
          <span style={{ fontSize: '1.5rem' }}>🚀</span>
          AI Trading System
        </h2>
        
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
          gap: '24px'
        }}>
          {/* ML Trading */}
          <div style={{
            backgroundColor: 'rgba(31, 41, 55, 0.5)',
            padding: '24px',
            borderRadius: '16px',
            border: '1px solid rgba(75, 85, 99, 0.3)',
            textAlign: 'center'
          }}>
            <div style={{
              fontSize: '3rem',
              marginBottom: '16px'
            }}>
              🤖
            </div>
            <h3 style={{
              fontSize: '1.3rem',
              fontWeight: '600',
              color: 'white',
              marginBottom: '12px'
            }}>
              ML Model Trading
            </h3>
            <p style={{
              color: '#94a3b8',
              fontSize: '0.9rem',
              marginBottom: '20px',
              lineHeight: '1.5'
            }}>
              Advanced machine learning algorithms with technical indicators for systematic trading
            </p>
            <button
              onClick={startMLTrading}
              disabled={loading || mlSystemActive || blockML}
              style={{
                width: '100%',
                padding: '16px 24px',
                background: (!mlSystemActive && !blockML) ? 
                  'linear-gradient(135deg, #3b82f6, #2563eb)' : 
                  'linear-gradient(135deg, #6b7280, #4b5563)',
                color: 'white',
                border: 'none',
                borderRadius: '12px',
                fontSize: '1rem',
                fontWeight: '500',
                cursor: (loading || mlSystemActive || blockML) ? 'not-allowed' : 'pointer',
                opacity: (loading || mlSystemActive || blockML) ? 0.7 : 1,
                transition: 'all 0.2s ease',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '8px'
              }}
              onMouseOver={(e) => {
                if (!loading && !mlSystemActive && !blockML) {
                  e.target.style.background = 'linear-gradient(135deg, #2563eb, #1d4ed8)'
                  e.target.style.transform = 'translateY(-2px)'
                }
              }}
              onMouseOut={(e) => {
                if (!loading && !mlSystemActive && !blockML) {
                  e.target.style.background = 'linear-gradient(135deg, #3b82f6, #2563eb)'
                  e.target.style.transform = 'translateY(0)'
                }
              }}
            >
              {loading && loadingStrategy === 'ml' ? (
                <>
                  <div style={{
                    width: '20px',
                    height: '20px',
                    border: '2px solid rgba(255, 255, 255, 0.3)',
                    borderTop: '2px solid white',
                    borderRadius: '50%',
                    animation: 'spin 1s linear infinite'
                  }}></div>
                  Starting ML System...
                </>
              ) : mlSystemActive ? (
                <>
                  <span>✅</span>
                  ML System Active
                </>
              ) : (
                <>
                  <span>🤖</span>
                  Start ML Trading
                </>
              )}
            </button>
            {mlSystemActive && (
              <button
                onClick={stopMLTrading}
                disabled={loading}
                style={{
                  width: '100%',
                  marginTop: '10px',
                  padding: '12px 16px',
                  background: 'linear-gradient(135deg, #ef4444, #dc2626)',
                  color: 'white',
                  border: 'none',
                  borderRadius: '10px',
                  fontSize: '0.95rem',
                  fontWeight: '500',
                  cursor: loading ? 'not-allowed' : 'pointer',
                  opacity: loading ? 0.7 : 1,
                }}
              >
                {loading && loadingStrategy === 'ml-stop' ? 'Stopping ML System...' : 'Stop ML Trading'}
              </button>
            )}
          </div>

          {/* LLM Trading */}
          <div style={{
            backgroundColor: 'rgba(31, 41, 55, 0.5)',
            padding: '24px',
            borderRadius: '16px',
            border: '1px solid rgba(75, 85, 99, 0.3)',
            textAlign: 'center'
          }}>
            <div style={{
              fontSize: '3rem',
              marginBottom: '16px'
            }}>
              🧠
            </div>
            <h3 style={{
              fontSize: '1.3rem',
              fontWeight: '600',
              color: 'white',
              marginBottom: '12px'
            }}>
              LLM Powered Trading
            </h3>
            <p style={{
              color: '#94a3b8',
              fontSize: '0.9rem',
              marginBottom: '20px',
              lineHeight: '1.5'
            }}>
              Language model with market analysis and adaptive decision making
            </p>
            <button
              onClick={startLLMTrading}
              disabled={loading || llmSystemActive || blockLLM}
              style={{
                width: '100%',
                padding: '16px 24px',
                background: (!llmSystemActive && !blockLLM) ? 
                  'linear-gradient(135deg, #8b5cf6, #6366f1)' : 
                  'linear-gradient(135deg, #6b7280, #4b5563)',
                color: 'white',
                border: 'none',
                borderRadius: '12px',
                fontSize: '1rem',
                fontWeight: '500',
                cursor: (loading || llmSystemActive || blockLLM) ? 'not-allowed' : 'pointer',
                opacity: (loading || llmSystemActive || blockLLM) ? 0.7 : 1,
                transition: 'all 0.2s ease',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '8px'
              }}
              onMouseOver={(e) => {
                if (!loading && !llmSystemActive && !blockLLM) {
                  e.target.style.background = 'linear-gradient(135deg, #6366f1, #4f46e5)'
                  e.target.style.transform = 'translateY(-2px)'
                }
              }}
              onMouseOut={(e) => {
                if (!loading && !llmSystemActive && !blockLLM) {
                  e.target.style.background = 'linear-gradient(135deg, #8b5cf6, #6366f1)'
                  e.target.style.transform = 'translateY(0)'
                }
              }}
            >
              {loading && loadingStrategy === 'llm' ? (
                <>
                  <div style={{
                    width: '20px',
                    height: '20px',
                    border: '2px solid rgba(255, 255, 255, 0.3)',
                    borderTop: '2px solid white',
                    borderRadius: '50%',
                    animation: 'spin 1s linear infinite'
                  }}></div>
                  Starting LLM System...
                </>
              ) : llmSystemActive ? (
                <>
                  <span>✅</span>
                  LLM System Active
                </>
              ) : (
                <>
                  <span>🧠</span>
                  Start LLM Trading
                </>
              )}
            </button>
            {llmSystemActive && (
              <button
                onClick={stopLLMTrading}
                disabled={loading}
                style={{
                  width: '100%',
                  marginTop: '10px',
                  padding: '12px 16px',
                  background: 'linear-gradient(135deg, #ef4444, #dc2626)',
                  color: 'white',
                  border: 'none',
                  borderRadius: '10px',
                  fontSize: '0.95rem',
                  fontWeight: '500',
                  cursor: loading ? 'not-allowed' : 'pointer',
                  opacity: loading ? 0.7 : 1,
                }}
              >
                {loading && loadingStrategy === 'llm-stop' ? 'Stopping LLM System...' : 'Stop LLM Trading'}
              </button>
            )}
          </div>

          {/* Hybrid: ML proposes, LLM verifies */}
          <div style={{
            backgroundColor: 'rgba(31, 41, 55, 0.5)',
            padding: '24px',
            borderRadius: '16px',
            border: '1px solid rgba(16, 185, 129, 0.35)',
            textAlign: 'center'
          }}>
            <div style={{ fontSize: '3rem', marginBottom: '16px' }}>🔀</div>
            <h3 style={{
              fontSize: '1.3rem',
              fontWeight: '600',
              color: 'white',
              marginBottom: '12px'
            }}>
              Hybrid (ML + LLM)
            </h3>
            <p style={{
              color: '#94a3b8',
              fontSize: '0.9rem',
              marginBottom: '20px',
              lineHeight: '1.5'
            }}>
              ML generates BUY/SELL; each proposal is verified by the LLM before paper execution. Stop-loss / take-profit auto-exits still apply.
            </p>
            <button
              onClick={startHybridTrading}
              disabled={loading || hybridSystemActive || blockHybrid}
              style={{
                width: '100%',
                padding: '16px 24px',
                background: (!hybridSystemActive && !blockHybrid)
                  ? 'linear-gradient(135deg, #10b981, #059669)'
                  : 'linear-gradient(135deg, #6b7280, #4b5563)',
                color: 'white',
                border: 'none',
                borderRadius: '12px',
                fontSize: '1rem',
                fontWeight: '500',
                cursor: (loading || hybridSystemActive || blockHybrid) ? 'not-allowed' : 'pointer',
                opacity: (loading || hybridSystemActive || blockHybrid) ? 0.7 : 1,
                transition: 'all 0.2s ease',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '8px'
              }}
              onMouseOver={(e) => {
                if (!loading && !hybridSystemActive && !blockHybrid) {
                  e.target.style.background = 'linear-gradient(135deg, #059669, #047857)'
                  e.target.style.transform = 'translateY(-2px)'
                }
              }}
              onMouseOut={(e) => {
                if (!loading && !hybridSystemActive && !blockHybrid) {
                  e.target.style.background = 'linear-gradient(135deg, #10b981, #059669)'
                  e.target.style.transform = 'translateY(0)'
                }
              }}
            >
              {loading && loadingStrategy === 'hybrid' ? (
                <>
                  <div style={{
                    width: '20px',
                    height: '20px',
                    border: '2px solid rgba(255, 255, 255, 0.3)',
                    borderTop: '2px solid white',
                    borderRadius: '50%',
                    animation: 'spin 1s linear infinite'
                  }}></div>
                  Starting Hybrid...
                </>
              ) : hybridSystemActive ? (
                <>
                  <span>✅</span>
                  Hybrid Active
                </>
              ) : (
                <>
                  <span>🔀</span>
                  Start Hybrid Trading
                </>
              )}
            </button>
            {hybridSystemActive && (
              <button
                onClick={stopHybridTrading}
                disabled={loading}
                style={{
                  width: '100%',
                  marginTop: '10px',
                  padding: '12px 16px',
                  background: 'linear-gradient(135deg, #ef4444, #dc2626)',
                  color: 'white',
                  border: 'none',
                  borderRadius: '10px',
                  fontSize: '0.95rem',
                  fontWeight: '500',
                  cursor: loading ? 'not-allowed' : 'pointer',
                  opacity: loading ? 0.7 : 1,
                }}
              >
                {loading && loadingStrategy === 'hybrid-stop' ? 'Stopping Hybrid...' : 'Stop Hybrid Trading'}
              </button>
            )}
          </div>
        </div>

        {/* System Status */}
        <div style={{
          marginTop: '24px',
          padding: '16px',
          backgroundColor: 'rgba(34, 197, 94, 0.1)',
          border: '1px solid rgba(34, 197, 94, 0.3)',
          borderRadius: '12px',
          fontSize: '0.9rem',
          color: '#94a3b8'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
            <div style={{
              width: '8px',
              height: '8px',
              backgroundColor: '#22c55e',
              borderRadius: '50%',
              animation: 'pulse 2s infinite'
            }}></div>
            <span>Systems Ready</span>
          </div>
          <div style={{ fontSize: '0.8rem' }}>
            Smart Allocator API: <strong>http://localhost:5000</strong> | 
            Trading Integration: <strong>http://localhost:8001</strong>
          </div>
        </div>
      </div>

      <style jsx>{`
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
      `}</style>
    </div>
  )
}

export default Trading
