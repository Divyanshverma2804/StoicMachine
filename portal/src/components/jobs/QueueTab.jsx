import React from 'react'
import SubmitForm from '../submit/SubmitForm'
import JobsList from '../jobs/JobsList'

export default function QueueTab() {
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '420px 1fr',
      height: '100%',
      overflow: 'hidden',
    }}>
      {/* Left: Submit */}
      <div style={{
        borderRight: '1px solid var(--line-0)',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}>
        <div style={{
          padding: '10px 16px',
          borderBottom: '1px solid var(--line-0)',
          fontSize: 10,
          color: 'var(--text-2)',
          letterSpacing: '0.1em',
          flexShrink: 0,
        }}>
          NEW BATCH
        </div>
        <div style={{ flex: 1, overflow: 'auto' }}>
          <SubmitForm />
        </div>
      </div>

      {/* Right: Queue */}
      <div style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div style={{
          padding: '10px 20px',
          borderBottom: '1px solid var(--line-0)',
          fontSize: 10,
          color: 'var(--text-2)',
          letterSpacing: '0.1em',
          flexShrink: 0,
        }}>
          JOB QUEUE
        </div>
        <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
          <JobsList />
        </div>
      </div>
    </div>
  )
}
