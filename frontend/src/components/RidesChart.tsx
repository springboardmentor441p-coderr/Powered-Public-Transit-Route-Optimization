import type { ReactNode } from 'react'
import { CartesianGrid, Line, LineChart, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { BRAND, INK, INK_2, RULE } from '../design/tokens'
import { addDays, fmtDate } from '../lib/dates'
import { fmt } from '../lib/format'
import { Value } from './Value'

export type RidesDay = { service_date: string; daytype: string | null; rides: number | null; reason: string | null }
const DAYTYPE: Record<string, string> = { W: 'weekday', A: 'Saturday', U: 'Sunday/holiday' }

function RidesTooltip<D extends RidesDay>({ active, payload, unit, extra }: {
  active?: boolean; payload?: { payload: D }[]; unit: string; extra?: (d: D) => ReactNode
}) {
  const d = payload?.[0]?.payload
  if (!active || !d) return null
  return (
    <div className="border border-rule-strong bg-panel px-3 py-2 text-sm">
      <div className="font-semibold">{fmtDate(d.service_date)}{d.daytype && <span className="font-normal text-ink-2"> · {DAYTYPE[d.daytype]}</span>}</div>
      <div>Recorded rides: <Value value={d.rides} unit={unit} reason={d.reason} /></div>
      {extra?.(d)}
    </div>
  )
}

/** Recorded rides per day. A day without a record breaks the line (never drawn at 0); days before the dated
 *  schedules are shaded and labelled. Shared by the network trend and a route's history. */
export function RidesChart<D extends RidesDay>({ days, rangeStart, scheduleStart, unit, extra, height = 280 }: {
  days: D[]; rangeStart: string; scheduleStart: string; unit: string; extra?: (d: D) => ReactNode; height?: number
}) {
  const shadeEnd = rangeStart < scheduleStart ? addDays(scheduleStart, -1) : null
  const long = days.length > 400
  return (
    <div style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={days} margin={{ top: 8, right: 12, bottom: 0, left: 4 }}>
          <CartesianGrid stroke={RULE} vertical={false} />
          {shadeEnd && (
            <ReferenceArea x1={rangeStart} x2={shadeEnd} fill="#EDF0F3" fillOpacity={1}
                           label={{ value: 'Recorded rides only, no dated schedule', position: 'insideTopLeft', fontSize: 11, fill: INK_2 }} />
          )}
          <XAxis dataKey="service_date" tick={{ fontSize: 11, fill: INK_2 }} tickLine={false} axisLine={{ stroke: RULE }}
                 minTickGap={48} tickFormatter={(d: string) => (long ? d.slice(0, 4) : fmtDate(d).slice(0, -5))} />
          <YAxis tick={{ fontSize: 11, fill: INK_2 }} tickLine={false} axisLine={false} width={64}
                 tickFormatter={(v: number) => fmt(v)}
                 label={{ value: unit, angle: -90, position: 'insideLeft', fontSize: 11, fill: INK_2, dx: -2 }} />
          <Tooltip content={<RidesTooltip unit={unit} extra={extra} />} cursor={{ stroke: INK, strokeWidth: 1 }} isAnimationActive={false} />
          <Line dataKey="rides" stroke={BRAND} strokeWidth={long ? 1 : 1.5} dot={false} connectNulls={false}
                isAnimationActive={false} activeDot={{ r: 4, stroke: '#FFFFFF', strokeWidth: 2 }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
