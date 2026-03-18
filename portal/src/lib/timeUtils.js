// IST = UTC + 5h 30m
export const utcToIST = (date) =>
  new Date(date.getTime() + (5 * 60 + 30) * 60000)

export const fmtDatetime = (d) => {
  const days = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat']
  const mons = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
  return `${days[d.getUTCDay()]} ${String(d.getUTCDate()).padStart(2,'0')} ${mons[d.getUTCMonth()]} ${String(d.getUTCHours()).padStart(2,'0')}:${String(d.getUTCMinutes()).padStart(2,'0')}`
}

export const fmtTime = (d) =>
  `${String(d.getUTCHours()).padStart(2,'0')}:${String(d.getUTCMinutes()).padStart(2,'0')}:${String(d.getUTCSeconds()).padStart(2,'0')}`

export const buildUTCDate = (dateStr, hour, min) =>
  new Date(`${dateStr}T${String(hour).padStart(2,'0')}:${String(min).padStart(2,'0')}:00Z`)

export const buildDatetimeLocal = (dateStr, hour, min) =>
  `${dateStr}T${String(hour).padStart(2,'0')}:${String(min).padStart(2,'0')}`

export const getNextDays = (n = 14) => {
  const days = []
  const now = new Date()
  const today = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()))
  const dayNames = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat']
  const monNames = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
  for (let i = 0; i < n; i++) {
    const d = new Date(today.getTime() + i * 86400000)
    const y = d.getUTCFullYear()
    const m = String(d.getUTCMonth() + 1).padStart(2,'0')
    const day = String(d.getUTCDate()).padStart(2,'0')
    const val = `${y}-${m}-${day}`
    const label = i === 0 ? `today  — ${day} ${monNames[d.getUTCMonth()]}` :
                  i === 1 ? `tomorrow — ${day} ${monNames[d.getUTCMonth()]}` :
                  `${dayNames[d.getUTCDay()].toLowerCase()} ${day} ${monNames[d.getUTCMonth()].toLowerCase()}`
    days.push({ label, val })
  }
  return days
}
