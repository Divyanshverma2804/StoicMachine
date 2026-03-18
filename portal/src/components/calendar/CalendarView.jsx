import React, { useRef, useEffect, useState } from 'react'
import FullCalendar from '@fullcalendar/react'
import dayGridPlugin from '@fullcalendar/daygrid'
import timeGridPlugin from '@fullcalendar/timegrid'
import interactionPlugin from '@fullcalendar/interaction'
import { fetchCalendarEvents, rescheduleJob } from '../../lib/api'
import { useJobs } from '../../hooks/useJobs'
import { useDeleteJob, useRetryJob } from '../../hooks/useJobs'
import { utcToIST, fmtDatetime } from '../../lib/timeUtils'
import StatusBadge from '../ui/StatusBadge'
import Btn from '../ui/Btn'
import toast from 'react-hot-toast'

const STATUS_COLORS = {
  pending:   '#f5a623',
  rendering: '#7b68ee',
  rendered:  '#50e3c2',
  uploading: '#4a9eff',
  done:      '#00e5a0',
  failed:    '#ff4444',
}

export default function CalendarTab() {
  const calRef = useRef(null)
  const { data: jobs = [] } = useJobs()
  const deleteJob = useDeleteJob()
  const retryJob  = useRetryJob()
  const [popup, setPopup] = useState(null)

  const unscheduled = jobs.filter(j => !j.upload_time && j.status !== 'done')

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '220px 1fr',
      height: '100%',
      overflow: 'hidden',
    }}>
      {/* Sidebar */}
      <div style={{
        borderRight: '1px solid var(--line-0)',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}>
        {/* Legend */}
        <div style={{
          padding: '10px 14px',
          borderBottom: '1px solid var(--line-0)',
          fontSize: 10,
          color: 'var(--text-2)',
          letterSpacing: '0.1em',
          flexShrink: 0,
        }}>
          STATUS LEGEND
        </div>
        <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--line-0)', flexShrink: 0 }}>
          {Object.entries(STATUS_COLORS).map(([s, c]) => (
            <div key={s} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 7, fontSize: 11 }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: c, flexShrink: 0 }} />
              <span style={{ color: 'var(--text-2)' }}>{s}</span>
            </div>
          ))}
        </div>

        {/* Unscheduled */}
        <div style={{
          padding: '10px 14px',
          borderBottom: '1px solid var(--line-0)',
          fontSize: 10,
          color: 'var(--text-2)',
          letterSpacing: '0.1em',
          flexShrink: 0,
        }}>
          UNSCHEDULED ({unscheduled.length})
        </div>
        <div style={{ flex: 1, overflowY: 'auto', padding: '8px 10px' }}>
          {unscheduled.length === 0 ? (
            <div style={{ fontSize: 11, color: 'var(--text-3)', padding: '12px 4px' }}>
              all jobs scheduled ✓
            </div>
          ) : unscheduled.map(j => (
            <div key={j.id} style={{
              padding: '7px 10px',
              marginBottom: 4,
              background: 'var(--bg-2)',
              border: '1px solid var(--line-0)',
              borderRadius: 3,
              fontSize: 11,
            }}>
              <div style={{ color: 'var(--text-1)', marginBottom: 3, fontWeight: 600 }}>
                {j.reel_name}
              </div>
              <StatusBadge status={j.status} />
            </div>
          ))}
        </div>
      </div>

      {/* Calendar */}
      <div style={{ overflow: 'auto', padding: 16, position: 'relative' }}>
        <style>{`
          .fc { font-family: var(--font-mono) !important; }
          .fc .fc-toolbar-title { font-size: 14px !important; font-weight: 700 !important; color: var(--text-0) !important; letter-spacing: 0.06em; }
          .fc .fc-button {
            background: transparent !important; border: 1px solid var(--line-2) !important;
            color: var(--text-1) !important; font-family: var(--font-mono) !important;
            font-size: 11px !important; border-radius: 3px !important; box-shadow: none !important;
            padding: 4px 10px !important; font-weight: 500 !important;
          }
          .fc .fc-button:hover { background: var(--bg-3) !important; color: var(--text-0) !important; }
          .fc .fc-button-primary:not(:disabled).fc-button-active {
            background: var(--accent-dim) !important; border-color: var(--accent) !important; color: var(--accent) !important;
          }
          .fc .fc-col-header-cell-cushion {
            color: var(--text-2) !important; font-size: 10px !important; font-weight: 600 !important;
            text-transform: uppercase; letter-spacing: 0.08em; text-decoration: none !important;
          }
          .fc .fc-daygrid-day-number { color: var(--text-2) !important; font-size: 11px !important; text-decoration: none !important; }
          .fc .fc-daygrid-day.fc-day-today { background: rgba(0,229,160,0.04) !important; }
          .fc .fc-daygrid-day.fc-day-today .fc-daygrid-day-number { color: var(--accent) !important; }
          .fc .fc-event { border-radius: 2px !important; font-size: 10px !important; font-weight: 600 !important; border: none !important; padding: 1px 4px !important; cursor: pointer; }
          .fc th, .fc td { border-color: var(--line-0) !important; }
          .fc table { border-color: var(--line-0) !important; }
          .fc .fc-scrollgrid { border-color: var(--line-0) !important; }
          .fc .fc-day-other .fc-daygrid-day-number { opacity: 0.3; }
          .fc .fc-toolbar { margin-bottom: 12px !important; }
        `}</style>

        <FullCalendar
          ref={calRef}
          plugins={[dayGridPlugin, timeGridPlugin, interactionPlugin]}
          initialView='dayGridMonth'
          headerToolbar={{
            left:   'prev,next today',
            center: 'title',
            right:  'dayGridMonth,timeGridWeek,listWeek',
          }}
          height='auto'
          editable={true}
          eventStartEditable={true}
          eventDurationEditable={false}
          events={async (info, success, failure) => {
            try {
              const events = await fetchCalendarEvents()
              success(events.map(e => ({
                ...e,
                backgroundColor: STATUS_COLORS[e.extendedProps?.status] || '#606060',
              })))
            } catch(err) { failure(err) }
          }}
          eventDrop={async (info) => {
            try {
              await rescheduleJob(info.event.extendedProps.job_id, info.event.start.toISOString())
              toast.success('rescheduled')
            } catch {
              info.revert()
              toast.error('reschedule failed')
            }
          }}
          eventClick={(info) => {
            const p  = info.event.extendedProps
            const dt = info.event.start
            setPopup({ id: p.job_id, name: info.event.title, status: p.status, dt, p })
          }}
        />
      </div>

      {/* Popup */}
      {popup && (
        <div
          style={{
            position: 'fixed', inset: 0,
            background: 'rgba(0,0,0,0.7)',
            zIndex: 200,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            backdropFilter: 'blur(2px)',
            animation: 'fadeIn 0.1s ease',
          }}
          onClick={e => { if (e.target === e.currentTarget) setPopup(null) }}
        >
          <div style={{
            background: 'var(--bg-1)',
            border: '1px solid var(--line-2)',
            borderRadius: 4,
            padding: 24,
            minWidth: 300,
            maxWidth: 400,
            width: '90vw',
          }}>
            <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 14, color: 'var(--text-0)' }}>
              {popup.name}
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 16, fontSize: 12 }}>
              <Row label='job id'   value={`#${popup.id}`} />
              <Row label='status'   value={<StatusBadge status={popup.status} />} />
              <Row label='utc'      value={fmtDatetime(popup.dt)} />
              <Row label='ist'      value={<span style={{ color: '#f5a623' }}>{fmtDatetime(utcToIST(popup.dt))}</span>} />
              {popup.p.yt_video_id && (
                <Row label='youtube' value={
                  <a href={`https://youtu.be/${popup.p.yt_video_id}`} target='_blank' rel='noreferrer'>
                    youtu.be/{popup.p.yt_video_id}
                  </a>
                } />
              )}
            </div>
            <div style={{ display: 'flex', gap: 6 }}>
              {popup.status === 'failed' && (
                <Btn size='sm' variant='warn' onClick={() => {
                  retryJob.mutate(popup.id); setPopup(null)
                }}>
                  retry
                </Btn>
              )}
              <Btn size='sm' variant='danger' onClick={() => {
                if (confirm('delete job?')) { deleteJob.mutate(popup.id); setPopup(null) }
              }}>
                delete
              </Btn>
              <Btn size='sm' onClick={() => setPopup(null)}>close</Btn>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function Row({ label, value }) {
  return (
    <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
      <span style={{ color: 'var(--text-2)', minWidth: 64, fontSize: 11 }}>{label}</span>
      <span style={{ color: 'var(--text-1)', fontSize: 11 }}>{value}</span>
    </div>
  )
}
