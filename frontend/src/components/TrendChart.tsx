import type { TrendDay, TrendResponse } from '../api/types'
import { fmt } from '../lib/format'
import { RidesChart } from './RidesChart'

/** Network recorded rides per day (the Start page), with the number of routes reporting in the tooltip. */
export function TrendChart({ t, height = 280 }: { t: TrendResponse; height?: number }) {
  return (
    <RidesChart<TrendDay> days={t.days} rangeStart={t.range.start} scheduleStart={t.range.schedule_window.start}
                          unit={t.units.rides} height={height}
                          extra={d => <>
                            <div className="text-xs text-ink-2">{fmt(d.routes_reporting)} routes reported</div>
                            {d.scheduled_trips != null
                              ? <div className="text-xs text-ink-2">Scheduled trips: {fmt(d.scheduled_trips)} on {fmt(d.routes_scheduled)} routes</div>
                              : d.status === 'recorded_rides_only' && <div className="text-xs text-ink-2">{d.reason}</div>}
                          </>} />
  )
}
