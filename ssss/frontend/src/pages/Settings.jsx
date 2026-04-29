import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from 'react-query'
import { 
  Settings as SettingsIcon, 
  Shield, 
  DollarSign, 
  AlertTriangle,
  Save,
  User,
  Brain,
  Bot
} from 'lucide-react'
import api from '../services/api'
import LoadingSpinner from '../components/LoadingSpinner'
import toast from 'react-hot-toast'
import { useAuthStore } from '../stores/authStore'

function Settings() {
  const { user } = useAuthStore()
  const queryClient = useQueryClient()
  
  const [activeTab, setActiveTab] = useState('risk')
  const [riskConfig, setRiskConfig] = useState({
    daily_loss_limit_pct: 3.0,
    max_risk_per_trade_pct: 1.5,
    max_position_size_lots: 5,
    max_daily_trades: 20
  })
  
  const [strategyConfig, setStrategyConfig] = useState({
    ml_confidence_threshold: 65,
    llm_confidence_threshold: 65,
    risk_reward_ratio: 2.0,
    atr_multiplier: 1.5
  })

  // Fetch current risk configuration
  const { data: riskData } = useQuery(
    'risk-config',
    () => api.get('/risk/config').then(res => res.data),
    {
      onSuccess: (data) => {
        if (data.config) {
          setRiskConfig(data.config)
        }
      }
    }
  )

  // Update risk configuration mutation
  const updateRiskConfigMutation = useMutation(
    (config) => api.post('/risk/config', config),
    {
      onSuccess: () => {
        toast.success('Risk configuration updated successfully!')
        queryClient.invalidateQueries('risk-config')
      },
      onError: (error) => {
        toast.error('Failed to update risk configuration: ' + (error.response?.data?.detail || error.message))
      }
    }
  )

  const handleRiskConfigChange = (field, value) => {
    setRiskConfig(prev => ({
      ...prev,
      [field]: parseFloat(value)
    }))
  }

  const handleStrategyConfigChange = (field, value) => {
    setStrategyConfig(prev => ({
      ...prev,
      [field]: parseFloat(value)
    }))
  }

  const handleSaveRiskConfig = () => {
    updateRiskConfigMutation.mutate(riskConfig)
  }

  const handleSaveStrategyConfig = () => {
    toast.success('Strategy configuration saved (mock)')
  }

  const tabs = [
    { id: 'risk', label: 'Risk Management', icon: Shield },
    { id: 'strategy', label: 'Strategy Settings', icon: Brain },
    { id: 'account', label: 'Account', icon: User }
  ]

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white">Settings</h1>
          <p className="text-gray-400 mt-1">
            Configure your trading preferences and risk parameters
          </p>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="trading-card p-2">
        <div className="flex space-x-2">
          {tabs.map((tab) => {
            const Icon = tab.icon
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center space-x-2 px-4 py-2 rounded-lg font-medium transition-colors ${
                  activeTab === tab.id
                    ? 'bg-blue-600 text-white'
                    : 'text-gray-400 hover:bg-gray-800 hover:text-white'
                }`}
              >
                <Icon className="w-4 h-4" />
                <span>{tab.label}</span>
              </button>
            )
          })}
        </div>
      </div>

      {/* Tab Content */}
      <div className="trading-card p-6">
        {/* Risk Management Tab */}
        {activeTab === 'risk' && (
          <div>
            <h2 className="text-xl font-semibold text-white mb-6 flex items-center">
              <Shield className="w-5 h-5 mr-2 text-yellow-400" />
              Risk Management Configuration
            </h2>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  Daily Loss Limit (%)
                </label>
                <input
                  type="number"
                  step="0.1"
                  min="0.5"
                  max="10"
                  value={riskConfig.daily_loss_limit_pct}
                  onChange={(e) => handleRiskConfigChange('daily_loss_limit_pct', e.target.value)}
                  className="input-field w-full"
                />
                <p className="text-xs text-gray-400 mt-1">
                  Stop trading when daily loss reaches this percentage
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  Max Risk per Trade (%)
                </label>
                <input
                  type="number"
                  step="0.1"
                  min="0.1"
                  max="5"
                  value={riskConfig.max_risk_per_trade_pct}
                  onChange={(e) => handleRiskConfigChange('max_risk_per_trade_pct', e.target.value)}
                  className="input-field w-full"
                />
                <p className="text-xs text-gray-400 mt-1">
                  Maximum percentage of capital to risk on single trade
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  Max Position Size (lots)
                </label>
                <input
                  type="number"
                  min="1"
                  max="10"
                  value={riskConfig.max_position_size_lots}
                  onChange={(e) => handleRiskConfigChange('max_position_size_lots', e.target.value)}
                  className="input-field w-full"
                />
                <p className="text-xs text-gray-400 mt-1">
                  Maximum number of lots per position
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  Max Daily Trades
                </label>
                <input
                  type="number"
                  min="1"
                  max="100"
                  value={riskConfig.max_daily_trades}
                  onChange={(e) => handleRiskConfigChange('max_daily_trades', e.target.value)}
                  className="input-field w-full"
                />
                <p className="text-xs text-gray-400 mt-1">
                  Maximum number of trades per day
                </p>
              </div>
            </div>

            <div className="mt-8 flex items-center justify-between">
              <div className="flex items-center space-x-2 text-yellow-400">
                <AlertTriangle className="w-4 h-4" />
                <span className="text-sm">
                  Lower risk settings provide better capital protection
                </span>
              </div>
              
              <button
                onClick={handleSaveRiskConfig}
                disabled={updateRiskConfigMutation.isLoading}
                className="btn-primary flex items-center"
              >
                {updateRiskConfigMutation.isLoading ? (
                  <LoadingSpinner size="sm" />
                ) : (
                  <>
                    <Save className="w-4 h-4 mr-2" />
                    Save Risk Settings
                  </>
                )}
              </button>
            </div>
          </div>
        )}

        {/* Strategy Settings Tab */}
        {activeTab === 'strategy' && (
          <div>
            <h2 className="text-xl font-semibold text-white mb-6 flex items-center">
              <Brain className="w-5 h-5 mr-2 text-purple-400" />
              Strategy Configuration
            </h2>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  ML Model Confidence Threshold (%)
                </label>
                <input
                  type="number"
                  step="1"
                  min="50"
                  max="95"
                  value={strategyConfig.ml_confidence_threshold}
                  onChange={(e) => handleStrategyConfigChange('ml_confidence_threshold', e.target.value)}
                  className="input-field w-full"
                />
                <p className="text-xs text-gray-400 mt-1">
                  Minimum confidence for ML model signals
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  LLM Confidence Threshold (%)
                </label>
                <input
                  type="number"
                  step="1"
                  min="50"
                  max="95"
                  value={strategyConfig.llm_confidence_threshold}
                  onChange={(e) => handleStrategyConfigChange('llm_confidence_threshold', e.target.value)}
                  className="input-field w-full"
                />
                <p className="text-xs text-gray-400 mt-1">
                  Minimum confidence for LLM signals
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  Risk-Reward Ratio
                </label>
                <input
                  type="number"
                  step="0.1"
                  min="1.0"
                  max="5.0"
                  value={strategyConfig.risk_reward_ratio}
                  onChange={(e) => handleStrategyConfigChange('risk_reward_ratio', e.target.value)}
                  className="input-field w-full"
                />
                <p className="text-xs text-gray-400 mt-1">
                  Target risk-reward ratio for trades
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  ATR Multiplier
                </label>
                <input
                  type="number"
                  step="0.1"
                  min="1.0"
                  max="3.0"
                  value={strategyConfig.atr_multiplier}
                  onChange={(e) => handleStrategyConfigChange('atr_multiplier', e.target.value)}
                  className="input-field w-full"
                />
                <p className="text-xs text-gray-400 mt-1">
                  Multiplier for ATR-based stop loss
                </p>
              </div>
            </div>

            <div className="mt-8 flex justify-end">
              <button
                onClick={handleSaveStrategyConfig}
                className="btn-primary flex items-center"
              >
                <Save className="w-4 h-4 mr-2" />
                Save Strategy Settings
              </button>
            </div>
          </div>
        )}

        {/* Account Tab */}
        {activeTab === 'account' && (
          <div>
            <h2 className="text-xl font-semibold text-white mb-6 flex items-center">
              <User className="w-5 h-5 mr-2 text-blue-400" />
              Account Information
            </h2>
            
            <div className="space-y-6">
              <div className="flex items-center space-x-4 p-4 bg-gray-800 rounded-lg">
                <div className="w-12 h-12 bg-blue-600 rounded-full flex items-center justify-center">
                  <span className="text-white text-lg font-bold">
                    {user?.username?.charAt(0).toUpperCase()}
                  </span>
                </div>
                <div>
                  <p className="text-lg font-medium text-white">{user?.username}</p>
                  <p className="text-sm text-gray-400">Paper Trading Account</p>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="p-4 bg-gray-800 rounded-lg">
                  <p className="text-sm text-gray-400 mb-1">Account Type</p>
                  <p className="text-lg font-medium text-white">Paper Trading</p>
                </div>
                
                <div className="p-4 bg-gray-800 rounded-lg">
                  <p className="text-sm text-gray-400 mb-1">Trading Mode</p>
                  <p className="text-lg font-medium text-green-400">Simulated</p>
                </div>
                
                <div className="p-4 bg-gray-800 rounded-lg">
                  <p className="text-sm text-gray-400 mb-1">Available Strategies</p>
                  <p className="text-lg font-medium text-white">4 Active</p>
                </div>
                
                <div className="p-4 bg-gray-800 rounded-lg">
                  <p className="text-sm text-gray-400 mb-1">Risk Level</p>
                  <p className="text-lg font-medium text-yellow-400">Moderate</p>
                </div>
              </div>

              <div className="p-4 bg-blue-900/30 border border-blue-700/50 rounded-lg">
                <p className="text-sm text-blue-300 mb-2">
                  <strong>Important:</strong> This is a paper trading platform for educational purposes only. No real money is involved.
                </p>
                <p className="text-xs text-blue-200">
                  All trades are simulated using real market data for learning and practice purposes.
                </p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default Settings
