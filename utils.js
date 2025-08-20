import { clsx } from "clsx";
import { twMerge } from "tailwind-merge"

export function cn(...inputs) {
  return twMerge(clsx(inputs));
}

export function formatCurrency(amount, currency = 'USD') {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: currency,
  }).format(amount)
}

export function formatDate(date, options = {}) {
  const defaultOptions = {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  }
  
  return new Intl.DateTimeFormat('en-US', { ...defaultOptions, ...options }).format(
    new Date(date)
  )
}

export function formatDateTime(date) {
  return new Intl.DateTimeFormat('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(date))
}

export function formatNumber(number, options = {}) {
  return new Intl.NumberFormat('en-US', options).format(number)
}

export function formatPercentage(value, decimals = 1) {
  return `${(value * 100).toFixed(decimals)}%`
}

export function truncateText(text, maxLength = 50) {
  if (text.length <= maxLength) return text
  return text.slice(0, maxLength) + '...'
}

export function getInitials(firstName, lastName) {
  return `${firstName?.[0] || ''}${lastName?.[0] || ''}`.toUpperCase()
}

export function debounce(func, wait) {
  let timeout
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout)
      func(...args)
    }
    clearTimeout(timeout)
    timeout = setTimeout(later, wait)
  }
}

export function generateId() {
  return Math.random().toString(36).substr(2, 9)
}

export function isValidEmail(email) {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  return emailRegex.test(email)
}

export function getStatusColor(status) {
  const statusColors = {
    // Deal statuses
    'lead': 'bg-gray-100 text-gray-800',
    'qualified': 'bg-blue-100 text-blue-800',
    'proposal': 'bg-yellow-100 text-yellow-800',
    'negotiation': 'bg-orange-100 text-orange-800',
    'won': 'bg-green-100 text-green-800',
    'lost': 'bg-red-100 text-red-800',
    
    // Order statuses
    'pending': 'bg-gray-100 text-gray-800',
    'confirmed': 'bg-blue-100 text-blue-800',
    'processing': 'bg-yellow-100 text-yellow-800',
    'shipped': 'bg-purple-100 text-purple-800',
    'delivered': 'bg-green-100 text-green-800',
    'cancelled': 'bg-red-100 text-red-800',
    
    // Payment statuses
    'paid': 'bg-green-100 text-green-800',
    'partial': 'bg-yellow-100 text-yellow-800',
    'overdue': 'bg-red-100 text-red-800',
    
    // Priority levels
    'low': 'bg-gray-100 text-gray-800',
    'medium': 'bg-yellow-100 text-yellow-800',
    'high': 'bg-orange-100 text-orange-800',
    'urgent': 'bg-red-100 text-red-800',
    
    // Default
    'default': 'bg-gray-100 text-gray-800'
  }
  
  return statusColors[status?.toLowerCase()] || statusColors.default
}

export function calculateDaysAgo(date) {
  const now = new Date()
  const targetDate = new Date(date)
  const diffTime = Math.abs(now - targetDate)
  const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24))
  
  if (diffDays === 0) return 'Today'
  if (diffDays === 1) return '1 day ago'
  if (diffDays < 7) return `${diffDays} days ago`
  if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`
  if (diffDays < 365) return `${Math.floor(diffDays / 30)} months ago`
  return `${Math.floor(diffDays / 365)} years ago`
}

export function sortBy(array, key, direction = 'asc') {
  return [...array].sort((a, b) => {
    const aVal = key.split('.').reduce((obj, k) => obj?.[k], a)
    const bVal = key.split('.').reduce((obj, k) => obj?.[k], b)
    
    if (aVal < bVal) return direction === 'asc' ? -1 : 1
    if (aVal > bVal) return direction === 'asc' ? 1 : -1
    return 0
  })
}

export function groupBy(array, key) {
  return array.reduce((groups, item) => {
    const group = key.split('.').reduce((obj, k) => obj?.[k], item)
    groups[group] = groups[group] || []
    groups[group].push(item)
    return groups
  }, {})
}
