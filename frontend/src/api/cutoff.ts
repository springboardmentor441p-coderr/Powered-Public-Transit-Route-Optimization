import { createContext, useContext } from 'react'

/** The replay cutoff for every API call made by the screens. Stage 6 (historical analysis) never sets it, so
 *  it is null; Stage 7's replay will wrap the screens in <CutoffContext.Provider value="2026-06-05">, and every
 *  request then carries ?cutoff=..., which the backend enforces in SQL. */
export const CutoffContext = createContext<string | null>(null)
export const useCutoff = () => useContext(CutoffContext)
