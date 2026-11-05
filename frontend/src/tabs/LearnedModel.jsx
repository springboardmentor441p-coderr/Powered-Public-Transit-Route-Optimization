import React, { useEffect, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { get, upload } from '../api.js'
import { Async, Card, Chips, DataTable, ErrorBox, Kpi, Note } from '../ui.jsx'
import { fmt, pct } from '../store.jsx'

function useStatic(path, params) {
  const [s, set] = useState({ loading: true, data: null, error: null })
  useEffect(() => { let off = false; set((x) => ({ ...x, loading: true })); get(path, params).then((d) => !off && set({ loading: false, data: d, error: null })).catch((e) => !off && set({ loading: false, data: null, error: e.message })); return () => { off = true } }, [path, JSON.stringify(params)])
  return s
}
function useJob(id) {
  const [j, setJ] = useState(null)
  useEffect(() => {
    if (!id) return undefined
    let stop = false
    const tick = async () => { try { const r = await get(`/model/jobs/${id}`); if (!stop) { setJ(r); if (r.status === 'running') setTimeout(tick, 1500) } } catch (e) { if (!stop) setJ({ status: 'failed', message: e.message }) } }
    tick(); return () => { stop = true }
  }, [id])
  return j
}
const FLAG_COLOR = (f) => (f.includes('under') ? '#4c78a8' : f.includes('over') ? '#e45756' : f.includes('unreliable') ? '#999' : '#54a24b')
const Flag = ({ f }) => <span className="pill" style={{ background: FLAG_COLOR(f) }}>{f}</span>
const GAP_COLS = [{ key: 'route_short_name', label: 'Route' }, { key: 'route_long_name', label: 'Name' }, { key: 'actual_trips', label: 'Actual trips/day', num: true },
  { key: 'expected_trips', label: 'Expected for peers', num: true }, { key: 'ratio', label: 'Ratio', num: true }, { key: 'flag', label: 'Peer comparison', render: (v) => <Flag f={v} /> }]

function JobBox({ job }) {
  if (!job) return null
  if (job.status === 'running') return <div className="loading" role="status"><span className="spin" />{job.message}</div>
  if (job.status === 'failed') return <ErrorBox error={job.message} />
  return null
}

function Analyze() {
  const [city, setCity] = useState('MyCity'); const [busy, setBusy] = useState(false); const [err, setErr] = useState(null); const [id, setId] = useState(null); const job = useJob(id)
  const submit = async (e) => { e.preventDefault(); setBusy(true); setErr(null); setId(null); try { setId((await upload('/model/analyze', new FormData(e.target))).job) } catch (x) { setErr(x.message) } finally { setBusy(false) } }
  const r = job?.status === 'done' ? job.result : null
  return (
    <Card title="Analyse your own bus feed with the model">
      <Note>The model learns from <b>your feed</b> (training on its routes, predicting routes it has not seen) and compares each route with similar ones. Large feeds can take a minute or two.</Note>
      <form onSubmit={submit}>
        <label className="field"><span>City name</span><input type="text" name="city" value={city} onChange={(e) => setCity(e.target.value)} required /></label>
        <label className="field"><span>GTFS feed (.zip)</span><input type="file" name="gtfs" accept=".zip" required /></label>
        <button className="btn" disabled={busy || job?.status === 'running'}>Analyse</button></form>
      {err && <ErrorBox error={err} />}<JobBox job={job} />
      {r && (<>
        <div className="kpis" style={{ marginTop: 12 }}><Kpi label="Routes compared" value={r.n_routes} />
          <Kpi label="Learning skill on held-out routes" value={r.skill == null ? '–' : pct(r.skill, 0)} sub={r.reliable === false ? 'weak: flags unreliable' : r.mode} />
          <Kpi label="Feed validation" value={r.validation.status} sub={`model ${r.model_version}`} /></div>
        <Chips options={Object.keys(r.counts)} value={[]} onChange={() => {}} label={(k) => `${k}: ${r.counts[k]}`} />
        {r.validation.issues.length > 0 && <Note>⚠️ {r.validation.issues.map((i) => i.message).join(' · ')}</Note>}
        <DataTable rows={r.rows} columns={GAP_COLS} /></>)}
    </Card>
  )
}

function Teach({ enabled }) {
  const [name, setName] = useState(''); const [token, setToken] = useState(''); const [err, setErr] = useState(null); const [id, setId] = useState(null); const job = useJob(id)
  const submit = async (e) => { e.preventDefault(); setErr(null); setId(null); try { setId((await upload('/model/learn', new FormData(e.target), { 'X-Admin-Token': token })).job) } catch (x) { setErr(x.message) } }
  return (
    <Card title="Teach the model with a new city (administrator)">
      {!enabled && <Note>Disabled on this server so that visitors cannot change the model. To enable, start the server with the environment variable <code>RR_ADMIN_TOKEN</code>.</Note>}
      <Note>The model retrains on all feeds learned so far plus the new one. A champion/challenger check promotes the new version only if generalisation to previously evaluated cities does not get worse by more than 5%. Takes a few minutes.</Note>
      <form onSubmit={submit}>
        <label className="field"><span>New city name</span><input type="text" name="name" value={name} onChange={(e) => setName(e.target.value)} required /></label>
        <label className="field"><span>GTFS feed (.zip)</span><input type="file" name="gtfs" accept=".zip" required /></label>
        <label className="field"><span>Admin token</span><input type="password" value={token} onChange={(e) => setToken(e.target.value)} required /></label>
        <button className="btn" disabled={!enabled || job?.status === 'running'}>Learn from this feed</button></form>
      {err && <ErrorBox error={err} />}<JobBox job={job} />
      {job?.status === 'done' && <Note>✅ Version <b>{job.result.version}</b> — {job.result.promoted ? 'PROMOTED' : 'rejected (kept the previous model)'}. {job.result.reason}</Note>}
    </Card>
  )
}

function GapExplorer({ cities }) {
  const [city, setCity] = useState(cities[0]); const [flag, setFlag] = useState('under'); const s = useStatic('/model/peer-gap', { city, flag, limit: 300 })
  return (
    <Card title="Which routes differ from their peers?" right={<select value={city} onChange={(e) => setCity(e.target.value)} aria-label="City">{cities.map((c) => <option key={c}>{c}</option>)}</select>}>
      <Note>Each city is learned from its own routes; flagged routes are the extreme ~10% tails. “Under-served vs peers” means <i>fewer trips than similar routes get</i>. Passenger data is needed to tell whether that causes crowding.</Note>
      <Chips options={['under', 'over']} value={flag} onChange={setFlag} label={(f) => (f === 'under' ? 'Relatively under-served' : 'Relatively over-served')} />
      <Async state={s} what="Loading">{(d) => <DataTable rows={d.rows} columns={GAP_COLS} pageSize={10} />}</Async>
    </Card>
  )
}

export default function LearnedModel() {
  const s = useStatic('/model', {})
  return (
    <Async state={s} what="Loading model">{({ card, registry, learning_enabled }) => {
      const wc = Object.entries(card.within_city || {}).map(([c, v]) => ({ city: c, 'Hour-average baseline': v.baseline_hour_mean.mae, 'Learned model': v.gradient_boosting.mae, skill: v.skill }))
      const lc = card.learning_curve.points.map((p) => ({ routes: p.n_routes, 'Learned model': p.mae, 'Baseline': card.learning_curve.baseline_hour_mean_mae }))
      const lo = Object.entries(card.loco.gradient_boosting || {}).map(([c, v]) => ({ city: c, learned: v.mae, baseline: card.loco.baseline_hour_mean[c].mae }))
      const imp = Object.entries(card.permutation_importance).map(([k, v]) => ({ k, v })).slice(0, 10)
      const avgSkill = wc.reduce((a, b) => a + b.skill, 0) / Math.max(wc.length, 1)
      return (<>
        <Card title="What the model learned">
          <Note>It <b>learns from real GTFS feeds</b> how each operator allocates service: how many trips a route gets in each hour given its length, stops, connectivity, location and overlap. It does not see passenger counts, because real feeds have none.
            Routes that get far fewer or more trips than comparable routes are flagged for review.</Note>
          <div className="kpis"><Kpi label="Model version" value={card.version} sub={card.best_model.replace('_', ' ')} /><Kpi label="Real routes learned from" value={fmt(card.n_routes, 0)} sub={card.trained_on.map((t) => t.name).join(' · ')} />
            <Kpi label="Error reduction vs baseline (held-out routes)" value={pct(avgSkill, 0)} sub="average over cities" tone="bal" /><Kpi label="Training rows (route-hours)" value={fmt(card.n_rows, 0)} /></div>
        </Card>
        <div className="grid2">
          <Card title="Learning each city from its own routes (error, lower is better)"><ResponsiveContainer width="100%" height={300}><BarChart data={wc}><CartesianGrid strokeDasharray="3 3" opacity={0.3} /><XAxis dataKey="city" /><YAxis /><Tooltip formatter={(v) => Number(v).toFixed(3)} /><Legend />
            <Bar dataKey="Hour-average baseline" fill="#9aa4b5" /><Bar dataKey="Learned model" fill="#4c78a8" /></BarChart></ResponsiveContainer><Note>Tested on routes never seen in training.</Note></Card>
          <Card title="Does it improve with more data?"><ResponsiveContainer width="100%" height={300}><LineChart data={lc}><CartesianGrid strokeDasharray="3 3" opacity={0.3} /><XAxis dataKey="routes" scale="log" type="number" domain={['auto', 'auto']} /><YAxis domain={['auto', 'auto']} /><Tooltip formatter={(v) => Number(v).toFixed(3)} /><Legend />
            <Line dataKey="Learned model" stroke="#4c78a8" strokeWidth={2.5} /><Line dataKey="Baseline" stroke="#999" strokeDasharray="5 4" dot={false} /></LineChart></ResponsiveContainer><Note>Training routes on the x-axis (log scale): error falls as the model sees more routes.</Note></Card>
        </div>
        <div className="grid2">
          <Card title="Honest limit: a city the model has never seen"><DataTable search={false} rows={lo} columns={[{ key: 'city', label: 'Unseen city' }, { key: 'learned', label: 'Pooled model error', num: true, render: (v) => v.toFixed(3) }, { key: 'baseline', label: 'Baseline error', num: true, render: (v) => v.toFixed(3) }]} />
            <Note>With only three operators, knowledge transfers weakly between cities, so the model is trained on each feed it analyses. More cities in the corpus will help.</Note></Card>
          <Card title="What drives the prediction"><ResponsiveContainer width="100%" height={260}><BarChart data={imp} layout="vertical" margin={{ left: 30 }}><CartesianGrid strokeDasharray="3 3" opacity={0.3} /><XAxis type="number" /><YAxis type="category" dataKey="k" width={130} tick={{ fontSize: 11 }} /><Tooltip /><ReferenceLine x={0} /><Bar dataKey="v" fill="#54a24b" /></BarChart></ResponsiveContainer><Note>Permutation importance: how much the error rises when a feature is shuffled.</Note></Card>
        </div>
        <GapExplorer cities={Object.keys(card.within_city)} />
        <Analyze />
        <Teach enabled={learning_enabled} />
        <Card title="Model versions (learning history)"><DataTable search={false} rows={[...registry].reverse()} columns={[{ key: 'version', label: 'Version' }, { key: 'trained_at', label: 'Trained' }, { key: 'cities', label: 'Cities', render: (v) => v.join(', ') },
          { key: 'n_routes', label: 'Routes', num: true }, { key: 'promoted', label: 'Promoted', render: (v) => (v ? 'yes' : 'no') }, { key: 'reason', label: 'Decision' }]} /></Card>
      </>)
    }}</Async>
  )
}
