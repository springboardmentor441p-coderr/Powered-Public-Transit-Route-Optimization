import React, { useMemo, useState } from 'react'
import { COLORS, CLASS_LABEL, fmt } from './store.jsx'

export const Card = ({ title, children, className = '', right }) => (
  <section className={`card ${className}`}>
    {(title || right) && <div className="card-h"><h3>{title}</h3>{right}</div>}
    {children}
  </section>
)
export const Kpi = ({ label, value, sub, tone }) => (
  <div className={`kpi ${tone || ''}`}><div className="kpi-v">{value}</div><div className="kpi-l">{label}</div>{sub && <div className="kpi-s">{sub}</div>}</div>
)
export const Loading = ({ what = 'Loading' }) => <div className="loading" role="status"><span className="spin" />{what}…</div>
export const ErrorBox = ({ error }) => <div className="err" role="alert">⚠️ {error}</div>
export const ClassPill = ({ c }) => <span className="pill" style={{ background: COLORS[c] || '#888' }}>{CLASS_LABEL[c] || c}</span>
export const ActionPill = ({ a }) => <span className={`pill act ${a.split(' ')[0].toLowerCase()}`}>{a}</span>
export const Note = ({ children }) => <p className="note">{children}</p>

export function Async({ state, what, children }) {
  if (state.error) return <ErrorBox error={state.error} />
  if (!state.data) return <Loading what={what} />
  return <div className={state.loading ? 'stale' : ''}>{children(state.data)}</div>
}

export function Chips({ options, value, onChange, multi = false, label = (x) => x }) {
  const on = (o) => (multi ? value.includes(o) : value === o)
  const click = (o) => onChange(multi ? (value.includes(o) ? value.filter((x) => x !== o) : [...value, o]) : o)
  return <div className="chips">{options.map((o) => <button key={o} className={`chip ${on(o) ? 'on' : ''}`} onClick={() => click(o)}>{label(o)}</button>)}</div>
}

export function Slider({ label, value, min, max, step = 1, onCommit, format = (v) => v }) {
  const [v, setV] = useState(value)
  React.useEffect(() => setV(value), [value])
  const commit = () => v !== value && onCommit(Number(v))
  return (
    <label className="slider"><span>{label}<b>{format(v)}</b></span>
      <input type="range" min={min} max={max} step={step} value={v} onChange={(e) => setV(e.target.value)}
        onMouseUp={commit} onTouchEnd={commit} onKeyUp={commit} onBlur={commit} /></label>
  )
}

/** Sortable, searchable, paginated table. columns: [{key,label,render?,num?}] */
export function DataTable({ rows, columns, pageSize = 12, search = true, onRow, selected, rowKey }) {
  const [q, setQ] = useState(''); const [sort, setSort] = useState({ key: null, dir: 1 }); const [page, setPage] = useState(0)
  const data = useMemo(() => {
    let r = rows
    if (q) { const s = q.toLowerCase(); r = r.filter((x) => columns.some((c) => String(x[c.key] ?? '').toLowerCase().includes(s))) }
    if (sort.key) r = [...r].sort((a, b) => ((a[sort.key] ?? -Infinity) > (b[sort.key] ?? -Infinity) ? 1 : -1) * sort.dir)
    return r
  }, [rows, q, sort, columns])
  const pages = Math.max(1, Math.ceil(data.length / pageSize)); const p = Math.min(page, pages - 1)
  return (
    <div className="dt">
      {search && <input className="search" placeholder="Search…" value={q} onChange={(e) => { setQ(e.target.value); setPage(0) }} aria-label="Search table" />}
      <div className="scroll"><table>
        <thead><tr>{columns.map((c) => (
          <th key={c.key} className={c.num ? 'num' : ''} onClick={() => setSort((s) => ({ key: c.key, dir: s.key === c.key ? -s.dir : 1 }))}>
            {c.label}{sort.key === c.key ? (sort.dir === 1 ? ' ▲' : ' ▼') : ''}</th>))}</tr></thead>
        <tbody>{data.slice(p * pageSize, (p + 1) * pageSize).map((r, i) => (
          <tr key={rowKey ? r[rowKey] : i} className={`${onRow ? 'click' : ''} ${selected && selected === r[rowKey] ? 'sel' : ''}`} onClick={() => onRow && onRow(r)}>
            {columns.map((c) => <td key={c.key} className={c.num ? 'num' : ''}>{c.render ? c.render(r[c.key], r) : (typeof r[c.key] === 'number' ? fmt(r[c.key], 2) : r[c.key])}</td>)}
          </tr>))}
          {!data.length && <tr><td colSpan={columns.length} className="muted">No rows</td></tr>}</tbody></table></div>
      <div className="pager"><span>{data.length} rows</span>
        <span><button disabled={p === 0} onClick={() => setPage(p - 1)}>‹ Prev</button> {p + 1} / {pages} <button disabled={p >= pages - 1} onClick={() => setPage(p + 1)}>Next ›</button></span></div>
    </div>
  )
}

/** Colour grid used for heat-maps and confusion matrices. */
export function Grid({ z, rows, cols, fmtCell = (v) => v, max, hue = 8 }) {
  const m = max ?? Math.max(...z.flat(), 1e-9)
  return (
    <div className="scroll"><table className="grid"><thead><tr><th />{cols.map((c) => <th key={c}>{c}</th>)}</tr></thead>
      <tbody>{z.map((r, i) => <tr key={rows[i]}><th>{rows[i]}</th>{r.map((v, j) => (
        <td key={j} title={`${rows[i]} · ${cols[j]}: ${fmtCell(v)}`} style={{ background: `hsla(${hue}, 85%, 52%, ${0.08 + 0.92 * (v / m)})`, color: v / m > 0.55 ? '#fff' : 'inherit' }}>{fmtCell(v)}</td>))}</tr>)}</tbody></table></div>
  )
}
