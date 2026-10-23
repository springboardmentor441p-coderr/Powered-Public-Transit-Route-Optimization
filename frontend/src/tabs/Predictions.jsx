import React, { useState } from 'react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useApi, pct, COLORS, CLASS_LABEL } from '../store.jsx'
import { Async, Card, Chips, ClassPill, DataTable, Grid, Note } from '../ui.jsx'

const NAME = { random_forest: 'Random Forest', xgboost: 'XGBoost' }
export default function Predictions() {
  const s = useApi('/predictions'); const [f, setF] = useState(['overcrowded', 'underutilized'])
  return (
    <Async state={s} what="Loading model results">{(d) => {
      const cm = d.models[d.best].grouped_cv.confusion; const imp = Object.entries(d.importance).slice(0, 12).map(([k, v]) => ({ k, v }))
      return (<>
        <Card title="How well can the model tell route status?">
          <Note>Two models were trained to predict whether a route is under-used, balanced or overcrowded <b>from its structure only</b> (length, stops, frequency, overlap, location), so it also works for cities without passenger counts.
            They were tested on whole cities they had never seen. Chance level is 33%.</Note>
          <DataTable search={false} rows={Object.entries(d.models).map(([k, v]) => ({ model: NAME[k] + (k === d.best ? ' ★ selected' : ''), cv: v.grouped_cv.accuracy, f1: v.grouped_cv.macro_f1, val: v.stratified_val.macro_f1, unseen: v.unseen_cities?.macro_f1 }))}
            columns={[{ key: 'model', label: 'Model' }, { key: 'cv', label: 'Accuracy (city-grouped CV)', num: true, render: pct }, { key: 'f1', label: 'F1 (CV)', num: true, render: (v) => v.toFixed(3) },
              { key: 'val', label: 'F1 (validation)', num: true, render: (v) => v.toFixed(3) }, { key: 'unseen', label: 'F1 (unseen cities)', num: true, render: (v) => v?.toFixed(3) }]} /></Card>
        <div className="grid2">
          <Card title="Predicted vs actual status (rows = actual)"><Grid z={cm} rows={d.classes.map((c) => CLASS_LABEL[c])} cols={d.classes.map((c) => CLASS_LABEL[c])} hue={210} /></Card>
          <Card title="What the model looks at most"><ResponsiveContainer width="100%" height={300}><BarChart data={imp} layout="vertical" margin={{ left: 40 }}>
            <CartesianGrid strokeDasharray="3 3" opacity={0.3} /><XAxis type="number" /><YAxis type="category" dataKey="k" width={130} tick={{ fontSize: 11 }} /><Tooltip /><Bar dataKey="v" fill="#4c78a8" /></BarChart></ResponsiveContainer></Card>
        </div>
        <Card title="Route predictions" className="mt" right={<Chips multi options={d.classes} value={f} onChange={setF} label={(c) => CLASS_LABEL[c]} />}>
          <DataTable rows={d.routes.filter((r) => f.includes(r.pred_class))} columns={[{ key: 'city', label: 'City' }, { key: 'route_short_name', label: 'Route' },
            { key: 'pred_class', label: 'Predicted', render: (v) => <ClassPill c={v} /> }, { key: 'confidence', label: 'Confidence', num: true, render: (v) => pct(v, 0) },
            { key: 'label', label: 'Actual', render: (v) => <ClassPill c={v} /> }, { key: 'peak_lf', label: 'Peak load', num: true }, { key: 'trips_per_day', label: 'Trips/day', num: true }, { key: 'route_length_km', label: 'km', num: true }]} /></Card>
      </>)
    }}</Async>
  )
}
