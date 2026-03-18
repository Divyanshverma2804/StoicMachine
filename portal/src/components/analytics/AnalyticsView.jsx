import React from 'react'
import { useAnalytics, useRefreshAnalytics } from '../../hooks/useAnalytics'
import Btn from '../ui/Btn'

function StatCard({ label, value, color }) {
  return (
    <div style={{
      background: 'var(--bg-2)',
      border: '1px solid var(--line-0)',
      borderRadius: 3,
      padding: '14px 16px',
    }}>
      <div style={{
        fontSize: 10,
        color: 'var(--text-2)',
        letterSpacing: '0.1em',
        textTransform: 'uppercase',
        marginBottom: 8,
      }}>
        {label}
      </div>
      <div style={{
        fontSize: 26,
        fontWeight: 700,
        color: color || 'var(--text-0)',
        fontFamily: 'var(--font-mono)',
        lineHeight: 1,
      }}>
        {value ?? '—'}
      </div>
    </div>
  )
}

export default function AnalyticsTab() {
  const { data = [], isLoading, refetch } = useAnalytics()
  const refresh = useRefreshAnalytics()

  const totals = data.reduce((acc, row) => {
    acc.total  += row.total  || 0
    acc.done   += row.done   || 0
    acc.failed += row.failed || 0
    acc.views  += (row.avg_views * row.done) || 0
    return acc
  }, { total: 0, done: 0, failed: 0, views: 0 })

  const avgViews = totals.done > 0 ? Math.round(totals.views / totals.done) : 0
  const maxViews = Math.max(...data.map(r => r.avg_views || 0), 1)

  return (
    <div style={{ height: '100%', overflowY: 'auto', padding: '20px 24px' }}>
      {/* Summary */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
        gap: 10,
        marginBottom: 24,
      }}>
        <StatCard label='total reels'   value={totals.total} />
        <StatCard label='published'     value={totals.done}   color='var(--accent)' />
        <StatCard label='total views'   value={totals.views.toLocaleString()} color='#4a9eff' />
        <StatCard label='avg views'     value={avgViews.toLocaleString()} color='#7b68ee' />
        <StatCard label='failed'        value={totals.failed} color='#ff4444' />
      </div>

      {/* Table header */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: 12,
      }}>
        <div style={{ fontSize: 10, color: 'var(--text-2)', letterSpacing: '0.1em' }}>
          CATEGORY BREAKDOWN
        </div>
        <Btn size='sm' onClick={() => refetch()} disabled={isLoading}>
          {isLoading ? 'loading…' : '↻ refresh'}
        </Btn>
      </div>

      {/* Table */}
      <div style={{
        background: 'var(--bg-1)',
        border: '1px solid var(--line-0)',
        borderRadius: 3,
        overflow: 'hidden',
      }}>
        {/* Header row */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: '200px 60px 60px 60px 100px 1fr',
          gap: 0,
          borderBottom: '1px solid var(--line-0)',
          padding: '7px 16px',
          fontSize: 10,
          color: 'var(--text-2)',
          letterSpacing: '0.08em',
          textTransform: 'uppercase',
        }}>
          <span>category</span>
          <span>total</span>
          <span>done</span>
          <span>failed</span>
          <span>avg views</span>
          <span>success</span>
        </div>

        {isLoading ? (
          <div style={{ padding: '24px 16px', fontSize: 12, color: 'var(--text-3)', textAlign: 'center' }}>
            loading…
          </div>
        ) : data.length === 0 ? (
          <div style={{ padding: '24px 16px', fontSize: 12, color: 'var(--text-3)', textAlign: 'center' }}>
            no data yet — publish some reels first
          </div>
        ) : data.map((row, i) => {
          const pct = Math.round(((row.done || 0) / Math.max(row.total || 0, 1)) * 100)
          const viewPct = Math.round(((row.avg_views || 0) / maxViews) * 100)
          return (
            <div
              key={row.category}
              style={{
                display: 'grid',
                gridTemplateColumns: '200px 60px 60px 60px 100px 1fr',
                gap: 0,
                padding: '9px 16px',
                borderBottom: i < data.length - 1 ? '1px solid var(--line-0)' : 'none',
                fontSize: 12,
                alignItems: 'center',
                transition: 'background 0.1s',
              }}
              onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-2)'}
              onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
            >
              <span style={{ fontWeight: 600, color: 'var(--text-0)' }}>{row.category}</span>
              <span style={{ color: 'var(--text-1)' }}>{row.total}</span>
              <span style={{ color: 'var(--accent)' }}>{row.done}</span>
              <span style={{ color: row.failed > 0 ? '#ff4444' : 'var(--text-2)' }}>{row.failed}</span>
              <span style={{ color: '#4a9eff', fontFamily: 'var(--font-mono)' }}>
                {(row.avg_views || 0).toLocaleString()}
              </span>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <div style={{
                  flex: 1, height: 4,
                  background: 'var(--line-0)',
                  borderRadius: 2,
                  overflow: 'hidden',
                }}>
                  <div style={{
                    height: '100%',
                    width: `${pct}%`,
                    background: pct > 80 ? 'var(--accent)' : pct > 40 ? '#4a9eff' : '#f5a623',
                    borderRadius: 2,
                    transition: 'width 0.5s ease',
                  }} />
                </div>
                <span style={{ fontSize: 10, color: 'var(--text-2)', width: 28, textAlign: 'right' }}>
                  {pct}%
                </span>
              </div>
            </div>
          )
        })}
      </div>

      <div style={{ marginTop: 12, fontSize: 11, color: 'var(--text-3)' }}>
        views synced every 6h via youtube readonly token. 0 views = not yet synced.
      </div>
    </div>
  )
}
