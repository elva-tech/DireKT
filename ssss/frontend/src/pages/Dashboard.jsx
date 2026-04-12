import React, { useState, useEffect } from 'react'
import { useQuery } from 'react-query'
import { 
  TrendingUp, 
  TrendingDown, 
  Activity, 
  DollarSign,
  BarChart3,
  Bot,
  Shield,
  Sparkles,
  ArrowUpRight,
  ArrowDownRight,
  Clock
} from 'lucide-react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts'
import api from '../services/api'
import LoadingSpinner from '../components/LoadingSpinner'

function Dashboard() {
  const [wsConnection, setWsConnection] = useState(null)
  const [selectedTimeframe, setSelectedTimeframe] = useState('1D')

  // Fetch portfolio data
  const { data: portfolioData, isLoading: portfolioLoading } = useQuery(
    'portfolio',
    () => api.get('/portfolio/summary').then(res => res.data),
    { refetchInterval: 30000 }
  )

  // Fetch market data
  const { data: marketData, isLoading: marketLoading } = useQuery(
    'market-data',
    () => api.get('/market/data').then(res => res.data),
    { refetchInterval: 5000 }
  )

  // Fetch risk metrics
  const { data: riskData, isLoading: riskLoading } = useQuery(
    'risk-metrics',
    () => api.get('/risk/metrics').then(res => res.data),
    { refetchInterval: 10000 }
  )

  // Generate mock chart data
  const generateChartData = () => {
    const data = []
    const points = 24
    const baseValue = 100000
    
    for (let i = points; i >= 0; i--) {
      const randomChange = (Math.random() - 0.5) * 2000
      const value = baseValue + randomChange + (points - i) * 500
      
      data.push({
        time: new Date(Date.now() - i * 3600000).toLocaleTimeString('en-US', { 
          hour: '2-digit', 
          minute: '2-digit'
        }),
        value: Math.round(value),
        pnl: Math.round(value - baseValue)
      })
    }
    
    return data
  }

  const [chartData, setChartData] = useState(generateChartData())

  useEffect(() => {
    const interval = setInterval(() => {
      setChartData(generateChartData())
    }, 10000)
    return () => clearInterval(interval)
  }, [])

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(amount)
  }

  const formatPercent = (value) => {
    return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`
  }

  const portfolio = portfolioData?.portfolio || {}
  const market = marketData?.market_data || {}
  const risk = riskData?.risk_metrics || {}

  if (portfolioLoading || marketLoading || riskLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <LoadingSpinner size="lg" />
          <p className="mt-4 text-gray-400 animate-pulse">Loading dashboard data...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-4xl font-bold text-white mb-2 flex items-center">
            <BarChart3 className="w-8 h-8 mr-3 text-blue-400" />
            Trading Dashboard
          </h1>
          <p className="text-gray-400 text-lg">
            Real-time MCX Silver Futures paper trading platform
          </p>
        </div>
        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-2">
            <div className="w-3 h-3 bg-green-500 rounded-full animate-pulse"></div>
            <span className="text-sm text-green-400 font-medium">Live Market</span>
          </div>
          <div className="text-sm text-gray-400">
            {new Date().toLocaleString('en-IN', { 
              weekday: 'short',
              hour: '2-digit',
              minute: '2-digit'
            })}
          </div>
        </div>
      </div>

      {/* Market Overview Card */}
      <div className="card-elevated p-8 border border-gray-700/50">
        <div className="flex items-center justify-between mb-8">
          <h2 className="text-2xl font-bold text-white flex items-center">
            <Activity className="w-6 h-6 mr-3 text-blue-400" />
            Market Overview
          </h2>
          <div className="flex items-center space-x-3">
            <span className="badge badge-info">SILVERM2026</span>
            <span className="text-sm text-gray-400">MCX Futures</span>
          </div>
        </div>
        
        <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
          <div className="text-center">
            <p className="text-sm text-gray-400 mb-3 font-medium">Last Price</p>
            <p className="text-3xl font-bold text-white mb-2">
              {formatCurrency(market.last_price || 0)}
            </p>
            <div className={`flex items-center justify-center text-sm font-medium ${
              (market.change || 0) >= 0 ? 'text-green-400' : 'text-red-400'
            }`}>
              {(market.change || 0) >= 0 ? (
                <ArrowUpRight className="w-4 h-4 mr-1" />
              ) : (
                <ArrowDownRight className="w-4 h-4 mr-1" />
              )}
              {formatCurrency(market.change || 0)} ({formatPercent(market.change_pct || 0)})
            </div>
          </div>
          
          <div className="text-center">
            <p className="text-sm text-gray-400 mb-3 font-medium">Volume</p>
            <p className="text-3xl font-bold text-white mb-2">
              {(market.volume || 0).toLocaleString()}
            </p>
            <p className="text-sm text-gray-500">Contracts</p>
          </div>
          
          <div className="text-center">
            <p className="text-sm text-gray-400 mb-3 font-medium">Open Interest</p>
            <p className="text-3xl font-bold text-white mb-2">
              {(market.oi || 0).toLocaleString()}
            </p>
            <p className="text-sm text-gray-500">Positions</p>
          </div>
          
          <div className="text-center">
            <p className="text-sm text-gray-400 mb-3 font-medium">Bid/Ask Spread</p>
            <p className="text-xl font-bold text-white">
              {formatCurrency(market.bid || 0)} / {formatCurrency(market.ask || 0)}
            </p>
            <p className="text-sm text-gray-500">Spread: {formatCurrency((market.ask || 0) - (market.bid || 0))}</p>
          </div>
        </div>
      </div>

      {/* Portfolio Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="metric-card group hover:shadow-glow transition-all duration-300">
          <div className="flex items-center justify-between mb-4">
            <h3 className="metric-label">Portfolio Value</h3>
            <div className="w-10 h-10 bg-gradient-to-br from-blue-600 to-blue-700 rounded-xl flex items-center justify-center">
              <DollarSign className="w-5 h-5 text-white" />
            </div>
          </div>
          <p className="metric-value mb-2">
            {formatCurrency(portfolio.total_value || 0)}
          </p>
          <div className={`metric-change flex items-center ${
            (portfolio.total_pnl || 0) >= 0 ? 'text-green-400' : 'text-red-400'
          }`}>
            {(portfolio.total_pnl || 0) >= 0 ? (
              <ArrowUpRight className="w-4 h-4 mr-1" />
            ) : (
              <ArrowDownRight className="w-4 h-4 mr-1" />
            )}
            {formatCurrency(portfolio.total_pnl || 0)} ({formatPercent(portfolio.total_pnl_pct || 0)})
          </div>
        </div>

        <div className="metric-card group hover:shadow-glow-green transition-all duration-300">
          <div className="flex items-center justify-between mb-4">
            <h3 className="metric-label">Available Balance</h3>
            <div className="w-10 h-10 bg-gradient-to-br from-green-600 to-green-700 rounded-xl flex items-center justify-center">
              <DollarSign className="w-5 h-5 text-white" />
            </div>
          </div>
          <p className="metric-value mb-2">
            {formatCurrency(portfolio.available_balance || 0)}
          </p>
          <p className="text-sm text-gray-500">
            {((portfolio.available_balance || 0) / (portfolio.total_value || 1) * 100).toFixed(1)}% of portfolio
          </p>
        </div>

        <div className="metric-card group hover:shadow-glow transition-all duration-300">
          <div className="flex items-center justify-between mb-4">
            <h3 className="metric-label">Today's P&L</h3>
            <div className="w-10 h-10 bg-gradient-to-br from-purple-600 to-purple-700 rounded-xl flex items-center justify-center">
              <Activity className="w-5 h-5 text-white" />
            </div>
          </div>
          <p className={`metric-value mb-2 ${
            (portfolio.today_pnl || 0) >= 0 ? 'text-green-400' : 'text-red-400'
          }`}>
            {formatCurrency(portfolio.today_pnl || 0)}
          </p>
          <p className={`text-sm ${
            (portfolio.today_pnl_pct || 0) >= 0 ? 'text-green-400' : 'text-red-400'
          }`}>
            {formatPercent(portfolio.today_pnl_pct || 0)}
          </p>
        </div>

        <div className="metric-card group hover:shadow-glow transition-all duration-300">
          <div className="flex items-center justify-between mb-4">
            <h3 className="metric-label">Win Rate</h3>
            <div className="w-10 h-10 bg-gradient-to-br from-yellow-600 to-yellow-700 rounded-xl flex items-center justify-center">
              <TrendingUp className="w-5 h-5 text-white" />
            </div>
          </div>
          <p className="metric-value mb-2">
            {portfolio.win_rate || 0}%
          </p>
          <p className="text-sm text-gray-500">
            {portfolio.daily_trades || 0} trades today
          </p>
        </div>
      </div>

      {/* Portfolio Performance Chart */}
      <div className="card-elevated p-8">
        <div className="flex items-center justify-between mb-8">
          <h2 className="text-2xl font-bold text-white flex items-center">
            <BarChart3 className="w-6 h-6 mr-3 text-purple-400" />
            Portfolio Performance
          </h2>
          <div className="flex space-x-2">
            {['1D', '1W', '1M'].map((tf) => (
              <button
                key={tf}
                onClick={() => setSelectedTimeframe(tf)}
                className={`px-4 py-2 rounded-xl text-sm font-medium transition-all duration-200 ${
                  selectedTimeframe === tf
                    ? 'bg-gradient-to-r from-blue-600 to-blue-700 text-white shadow-lg'
                    : 'text-gray-400 hover:bg-gray-800/50 hover:text-white'
                }`}
              >
                {tf}
              </button>
            ))}
          </div>
        </div>
        
        <div className="h-96">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData}>
              <defs>
                <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3}/>
                  <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                </linearGradient>
                <linearGradient id="colorPnl" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#10b981" stopOpacity={0.3}/>
                  <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis 
                dataKey="time" 
                stroke="#9ca3af"
                tick={{ fill: '#9ca3af', fontSize: 12 }}
              />
              <YAxis 
                stroke="#9ca3af"
                tick={{ fill: '#9ca3af', fontSize: 12 }}
                tickFormatter={(value) => `₹${(value / 1000).toFixed(0)}k`}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#1f2937',
                  border: '1px solid #374151',
                  borderRadius: '12px'
                }}
                labelStyle={{ color: '#f3f4f6' }}
                formatter={(value, name) => [
                  name === 'value' ? formatCurrency(value) : value,
                  name === 'value' ? 'Portfolio Value' : 'P&L'
                ]}
              />
              <Area
                type="monotone"
                dataKey="value"
                stroke="#3b82f6"
                strokeWidth={2}
                fillOpacity={1}
                fill="url(#colorValue)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Risk Metrics & Quick Actions */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Risk Metrics */}
        <div className="card-elevated p-6">
          <h3 className="text-xl font-semibold text-white mb-6 flex items-center">
            <Shield className="w-5 h-5 mr-2 text-yellow-400" />
            Risk Metrics
          </h3>
          
          <div className="space-y-4">
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-gray-400">Risk Score</span>
                <span className="text-lg font-bold text-white">
                  {risk.risk_score || 0}
                </span>
              </div>
              <div className="w-full bg-gray-700 rounded-full h-2">
                <div 
                  className={`h-2 rounded-full transition-all duration-500 ${
                    (risk.risk_score || 0) < 30 ? 'bg-green-500' :
                    (risk.risk_score || 0) < 70 ? 'bg-yellow-500' :
                    'bg-red-500'
                  }`}
                  style={{ width: `${Math.min(risk.risk_score || 0, 100)}%` }}
                ></div>
              </div>
            </div>
            
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-xs text-gray-400 mb-1">Drawdown</p>
                <p className="text-sm font-medium text-white">
                  {formatPercent(risk.current_drawdown || 0)}
                </p>
              </div>
              <div>
                <p className="text-xs text-gray-400 mb-1">Daily Limit</p>
                <p className="text-sm font-medium text-white">
                  {formatCurrency(risk.daily_loss_limit || 0)}
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Quick Actions */}
        <div className="lg:col-span-2 card-elevated p-6">
          <h3 className="text-xl font-semibold text-white mb-6 flex items-center">
            <Sparkles className="w-5 h-5 mr-2 text-purple-400" />
            Quick Actions
          </h3>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <button className="btn btn-primary group">
              <Bot className="w-4 h-4 mr-2 group-hover:animate-pulse" />
              Generate Signal
            </button>
            <button className="btn btn-secondary group">
              <DollarSign className="w-4 h-4 mr-2 group-hover:animate-pulse" />
              Calculate Lots
            </button>
            <button className="btn btn-ghost group">
              <BarChart3 className="w-4 h-4 mr-2 group-hover:animate-pulse" />
              View Analytics
            </button>
          </div>
          
          <div className="mt-6 p-4 bg-gradient-to-r from-blue-900/30 to-purple-900/30 border border-blue-700/50 rounded-xl">
            <div className="flex items-center mb-2">
              <Clock className="w-4 h-4 text-blue-400 mr-2" />
              <span className="text-sm font-medium text-blue-300">
                Market Status
              </span>
            </div>
            <p className="text-xs text-gray-400">
              MCX Silver Futures market is currently active. Real-time data streaming enabled.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

export default Dashboard
