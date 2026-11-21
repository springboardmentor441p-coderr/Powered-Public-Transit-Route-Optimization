import { CartesianGrid, Line, LineChart, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { TrendDay, TrendResponse } from '../api/types'
import { BRAND, INK, INK_2, RULE } from '../design/tokens'
import { addDays, fmtDate } from '../lib/dates'
import { fmt } from '../lib/format'
import { Value } from './Value'

const DAYTYPE: Record<string, string> = { W: 'weekday', A: 'Saturday', U: 'Sunday/holiday' }

function TrendTooltip({ active, payload, unit }: { active?: boolean; payload?: { payload: TrendDay }[]; unit: string }) {
  const d = payload?.[0]?.payload
  if (!active || !d) return null
  return (
    <div className="border border-rule-strong bg-panel px-3 py-2 text-sm">
      <div className="font-semibold">{fmtDate(d.service_date)}{d.daytype && <span className="font-normal text-ink-2"> · {DAYTYPE[d.daytype]}</span>}</div>
      <div>Recorded rides: <Value value={d.rides} unit={unit} reason={d.reason} /></div>
      <div className="text-xs text-ink-2">{fmt(d.routes_reporting)} routes reported</div>
      {d.scheduled_trips != null
        ? <div className="text-xs text-ink-2">Scheduled trips: {fmt(d.scheduled_trips)} on {fmt(d.routes_scheduled)} routes</div>
        : d.status === 'recorded_rides_only' && <div className="text-xs text-ink-2">{d.reason}</div>}
    </div>
  )
}

/** Network recorded rides per day. A day without any record breaks the line (never drawn at 0); days before the
 *  dated schedules are shaded and labelled. */
export function TrendChart({ t, height = 280 }: { t: TrendResponse; height?: number }) {
  const w0 = t.range.schedule_window.start
  const shadeEnd = t.range.start < w0 ? addDays(w0, -1) : null
  const long = t.count > 400
  return (
    <div style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={t.days} margin={{ top: 8, right: 12, bottom: 0, left: 4 }}>
          <CartesianGrid stroke={RULE} vertical={false} />
          {shadeEnd && (
            <ReferenceArea x1={t.range.start} x2={shadeEnd} fill="#EDF0F3" fillOpacity={1}
                           label={{ value: 'Recorded rides only, no dated schedule', position: 'insideTopLeft', fontSize: 11, fill: INK_2 }} />
          )}
          <XAxis dataKey="service_date" tick={{ fontSize: 11, fill: INK_2 }} tickLine={false} axisLine={{ stroke: RULE }}
                 minTickGap={48} tickFormatter={(d: string) => (long ? d.slice(0, 4) : fmtDate(d).slice(0, -5))} />
          <YAxis tick={{ fontSize: 11, fill: INK_2 }} tickLine={false} axisLine={false} width={64}
                 tickFormatter={(v: number) => fmt(v)}
                 label={{ value: t.units.rides, angle: -90, position: 'insideLeft', fontSize: 11, fill: INK_2, dx: -2 }} />
          <Tooltip content={<TrendTooltip unit={t.units.rides} />} cursor={{ stroke: INK, strokeWidth: 1 }} isAnimationActive={false} />
          <Line dataKey="rides" stroke={BRAND} strokeWidth={long ? 1 : 1.5} dot={false} connectNulls={false}
                isAnimationActive={false} activeDot={{ r: 4, stroke: '#FFFFFF', strokeWidth: 2 }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
