import React, { useState, useEffect } from 'react'
import { fmtTime, utcToIST } from '../../lib/timeUtils'

const TABS = [
  { id: 'queue',     label: 'queue'     },
  { id: 'calendar',  label: 'calendar'  },
  { id: 'diary',     label: 'diary'     },
  { id: 'analytics', label: 'analytics' },
]

export default function Header({ activeTab, onTabChange }) {
  const [utc, setUtc] = useState('')
  const [ist, setIst] = useState('')

  useEffect(() => {
    const tick = () => {
      const now = new Date()
      setUtc(fmtTime(now))
      setIst(fmtTime(utcToIST(now)))
    }
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [])

  return (
    <header style={{
      height: 44,
      borderBottom: '1px solid var(--line-0)',
      display: 'flex',
      alignItems: 'center',
      paddingLeft: 0,
      background: 'var(--bg-0)',
      flexShrink: 0,
      position: 'sticky',
      top: 0,
      zIndex: 100,
    }}>
      {/* Wordmark */}
      <div style={{
        width: 160,
        padding: '0 20px',
        borderRight: '1px solid var(--line-0)',
        height: '100%',
        display: 'flex',
        alignItems: 'center',
        flexShrink: 0,
      }}>
        <span style={{
          fontFamily: 'var(--font-mono)',
          fontWeight: 700,
          fontSize: 13,
          letterSpacing: '0.12em',
          color: 'var(--text-0)',
          textTransform: 'uppercase',
        }}>
          reel<span style={{ color: 'var(--accent)' }}>forge</span>
        </span>
      </div>

      {/* Nav */}
      <nav style={{ display: 'flex', height: '100%', flex: 1 }}>
        {TABS.map(tab => (
          <button
            key={tab.id}
            onClick={() => onTabChange(tab.id)}
            style={{
              height: '100%',
              padding: '0 20px',
              background: 'transparent',
              border: 'none',
              borderRight: '1px solid var(--line-0)',
              borderBottom: activeTab === tab.id
                ? '1px solid var(--accent)'
                : '1px solid transparent',
              color: activeTab === tab.id ? 'var(--text-0)' : 'var(--text-2)',
              fontSize: 12,
              fontFamily: 'var(--font-mono)',
              fontWeight: activeTab === tab.id ? 600 : 400,
              letterSpacing: '0.06em',
              cursor: 'pointer',
              transition: 'color 0.1s',
              marginBottom: activeTab === tab.id ? -1 : 0,
            }}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      {/* Clock + status */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 0,
        height: '100%',
        flexShrink: 0,
      }}>
        <div style={{
          padding: '0 16px',
          borderLeft: '1px solid var(--line-0)',
          height: '100%',
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          fontSize: 11,
          fontFamily: 'var(--font-mono)',
        }}>
          <span style={{ color: 'var(--text-2)' }}>
            utc <span style={{ color: 'var(--text-1)' }}>{utc}</span>
          </span>
          <span style={{ color: 'var(--line-2)' }}>|</span>
          <span style={{ color: 'var(--text-2)' }}>
            ist <span style={{ color: '#f5a623' }}>{ist}</span>
          </span>
        </div>
        <div style={{
          padding: '0 14px',
          borderLeft: '1px solid var(--line-0)',
          height: '100%',
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          fontSize: 11,
          color: 'var(--text-2)',
        }}>
          <span style={{
            width: 5, height: 5, borderRadius: '50%',
            background: 'var(--accent)',
            animation: 'pulse-dot 2s ease infinite',
          }} />
          live
        </div>
        <a
          href='/logout'
          onClick={e => { if (!confirm('lock session?')) e.preventDefault() }}
          style={{
            padding: '0 14px',
            borderLeft: '1px solid var(--line-0)',
            height: '100%',
            display: 'flex',
            alignItems: 'center',
            fontSize: 11,
            color: 'var(--text-2)',
            textDecoration: 'none',
            fontFamily: 'var(--font-mono)',
            transition: 'color 0.1s',
          }}
          onMouseEnter={e => e.target.style.color = '#ff4444'}
          onMouseLeave={e => e.target.style.color = 'var(--text-2)'}
        >
          lock
        </a>
      </div>
    </header>
  )
}
