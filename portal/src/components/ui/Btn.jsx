import React from 'react'

const VARIANTS = {
  default: {
    background: 'transparent',
    border: '1px solid var(--line-2)',
    color: 'var(--text-1)',
    hoverBg: 'var(--bg-3)',
    hoverColor: 'var(--text-0)',
    hoverBorder: 'var(--line-2)',
  },
  primary: {
    background: 'var(--accent)',
    border: '1px solid var(--accent)',
    color: '#000',
    hoverBg: '#00ffb3',
    hoverColor: '#000',
    hoverBorder: '#00ffb3',
  },
  danger: {
    background: 'transparent',
    border: '1px solid var(--line-1)',
    color: 'var(--text-2)',
    hoverBg: 'rgba(255,68,68,0.1)',
    hoverColor: '#ff4444',
    hoverBorder: 'rgba(255,68,68,0.4)',
  },
  warn: {
    background: 'transparent',
    border: '1px solid rgba(245,166,35,0.3)',
    color: '#f5a623',
    hoverBg: 'rgba(245,166,35,0.1)',
    hoverColor: '#f5a623',
    hoverBorder: 'rgba(245,166,35,0.6)',
  },
  success: {
    background: 'transparent',
    border: '1px solid rgba(0,229,160,0.3)',
    color: 'var(--accent)',
    hoverBg: 'var(--accent-dim)',
    hoverColor: 'var(--accent)',
    hoverBorder: 'rgba(0,229,160,0.6)',
  },
}

export default function Btn({
  children, onClick, variant = 'default', size = 'md',
  disabled, style, type = 'button', title,
}) {
  const [hovered, setHovered] = React.useState(false)
  const v = VARIANTS[variant] || VARIANTS.default

  const padding = size === 'sm' ? '3px 10px' : size === 'lg' ? '9px 20px' : '5px 14px'
  const fontSize = size === 'sm' ? 11 : size === 'lg' ? 13 : 12

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      title={title}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        padding,
        fontSize,
        fontFamily: 'var(--font-mono)',
        fontWeight: 500,
        letterSpacing: '0.04em',
        borderRadius: 3,
        background: hovered && !disabled ? v.hoverBg : v.background,
        border: hovered && !disabled ? `1px solid ${v.hoverBorder}` : v.border,
        color: hovered && !disabled ? v.hoverColor : v.color,
        transition: 'all 0.1s',
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.4 : 1,
        whiteSpace: 'nowrap',
        ...style,
      }}
    >
      {children}
    </button>
  )
}
