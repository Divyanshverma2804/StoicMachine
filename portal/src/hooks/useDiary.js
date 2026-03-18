import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import * as api from '../lib/api'
import toast from 'react-hot-toast'

export const useDiary = () =>
  useQuery({ queryKey: ['diary'], queryFn: api.fetchDiary })

export const useCreateDiary = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ title, content, tag }) => api.createDiaryEntry(title, content, tag),
    onSuccess: () => { qc.invalidateQueries(['diary']); toast.success('draft saved') },
    onError: () => toast.error('save failed'),
  })
}

export const useUpdateDiary = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, fields }) => api.updateDiaryEntry(id, fields),
    onSuccess: () => { qc.invalidateQueries(['diary']); toast.success('saved') },
    onError: () => toast.error('save failed'),
  })
}

export const useDeleteDiary = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: api.deleteDiaryEntry,
    onSuccess: () => { qc.invalidateQueries(['diary']); toast.success('entry deleted') },
    onError: () => toast.error('delete failed'),
  })
}
