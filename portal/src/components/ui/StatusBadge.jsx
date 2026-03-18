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
  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: 5,
      fontFamily: 'var(--font-mono)',
      fontSize: 10,
      fontWeight: 600,
      letterSpacing: '0.08em',
      textTransform: 'uppercase',
      color,
    }}>
      <span style={{
        width: 5,
        height: 5,
        borderRadius: '50%',
        background: color,
        flexShrink: 0,
        animation: ['rendering','uploading'].includes(status)
          ? 'pulse-dot 1.4s ease infinite'
          : 'none',
      }} />
      {status}
    </span>
  )
}
