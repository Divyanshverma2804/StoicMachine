import React, { useState, useEffect } from 'react'
import DateTimePicker from '../ui/DateTimePicker'
import Btn from '../ui/Btn'

const PRIVACY_OPTS = [
  { value: 'public',   label: 'public'   },
  { value: 'unlisted', label: 'unlisted' },
  { value: 'private',  label: 'private'  },
]

export default function SubmitForm() {
  const [content, setContent] = useState(() => sessionStorage.getItem('rf_content') || '')
  const [pickedTime, setPickedTime] = useState(null)
  const [privacy, setPrivacy] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const reelCount = (content.match(/^# ReelName:/gm) || []).length

  useEffect(() => {
    sessionStorage.setItem('rf_content', content)
  }, [content])

  const handleSubmit = (e) => {
    if (reelCount === 0) {
      e.preventDefault()
      return
    }
    setSubmitting(true)
    sessionStorage.removeItem('rf_content')
  }

  const inputSty = {
    padding: '5px 10px',
    borderRadius: 3,
    fontSize: 12,
    color: 'var(--text-1)',
  }

  return (
    <form
      method='POST'
      action='/submit'
      onSubmit={handleSubmit}
      style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}
    >
      {/* Hidden actual input */}
      <input
        type='datetime-local'
        name='upload_time'
        value={pickedTime?.datetimeLocal || ''}
        readOnly
        style={{ display: 'none' }}
      />
      <input type='hidden' name='privacy' value={privacy} />

      {/* Textarea */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: '14px 16px', gap: 10 }}>
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          fontSize: 10,
          color: 'var(--text-2)',
          letterSpacing: '0.06em',
        }}>
          <span>CONTENT.MD</span>
          <span style={{ color: reelCount > 0 ? 'var(--accent)' : 'var(--text-3)' }}>
            {content.length > 0
              ? `${content.length} chars · ${reelCount} reel${reelCount !== 1 ? 's' : ''}`
              : '0 chars'}
          </span>
        </div>

        <textarea
          name='content_md'
          value={content}
          onChange={e => setContent(e.target.value)}
          placeholder={`# ReelName: stoic_discipline\n\n## Hook:\nMost people quit when it gets hard.\n\n## Conflict:\nThey think motivation is the answer.\n\n## Shift:\nDiscipline is a decision.\n\n## Punch:\nThe ones who win aren't more motivated.\nThey're more committed.\n\n## Engage:\nType IRON if this hit.\n\n---\n\n# ReelName: next_reel\n...`}
          style={{
            flex: 1,
            resize: 'none',
            width: '100%',
            padding: '10px 12px',
            lineHeight: 1.7,
            fontSize: 12,
            color: 'var(--text-1)',
            background: 'var(--bg-0)',
            border: '1px solid var(--line-1)',
            borderRadius: 3,
            minHeight: 300,
          }}
        />
      </div>

      {/* Options */}
      <div style={{
        borderTop: '1px solid var(--line-0)',
        padding: '12px 16px',
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
        background: 'var(--bg-1)',
        flexShrink: 0,
      }}>
        {/* Time picker */}
        <div>
          <div style={{ fontSize: 10, color: 'var(--text-2)', letterSpacing: '0.06em', marginBottom: 7 }}>
            UPLOAD TIME (UTC) — applies to all reels
          </div>
          <DateTimePicker value={null} onChange={setPickedTime} />
        </div>

        {/* Privacy */}
        <div>
          <div style={{ fontSize: 10, color: 'var(--text-2)', letterSpacing: '0.06em', marginBottom: 7 }}>
            VISIBILITY
          </div>
          <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
            {PRIVACY_OPTS.map(opt => (
              <button
                key={opt.value}
                type='button'
                onClick={() => setPrivacy(p => p === opt.value ? '' : opt.value)}
                style={{
                  padding: '4px 12px',
                  fontSize: 11,
                  fontFamily: 'var(--font-mono)',
                  background: privacy === opt.value ? 'rgba(0,229,160,0.1)' : 'transparent',
                  border: `1px solid ${privacy === opt.value ? 'var(--accent)' : 'var(--line-1)'}`,
                  color: privacy === opt.value ? 'var(--accent)' : 'var(--text-2)',
                  borderRadius: 2,
                  cursor: 'pointer',
                  transition: 'all 0.1s',
                }}
              >
                {opt.label}
              </button>
            ))}
            {!privacy && (
              <span style={{ fontSize: 10, color: 'var(--text-3)', marginLeft: 6 }}>
                using env default
              </span>
            )}
          </div>
        </div>

        {/* Submit */}
        <Btn
          type='submit'
          variant='primary'
          size='lg'
          disabled={submitting || reelCount === 0}
        >
          {submitting
            ? 'queueing…'
            : reelCount > 0
              ? `queue ${reelCount} reel${reelCount !== 1 ? 's' : ''} →`
              : 'paste a script above'}
        </Btn>
      </div>
    </form>
  )
}
