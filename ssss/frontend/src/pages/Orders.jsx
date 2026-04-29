import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from 'react-query'
import { 
  Receipt, 
  TrendingUp, 
  TrendingDown, 
  X, 
  Check,
  Clock,
  AlertCircle
} from 'lucide-react'
import api from '../services/api'
import LoadingSpinner from '../components/LoadingSpinner'
import toast from 'react-hot-toast'

function Orders() {
  const [filter, setFilter] = useState('all')
  const queryClient = useQueryClient()

  // Fetch orders
  const { data: ordersData, isLoading: ordersLoading } = useQuery(
    'orders',
    () => api.get('/trading/orders/history').then(res => res.data),
    { refetchInterval: 10000 } // Refresh every 10 seconds
  )

  // Cancel order mutation
  const cancelOrderMutation = useMutation(
    (orderId) => api.delete(`/trading/orders/${orderId}`),
    {
      onSuccess: () => {
        toast.success('Order cancelled successfully!')
        queryClient.invalidateQueries('orders')
      },
      onError: (error) => {
        toast.error('Failed to cancel order: ' + (error.response?.data?.detail || error.message))
      }
    }
  )

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    }).format(amount)
  }

  const formatDateTime = (dateString) => {
    const date = new Date(dateString)
    return date.toLocaleString('en-IN', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  const getStatusIcon = (status) => {
    switch (status) {
      case 'COMPLETED':
        return <Check className="w-4 h-4 text-green-400" />
      case 'PENDING':
        return <Clock className="w-4 h-4 text-yellow-400" />
      case 'CANCELLED':
        return <X className="w-4 h-4 text-red-400" />
      case 'REJECTED':
        return <AlertCircle className="w-4 h-4 text-red-400" />
      default:
        return <Clock className="w-4 h-4 text-gray-400" />
    }
  }

  const getStatusColor = (status) => {
    switch (status) {
      case 'COMPLETED':
        return 'text-green-400'
      case 'PENDING':
        return 'text-yellow-400'
      case 'CANCELLED':
      case 'REJECTED':
        return 'text-red-400'
      default:
        return 'text-gray-400'
    }
  }

  const handleCancelOrder = (orderId) => {
    if (window.confirm('Are you sure you want to cancel this order?')) {
      cancelOrderMutation.mutate(orderId)
    }
  }

  const orders = ordersData?.orders || []
  
  const filteredOrders = orders.filter(order => {
    if (filter === 'all') return true
    if (filter === 'buy') return order.action === 'BUY'
    if (filter === 'sell') return order.action === 'SELL'
    if (filter === 'completed') return order.status === 'COMPLETED'
    if (filter === 'pending') return order.status === 'PENDING'
    return true
  })

  if (ordersLoading) {
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
          <h1 className="text-3xl font-bold text-white">Order History</h1>
          <p className="text-gray-400 mt-1">
            Track and manage your paper trading orders
          </p>
        </div>
        <div className="text-sm text-gray-400">
          Total Orders: {orders.length}
        </div>
      </div>

      {/* Filters */}
      <div className="trading-card p-4">
        <div className="flex flex-wrap gap-2">
          {[
            { value: 'all', label: 'All Orders' },
            { value: 'buy', label: 'Buy Orders' },
            { value: 'sell', label: 'Sell Orders' },
            { value: 'completed', label: 'Completed' },
            { value: 'pending', label: 'Pending' }
          ].map((filterOption) => (
            <button
              key={filterOption.value}
              onClick={() => setFilter(filterOption.value)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                filter === filterOption.value
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-white'
              }`}
            >
              {filterOption.label}
            </button>
          ))}
        </div>
      </div>

      {/* Orders Table */}
      <div className="trading-card p-6">
        <h2 className="text-xl font-semibold text-white mb-6 flex items-center">
          <Receipt className="w-5 h-5 mr-2 text-blue-400" />
          Orders
        </h2>

        {filteredOrders.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-700">
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-400">Order ID</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-400">Symbol</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-400">Action</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-400">Quantity</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-400">Price</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-400">Status</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-400">P&L</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-400">Time</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-400">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredOrders.map((order, index) => (
                  <tr key={index} className="border-b border-gray-800 hover:bg-gray-800/50 transition-colors">
                    <td className="py-3 px-4">
                      <span className="text-white font-mono text-sm">{order.order_id}</span>
                    </td>
                    <td className="py-3 px-4 text-white font-medium">{order.symbol}</td>
                    <td className="py-3 px-4">
                      <span className={`inline-flex items-center px-2 py-1 rounded text-xs font-medium ${
                        order.action === 'BUY' 
                          ? 'bg-green-900/50 text-green-300' 
                          : 'bg-red-900/50 text-red-300'
                      }`}>
                        {order.action === 'BUY' ? (
                          <TrendingUp className="w-3 h-3 mr-1" />
                        ) : (
                          <TrendingDown className="w-3 h-3 mr-1" />
                        )}
                        {order.action}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-white">{order.quantity} kg</td>
                    <td className="py-3 px-4 text-white font-mono">
                      {formatCurrency(order.price)}
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex items-center space-x-2">
                        {getStatusIcon(order.status)}
                        <span className={`text-sm font-medium ${getStatusColor(order.status)}`}>
                          {order.status}
                        </span>
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      {order.pnl !== undefined && (
                        <span className={`font-medium ${
                          order.pnl >= 0 ? 'text-green-400' : 'text-red-400'
                        }`}>
                          {formatCurrency(order.pnl)}
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-sm text-gray-400">
                      {formatDateTime(order.created_at)}
                    </td>
                    <td className="py-3 px-4">
                      {order.status === 'PENDING' && (
                        <button
                          onClick={() => handleCancelOrder(order.order_id)}
                          disabled={cancelOrderMutation.isLoading}
                          className="text-red-400 hover:text-red-300 text-sm font-medium transition-colors"
                        >
                          {cancelOrderMutation.isLoading ? 'Cancelling...' : 'Cancel'}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center py-12 text-gray-400">
            <Receipt className="w-16 h-16 mx-auto mb-4 opacity-50" />
            <p className="text-lg mb-2">No orders found</p>
            <p className="text-sm">
              {filter === 'all' 
                ? 'Start trading to see your orders here'
                : `No ${filter} orders found`
              }
            </p>
          </div>
        )}
      </div>

      {/* Order Statistics */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="trading-card p-6">
          <h3 className="text-sm font-medium text-gray-400 mb-2">Total Orders</h3>
          <p className="text-2xl font-bold text-white">{orders.length}</p>
        </div>
        
        <div className="trading-card p-6">
          <h3 className="text-sm font-medium text-gray-400 mb-2">Completed</h3>
          <p className="text-2xl font-bold text-green-400">
            {orders.filter(o => o.status === 'COMPLETED').length}
          </p>
        </div>
        
        <div className="trading-card p-6">
          <h3 className="text-sm font-medium text-gray-400 mb-2">Pending</h3>
          <p className="text-2xl font-bold text-yellow-400">
            {orders.filter(o => o.status === 'PENDING').length}
          </p>
        </div>
        
        <div className="trading-card p-6">
          <h3 className="text-sm font-medium text-gray-400 mb-2">Total P&L</h3>
          <p className="text-2xl font-bold text-white">
            {formatCurrency(
              orders.reduce((total, order) => total + (order.pnl || 0), 0)
            )}
          </p>
        </div>
      </div>
    </div>
  )
}

export default Orders
