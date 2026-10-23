import React, { useState } from 'react'
import { post, upload } from '../api.js'
import { useApp } from '../store.jsx'
import { Card, ErrorBox, Note } from '../ui.jsx'

export default function YourData() {
  const { meta, setDataset, setCities, refreshMeta, dataset } = useApp()
  const [busy, setBusy] = useState(false); const [msg, setMsg] = useState(null); const [err, setErr] = useState(null)
  const [city, setCity] = useState('MyCity'); const [gen, setGen] = useState('Pune'); const [seed, setSeed] = useState(123)
  const done = (r) => { setMsg(`Loaded “${r.label}”: ${r.routes} routes${r.has_forecast ? ', with forecast' : ''}.`); setDataset(r.dataset); setCities([]); refreshMeta() }
  const run = async (fn) => { setBusy(true); setErr(null); setMsg(null); try { done(await fn()) } catch (e) { setErr(e.message) } finally { setBusy(false) } }
  const onUpload = (e) => { e.preventDefault(); const f = new FormData(e.target); f.set('city', city); run(() => upload('/upload', f)) }
  return (
    <>
      {msg && <Card><b>✅ {msg}</b> Explore the other tabs to see the results.</Card>}{err && <ErrorBox error={err} />}
      <div className="grid2">
        <Card title="Analyse your own bus feed">
          <Note>Upload a GTFS <code>.zip</code> (routes, trips, stop_times, stops, calendar). Optionally add passenger counts and past monthly ridership for a forecast.</Note>
          <form onSubmit={onUpload}>
            <label className="field"><span>City name</span><input type="text" value={city} onChange={(e) => setCity(e.target.value)} required /></label>
            <label className="field"><span>GTFS feed (.zip) *</span><input type="file" name="gtfs" accept=".zip" required /></label>
            <label className="field"><span>Passenger counts (optional CSV: route_id, day_type, hour, boardings)</span><input type="file" name="ridership" accept=".csv" /></label>
            <label className="field"><span>Past monthly ridership (optional CSV: route_id, month, boardings) – enables forecasting</span><input type="file" name="history" accept=".csv" /></label>
            <button className="btn" disabled={busy}>{busy ? 'Analysing…' : 'Analyse my feed'}</button></form>
          <Note>No files handy? Download samples: <a href="/api/sample/Pune_gtfs.zip">Pune GTFS</a> · <a href="/api/sample/Pune_ridership.csv">ridership</a> · <a href="/api/sample/Pune_history.csv">history</a></Note></Card>
        <Card title="Or generate a synthetic city">
          <Note>Creates a realistic bus network with a few years of history, then runs the full analysis.</Note>
          <label className="field"><span>City</span><select value={gen} onChange={(e) => setGen(e.target.value)}>{meta.generator_cities.map((c) => <option key={c}>{c}</option>)}</select></label>
          <label className="field"><span>Random seed</span><input type="number" value={seed} onChange={(e) => setSeed(+e.target.value)} /></label>
          <button className="btn" disabled={busy} onClick={() => run(() => post('/generate', { city: gen, seed }))}>{busy ? 'Working…' : 'Generate and analyse'}</button>
          {dataset !== 'demo' && <p><button className="btn ghost" onClick={() => { setDataset('demo'); setCities([]) }}>← Back to the 23-city demo</button></p>}</Card>
      </div>
    </>
  )
}
