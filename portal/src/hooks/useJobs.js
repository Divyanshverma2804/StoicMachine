import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import * as api from '../lib/api'
import toast from 'react-hot-toast'

export const useJobs = () =>
  useQuery({
    queryKey: ['jobs'],
    queryFn: api.fetchJobs,
    refetchInterval: 8000,
    staleTime: 4000,
  })

export const useSubmitBatch = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ contentMd, uploadTime, privacy, voice }) => api.submitBatch(contentMd, uploadTime, privacy, voice),
    onSuccess: (data) => {
      qc.invalidateQueries(['jobs'])
      toast.success(`${data.count || 'reels'} queued for processing`)
    },
    onError: () => toast.error('batch queue failed'),
  })
}

export const useRetryJob = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: api.retryJob,
    onSuccess: () => { qc.invalidateQueries(['jobs']); toast.success('job queued for retry') },
    onError: () => toast.error('retry failed'),
  })
}

export const useDeleteJob = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: api.deleteJob,
    onSuccess: () => { qc.invalidateQueries(['jobs']); toast.success('job deleted') },
    onError: () => toast.error('delete failed'),
  })
}

export const useSetUploadTime = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, datetimeLocal }) => api.setUploadTime(id, datetimeLocal),
    onSuccess: () => { qc.invalidateQueries(['jobs']); toast.success('upload time set') },
    onError: () => toast.error('failed to set time'),
  })
}

export const useSetJobPrivacy = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, privacy }) => api.setJobPrivacy(id, privacy),
    onSuccess: (_, { privacy }) => { qc.invalidateQueries(['jobs']); toast.success(`privacy → ${privacy}`) },
    onError: () => toast.error('failed to set privacy'),
  })
}

export const useUploadNow = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: api.uploadNow,
    onSuccess: () => {
      toast.success('upload started')
      // Poll more aggressively while uploading
      const interval = setInterval(() => qc.invalidateQueries(['jobs']), 3000)
      setTimeout(() => clearInterval(interval), 60000)
    },
    onError: () => toast.error('upload failed to start'),
  })
}

export const useBulkSchedule = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ jobIds, spanHrs, privacy }) => api.bulkSchedule(jobIds, spanHrs, privacy),
    onSuccess: (data) => {
      qc.invalidateQueries(['jobs'])
      toast.success(`${data.count} reels scheduled`)
    },
    onError: () => toast.error('bulk schedule failed'),
  })
}

export const useRefreshStats = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: api.refreshStats,
    onSuccess: () => { qc.invalidateQueries(['jobs']); toast.success('stats refreshed') },
    onError: () => toast.error('stats fetch failed'),
  })
}
