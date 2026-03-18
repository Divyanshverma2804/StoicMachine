import React, { useState, useMemo } from 'react'
import { useJobs } from '../../hooks/useJobs'
import JobCard from './JobCard'
import BulkScheduleBar from './BulkScheduleBar'

const CATEGORIES = [
  'silent_power','stoic_philosophy','harsh_truths','discipline',
  'psychological_power','respect_dynamics','masculine_mindset','self_mastery','uncategorized',
]

const STATUS_ORDER = ['rendering','uploading','pending','rendered','failed','done']

export default function JobsList() {
  const { data: jobs = [], isLoading } = useJobs()
  const [filter, setFilter] = useState('')
  const [selected, setSelected] = useState(new Set())

  const counts = useMemo(() => {
    const c = { pending:0, rendering:0, rendered:0, uploading:0, done:0, failed:0 }
    jobs.forEach(j => { if (c[j.status] !== undefined) c[j.status]++ })
    return c
  }, [jobs])

  const filtered = useMemo(() => {
    const base = filter ? jobs.filter(j => (j.category || 'uncategorized') === filter) : jobs
    return [...base].sort((a, b) => {
      const ai = STATUS_ORDER.indexOf(a.status)
      const bi = STATUS_ORDER.indexOf(b.status)
      return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi)
    })
  }, [jobs, filter])

  const toggleSelect = (id) => {
    setSelected(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const clearSelect = () => setSelected(new Set())

  if (isLoading) return (
    <div style={{ padding: 20, color: 'var(--text-2)', fontSize: 12 }}>
      loading jobs…
    </div>
  )

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Stats bar */}
      <div style={{
        display: 'flex',
        gap: 0,
        borderBottom: '1px solid var(--line-0)',
        flexShrink: 0,
      }}>
        {Object.entries(counts).map(([status, n]) => (
          <div key={status} style={{
            padding: '8px 14px',
            borderRight: '1px solid var(--line-0)',
            fontSize: 11,
            fontFamily: 'var(--font-mono)',
            color: n > 0 ? 'var(--text-1)' : 'var(--text-3)',
          }}>
            <span style={{ color: n > 0 ? 'var(--text-0)' : 'var(--text-3)', fontWeight: 600 }}>{n}</span>
            {' '}{status}
          </div>
        ))}
      </div>

      {/* Category filter */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 0,
        borderBottom: '1px solid var(--line-0)',
        flexShrink: 0,
        overflowX: 'auto',
        padding: '0 4px',
      }}>
        <span style={{ fontSize: 10, color: 'var(--text-3)', padding: '0 10px', whiteSpace: 'nowrap', letterSpacing: '0.06em' }}>
          FILTER
        </span>
        {[{ label: 'all', value: '' }, ...CATEGORIES.map(c => ({ label: c, value: c }))].map(opt => (
          <button
            key={opt.value}
            onClick={() => setFilter(opt.value)}
            style={{
              padding: '9px 12px',
              fontSize: 11,
              fontFamily: 'var(--font-mono)',
              background: 'transparent',
              border: 'none',
              borderBottom: filter === opt.value ? '1px solid var(--accent)' : '1px solid transparent',
              color: filter === opt.value ? 'var(--text-0)' : 'var(--text-2)',
              cursor: 'pointer',
              whiteSpace: 'nowrap',
              transition: 'color 0.1s',
            }}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {/* Jobs */}
      <div style={{ flex: 1, overflowY: 'auto' }}>
        {filtered.length === 0 ? (
          <div style={{
            padding: '48px 20px',
            textAlign: 'center',
            color: 'var(--text-3)',
            fontSize: 12,
          }}>
            <div style={{ fontSize: 28, marginBottom: 12 }}>_</div>
            no jobs yet — paste a script to get started
          </div>
        ) : (
          filtered.map(job => (
            <JobCard
              key={job.id}
              job={job}
              selected={selected.has(String(job.id))}
              onToggleSelect={toggleSelect}
            />
          ))
        )}
      </div>

      {/* Bulk bar */}
      <BulkScheduleBar
        selected={selected}
        jobs={jobs}
        onClear={clearSelect}
      />
    </div>
  )
}
