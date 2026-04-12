import React, { useState, useEffect } from 'react'
import { useQuery } from 'react-query'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts'
import { TrendingUp, TrendingDown, DollarSign, Briefcase, Activity } from 'lucide-react'
import api from '../services/api'
import LoadingSpinner from '../components/LoadingSpinner'

function Portfolio() {
  const [timeframe, setTimeframe] = useState('1D')
  const [chartData, setChartData] = useState([])

  // Fetch portfolio data
  const { data: portfolioData, isLoading: portfolioLoading } = useQuery(
    'portfolio',
    () => api.get('/portfolio/summary').then(res => res.data),
    { refetchInterval: 30000 }
  )

  // Generate mock chart data based on timeframe
  useEffect(() => {
    const generateChartData = () => {
      const now = new Date()
      const data = []
      let points = 24 // 1 hour intervals for 1 day
      
      if (timeframe === '1D') points = 24
      else if (timeframe === '1W') points = 7
      else if (timeframe === '1M') points = 30
      
      const baseValue = 100000
      const volatility = 0.02
      
      for (let i = points; i >= 0; i--) {
        const time = new Date(now.getTime() - i * (timeframe === '1D' ? 3600000 : timeframe === '1W' ? 86400000 : 2592000000))
        const randomChange = (Math.random() - 0.5) * volatility * baseValue
        const value = baseValue + randomChange + (points - i) * 50 // Slight uptrend
        
        data.push({
          time: time.toLocaleTimeString('en-US', { 
            hour: '2-digit', 
            minute: '2-digit',
            ...(timeframe !== '1D' && { month: 'short', day: 'numeric' })
          }),
          value: Math.round(value),
          pnl: Math.round(value - baseValue)
        })
      }
      
      setChartData(data)
    }

    generateChartData()
    const interval = setInterval(generateChartData, 5000)
    return () => clearInterval(interval)
  }, [timeframe])

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
  const currentValue = chartData.length > 0 ? chartData[chartData.length - 1].value : 100000
  const totalPnL = currentValue - 100000
  const totalPnLPct = (totalPnL / 100000) * 100

  if (portfolioLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white">Portfolio</h1>
          <p className="text-gray-400 mt-1">
            Track your paper trading performance and holdings
          </p>
        </div>
        <div className="flex items-center space-x-2">
          {['1D', '1W', '1M'].map((tf) => (
            <button
              key={tf}
              onClick={() => setTimeframe(tf)}
              className={`px-3 py-1 rounded-lg text-sm font-medium transition-colors ${
                timeframe === tf
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-white'
              }`}
            >
              {tf}
            </button>
          ))}
        </div>
      </div>

      {/* Portfolio Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="trading-card p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-medium text-gray-400">Total Value</h3>
            <DollarSign className="w-4 h-4 text-blue-400" />
          </div>
          <p className="text-2xl font-bold text-white">
            {formatCurrency(currentValue)}
          </p>
          <p className={`text-sm mt-2 ${
            totalPnL >= 0 ? 'text-green-400' : 'text-red-400'
          }`}>
            {totalPnL >= 0 ? (
              <TrendingUp className="inline w-4 h-4 mr-1" />
            ) : (
              <TrendingDown className="inline w-4 h-4 mr-1" />
            )}
            {formatCurrency(totalPnL)} ({formatPercent(totalPnLPct)})
          </p>
        </div>

        <div className="trading-card p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-medium text-gray-400">Available Balance</h3>
            <Briefcase className="w-4 h-4 text-green-400" />
          </div>
          <p className="text-2xl font-bold text-white">
            {formatCurrency(portfolio.available_balance || 0)}
          </p>
          <p className="text-sm text-gray-400 mt-2">
            {((portfolio.available_balance || 0) / currentValue * 100).toFixed(1)}% of portfolio
          </p>
        </div>

        <div className="trading-card p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-medium text-gray-400">Today's P&L</h3>
            <Activity className="w-4 h-4 text-purple-400" />
          </div>
          <p className={`text-2xl font-bold ${
            (portfolio.today_pnl || 0) >= 0 ? 'text-green-400' : 'text-red-400'
          }`}>
            {formatCurrency(portfolio.today_pnl || 0)}
          </p>
          <p className={`text-sm mt-2 ${
            (portfolio.today_pnl_pct || 0) >= 0 ? 'text-green-400' : 'text-red-400'
          }`}>
            {formatPercent(portfolio.today_pnl_pct || 0)}
          </p>
        </div>

        <div className="trading-card p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-medium text-gray-400">Win Rate</h3>
            <TrendingUp className="w-4 h-4 text-yellow-400" />
          </div>
          <p className="text-2xl font-bold text-white">
            {portfolio.win_rate || 0}%
          </p>
          <p className="text-sm text-gray-400 mt-2">
            {portfolio.daily_trades || 0} trades today
          </p>
        </div>
      </div>

      {/* Portfolio Chart */}
      <div className="trading-card p-6">
        <h2 className="text-xl font-semibold text-white mb-6">Portfolio Performance</h2>
        <div className="h-80">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData}>
              <defs>
                <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3}/>
                  <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
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
                  borderRadius: '8px'
                }}
                labelStyle={{ color: '#f3f4f6' }}
                formatter={(value, name) => [
                  name === 'value' ? formatCurrency(value) : value,
                  name === 'value' ? 'Portfolio Value' : name
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

      {/* Current Positions */}
      <div className="trading-card p-6">
        <h2 className="text-xl font-semibold text-white mb-6">Current Positions</h2>
        
        {portfolio.positions && portfolio.positions.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-700">
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-400">Symbol</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-400">Quantity</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-400">Avg Price</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-400">Current Price</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-400">P&L</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-400">P&L %</th>
                </tr>
              </thead>
              <tbody>
                {portfolio.positions.map((position, index) => (
                  <tr key={index} className="border-b border-gray-800">
                    <td className="py-3 px-4 text-white font-medium">{position.symbol}</td>
                    <td className="py-3 px-4 text-white">{position.quantity} kg</td>
                    <td className="py-3 px-4 text-white">{formatCurrency(position.avg_price)}</td>
                    <td className="py-3 px-4 text-white">{formatCurrency(position.current_price)}</td>
                    <td className={`py-3 px-4 font-medium ${
                      position.pnl >= 0 ? 'text-green-400' : 'text-red-400'
                    }`}>
                      {formatCurrency(position.pnl)}
                    </td>
                    <td className={`py-3 px-4 font-medium ${
                      position.pnl_pct >= 0 ? 'text-green-400' : 'text-red-400'
                    }`}>
                      {formatPercent(position.pnl_pct)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center py-8 text-gray-400">
            <Briefcase className="w-12 h-12 mx-auto mb-4 opacity-50" />
            <p>No open positions</p>
          </div>
        )}
      </div>
    </div>
  )
}

export default Portfolio
