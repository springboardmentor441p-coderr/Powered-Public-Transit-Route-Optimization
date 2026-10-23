import React from 'react'
import { Bar, BarChart, CartesianGrid, Legend, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from 'recharts'
import { useApi, useApp, COLORS, CLASS_LABEL } from '../store.jsx'
import { Async, Card, Kpi, DataTable, ClassPill, ActionPill, Note } from '../ui.jsx'

const CLS = ['underutilized', 'balanced', 'overcrowded']

export default function Overview() {
  const s = useApi('/overview'); const { meta, scenario } = useApp()
  return (
    <Async state={s} what="Analysing routes">{(d) => (<>
      <div className="hero"><h2>Find the bus routes that need help</h2>
        <p>RouteRanker learns from transit data to spot overcrowded and under-used routes, forecasts next year’s demand, and recommends where to add buses, cut buses or merge routes.</p></div>
      <div className="kpis">
        <Kpi label="Cities" value={d.kpis.cities} /><Kpi label="Routes analysed" value={d.kpis.routes} />
        <Kpi label="Overcrowded" value={d.kpis.overcrowded} tone="over" /><Kpi label="Under-used" value={d.kpis.underutilized} tone="under" />
        <Kpi label="Balanced" value={d.kpis.balanced} tone="bal" /></div>
      <Note>Planning for: <b>{{ today: 'today’s demand', avg: 'the next 12 months (forecast average)', peak: 'the busiest forecast month' }[meta?.scenario || scenario]}</b>.
        Ridership source: <b>{meta?.ridership_source}</b>{meta?.ridership_source === 'estimated' ? ' (no passenger counts supplied, so demand is estimated from stop locations).' : '.'}</Note>
      <div className="grid2">
        <Card title="Route status by city"><ResponsiveContainer width="100%" height={330}><BarChart data={d.by_city} margin={{ bottom: 40 }}>
          <CartesianGrid strokeDasharray="3 3" opacity={0.3} /><XAxis dataKey="city" angle={-45} textAnchor="end" interval={0} height={70} tick={{ fontSize: 11 }} /><YAxis /><Tooltip /><Legend verticalAlign="top" />
          {CLS.map((c) => <Bar key={c} dataKey={c} name={CLASS_LABEL[c]} stackId="a" fill={COLORS[c]} />)}</BarChart></ResponsiveContainer></Card>
        <Card title="Average vs peak crowding (1.0 = bus full)"><ResponsiveContainer width="100%" height={330}><ScatterChart>
          <CartesianGrid strokeDasharray="3 3" opacity={0.3} /><XAxis type="number" dataKey="x" name="Average load" domain={[0, 'auto']} /><YAxis type="number" dataKey="y" name="Peak load" domain={[0, 'auto']} />
          <Tooltip cursor={{ strokeDasharray: '3 3' }} formatter={(v) => Number(v).toFixed(2)} /><Legend verticalAlign="top" />
          <ReferenceLine y={d.thresholds.over} stroke="#999" strokeDasharray="4 4" /><ReferenceLine x={d.thresholds.under} stroke="#999" strokeDasharray="4 4" />
          {CLS.map((c) => <Scatter key={c} name={CLASS_LABEL[c]} data={d.scatter.filter((p) => p.cls === c)} fill={COLORS[c]} fillOpacity={0.7} />)}</ScatterChart></ResponsiveContainer></Card>
      </div>
      <Card title="Top 10 priority routes" className="mt">
        <DataTable search={false} pageSize={10} rows={d.top} columns={[
          { key: 'city', label: 'City' }, { key: 'route_short_name', label: 'Route' }, { key: 'pred_class', label: 'Status', render: (v) => <ClassPill c={v} /> },
          { key: 'action', label: 'Action', render: (v) => <ActionPill a={v} /> }, { key: 'detail', label: 'What to do' }]} />
      </Card>
      <Card title="How to use this site"><ol className="steps">
        <li>Choose a <b>city</b> in the left panel (or open <b>Your data</b> to upload a bus feed).</li>
        <li>Pick what to plan for at the top: <b>Today</b> or the <b>forecast</b> for the next 12 months.</li>
        <li>Open <b>Recommendations</b> to see which routes need more buses, fewer buses or a merge, then <b>Impact</b> for the expected benefit.</li>
        <li>Download the list as CSV. Change any setting on the left and everything updates.</li></ol></Card>
    </>)}</Async>
  )
}
