import React from 'react'
import { CartesianGrid, Legend, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from 'recharts'
import { useApi } from '../store.jsx'
import { Async, Card, DataTable, Note } from '../ui.jsx'

const PAL = ['#4c78a8', '#e45756', '#54a24b', '#f2994a', '#9c6ade', '#17becf', '#8c564b', '#7f7f7f']
const group = (pts, key) => [...new Set(pts.map((p) => p[key]))].sort().map((g) => ({ g, data: pts.filter((p) => p[key] === g) }))

function Plot({ pts, k, title }) {
  return (
    <Card title={title}><ResponsiveContainer width="100%" height={340}><ScatterChart>
      <CartesianGrid strokeDasharray="3 3" opacity={0.3} /><XAxis type="number" dataKey="pca1" name="Component 1" /><YAxis type="number" dataKey="pca2" name="Component 2" />
      <Tooltip content={({ payload }) => payload?.[0] ? <div className="card" style={{ padding: 8 }}>{payload[0].payload.city} · {payload[0].payload.name}<br />{payload[0].payload[k]}</div> : null} /><Legend verticalAlign="top" />
      {group(pts, k).map((s, i) => <Scatter key={s.g} name={s.g} data={s.data} fill={s.g === 'outlier' ? '#999' : PAL[i % PAL.length]} fillOpacity={0.75} />)}</ScatterChart></ResponsiveContainer></Card>
  )
}

export default function Clusters() {
  const s = useApi('/clusters')
  return (
    <Async state={s} what="Grouping routes">{(d) => (<>
      <Card title="Groups of similar routes"><Note>Routes are grouped by how they are used (riders, crowding, peak pattern, length, frequency). KMeans finds {d.metrics.k} broad groups
        (silhouette {d.metrics.kmeans_silhouette.toFixed(2)}); DBSCAN also flags unusual routes as outliers ({Math.round(d.metrics.dbscan_noise_frac * 100)}% here). Usage varies smoothly, so the groups overlap.</Note></Card>
      <div className="grid2"><Plot pts={d.points} k="kmeans" title="KMeans groups" /><Plot pts={d.points} k="dbscan" title="DBSCAN groups and outliers" /></div>
      <Card title="What each KMeans group looks like" className="mt"><DataTable search={false} rows={d.profiles} columns={[{ key: 'kmeans_cluster', label: 'Group' }, { key: 'routes', label: 'Routes', num: true },
        { key: 'boardings_day', label: 'Riders/day', num: true }, { key: 'avg_lf', label: 'Avg load', num: true }, { key: 'peak_lf', label: 'Peak load', num: true },
        { key: 'trips_day', label: 'Trips/day', num: true }, { key: 'length_km', label: 'Length km', num: true }]} /></Card>
    </>)}</Async>
  )
}
