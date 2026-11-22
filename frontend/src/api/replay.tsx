import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { replay } from './client'
import { HISTORICAL, ScopeContext, type RequestScope } from './cutoff'
import { ReplayContext as Ctx, type Mode, type ReplayApi } from './replayContext'
import type { ReplayState } from './types'

/** The replay mode for the whole app. The SERVER owns the clock: this only keeps the session id (so a browser refresh
 *  returns to the same session), asks the server for its state, sends controls, and polls while playing. Every screen
 *  gets its request scope from here: historical (nothing) or the session id (the backend derives the cutoff). */
const STORE = 'routeranker.replay'
const POLL_MS = 1000

function readStore(): { mode: Mode; session: string | null } {
  try {
    const v = JSON.parse(localStorage.getItem(STORE) ?? 'null') as { mode?: Mode; session?: string } | null
    return { mode: v?.mode === 'replay' ? 'replay' : 'historical', session: v?.session ?? null }
  } catch { return { mode: 'historical', session: null } }
}
function writeStore(mode: Mode, session: string | null) {
  try { localStorage.setItem(STORE, JSON.stringify({ mode, session })) } catch { /* private window: per-tab only */ }
}



export function ReplayProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<Mode>(() => readStore().mode)
  const [session, setSession] = useState<string | null>(() => readStore().session)
  const [state, setState] = useState<ReplayState | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => { writeStore(mode, session) }, [mode, session])

  // restore after a refresh, and poll while playing (the server advances the clock; we only read it)
  useEffect(() => {
    if (mode !== 'replay' || !session) return
    const ctrl = new AbortController()
    const load = () => replay.get(session, ctrl.signal).then(s => { setState(s); setError(null) }, (e: Error & { status?: number }) => {
      if (e.name === 'AbortError') return
      if (e.status === 404) { setSession(null); setState(null); setMode('historical') }
      setError(e.message)
    })
    void load()
    const playing = state?.status === 'playing'
    const id = playing ? window.setInterval(load, POLL_MS) : undefined
    return () => { ctrl.abort(); if (id) window.clearInterval(id) }
  }, [mode, session, state?.status])

  const enter = useCallback(async (start?: string) => {
    setBusy(true)
    try {
      const s = await replay.create(start ? { start_date: start } : {})
      setSession(s.session_id); setState(s); setMode('replay'); setError(null)
    } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }, [])

  const leave = useCallback(() => { setMode('historical') }, [])
  // back to replay: the stored session if there is one (the server still has its day), else a new session
  const resume = useCallback(() => { if (session) setMode('replay'); else void enter() }, [session, enter])

  const act = useCallback<ReplayApi['act']>(async (action, extra = {}) => {
    if (!session) return
    setBusy(true)
    try {
      const s = await replay.control(session, action, extra)
      setState(s); setSession(s.session_id); setError(null)          // reset returns a NEW session
    } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }, [session])

  const scope = useMemo<RequestScope>(() => mode === 'replay' && state
    ? { cutoff: null, session: state.session_id, tick: `${state.revealed_through}|${state.complete}` }
    : HISTORICAL, [mode, state])

  const api = useMemo<ReplayApi>(() => ({ mode, state: mode === 'replay' ? state : null, error, busy, enter, resume, leave, act }),
                                 [mode, state, error, busy, enter, resume, leave, act])
  // while a stored replay is being restored, screens wait instead of briefly loading the whole historical period
  const restoring = mode === 'replay' && session != null && state == null && error == null
  return (
    <Ctx.Provider value={api}>
      <ScopeContext.Provider value={scope}>{restoring ? null : children}</ScopeContext.Provider>
    </Ctx.Provider>
  )
}
