import React from 'react'

const STATUS_COLORS = {
  pending:   '#f5a623',
  rendering: '#7b68ee',
  rendered:  '#50e3c2',
  uploading: '#4a9eff',
  done:      '#00e5a0',
  failed:    '#ff4444',
}

export default function StatusBadge({ status }) {
  const color = STATUS_COLORS[status] || '#606060'
  const isActive = ['rendering','uploading'].includes(status)
  
  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: 6,
      fontFamily: 'var(--font-mono)',
      fontSize: 10,
      fontWeight: 700,
      letterSpacing: '0.1em',
      textTransform: 'uppercase',
      color,
      background: `${color}15`,
      padding: '2px 8px',
      borderRadius: 4,
      border: `1px solid ${color}30`,
      transition: 'all 0.2s ease',
      animation: isActive ? 'blink 2s ease infinite' : 'none',
    }}>
      <span style={{
        width: 6,
        height: 6,
        borderRadius: '50%',
        background: color,
        flexShrink: 0,
        boxShadow: isActive ? `0 0 8px ${color}` : 'none',
        animation: isActive
          ? 'pulse-dot 1.2s cubic-bezier(0.4, 0, 0.6, 1) infinite'
          : 'none',
      }} />
      {status}
    </span>
  )
}
