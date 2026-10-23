import React, { useEffect, useState } from 'react'
import { Bar, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useApi, useApp, fmt } from '../store.jsx'
import { url } from '../api.js'
import { ActionPill, Async, Card, Chips, ClassPill, DataTable, Note } from '../ui.jsx'
import MapView from '../MapView.jsx'

function Detail({ uid }) {
  const s = useApi('/route', { uid })
  return (
    <Async state={s} what="Loading route">{(d) => (
      <Card title={`Route ${d.rec.route_short_name} – ${d.rec.action}`}>
        <p style={{ margin: 0 }}>{d.rec.detail} {d.rec.structural_option && <b>{d.rec.structural_option}</b>}</p>
        <div className="grid2" style={{ marginTop: 12 }}>
          <ResponsiveContainer width="100%" height={280}><ComposedChart data={d.hourly}><CartesianGrid strokeDasharray="3 3" opacity={0.3} /><XAxis dataKey="hour" /><YAxis allowDecimals={false} /><Tooltip /><Legend />
            <Bar dataKey="current" name="Buses/hour now" fill="#9aa4b5" /><Bar dataKey="recommended" name="Buses/hour recommended" fill="#e45756" />
            <Line dataKey="needed" name="Needed at target crowding" stroke="#4c78a8" strokeWidth={2} dot={false} /></ComposedChart></ResponsiveContainer>
          <MapView line={d.stops} /></div></Card>)}</Async>
  )
}

export default function Recommendations() {
  const s = useApi('/recommendations'); const { query } = useApp()
  const [acts, setActs] = useState(null); const [sel, setSel] = useState(null)
  useEffect(() => { if (s.data && !sel) setSel(s.data.recs[0]?.route_uid) }, [s.data])           // eslint-disable-line
  return (
    <Async state={s} what="Optimising service">{(d) => {
      const all = Object.keys(d.actions); const on = acts || all.filter((a) => a !== 'No change'); const rows = d.recs.filter((r) => on.includes(r.action))
      return (<>
        <Card title="Recommended changes" right={<a className="btn" href={url('/download/recommendations.csv', { ...query, actions: on.join(',') })}>⬇ Download CSV</a>}>
          <Note>Sorted by impact. Click a row to see the hourly plan and the route on the map. {d.n_merges} merge(s) suggested.</Note>
          <Chips multi options={all} value={on} onChange={setActs} label={(a) => `${a} (${d.actions[a]})`} />
          <div style={{ height: 10 }} />
          <DataTable rowKey="route_uid" selected={sel} onRow={(r) => setSel(r.route_uid)} rows={rows} columns={[{ key: 'city', label: 'City' }, { key: 'route_short_name', label: 'Route' },
            { key: 'pred_class', label: 'Status', render: (v) => <ClassPill c={v} /> }, { key: 'action', label: 'Action', render: (v) => <ActionPill a={v} /> },
            { key: 'trips_day_before', label: 'Trips/day now', num: true, render: (v) => fmt(v, 0) }, { key: 'trips_day_after', label: 'Recommended', num: true, render: (v) => fmt(v, 0) },
            { key: 'peak_headway_before_min', label: 'Peak wait now (min)', num: true, render: (v) => fmt(v) }, { key: 'peak_headway_after_min', label: 'Recommended', num: true, render: (v) => fmt(v) }]} /></Card>
        {sel && <Detail uid={sel} />}
      </>)
    }}</Async>
  )
}
