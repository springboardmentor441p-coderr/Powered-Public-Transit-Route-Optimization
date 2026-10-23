import React, { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { get } from './api.js'

const Ctx = createContext(null)
export const useApp = () => useContext(Ctx)

export const COLORS = { underutilized: '#4c78a8', balanced: '#54a24b', overcrowded: '#e45756' }
export const CLASS_LABEL = { underutilized: 'Under-used', balanced: 'Balanced', overcrowded: 'Overcrowded' }
export const fmt = (v, d = 1) => (v === null || v === undefined || Number.isNaN(v) ? '–' : Number(v).toLocaleString('en-IN', { maximumFractionDigits: d }))
export const pct = (v, d = 1) => (v === null || v === undefined ? '–' : `${(v * 100).toFixed(d)}%`)

export function AppProvider({ children }) {
  const [dataset, setDataset] = useState('demo')
  const [scenario, setScenario] = useState('today')
  const [params, setParams] = useState(null)         // committed optimisation settings (null = server defaults)
  const [cities, setCities] = useState([])           // [] = all
  const [meta, setMeta] = useState(null)
  const [error, setError] = useState(null)
  const [tick, setTick] = useState(0)

  const query = useMemo(() => ({ dataset, scenario, ...(params || {}), cities: cities.join(',') }), [dataset, scenario, params, cities])
  useEffect(() => {
    const ac = new AbortController()
    get('/meta', query, ac.signal).then((m) => { setMeta(m); setError(null) }).catch((e) => { if (e.name !== 'AbortError') setError(e.message) })
    return () => ac.abort()
  }, [JSON.stringify(query), tick])                  // eslint-disable-line react-hooks/exhaustive-deps

  const value = { dataset, setDataset, scenario, setScenario, params, setParams, cities, setCities, meta, error, query,
    refreshMeta: () => setTick((t) => t + 1), usedParams: params || meta?.defaults }
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

/** Fetch an endpoint with the global query (dataset, scenario, settings, city filter) plus extra params. */
export function useApi(path, extra = {}) {
  const { query } = useApp()
  const [state, setState] = useState({ loading: true, data: null, error: null })
  const key = JSON.stringify([path, query, extra])
  useEffect(() => {
    const ac = new AbortController()
    setState((s) => ({ ...s, loading: true, error: null }))
    get(path, { ...query, ...extra }, ac.signal)
      .then((data) => setState({ loading: false, data, error: null }))
      .catch((e) => { if (e.name !== 'AbortError') setState({ loading: false, data: null, error: e.message }) })
    return () => ac.abort()
  }, [key])                                          // eslint-disable-line react-hooks/exhaustive-deps
  return state
}
