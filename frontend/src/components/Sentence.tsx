import { useId, useState, type ReactNode } from 'react'
import { fieldWidth } from '../lib/format'

/** Sentence controls: a page states its view as a readable sentence whose choices are inline dropdowns.
 *  The sentence doubles as the summary, so a screenshot says exactly what the page shows. */
export function Sentence({ children }: { children: ReactNode }) {
  return <p className="mb-5 text-md leading-9 text-ink">{children}</p>
}

export function Choice<T extends string>({ label, value, options, onChange, warn = false }: {
  label: string; value: T; options: { value: T; text: string }[]; onChange: (v: T) => void; warn?: boolean
}) {
  // A real <label for> (visually hidden: the sentence itself is the visible label) plus an id and a name.
  // Chrome's Issues panel flags a form field without an id/name and a field without an associated label.
  const id = useId()
  const name = label.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '')
  return (
    <>
      <label htmlFor={id} className="sr-only">{label}</label>
      <select id={id} name={name} value={value} onChange={e => onChange(e.target.value as T)}
              className={`ml-1 mr-0 cursor-pointer appearance-none border-0 border-b-2 px-0.5 py-0 font-semibold [field-sizing:content] ${
                warn ? 'border-warn-ink bg-warn-bg text-warn-ink' : 'border-brand bg-transparent text-ink hover:bg-hover'}`}>
        {options.map(o => <option key={o.value} value={o.value}>{o.text}</option>)}
      </select>
    </>
  )
}

/** A whole-number choice inside a sentence: type any value, or pick a common one from the list (a <datalist>).
 *  `parse` returns null for a value that is not allowed; the field then keeps what was typed, says why, and the
 *  page keeps the last valid value. */
export function NumberChoice({ label, value, suggestions, parse, invalidText, onChange, warn = false }: {
  label: string; value: number; suggestions: { value: number; text: string }[]
  parse: (text: string) => number | null; invalidText: string; onChange: (v: number) => void; warn?: boolean
}) {
  const id = useId(), listId = useId()
  const name = label.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '')
  // The field keeps what was typed; when the page's value changes from outside (e.g. "Back to the reference
  // gate"), the text follows it. Adjusted during render, not in an effect (React's "storing previous props").
  const [text, setText] = useState(String(value))
  const [seen, setSeen] = useState(value)
  if (value !== seen) { setSeen(value); setText(String(value)) }
  const invalid = parse(text) == null
  return (
    <>
      <label htmlFor={id} className="sr-only">{label}</label>
      <input id={id} name={name} type="number" min={1} step={1} inputMode="numeric" list={listId} value={text}
             aria-invalid={invalid} aria-describedby={invalid ? `${id}-err` : undefined}
             onChange={e => { setText(e.target.value); const n = parse(e.target.value); if (n != null) onChange(n) }}
             style={{ width: fieldWidth(text) }}
             className={`mx-0.5 border-0 border-b-2 px-1 py-0 text-center font-semibold num [appearance:textfield]
                         [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none ${
               invalid ? 'border-warn-ink bg-warn-bg text-warn-ink'
               : warn ? 'border-warn-ink bg-warn-bg text-warn-ink' : 'border-brand bg-transparent text-ink hover:bg-hover'}`} />
      <datalist id={listId}>{suggestions.map(s => <option key={s.value} value={s.value}>{s.text}</option>)}</datalist>
      {invalid && <span id={`${id}-err`} role="alert" className="ml-1 text-xs text-warn-ink">{invalidText}</span>}
    </>
  )
}
