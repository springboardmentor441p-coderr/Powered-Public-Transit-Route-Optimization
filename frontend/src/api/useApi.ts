import { useCallback, useEffect, useState } from 'react'
import type { ApiOptions } from './client'
import { useCutoff } from './cutoff'

export type ApiState<T> =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ok'; data: T }

/** Run an API call for a component: loading -> ok | error, with retry. The cutoff from CutoffContext is passed
 *  to every call, and an older request is aborted when the inputs change (so a slow answer can never
 *  overwrite a newer one). `key` must change whenever the request changes. */
export function useApi<T>(call: (o: ApiOptions) => Promise<T>, key: string): ApiState<T> & { retry: () => void } {
  const cutoff = useCutoff()
  const [state, setState] = useState<ApiState<T>>({ status: 'loading' })
  const [attempt, setAttempt] = useState(0)
  const retry = useCallback(() => setAttempt(a => a + 1), [])

  useEffect(() => {
    const ctrl = new AbortController()
    setState({ status: 'loading' })
    call({ cutoff, signal: ctrl.signal })
      .then(data => setState({ status: 'ok', data }))
      .catch((e: Error) => { if (e.name !== 'AbortError') setState({ status: 'error', message: e.message }) })
    return () => ctrl.abort()
    // `call` is a new function each render; `key` (plus cutoff and attempt) says when the request really changed
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, cutoff, attempt])

  return { ...state, retry }
}
