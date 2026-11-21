import { describe, expect, it } from 'vitest'
import type { HistoryDay } from '../api/types'
import { daytypeMeans, recordCoverage, shareOfWeekday } from './routeProfile'

const D = (date: string, daytype: HistoryDay['daytype'], rides: number | null): HistoryDay => ({
  service_date: date, daytype, rides, selected_snapshot_id: null, scheduled_trips: null, scheduled_service_hours: null,
  duration_complete: null, trips_missing_duration: null, rides_per_scheduled_trip: null, rides_per_scheduled_hour: null,
  status: rides == null ? 'schedule_without_ridership' : 'matched', reason: rides == null ? 'service was scheduled but no ridership was recorded' : null,
  reason_code: rides == null ? 'no_ridership_record' : null,
  has_record: rides != null, has_schedule: true,
})

describe('daytypeMeans', () => {
  it('averages only days with a record; a missing day is never counted as 0', () => {
    const m = daytypeMeans([D('2026-01-05', 'W', 100), D('2026-01-06', 'W', null), D('2026-01-07', 'W', 300), D('2026-01-10', 'A', 50)])
    expect(m.W).toEqual({ daytype: 'W', days: 2, mean: 200 })
    expect(m.A.mean).toBe(50)
    expect(m.U).toEqual({ daytype: 'U', days: 0, mean: null })
  })
  it('a recorded 0 is a real 0 and is counted', () => {
    expect(daytypeMeans([D('2026-01-05', 'W', 0), D('2026-01-06', 'W', 10)]).W.mean).toBe(5)
  })
})

describe('shareOfWeekday', () => {
  it('is null (not 0) when a day type has no recorded day', () => {
    const m = daytypeMeans([D('2026-01-05', 'W', 100), D('2026-01-10', 'A', 40)])
    expect(shareOfWeekday(m, 'A')).toBeCloseTo(0.4)
    expect(shareOfWeekday(m, 'U')).toBeNull()
  })
})

describe('recordCoverage', () => {
  it('counts scheduled days with and without a record', () => {
    expect(recordCoverage({ matched: 191, schedule_without_ridership: 24, no_service_no_record: 36 })).toEqual({ recorded: 191, scheduled: 215 })
  })
})
