import { SLATE_RAMP } from '../design/tokens'
import { fmt } from '../lib/format'
import { buildRhythm, WEEKDAYS, type DayIn } from '../lib/rhythm'

/** Weekday-rhythm grid: weeks across, Mon..Sun down, each cell shaded by recorded rides (one slate hue).
 *  A missing day is an outlined empty cell with its reason; a recorded 0 is a filled cell marked "0". */
export function RhythmGrid({ days, unit }: { days: DayIn[]; unit: string }) {
  const { weeks, weekStarts, lo, hi } = buildRhythm(days, SLATE_RAMP.length)
  const cell = 'h-4 w-4'
  return (
    <div>
      <div className="flex gap-[3px] overflow-x-auto pb-1" role="img"
           aria-label={`Recorded rides per day, ${weeks.length} weeks; outlined cells are days without a record`}>
        <div className="mr-1 flex flex-col gap-[3px] text-[11px] leading-4 text-ink-2">
          {WEEKDAYS.map(d => <div key={d} className="h-4">{d}</div>)}
        </div>
        {weeks.map((col, w) => (
          <div key={weekStarts[w]} className="flex flex-col gap-[3px]">
            {col.map((c, d) => {
              if (c.kind === 'outside') return <div key={d} className={cell} />
              if (c.kind === 'missing') {
                return <div key={d} title={`${c.date}: unavailable – ${c.reason}`}
                            className={`${cell} border border-dashed border-ink-2 bg-panel`} />
              }
              const label = `${c.date}: ${fmt(c.rides)} ${unit}`
              return c.kind === 'zero'
                ? <div key={d} title={label} className={`${cell} flex items-center justify-center border border-rule-strong bg-panel text-[9px] font-semibold text-ink`}>0</div>
                : <div key={d} title={label} className={cell} style={{ background: SLATE_RAMP[c.step] }} />
            })}
          </div>
        ))}
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-ink-2">
        <span className="flex items-center gap-1">
          <span className="num">{fmt(lo)}</span>
          {SLATE_RAMP.map(c => <span key={c} className="h-3 w-4" style={{ background: c }} />)}
          <span className="num">{fmt(hi)}</span> {unit}
        </span>
        <span className="flex items-center gap-1"><span className="h-3 w-3 border border-dashed border-ink-2" /> no record (hover for the reason)</span>
        <span className="flex items-center gap-1"><span className="flex h-3 w-3 items-center justify-center border border-rule-strong text-[8px] text-ink">0</span> recorded zero</span>
      </div>
    </div>
  )
}
