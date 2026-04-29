import React, { useState, useEffect, useCallback } from 'react'
import { useAuthStore } from '../stores/authStore'

const INTEGRATION_BASE = import.meta.env.VITE_INTEGRATION_URL || 'http://localhost:8001'

function fmtPrice(v) {
  if (v === undefined || v === null || v === '') return '—'
  const n = Number(v)
  if (Number.isNaN(n)) return String(v)
  return `₹${n.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function fmtTs(v) {
  if (!v) return '—'
  const s = String(v)
  return s.replace('T', ' ').slice(0, 19)
}

function History() {
  const { tradingStrategy, user } = useAuthStore()
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState(null)
  const [payload, setPayload] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setErr(null)
    try {
      const params = new URLSearchParams({ limit: '1000' })
      if (user?.user_id) params.set('user_id', String(user.user_id))
      if (user?.username) params.set('username', String(user.username))
      const r = await fetch(`${INTEGRATION_BASE}/api/trading/history?${params.toString()}`)
      const data = await r.json().catch(() => ({}))
      if (!r.ok) {
        setErr(data?.detail || data?.message || `HTTP ${r.status}`)
        setPayload(null)
      } else {
        setPayload(data)
      }
    } catch (e) {
      setErr(e?.message || 'Could not reach integration service (port 8001)')
      setPayload(null)
    } finally {
      setLoading(false)
    }
  }, [user?.user_id, user?.username])

  useEffect(() => {
    load()
    const t = setInterval(load, 15000)
    return () => clearInterval(t)
  }, [load])

  const events = [...(payload?.events || [])].reverse()
  const sessionTrades = payload?.session_trades || []

  return (
    <div style={{ maxWidth: '1400px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: '700', color: 'white', margin: 0 }}>
            Trade history
          </h1>
          <p style={{ color: '#94a3b8', fontSize: '0.95rem', margin: '8px 0 0' }}>
            Paper-bot OPEN/CLOSE events are appended to disk and listed here. UI preference: <strong>{tradingStrategy?.toUpperCase() || 'ML'}</strong>
          </p>
        </div>
        <button
          type="button"
          onClick={load}
          disabled={loading}
          style={{
            padding: '10px 20px',
            borderRadius: '10px',
            border: '1px solid rgba(59, 130, 246, 0.5)',
            background: 'rgba(59, 130, 246, 0.15)',
            color: '#93c5fd',
            fontWeight: '600',
            cursor: loading ? 'wait' : 'pointer',
          }}
        >
          {loading ? 'Refreshing…' : 'Refresh'}
        </button>
      </div>

      {err && (
        <div style={{
          padding: '14px 18px',
          borderRadius: '12px',
          background: 'rgba(239, 68, 68, 0.12)',
          border: '1px solid rgba(239, 68, 68, 0.35)',
          color: '#fecaca',
          marginBottom: '20px',
        }}>
          {err}
        </div>
      )}

      {payload && (
        <div style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: '12px',
          marginBottom: '20px',
          fontSize: '0.9rem',
          color: '#94a3b8',
        }}>
          <span style={{ padding: '8px 14px', background: 'rgba(255,255,255,0.06)', borderRadius: '8px' }}>
            Logged events: <strong style={{ color: 'white' }}>{payload.event_count ?? 0}</strong>
          </span>
          <span style={{ padding: '8px 14px', background: 'rgba(255,255,255,0.06)', borderRadius: '8px' }}>
            Bot:{' '}
            <strong style={{ color: payload.bot_active ? '#4ade80' : '#f87171' }}>
              {payload.bot_active ? 'running' : 'stopped'}
            </strong>
            {Array.isArray(payload.active_strategies) && payload.active_strategies.length > 0
              ? ` (${payload.active_strategies.map((s) => String(s).toUpperCase()).join(', ')})`
              : ''}
          </span>
          {payload.history_file && (
            <span style={{ padding: '8px 14px', background: 'rgba(255,255,255,0.06)', borderRadius: '8px' }} title="Server-side JSONL path">
              File: <code style={{ color: '#e2e8f0' }}>{payload.history_file}</code>
            </span>
          )}
        </div>
      )}

      {sessionTrades.length > 0 && (
        <div style={{
          marginBottom: '24px',
          padding: '16px 18px',
          borderRadius: '14px',
          background: 'rgba(30, 41, 59, 0.7)',
          border: '1px solid rgba(148, 163, 184, 0.15)',
        }}>
          <h2 style={{ fontSize: '1rem', color: '#e2e8f0', margin: '0 0 12px' }}>Current session positions</h2>
          <div style={{ display: 'grid', gap: '10px' }}>
            {sessionTrades.map((t, i) => (
              <div
                key={`${t.order_id || i}-${t.status || i}`}
                style={{
                  display: 'flex',
                  flexWrap: 'wrap',
                  gap: '12px 20px',
                  fontSize: '0.88rem',
                  color: '#cbd5e1',
                  padding: '10px 12px',
                  background: 'rgba(15, 23, 42, 0.5)',
                  borderRadius: '10px',
                }}
              >
                <span><strong>Status</strong>: {t.status || '—'}</span>
                <span><strong>Symbol</strong>: {t.symbol || '—'}</span>
                <span><strong>Qty</strong>: {t.quantity ?? '—'}</span>
                <span><strong>Entry</strong>: {fmtPrice(t.entry_price)}</span>
                {t.status === 'CLOSED' && (
                  <>
                    <span><strong>Exit</strong>: {fmtPrice(t.exit_price)}</span>
                    <span><strong>P&amp;L</strong>: {fmtPrice(t.pnl)} ({t.pnl_pct != null ? `${Number(t.pnl_pct).toFixed(2)}%` : '—'})</span>
                  </>
                )}
                <span><strong>Order</strong>: <code style={{ fontSize: '0.8rem' }}>{t.order_id || '—'}</code></span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div style={{
        borderRadius: '14px',
        overflow: 'hidden',
        border: '1px solid rgba(148, 163, 184, 0.15)',
        background: 'rgba(15, 23, 42, 0.55)',
      }}>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
            <thead>
              <tr style={{ background: 'rgba(30, 41, 59, 0.9)', color: '#94a3b8', textAlign: 'left' }}>
                <th style={{ padding: '12px 14px' }}>Time</th>
                <th style={{ padding: '12px 8px' }}>Type</th>
                <th style={{ padding: '12px 8px' }}>Engine</th>
                <th style={{ padding: '12px 8px' }}>Symbol</th>
                <th style={{ padding: '12px 8px' }}>Qty</th>
                <th style={{ padding: '12px 8px' }}>Entry</th>
                <th style={{ padding: '12px 8px' }}>Exit</th>
                <th style={{ padding: '12px 8px' }}>P&amp;L</th>
                <th style={{ padding: '12px 8px' }}>Exit reason</th>
                <th style={{ padding: '12px 8px' }}>Order</th>
              </tr>
            </thead>
            <tbody>
              {events.length === 0 && !loading && (
                <tr>
                  <td colSpan={10} style={{ padding: '28px', textAlign: 'center', color: '#64748b' }}>
                    No trades logged yet. Start ML, LLM, or Hybrid on the Trading page; executions will appear here.
                  </td>
                </tr>
              )}
              {events.map((row, idx) => {
                const t = fmtTs(
                  row.lifecycle === 'CLOSED'
                    ? (row.close_timestamp || row.timestamp)
                    : row.timestamp,
                )
                const lifecycle = row.lifecycle || '—'
                const isOpen = lifecycle === 'OPEN'
                return (
                  <tr
                    key={`${row.order_id || idx}-${lifecycle}-${t}-${idx}`}
                    style={{
                      borderTop: '1px solid rgba(51, 65, 85, 0.5)',
                      color: '#e2e8f0',
                      background: idx % 2 === 0 ? 'transparent' : 'rgba(30, 41, 59, 0.25)',
                    }}
                  >
                    <td style={{ padding: '10px 14px', whiteSpace: 'nowrap' }}>{t}</td>
                    <td style={{ padding: '10px 8px' }}>
                      <span style={{
                        padding: '2px 8px',
                        borderRadius: '6px',
                        fontWeight: 600,
                        fontSize: '0.75rem',
                        background: isOpen ? 'rgba(74, 222, 128, 0.15)' : 'rgba(148, 163, 184, 0.15)',
                        color: isOpen ? '#4ade80' : '#94a3b8',
                      }}>
                        {lifecycle}
                      </span>
                    </td>
                    <td style={{ padding: '10px 8px', textTransform: 'uppercase' }}>{row.decision_engine || '—'}</td>
                    <td style={{ padding: '10px 8px' }}>{row.symbol || '—'}</td>
                    <td style={{ padding: '10px 8px' }}>{row.quantity ?? '—'}</td>
                    <td style={{ padding: '10px 8px' }}>{fmtPrice(row.entry_price)}</td>
                    <td style={{ padding: '10px 8px' }}>{fmtPrice(row.exit_price)}</td>
                    <td style={{ padding: '10px 8px', color: Number(row.pnl) >= 0 ? '#4ade80' : '#f87171' }}>
                      {row.pnl != null && row.pnl !== '' ? fmtPrice(row.pnl) : '—'}
                    </td>
                    <td style={{ padding: '10px 8px', maxWidth: '160px', wordBreak: 'break-word' }}>
                      {row.exit_reason || '—'}
                    </td>
                    <td style={{ padding: '10px 8px' }}>
                      <code style={{ fontSize: '0.75rem', color: '#94a3b8' }}>{row.order_id || '—'}</code>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

export default History
