import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import * as api from '../lib/api'

export const useAnalytics = () =>
  useQuery({ queryKey: ['analytics'], queryFn: api.fetchAnalytics })

export const useRefreshAnalytics = () => {
  const qc = useQueryClient()
  return () => qc.invalidateQueries(['analytics'])
}
