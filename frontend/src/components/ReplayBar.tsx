import { useId, useState } from 'react'
import { useReplay } from '../api/replayContext'
import { fmtDate } from '../lib/dates'
import { replayHeadline, replayProgress } from '../lib/replay'

const SPEEDS = [1, 2, 5, 10]

/** The mode switch for the top bar: "Historical analysis | Historical replay" (spec 9.13.1 labels). */
export function ModeSwitch() {
  const r = useReplay()
  const btn = (on: boolean) => `h-7 whitespace-nowrap px-2.5 text-sm ${on ? 'bg-white font-semibold text-brand' : 'text-white hover:bg-white/10'}`
  return (
    <div role="group" aria-label="Mode" className="flex border border-brand-text">
      <button type="button" aria-pressed={r.mode === 'historical'} className={btn(r.mode === 'historical')} onClick={r.leave}>
        Historical analysis</button>
      <button type="button" aria-pressed={r.mode === 'replay'} className={btn(r.mode === 'replay')} disabled={r.busy}
              onClick={r.resume}>Historical replay</button>
    </div>
  )
}

/** The replay controls, under the top bar while in replay: the virtual day, what is revealed, the stated delay
 *  assumption, and Start/Pause, next day, next week, a date to move to, speed, jump to end and reset. The server owns
 *  the clock; every button is a request to it. */
export function ReplayBar() {
  const r = useReplay()
  const dateId = useId(), speedId = useId()
  const [to, setTo] = useState('')
  const s = r.state
  if (r.mode !== 'replay') return null
  if (!s) {
    return <div className="border-b border-rule bg-panel px-6 py-2 text-sm" role="status">
      {r.error ? <span>Replay unavailable – {r.error}</span> : 'Starting the replay…'}</div>
  }
  const done = s.complete
  const b = 'btn-secondary h-8 px-2.5 text-sm disabled:opacity-50'
  return (
    <div className="border-b border-rule-strong bg-panel" aria-label="Replay controls">
      <div className="mx-auto flex max-w-[1440px] flex-wrap items-center gap-x-4 gap-y-2 px-6 py-2">
        <div className="min-w-0">
          <div className="text-md font-semibold" aria-live="polite">{replayHeadline(s)}</div>
          <div className="text-xs text-ink-2">
            Assumption: {s.delay_assumption} ({s.delay_note}). Day {Math.min(s.days_revealed + (done ? 0 : 1), s.days_total)} of{' '}
            {s.days_total}, {fmtDate(s.start_date)} – {fmtDate(s.final_date)}.
          </div>
          <div className="mt-1 h-1 w-full max-w-[24rem] bg-rule" aria-hidden><div className="h-1 bg-brand" style={{ width: `${replayProgress(s) * 100}%` }} /></div>
        </div>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          {s.status === 'playing'
            ? <button type="button" className={b} onClick={() => void r.act('pause')} disabled={r.busy}>Pause</button>
            : <button type="button" className={b} onClick={() => void r.act('start')} disabled={r.busy || done}>Play</button>}
          <label htmlFor={speedId} className="sr-only">Playback speed</label>
          <select id={speedId} name="replay_speed" className="h-8 border border-rule-strong bg-panel px-1 text-sm" value={s.speed_seconds}
                  onChange={e => void r.act('set_speed', { speed_seconds: Number(e.target.value) })} disabled={r.busy}>
            {[...new Set([...SPEEDS, s.speed_seconds])].sort((x, y) => x - y).map(v => <option key={v} value={v}>1 day every {v} s</option>)}
          </select>
          <button type="button" className={b} onClick={() => void r.act('advance')} disabled={r.busy || done}>Next day</button>
          <button type="button" className={b} onClick={() => void r.act('next_week')} disabled={r.busy || done}>Next week</button>
          <span className="flex items-center gap-1">
            <label htmlFor={dateId} className="sr-only">Move to a later day</label>
            <input id={dateId} name="replay_to" type="date" className="h-8 border border-rule-strong bg-panel px-1 text-sm"
                   min={s.virtual_date ?? undefined} max={s.final_date} value={to} onChange={e => setTo(e.target.value)} disabled={done} />
            <button type="button" className={b} disabled={r.busy || done || !to} onClick={() => { void r.act('select_date', { to }); setTo('') }}>Go</button>
          </span>
          <button type="button" className={b} onClick={() => void r.act('jump_to_end')} disabled={r.busy || done}>Jump to end</button>
          <button type="button" className={b} onClick={() => void r.act('reset')} disabled={r.busy}
                  title="Start a clean new replay from the same day; the old one is kept">Reset</button>
        </div>
      </div>
      {r.error && <div className="mx-auto max-w-[1440px] px-6 pb-2 text-xs text-warn-ink" role="alert">{r.error}</div>}
    </div>
  )
}
