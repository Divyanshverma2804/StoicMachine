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
  const [catFilter, setCatFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [selected, setSelected] = useState(new Set())

  const counts = useMemo(() => {
    const c = { pending:0, rendering:0, rendered:0, uploading:0, done:0, failed:0 }
    jobs.forEach(j => { if (c[j.status] !== undefined) c[j.status]++ })
    return c
  }, [jobs])

  const filtered = useMemo(() => {
    let base = jobs
    if (catFilter) {
      base = base.filter(j => (j.category || 'uncategorized') === catFilter)
    }
    if (statusFilter) {
      if (statusFilter === 'rendered_not_scheduled') {
        base = base.filter(j => j.status === 'rendered' && !j.upload_time)
      } else {
        base = base.filter(j => j.status === statusFilter)
      }
    }

    return [...base].sort((a, b) => {
      const ai = STATUS_ORDER.indexOf(a.status)
      const bi = STATUS_ORDER.indexOf(b.status)
      return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi)
    })
  }, [jobs, catFilter, statusFilter])

  const toggleSelect = (id) => {
    setSelected(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const clearSelect = () => setSelected(new Set())

  if (isLoading) return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Skeleton stats */}
      <div style={{ display: 'flex', borderBottom: '1px solid var(--line-0)' }}>
        {[1,2,3,4,5,6].map(i => (
          <div key={i} style={{ padding: '8px 14px', borderRight: '1px solid var(--line-0)', width: 80 }}>
            <div style={{ height: 12, background: 'var(--bg-3)', borderRadius: 2, animation: 'pulse-dot 1.5s infinite' }} />
          </div>
        ))}
      </div>
      {/* Skeleton cards */}
      <div style={{ flex: 1, padding: '20px' }}>
        {[1,2,3,4].map(i => (
          <div key={i} style={{ marginBottom: 20, padding: 16, border: '1px solid var(--line-0)', borderRadius: 4, opacity: 0.5 }}>
            <div style={{ height: 14, width: '40%', background: 'var(--bg-3)', marginBottom: 12, animation: 'pulse-dot 1.5s infinite' }} />
            <div style={{ height: 10, width: '60%', background: 'var(--bg-3)', animation: 'pulse-dot 1.5s infinite' }} />
          </div>
        ))}
      </div>
    </div>
  )

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Stats & Filters */}
      <div style={{ display: 'flex', flexDirection: 'column', borderBottom: '1px solid var(--line-0)', flexShrink: 0 }}>
        {/* Status Filter */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 0,
          borderBottom: '1px solid var(--line-0)',
          overflowX: 'auto',
          padding: '0 4px',
        }}>
          <span style={{ fontSize: 10, color: 'var(--text-3)', padding: '0 10px', whiteSpace: 'nowrap', letterSpacing: '0.06em' }}>
            STATUS
          </span>
          {[
            { label: 'all', value: '' },
            { label: 'rendered (unscheduled)', value: 'rendered_not_scheduled' },
            { label: 'done', value: 'done' },
            { label: 'failed', value: 'failed' },
            { label: 'pending', value: 'pending' },
            { label: 'rendering', value: 'rendering' },
            { label: 'uploading', value: 'uploading' },
          ].map(opt => (
            <button
              key={opt.value}
              onClick={() => setStatusFilter(opt.value)}
              style={{
                padding: '9px 12px',
                fontSize: 11,
                fontFamily: 'var(--font-mono)',
                background: 'transparent',
                border: 'none',
                borderBottom: statusFilter === opt.value ? '1px solid var(--accent)' : '1px solid transparent',
                color: statusFilter === opt.value ? 'var(--text-0)' : 'var(--text-2)',
                cursor: 'pointer',
                whiteSpace: 'nowrap',
                transition: 'all 0.1s',
              }}
            >
              {opt.label}
              {counts[opt.value] > 0 && (
                <span style={{ marginLeft: 6, fontSize: 9, opacity: 0.6 }}>({counts[opt.value]})</span>
              )}
            </button>
          ))}
        </div>

        {/* Category filter */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 0,
          flexShrink: 0,
          overflowX: 'auto',
          padding: '0 4px',
        }}>
          <span style={{ fontSize: 10, color: 'var(--text-3)', padding: '0 10px', whiteSpace: 'nowrap', letterSpacing: '0.06em' }}>
            CATEGORY
          </span>
          {[{ label: 'all', value: '' }, ...CATEGORIES.map(c => ({ label: c, value: c }))].map(opt => (
            <button
              key={opt.value}
              onClick={() => setCatFilter(opt.value)}
              style={{
                padding: '9px 12px',
                fontSize: 11,
                fontFamily: 'var(--font-mono)',
                background: 'transparent',
                border: 'none',
                borderBottom: catFilter === opt.value ? '1px solid var(--accent)' : '1px solid transparent',
                color: catFilter === opt.value ? 'var(--text-0)' : 'var(--text-2)',
                cursor: 'pointer',
                whiteSpace: 'nowrap',
                transition: 'color 0.1s',
              }}
            >
              {opt.label}
            </button>
          ))}
        </div>
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
