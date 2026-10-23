import React, { useState } from 'react'
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useApi, useApp } from '../store.jsx'
import { Async, Card, DataTable, Grid, Note } from '../ui.jsx'
import MapView from '../MapView.jsx'

export default function Explore() {
  const { meta } = useApp(); const cities = meta.selected
  const [city, setCity] = useState(cities[0]); const c = cities.includes(city) ? city : cities[0]
  const s = useApi('/eda', { city: c })
  return (
    <>
      <Card title="Explore a city" right={<select value={c} onChange={(e) => setCity(e.target.value)} aria-label="City">{cities.map((x) => <option key={x}>{x}</option>)}</select>}>
        <Note>See when people ride, where the busiest stops are, and which under-used routes duplicate each other.</Note></Card>
      <Async state={s} what="Loading city">{(d) => (<>
        <div className="grid2">
          <Card title={`Riders by hour – ${c}`}><ResponsiveContainer width="100%" height={300}><LineChart data={d.hourly}>
            <CartesianGrid strokeDasharray="3 3" opacity={0.3} /><XAxis dataKey="hour" /><YAxis tickFormatter={(v) => `${Math.round(v / 1000)}k`} /><Tooltip formatter={(v) => Math.round(v).toLocaleString('en-IN')} /><Legend />
            <Line dataKey="weekday" stroke="#4c78a8" strokeWidth={2.5} dot={false} /><Line dataKey="weekend" stroke="#e45756" strokeWidth={2.5} dot={false} /></LineChart></ResponsiveContainer></Card>
          <Card title="When does each city ride? (share of weekday riders, % per hour)"><Grid z={d.heat.z} rows={d.heat.cities} cols={d.heat.hours} fmtCell={(v) => Math.round(v * 100)} /></Card>
        </div>
        <Card title="Busiest stops (bigger circle = more boardings)"><MapView stops={d.stops} /></Card>
        <Card title="Under-used routes that share most stops with another route (merge candidates)">
          <DataTable pageSize={8} search={false} rows={d.overlaps} columns={[{ key: 'route_a', label: 'Route A' }, { key: 'route_b', label: 'Route B' },
            { key: 'shared_stops', label: 'Shared stops', num: true }, { key: 'overlap_ratio', label: 'Overlap', num: true, render: (v) => `${Math.round(v * 100)}%` },
            { key: 'jaccard', label: 'Similarity', num: true }]} /></Card>
      </>)}</Async>
    </>
  )
}
