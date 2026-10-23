import React, { useState } from 'react'
import { AppProvider, useApp } from './store.jsx'
import { Card, ErrorBox, Loading, Slider } from './ui.jsx'
import Overview from './tabs/Overview.jsx'
import Explore from './tabs/Explore.jsx'
import Clusters from './tabs/Clusters.jsx'
import Predictions from './tabs/Predictions.jsx'
import Forecast from './tabs/Forecast.jsx'
import Recommendations from './tabs/Recommendations.jsx'
import Impact from './tabs/Impact.jsx'
import YourData from './tabs/YourData.jsx'

const TABS = [['Overview', Overview], ['Explore', Explore], ['Clusters', Clusters], ['Predictions', Predictions], ['Forecast', Forecast],
  ['Recommendations', Recommendations], ['Impact', Impact], ['Your data', YourData]]
const SCEN = [['today', 'Today'], ['avg', 'Next 12 months'], ['peak', 'Busiest month']]

class Boundary extends React.Component {
  state = { e: null }
  static getDerivedStateFromError(e) { return { e } }
  componentDidUpdate(p) { if (p.k !== this.props.k && this.state.e) this.setState({ e: null }) }
  render() { return this.state.e ? <ErrorBox error={`Something went wrong: ${this.state.e.message}`} /> : this.props.children }
}

function Sidebar({ open }) {
  const { meta, cities, setCities, usedParams, setParams } = useApp(); const [q, setQ] = useState('')
  const sel = cities.length ? cities : meta.cities; const set = (k) => (v) => setParams({ ...usedParams, [k]: v })
  const toggle = (c) => { const n = sel.includes(c) ? sel.filter((x) => x !== c) : [...sel, c]; setCities(n.length === meta.cities.length || n.length === 0 ? [] : n) }
  return (
    <aside className={`side ${open ? 'open' : ''}`}>
      <h4>Cities ({sel.length})</h4>
      <input className="search" placeholder="Find city…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Find city" />
      <div className="chips" style={{ marginBottom: 6 }}><button className="chip" onClick={() => setCities([])}>All</button>
        <button className="chip" onClick={() => setCities([meta.cities[0]])}>One</button></div>
      <div className="citylist">{meta.cities.filter((c) => c.toLowerCase().includes(q.toLowerCase())).map((c) => (
        <label key={c}><input type="checkbox" checked={sel.includes(c)} onChange={() => toggle(c)} />{c}</label>))}</div>
      <h4>Service settings</h4>
      <Slider label="Bus capacity" value={usedParams.capacity} min={30} max={120} step={5} onCommit={set('capacity')} />
      <Slider label="Target crowding" value={usedParams.target_lf} min={0.4} max={1} step={0.05} onCommit={set('target_lf')} format={(v) => `${Math.round(v * 100)}% full`} />
      <Slider label="Min buses / hour" value={usedParams.min_tph} min={1} max={6} onCommit={set('min_tph')} />
      <Slider label="Max buses / hour" value={usedParams.max_tph} min={8} max={40} onCommit={set('max_tph')} />
      <Slider label="Merge if stops overlap ≥" value={usedParams.merge_overlap} min={0.3} max={0.9} step={0.05} onCommit={set('merge_overlap')} format={(v) => `${Math.round(v * 100)}%`} />
      <Slider label="Suggest splitting routes ≥ (km)" value={usedParams.split_km} min={10} max={40} onCommit={set('split_km')} />
      <button className="btn ghost" style={{ width: '100%', marginTop: 8 }} onClick={() => setParams(null)}>Reset settings</button>
    </aside>
  )
}

function Shell() {
  const { meta, error, dataset, setDataset, setCities, scenario, setScenario } = useApp()
  const [tab, setTab] = useState(0); const [open, setOpen] = useState(false)
  if (error && !meta) return <div style={{ padding: 24 }}><ErrorBox error={`Cannot reach the RouteRanker server: ${error}. Start it with: uvicorn server.main:app --port 8000`} /></div>
  if (!meta) return <Loading what="Starting RouteRanker (the first start trains the models and can take a minute)" />
  const T = TABS[tab][1]
  return (
    <div className="shell">
      <header className="top">
        <button className="btn ghost menu-btn" onClick={() => setOpen(!open)} aria-label="Toggle menu">☰</button>
        <div className="brand">🚌 RouteRanker<small>AI-powered bus route optimisation</small></div><div className="sp" />
        <label className="muted">Data <select value={dataset} onChange={(e) => { setDataset(e.target.value); setCities([]) }} aria-label="Dataset">{meta.datasets.map((d) => <option key={d.id} value={d.id}>{d.label}</option>)}</select></label>
        <div className="seg" role="group" aria-label="Planning horizon">{SCEN.map(([k, l]) => (
          <button key={k} className={(meta.scenario) === k ? 'on' : ''} disabled={k !== 'today' && !meta.has_forecast} title={k !== 'today' && !meta.has_forecast ? 'Needs past ridership data' : ''} onClick={() => setScenario(k)}>{l}</button>))}</div>
      </header>
      <Sidebar open={open} />
      <main onClick={() => open && setOpen(false)}>
        {error && <ErrorBox error={error} />}
        <nav className="tabs" role="tablist">{TABS.map(([n], i) => <button key={n} role="tab" aria-selected={i === tab} className={`tab ${i === tab ? 'on' : ''}`} onClick={() => setTab(i)}>{n}</button>)}</nav>
        <Boundary k={tab}><T /></Boundary>
      </main>
    </div>
  )
}
export default function App() { return <AppProvider><Shell /></AppProvider> }
