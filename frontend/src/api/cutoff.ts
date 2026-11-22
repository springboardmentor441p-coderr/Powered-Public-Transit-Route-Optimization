import { createContext, useContext } from 'react'

/** What every API call made by the screens is scoped to.
 *  - Historical analysis: no cutoff and no session (the whole period, Stage 6).
 *  - Replay: the session id only. The backend takes the cutoff from the stored session and hides every later date
 *    in SQL; the frontend never sends a replay date.
 *  `tick` changes whenever the replay reveals a day (or completes), so every screen refetches. */
export type RequestScope = { cutoff: string | null; session: string | null; tick: string }

export const HISTORICAL: RequestScope = { cutoff: null, session: null, tick: 'historical' }
export const ScopeContext = createContext<RequestScope>(HISTORICAL)
export const useRequestScope = () => useContext(ScopeContext)
