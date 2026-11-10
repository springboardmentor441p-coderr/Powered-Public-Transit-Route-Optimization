import { useCallback, useEffect, useState } from 'react'
import { explainApiError } from '../services/api'

export interface ResourceState<T> {
  data: T | null
  loading: boolean
  error: string | null
  reload: () => void
}

export function useResource<T>(loader: () => Promise<T>, dependencies: readonly unknown[] = []): ResourceState<T> {
  const stableLoader = useCallback(loader, dependencies)
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [revision, setRevision] = useState(0)

  useEffect(() => {
    let active = true
    setLoading(true)
    setError(null)
    stableLoader()
      .then((result) => { if (active) setData(result) })
      .catch((reason: unknown) => { if (active) { setData(null); setError(explainApiError(reason)) } })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [stableLoader, revision])

  const reload = useCallback(() => setRevision((current) => current + 1), [])
  return { data, loading, error, reload }
}
