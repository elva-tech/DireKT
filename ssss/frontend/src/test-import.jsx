// Test import
import useAuthStore from './stores/authStore.js'

console.log('useAuthStore:', useAuthStore)
console.log('useAuthStore type:', typeof useAuthStore)

// Test if it's a function
if (typeof useAuthStore === 'function') {
  console.log('✅ useAuthStore imported successfully!')
} else {
  console.log('❌ useAuthStore import failed:', useAuthStore)
}

export default function TestComponent() {
  const auth = useAuthStore()
  console.log('Auth state:', auth)
  
  return (
    <div>
      <h1>Test Component</h1>
      <p>Auth: {JSON.stringify(auth)}</p>
    </div>
  )
}
