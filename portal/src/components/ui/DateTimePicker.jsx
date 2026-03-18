import React, { useState, useEffect } from 'react'
import { getNextDays, buildUTCDate, buildDatetimeLocal, utcToIST, fmtDatetime } from '../../lib/timeUtils'
import Btn from './Btn'

export default function DateTimePicker({ value, onChange, compact = false }) {
  const days = getNextDays(14)
  const [date, setDate] = useState(value?.date || '')
  const [hour, setHour] = useState(value?.hour ?? 12)
  const [min, setMin] = useState(value?.min ?? 0)

  useEffect(() => {
    if (!date) { onChange(null); return }
    const h = Math.max(0, Math.min(23, parseInt(hour) || 0))
    const m = Math.max(0, Math.min(59, parseInt(min) || 0))
    const utc = buildUTCDate(date, h, m)
    const ist = utcToIST(utc)
    onChange({ date, hour: h, min: m, datetimeLocal: buildDatetimeLocal(date, h, m), utc, ist })
  }, [date, hour, min])

  const setNow = () => {
    const n = new Date(Date.now() + 3600000)
    const d = `${n.getUTCFullYear()}-${String(n.getUTCMonth()+1).padStart(2,'0')}-${String(n.getUTCDate()).padStart(2,'0')}`
    setDate(d); setHour(n.getUTCHours()); setMin(n.getUTCMinutes())
  }

  const setTomorrow9 = () => {
    const n = new Date(Date.now() + 86400000)
    const d = `${n.getUTCFullYear()}-${String(n.getUTCMonth()+1).padStart(2,'0')}-${String(n.getUTCDate()).padStart(2,'0')}`
    setDate(d); setHour(9); setMin(0)
  }

  const inputSty = {
    padding: compact ? '4px 8px' : '5px 10px',
    borderRadius: 3,
    fontSize: 12,
  }

  const istPreview = date
    ? (() => {
        const h = Math.max(0, Math.min(23, parseInt(hour) || 0))
        const m = Math.max(0, Math.min(59, parseInt(min) || 0))
        return fmtDatetime(utcToIST(buildUTCDate(date, h, m)))
      })()
    : null

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
        <select value={date} onChange={e => setDate(e.target.value)} style={{ ...inputSty, minWidth: 160 }}>
          <option value=''>-- no date --</option>
          {days.map(d => <option key={d.val} value={d.val}>{d.label}</option>)}
        </select>
        <input
          type='number' value={hour} min={0} max={23}
          onChange={e => setHour(e.target.value)}
          placeholder='HH' style={{ ...inputSty, width: 52 }}
        />
        <span style={{ color: 'var(--text-2)', fontSize: 12 }}>:</span>
        <input
          type='number' value={min} min={0} max={59}
          onChange={e => setMin(e.target.value)}
          placeholder='MM' style={{ ...inputSty, width: 52 }}
        />
        <Btn size='sm' onClick={setNow}>+1h</Btn>
        {!compact && <Btn size='sm' onClick={setTomorrow9}>tmrw 09:00</Btn>}
        {!compact && date && (
          <Btn size='sm' variant='danger' onClick={() => { setDate(''); onChange(null) }}>clear</Btn>
        )}
      </div>
      {istPreview && (
        <div style={{ fontSize: 11, color: '#f5a623', fontFamily: 'var(--font-mono)' }}>
          → IST {istPreview}
        </div>
      )}
    </div>
  )
}
