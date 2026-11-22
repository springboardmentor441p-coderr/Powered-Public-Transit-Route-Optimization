import { createContext, useContext } from 'react'
import type { ReplayAction } from './client'
import type { ReplayState } from './types'

/** The replay mode for the whole app (provided by ReplayProvider in replay.tsx). */
export type Mode = 'historical' | 'replay'
export type ReplayApi = {
  mode: Mode
  state: ReplayState | null
  error: string | null
  busy: boolean
  enter: (start?: string) => Promise<void>
  resume: () => void
  leave: () => void
  act: (action: ReplayAction, extra?: { days?: number; to?: string; speed_seconds?: number; start_date?: string }) => Promise<void>
}

export const ReplayContext = createContext<ReplayApi | null>(null)

export function useReplay(): ReplayApi {
  const v = useContext(ReplayContext)
  if (!v) throw new Error('useReplay must be used inside ReplayProvider')
  return v
}
