import React, { useState, useMemo } from 'react'
import Btn from '../ui/Btn'
import { useBulkSchedule } from '../../hooks/useJobs'
import { buildUTCDate, utcToIST, fmtDatetime } from '../../lib/timeUtils'

const PRIVACY_OPTS = [
  { value: 'public',   label: 'public'   },
  { value: 'unlisted', label: 'unlisted' },
  { value: 'private',  label: 'private'  },
]

export default function BulkScheduleBar({ selected, jobs, onClear }) {
  const [spanHrs, setSpanHrs] = useState(8)
  const [privacy, setPrivacy] = useState('public')
  const bulkSchedule = useBulkSchedule()

  const selectedJobs = useMemo(() =>
    [...selected].map(id => jobs.find(j => String(j.id) === id)).filter(Boolean),
    [selected, jobs]
  )

  const preview = useMemo(() => {
    const n = selectedJobs.length
    if (n === 0) return []
    const now = Date.now() + 5 * 60 * 1000
    const gap = n > 1 ? (spanHrs * 3600000) / (n - 1) : 0
    return selectedJobs.map((job, i) => {
      const t = new Date(now + gap * i)
      const ist = utcToIST(t)
      return { job, utc: fmtDatetime(t), ist: fmtDatetime(ist) }
    })
  }, [selectedJobs, spanHrs])

  const confirm = () => {
    if (!window.confirm(
      `Schedule ${selectedJobs.length} reels over ${spanHrs}h?\nFirst: ~5 min from now`
    )) return
    bulkSchedule.mutate(
      { jobIds: [...selected], spanHrs, privacy },
      { onSuccess: onClear }
    )
  }

  if (selected.size === 0) return null

  return (
    <div style={{
      position: 'sticky',
      bottom: 0,
      background: 'var(--bg-1)',
      borderTop: '1px solid var(--accent)',
      padding: '12px 20px',
      display: 'flex',
      gap: 16,
      alignItems: 'flex-start',
      flexWrap: 'wrap',
      zIndex: 50,
      animation: 'fadeIn 0.15s ease',
    }}>
      {/* Count */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, paddingTop: 2 }}>
        <span style={{
          background: 'var(--accent)',
          color: '#000',
          fontWeight: 700,
          fontSize: 11,
          padding: '2px 8px',
          borderRadius: 2,
        }}>
          {selected.size}
        </span>
        <span style={{ fontSize: 11, color: 'var(--text-1)' }}>selected</span>
        <Btn size='sm' variant='danger' onClick={onClear}>clear</Btn>
      </div>

      {/* Span */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        <div style={{ fontSize: 10, color: 'var(--text-2)', letterSpacing: '0.06em' }}>SPREAD (hrs)</div>
        <input
          type='number'
          value={spanHrs}
          min={0.5} max={168} step={0.5}
          onChange={e => setSpanHrs(parseFloat(e.target.value) || 8)}
          style={{ width: 72, padding: '4px 8px', fontSize: 12 }}
        />
      </div>

      {/* Privacy */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        <div style={{ fontSize: 10, color: 'var(--text-2)', letterSpacing: '0.06em' }}>VISIBILITY</div>
        <div style={{ display: 'flex', gap: 4 }}>
          {PRIVACY_OPTS.map(opt => (
            <button
              key={opt.value}
              onClick={() => setPrivacy(opt.value)}
              style={{
                padding: '4px 10px',
                fontSize: 11,
                fontFamily: 'var(--font-mono)',
                background: privacy === opt.value ? 'rgba(0,229,160,0.12)' : 'transparent',
                border: `1px solid ${privacy === opt.value ? 'var(--accent)' : 'var(--line-1)'}`,
                color: privacy === opt.value ? 'var(--accent)' : 'var(--text-2)',
                borderRadius: 2,
                cursor: 'pointer',
              }}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* Preview */}
      <div style={{ flex: 1, minWidth: 200, maxWidth: 380 }}>
        <div style={{ fontSize: 10, color: 'var(--text-2)', letterSpacing: '0.06em', marginBottom: 4 }}>PREVIEW</div>
        <div style={{
          maxHeight: 88,
          overflowY: 'auto',
          fontSize: 10,
          fontFamily: 'var(--font-mono)',
          lineHeight: 1.8,
        }}>
          {preview.map(({ job, utc, ist }, i) => (
            <div key={job.id} style={{ display: 'flex', gap: 8, color: 'var(--text-2)' }}>
              <span style={{ color: 'var(--text-3)', minWidth: 16 }}>{i+1}.</span>
              <span style={{ color: 'var(--text-1)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {job.reel_name}
              </span>
              <span style={{ color: '#f5a623', whiteSpace: 'nowrap' }}>{utc}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Confirm */}
      <div style={{ paddingTop: 18 }}>
        <Btn variant='primary' onClick={confirm} disabled={bulkSchedule.isPending}>
          {bulkSchedule.isPending ? 'scheduling…' : `schedule ${selected.size}`}
        </Btn>
      </div>
    </div>
  )
}
