import React from 'react'
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useApi, fmt } from '../store.jsx'
import { Async, Card, DataTable, Note } from '../ui.jsx'

export default function Impact() {
  const s = useApi('/impact')
  return (
    <Async state={s} what="Simulating impact">{(d) => {
      const pick = (keys) => d.rows.filter((r) => keys.includes(r.key)).map((r) => ({ metric: r.metric, Current: r.current, Optimised: r.optimised }))
      const Chart = ({ data, title }) => <Card title={title}><ResponsiveContainer width="100%" height={260}><BarChart data={data}><CartesianGrid strokeDasharray="3 3" opacity={0.3} /><XAxis dataKey="metric" tick={{ fontSize: 11 }} /><YAxis /><Tooltip formatter={(v) => fmt(v, 0)} /><Legend />
        <Bar dataKey="Current" fill="#9aa4b5" /><Bar dataKey="Optimised" fill="#54a24b" /></BarChart></ResponsiveContainer></Card>
      return (<>
        <Card title="Current vs optimised service (weekday)"><Note>Simulation: passengers stay the same, buses are moved to where they are needed. Merged routes count as one service.</Note>
          <DataTable search={false} pageSize={12} rows={d.rows} columns={[{ key: 'metric', label: 'Measure' }, { key: 'current', label: 'Current', num: true, render: (v) => fmt(v, v < 10 ? 2 : 0) },
            { key: 'optimised', label: 'Optimised', num: true, render: (v) => fmt(v, v < 10 ? 2 : 0) }, { key: 'change_pct', label: 'Change', num: true, render: (v) => `${v > 0 ? '+' : ''}${v.toFixed(1)}%` }]} /></Card>
        <div className="grid2"><Chart title="Problem routes" data={pick(['n_routes_overcrowded', 'n_routes_underutilized'])} /><Chart title="Fleet effort" data={pick(['total_trips_day', 'bus_hours_day'])} /></div>
        <Card title="Overcrowded routes per city" className="mt"><ResponsiveContainer width="100%" height={320}><BarChart data={d.per_city.map((r) => ({ city: r.city, Current: r.before_n_routes_overcrowded, Optimised: r.after_n_routes_overcrowded }))} margin={{ bottom: 40 }}>
          <CartesianGrid strokeDasharray="3 3" opacity={0.3} /><XAxis dataKey="city" angle={-45} textAnchor="end" interval={0} height={70} tick={{ fontSize: 11 }} /><YAxis /><Tooltip /><Legend verticalAlign="top" />
          <Bar dataKey="Current" fill="#e45756" /><Bar dataKey="Optimised" fill="#54a24b" /></BarChart></ResponsiveContainer></Card>
      </>)
    }}</Async>
  )
}
