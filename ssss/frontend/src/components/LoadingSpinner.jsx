import React from 'react'

function LoadingSpinner({ size = 'md' }) {
  const sizeClasses = {
    sm: 'w-4 h-4',
    md: 'w-6 h-6',
    lg: 'w-8 h-8',
    xl: 'w-12 h-12'
  }

  return (
    <div className="flex items-center justify-center">
      <div 
        className={`
          ${sizeClasses[size]} 
          border-2 border-blue-600 border-t-transparent 
          rounded-full animate-spin
        `}
      ></div>
    </div>
  )
}

export default LoadingSpinner
