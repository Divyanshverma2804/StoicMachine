import axios from 'axios'

const api = axios.create({ baseURL: '' })

// ── Jobs ──────────────────────────────────────────────────
export const fetchJobs = () =>
  api.get('/jobs').then(r => r.data)

export const retryJob = (id) =>
  api.post(`/jobs/${id}/retry`)

export const deleteJob = (id) =>
  api.delete(`/jobs/${id}`)

export const setUploadTime = (id, datetimeLocal) => {
  const fd = new FormData()
  fd.append('upload_time', datetimeLocal)
  return api.post(`/jobs/${id}/set_upload_time`, fd)
}

export const setJobPrivacy = (id, privacy) => {
  const fd = new FormData()
  fd.append('privacy', privacy)
  return api.post(`/jobs/${id}/set_privacy`, fd)
}

export const uploadNow = (id) =>
  api.post(`/jobs/${id}/upload_now`)

export const refreshStats = (id) =>
  api.post(`/jobs/${id}/refresh_stats`).then(r => r.data)

export const bulkSchedule = (jobIds, spanHrs, privacy) => {
  const fd = new FormData()
  fd.append('job_ids', jobIds.join(','))
  fd.append('span_hrs', String(spanHrs))
  fd.append('privacy', privacy)
  return api.post('/jobs/bulk_schedule', fd).then(r => r.data)
}

export const rescheduleJob = (id, newTime) => {
  const fd = new FormData()
  fd.append('new_time', newTime)
  return api.post(`/jobs/${id}/reschedule`, fd)
}

// ── Calendar ──────────────────────────────────────────────
export const fetchCalendarEvents = () =>
  api.get('/calendar/events').then(r => r.data)

// ── Diary ─────────────────────────────────────────────────
export const fetchDiary = () =>
  api.get('/diary').then(r => r.data)

export const createDiaryEntry = (title, content, tag = '') => {
  const fd = new FormData()
  fd.append('title', title)
  fd.append('content', content)
  fd.append('tag', tag)
  return api.post('/diary', fd).then(r => r.data)
}

export const updateDiaryEntry = (id, fields) => {
  const fd = new FormData()
  Object.entries(fields).forEach(([k, v]) => fd.append(k, v))
  return api.patch(`/diary/${id}`, fd).then(r => r.data)
}

export const deleteDiaryEntry = (id) =>
  api.delete(`/diary/${id}`)

// ── Analytics ─────────────────────────────────────────────
export const fetchAnalytics = () =>
  api.get('/analytics/categories').then(r => r.data)
