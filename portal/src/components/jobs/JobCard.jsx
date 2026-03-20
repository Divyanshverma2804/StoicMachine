import React, { useState } from 'react'
import StatusBadge from '../ui/StatusBadge'
import Btn from '../ui/Btn'
import DateTimePicker from '../ui/DateTimePicker'
import toast from 'react-hot-toast'
import {
  useRetryJob, useDeleteJob, useSetUploadTime,
  useSetJobPrivacy, useUploadNow, useRefreshStats,
} from '../../hooks/useJobs'

const PRIVACY_OPTS = [
  { value: 'public',   label: '🌍 pub'  },
  { value: 'unlisted', label: '🔗 unl'  },
  { value: 'private',  label: '🔒 priv' },
]

export default function JobCard({ job, selected, onToggleSelect }) {
  const [showTimePicker, setShowTimePicker] = useState(false)
  const [pickedTime, setPickedTime] = useState(null)
  const [isHovered, setIsHovered] = useState(false)

  const retryJob     = useRetryJob()
  const deleteJob    = useDeleteJob()
  const setTime      = useSetUploadTime()
  const setPrivacy   = useSetJobPrivacy()
  const uploadNow    = useUploadNow()
  const refreshStats = useRefreshStats()

  const id = String(job.id)
  const isRendered = job.status === 'rendered'

  const handleSetTime = () => {
    if (!pickedTime) return
    setTime.mutate({ id, datetimeLocal: pickedTime.datetimeLocal })
    setShowTimePicker(false)
  }

  const handleCopyName = () => {
    navigator.clipboard.writeText(job.reel_name)
    toast.success('copied to clipboard', { duration: 1500, icon: '📋' })
  }

  return (
    <div
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      style={{
        borderBottom: '1px solid var(--line-0)',
        padding: '16px 20px',
        background: selected ? 'rgba(0,229,160,0.03)' : (isHovered ? 'var(--bg-1)' : 'transparent'),
        borderLeft: selected ? '2px solid var(--accent)' : '2px solid transparent',
        transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
        animation: 'fadeIn 0.2s ease',
        position: 'relative',
      }}
    >
      {/* Top row */}
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12, marginBottom: 8 }}>
        {isRendered && (
          <input
            type='checkbox'
            checked={selected}
            onChange={() => onToggleSelect(id)}
            style={{ marginTop: 2, accentColor: 'var(--accent)', cursor: 'pointer' }}
          />
        )}
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <span style={{
              fontSize: 13,
              fontWeight: 600,
              color: 'var(--text-0)',
              letterSpacing: '0.02em',
            }}>
              {job.reel_name}
            </span>
            <button
              onClick={handleCopyName}
              title="Copy Reel Name"
              style={{
                background: 'none',
                border: 'none',
                color: 'var(--text-3)',
                cursor: 'pointer',
                padding: '4px',
                fontSize: 10,
                display: 'flex',
                alignItems: 'center',
                transition: 'color 0.1s',
              }}
              onMouseEnter={(e) => e.target.style.color = 'var(--text-1)'}
              onMouseLeave={(e) => e.target.style.color = 'var(--text-3)'}
            >
              📋
            </button>
            <StatusBadge status={job.status} />
            {job.category && job.category !== 'uncategorized' && (
              <span style={{
                fontSize: 10,
                color: 'var(--text-2)',
                border: '1px solid var(--line-1)',
                padding: '1px 6px',
                borderRadius: 2,
              }}>
                {job.category}
              </span>
            )}
            {job.privacy && (
              <span style={{
                fontSize: 10,
                color: 'var(--text-2)',
                border: '1px solid var(--line-1)',
                padding: '1px 6px',
                borderRadius: 2,
              }}>
                {job.privacy}
              </span>
            )}
          </div>

          {/* Meta row */}
          <div style={{
            display: 'flex',
            gap: 16,
            marginTop: 5,
            fontSize: 11,
            color: 'var(--text-2)',
            flexWrap: 'wrap',
          }}>
            <span>#{id}</span>
            <span>{job.batch_id?.slice(0,8)}…</span>
            <span>{job.created_at}</span>
            {job.upload_time && (
              <span style={{ color: '#f5a623' }}>⏰ {job.upload_time}</span>
            )}
            {job.status === 'done' && job.views != null && (
              <span style={{ color: 'var(--accent)' }}>👁 {Number(job.views).toLocaleString()}</span>
            )}
            {job.yt_video_id && (
              <a
                href={`https://youtu.be/${job.yt_video_id}`}
                target='_blank'
                rel='noreferrer'
                style={{ color: 'var(--accent)', fontSize: 11 }}
              >
                youtu.be/{job.yt_video_id}
              </a>
            )}
          </div>
        </div>
      </div>

      {/* Error */}
      {job.error_msg && (
        <div style={{
          margin: '6px 0',
          padding: '6px 10px',
          background: 'rgba(255,68,68,0.06)',
          border: '1px solid rgba(255,68,68,0.15)',
          borderRadius: 3,
          fontSize: 11,
          color: '#ff6666',
          fontFamily: 'var(--font-mono)',
          wordBreak: 'break-all',
        }}>
          ✗ {job.error_msg}
        </div>
      )}

      {/* Actions */}
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center', marginTop: 6 }}>
        {['failed','pending'].includes(job.status) && (
          <Btn size='sm' variant='warn' onClick={() => retryJob.mutate(id)} disabled={retryJob.isPending}>
            retry
          </Btn>
        )}

        {isRendered && (
          <>
            <Btn size='sm' onClick={() => setShowTimePicker(v => !v)}>
              {showTimePicker ? 'cancel' : 'schedule'}
            </Btn>
            <Btn size='sm' variant='success' onClick={() => uploadNow.mutate(id)} disabled={uploadNow.isPending}>
              {uploadNow.isPending ? 'uploading…' : '↑ upload now'}
            </Btn>
            {/* Privacy chips */}
            {PRIVACY_OPTS.map(opt => (
              <button
                key={opt.value}
                onClick={() => setPrivacy.mutate({ id, privacy: opt.value })}
                style={{
                  padding: '3px 8px',
                  fontSize: 10,
                  fontFamily: 'var(--font-mono)',
                  background: job.privacy === opt.value ? 'rgba(0,229,160,0.1)' : 'transparent',
                  border: `1px solid ${job.privacy === opt.value ? 'var(--accent)' : 'var(--line-1)'}`,
                  color: job.privacy === opt.value ? 'var(--accent)' : 'var(--text-2)',
                  borderRadius: 2,
                  cursor: 'pointer',
                  transition: 'all 0.1s',
                }}
              >
                {opt.label}
              </button>
            ))}
          </>
        )}

        {job.status === 'done' && job.yt_video_id && (
          <Btn size='sm' onClick={() => refreshStats.mutate(id)} disabled={refreshStats.isPending}>
            {refreshStats.isPending ? 'fetching…' : '↻ stats'}
          </Btn>
        )}

        <Btn size='sm' variant='danger' onClick={() => {
          if (confirm('delete job?')) deleteJob.mutate(id)
        }}>
          ✕
        </Btn>
      </div>

      {/* Time picker inline */}
      {showTimePicker && (
        <div style={{
          marginTop: 10,
          padding: '10px 12px',
          background: 'var(--bg-2)',
          border: '1px solid var(--line-1)',
          borderRadius: 3,
        }}>
          <div style={{ fontSize: 11, color: 'var(--text-2)', marginBottom: 8 }}>
            set upload time (utc)
          </div>
          <DateTimePicker compact value={null} onChange={setPickedTime} />
          <div style={{ marginTop: 8 }}>
            <Btn size='sm' variant='success' onClick={handleSetTime} disabled={!pickedTime || setTime.isPending}>
              {setTime.isPending ? 'saving…' : 'confirm'}
            </Btn>
          </div>
        </div>
      )}
    </div>
  )
}
