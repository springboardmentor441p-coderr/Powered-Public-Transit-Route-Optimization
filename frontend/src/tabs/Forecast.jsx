import React, { useState } from 'react'
import { Area, CartesianGrid, ComposedChart, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useApi, useApp, pct, fmt } from '../store.jsx'
import { Async, Card, ClassPill, DataTable, Kpi, Note } from '../ui.jsx'

const K = (v) => `${Math.round(v / 1000)}k`
export default function Forecast() {
  const { meta } = useApp(); const cities = meta.selected
  const [city, setCity] = useState(cities[0]); const c = cities.includes(city) ? city : cities[0]; const [route, setRoute] = useState('')
  const s = useApi('/forecast', { city: c, route })
  if (!meta.has_forecast) return <Card title="Forecast"><Note>No forecast for this dataset. Upload a past-ridership file (<code>ridership_history.csv</code> with route_id, month, boardings, at least 26 months) in <b>Your data</b>, or use the demo data.</Note></Card>
  return (
    <Async state={s} what="Forecasting">{(d) => {
      const m = d.metrics; const rows = {}
      d.city_hist.forEach((r) => { rows[r.month] = { month: r.month, actual: r.boardings } })
      d.backtest.forEach((r) => { rows[r.month] = { ...(rows[r.month] || { month: r.month }), backtest: r.model } })
      const last = d.city_hist[d.city_hist.length - 1]; rows[last.month].forecast = last.boardings
      d.city_fc.forEach((r) => { rows[r.month] = { month: r.month, forecast: r.forecast } })
      const cityData = Object.values(rows).sort((a, b) => a.month.localeCompare(b.month))
      const rr = {}; d.route_hist.forEach((r) => { rr[r.month] = { month: r.month, actual: r.boardings } })
      const rl = d.route_hist[d.route_hist.length - 1]; rr[rl.month].forecast = rl.boardings
      d.route_fc.forEach((r) => { rr[r.month] = { month: r.month, forecast: r.forecast, lo: r.lo, band: r.hi - r.lo } })
      const routeData = Object.values(rr).sort((a, b) => a.month.localeCompare(b.month))
      return (<>
        <Card title="Learning from the past to predict the future">
          <Note>The model studies past monthly ridership (trend, seasons, city-wide patterns) and predicts the next 12 months for every route. Pick “Next 12 months” or “Busiest month” at the top to re-plan service for that future demand.</Note>
          {m && <div className="kpis"><Kpi label="Forecast error (WAPE) on a year it had never seen" value={pct(m.model.wape)} sub={`best simple baseline ${pct(m.seasonal_naive_drift.wape)}`} />
            <Kpi label="Naive “same as last 3 months”" value={pct(m.naive_last3.wape)} /><Kpi label="Past months learned from" value={m.train_months} />
            <Kpi label="Actual values inside the 80% range" value={pct(m.interval80_coverage, 0)} /><Kpi label="Routes turning overcrowded at the peak (no change)" value={d.n_risk} tone="over" /></div>}
        </Card>
        <Card title={`Weekday riders – all routes in ${c}`} right={<select value={c} onChange={(e) => { setCity(e.target.value); setRoute('') }} aria-label="City">{cities.map((x) => <option key={x}>{x}</option>)}</select>}>
          <ResponsiveContainer width="100%" height={320}><LineChart data={cityData}><CartesianGrid strokeDasharray="3 3" opacity={0.3} /><XAxis dataKey="month" tick={{ fontSize: 11 }} minTickGap={30} />
            <YAxis tickFormatter={K} domain={['auto', 'auto']} /><Tooltip formatter={(v) => fmt(v, 0)} /><Legend />
            <Line dataKey="actual" name="Past (actual)" stroke="#4c78a8" strokeWidth={2.5} dot={false} connectNulls />
            <Line dataKey="backtest" name="Test: predicted from older data" stroke="#54a24b" strokeDasharray="2 3" dot={false} connectNulls />
            <Line dataKey="forecast" name="Forecast" stroke="#e45756" strokeWidth={2.5} strokeDasharray="6 4" dot={false} connectNulls /></LineChart></ResponsiveContainer></Card>
        <Card title="One route, with 80% range" right={<select value={d.route} onChange={(e) => setRoute(e.target.value)} aria-label="Route">{d.routes.map((r) => <option key={r.route_uid} value={r.route_uid}>{r.route_short_name}</option>)}</select>}>
          <ResponsiveContainer width="100%" height={300}><ComposedChart data={routeData}><CartesianGrid strokeDasharray="3 3" opacity={0.3} /><XAxis dataKey="month" tick={{ fontSize: 11 }} minTickGap={30} /><YAxis domain={['auto', 'auto']} /><Tooltip formatter={(v) => fmt(v, 0)} />
            <Area dataKey="lo" stackId="b" stroke="none" fill="transparent" legendType="none" /><Area dataKey="band" stackId="b" stroke="none" fill="#e45756" fillOpacity={0.2} name="80% range" />
            <Line dataKey="actual" name="Past" stroke="#4c78a8" strokeWidth={2.5} dot={false} connectNulls /><Line dataKey="forecast" name="Forecast" stroke="#e45756" strokeWidth={2.5} strokeDasharray="6 4" dot={false} connectNulls /></ComposedChart></ResponsiveContainer></Card>
        <Card title="Fastest-growing routes and what happens if service stays the same">
          <DataTable pageSize={10} rows={d.risk} columns={[{ key: 'city', label: 'City' }, { key: 'route_short_name', label: 'Route' }, { key: 'fc_growth_pct', label: 'Growth next 12 mo', num: true, render: (v) => `${v > 0 ? '+' : ''}${v.toFixed(1)}%` },
            { key: 'fc_peak_month', label: 'Peak month' }, { key: 'class_now', label: 'Today', render: (v) => <ClassPill c={v} /> }, { key: 'class_avg', label: 'Next 12 mo (avg)', render: (v) => <ClassPill c={v} /> },
            { key: 'class_peak', label: 'At peak month', render: (v) => <ClassPill c={v} /> }]} /></Card>
      </>)
    }}</Async>
  )
}
