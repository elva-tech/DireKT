import React, { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from 'react-query'
import { 
  TrendingUp, 
  TrendingDown, 
  Play, 
  Pause, 
  Settings,
  Brain,
  Bot,
  Target
} from 'lucide-react'
import api from '../services/api'
import LoadingSpinner from '../components/LoadingSpinner'
import toast from 'react-hot-toast'

function Trading() {
  const [selectedStrategy, setSelectedStrategy] = useState('')
  const [signal, setSignal] = useState(null)
  const [isGenerating, setIsGenerating] = useState(false)
  const [lotInfo, setLotInfo] = useState(null)
  const [currentPrice, setCurrentPrice] = useState(28150)
  
  const queryClient = useQueryClient()

  // Fetch available strategies
  const { data: strategiesData, isLoading: strategiesLoading } = useQuery(
    'strategies',
    () => api.get('/strategies/available').then(res => res.data),
    { staleTime: 30 * 60 * 1000 } // 30 minutes
  )

  // Fetch market data
  const { data: marketData } = useQuery(
    'market-data',
    () => api.get('/market/data').then(res => res.data),
    { refetchInterval: 5000 }
  )

  // Generate signal mutation
  const generateSignalMutation = useMutation(
    () => api.post('/trading/signals/generate'),
    {
      onSuccess: (response) => {
        setSignal(response.data.signal)
        toast.success('Trading signal generated successfully!')
      },
      onError: (error) => {
        toast.error('Failed to generate signal: ' + (error.response?.data?.detail || error.message))
      }
    }
  )

  // Calculate lots mutation
  const calculateLotsMutation = useMutation(
    (price) => api.post('/lot/calculate', { current_price: price }),
    {
      onSuccess: (response) => {
        setLotInfo(response.data.lot_info)
        toast.success('Lot calculation completed!')
      },
      onError: (error) => {
        toast.error('Failed to calculate lots: ' + (error.response?.data?.detail || error.message))
      }
    }
  )

  // Place order mutation
  const placeOrderMutation = useMutation(
    (orderData) => api.post('/trading/orders/place', orderData),
    {
      onSuccess: (response) => {
        toast.success('Order placed successfully!')
        queryClient.invalidateQueries('orders')
        queryClient.invalidateQueries('portfolio')
      },
      onError: (error) => {
        toast.error('Failed to place order: ' + (error.response?.data?.detail || error.message))
      }
    }
  )

  useEffect(() => {
    if (marketData?.market_data?.last_price) {
      setCurrentPrice(marketData.market_data.last_price)
    }
  }, [marketData])

  useEffect(() => {
    // Auto-calculate lots when price changes
    if (currentPrice > 0) {
      calculateLotsMutation.mutate(currentPrice)
    }
  }, [currentPrice])

  const handleGenerateSignal = () => {
    if (!selectedStrategy) {
      toast.error('Please select a strategy first')
      return
    }
    
    setIsGenerating(true)
    generateSignalMutation.mutate()
    setTimeout(() => setIsGenerating(false), 2000)
  }

  const handlePlaceOrder = () => {
    if (!signal || signal.action === 'HOLD') {
      toast.error('No valid signal to execute')
      return
    }
    
    if (!lotInfo || lotInfo.max_lots === 0) {
      toast.error('No lots available for trading')
      return
    }

    const orderData = {
      symbol: 'SILVERM2026',
      action: signal.action,
      quantity: lotInfo.trade_quantity,
      order_type: 'LIMIT',
      price: signal.entry_price,
      stop_loss: signal.stop_loss,
      target: signal.target
    }

    placeOrderMutation.mutate(orderData)
  }

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    }).format(amount)
  }

  const formatPercent = (value) => {
    return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`
  }

  const strategies = strategiesData?.strategies || {}
  const market = marketData?.market_data || {}

  if (strategiesLoading) {
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
          <h1 className="text-3xl font-bold text-white">Trading Terminal</h1>
          <p className="text-gray-400 mt-1">
            AI-powered paper trading with real-time market data
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <div className="w-3 h-3 bg-green-500 rounded-full animate-pulse"></div>
          <span className="text-sm text-green-400">
            Market: {market.last_price ? 'Open' : 'Closed'}
          </span>
        </div>
      </div>

      {/* Market Data Bar */}
      <div className="trading-card p-4">
        <div className="grid grid-cols-2 md:grid-cols-6 gap-4 text-center">
          <div>
            <p className="text-xs text-gray-400">Last Price</p>
            <p className="text-lg font-bold text-white">
              {formatCurrency(market.last_price || 0)}
            </p>
            <p className={`text-xs ${
              (market.change || 0) >= 0 ? 'text-green-400' : 'text-red-400'
            }`}>
              {formatPercent(market.change_pct || 0)}
            </p>
          </div>
          <div>
            <p className="text-xs text-gray-400">Volume</p>
            <p className="text-lg font-bold text-white">
              {(market.volume || 0).toLocaleString()}
            </p>
          </div>
          <div>
            <p className="text-xs text-gray-400">High</p>
            <p className="text-lg font-bold text-white">
              {formatCurrency(market.high || 0)}
            </p>
          </div>
          <div>
            <p className="text-xs text-gray-400">Low</p>
            <p className="text-lg font-bold text-white">
              {formatCurrency(market.low || 0)}
            </p>
          </div>
          <div>
            <p className="text-xs text-gray-400">Bid</p>
            <p className="text-lg font-bold text-white">
              {formatCurrency(market.bid || 0)}
            </p>
          </div>
          <div>
            <p className="text-xs text-gray-400">Ask</p>
            <p className="text-lg font-bold text-white">
              {formatCurrency(market.ask || 0)}
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Strategy Selection */}
        <div className="trading-card p-6">
          <h2 className="text-xl font-semibold text-white mb-6 flex items-center">
            <Brain className="w-5 h-5 mr-2 text-purple-400" />
            Strategy Selection
          </h2>
          
          <div className="space-y-4">
            {Object.entries(strategies).map(([key, strategy]) => (
              <div
                key={key}
                onClick={() => setSelectedStrategy(key)}
                className={`p-4 rounded-lg border cursor-pointer transition-all duration-200 ${
                  selectedStrategy === key
                    ? 'border-blue-500 bg-blue-900/30'
                    : 'border-gray-700 hover:border-gray-600 hover:bg-gray-800/50'
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <h3 className="font-medium text-white flex items-center">
                    {key === 'ml_model' && <Bot className="w-4 h-4 mr-2 text-blue-400" />}
                    {key === 'llm_model' && <Brain className="w-4 h-4 mr-2 text-purple-400" />}
                    {key === 'rule_based' && <Target className="w-4 h-4 mr-2 text-green-400" />}
                    {key === 'hybrid' && <Settings className="w-4 h-4 mr-2 text-orange-400" />}
                    {strategy.name}
                  </h3>
                  <span className={`px-2 py-1 rounded text-xs font-medium ${
                    strategy.requires_llm && strategy.requires_ml_model ? 'bg-orange-600 text-white' :
                    strategy.requires_llm ? 'bg-purple-600 text-white' :
                    strategy.requires_ml_model ? 'bg-blue-600 text-white' :
                    'bg-gray-600 text-white'
                  }`}>
                    {strategy.min_confidence}% min
                  </span>
                </div>
                <p className="text-sm text-gray-400 mb-3">
                  {strategy.description}
                </p>
                <div className="flex flex-wrap gap-2">
                  {strategy.requires_ml_model && (
                    <span className="text-xs bg-blue-900/50 text-blue-300 px-2 py-1 rounded">
                      ML Model
                    </span>
                  )}
                  {strategy.requires_llm && (
                    <span className="text-xs bg-purple-900/50 text-purple-300 px-2 py-1 rounded">
                      LLM
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>

          <button
            onClick={handleGenerateSignal}
            disabled={!selectedStrategy || isGenerating || generateSignalMutation.isLoading}
            className="btn-primary w-full mt-6 flex items-center justify-center"
          >
            {isGenerating || generateSignalMutation.isLoading ? (
              <LoadingSpinner size="sm" />
            ) : (
              <>
                <Play className="w-4 h-4 mr-2" />
                Generate Signal
              </>
            )}
          </button>
        </div>

        {/* Signal & Order */}
        <div className="space-y-6">
          {/* Trading Signal */}
          <div className="trading-card p-6">
            <h2 className="text-xl font-semibold text-white mb-6 flex items-center">
              <Target className="w-5 h-5 mr-2 text-green-400" />
              Trading Signal
            </h2>
            
            {signal ? (
              <div className="space-y-4">
                <div className={`p-4 rounded-lg border ${
                  signal.action === 'BUY' ? 'bg-green-900/30 border-green-700' :
                  signal.action === 'SELL' ? 'bg-red-900/30 border-red-700' :
                  'bg-gray-800 border-gray-700'
                }`}>
                  <div className="flex items-center justify-between mb-2">
                    <span className={`text-2xl font-bold ${
                      signal.action === 'BUY' ? 'text-green-400' :
                      signal.action === 'SELL' ? 'text-red-400' :
                      'text-gray-400'
                    }`}>
                      {signal.action}
                    </span>
                    <span className="text-lg font-medium text-white">
                      {signal.confidence}%
                    </span>
                  </div>
                  <p className="text-sm text-gray-400 mb-3">
                    {signal.reason}
                  </p>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-xs text-gray-400">Entry Price</p>
                    <p className="text-lg font-bold text-white">
                      {formatCurrency(signal.entry_price)}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-400">Risk/Reward</p>
                    <p className="text-lg font-bold text-white">
                      1:{signal.risk_reward_ratio?.toFixed(2) || 'N/A'}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-400">Stop Loss</p>
                    <p className="text-lg font-bold text-red-400">
                      {formatCurrency(signal.stop_loss)}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-400">Target</p>
                    <p className="text-lg font-bold text-green-400">
                      {formatCurrency(signal.target)}
                    </p>
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-center py-8 text-gray-400">
                <Target className="w-12 h-12 mx-auto mb-4 opacity-50" />
                <p>Generate a trading signal to see details</p>
              </div>
            )}
          </div>

          {/* Lot Information */}
          {lotInfo && (
            <div className="trading-card p-6">
              <h3 className="text-lg font-semibold text-white mb-4">Position Sizing</h3>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-xs text-gray-400">Max Lots</p>
                  <p className="text-lg font-bold text-white">{lotInfo.max_lots}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-400">Trade Quantity</p>
                  <p className="text-lg font-bold text-white">{lotInfo.trade_quantity} kg</p>
                </div>
                <div>
                  <p className="text-xs text-gray-400">Margin per Lot</p>
                  <p className="text-sm font-medium text-white">
                    {formatCurrency(lotInfo.margin_per_lot)}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-gray-400">Capital Utilization</p>
                  <p className="text-sm font-medium text-white">
                    {lotInfo.utilization_pct.toFixed(1)}%
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Place Order Button */}
          {signal && signal.action !== 'HOLD' && (
            <button
              onClick={handlePlaceOrder}
              disabled={placeOrderMutation.isLoading || !lotInfo || lotInfo.max_lots === 0}
              className="btn-success w-full flex items-center justify-center"
            >
              {placeOrderMutation.isLoading ? (
                <LoadingSpinner size="sm" />
              ) : (
                <>
                  <Play className="w-4 h-4 mr-2" />
                  Place {signal.action} Order
                </>
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

export default Trading
