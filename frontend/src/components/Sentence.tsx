import { useId, type ReactNode } from 'react'

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
              className={`mx-0.5 cursor-pointer appearance-none border-0 border-b-2 px-1 py-0 font-semibold ${
                warn ? 'border-warn-ink bg-warn-bg text-warn-ink' : 'border-brand bg-transparent text-ink hover:bg-hover'}`}>
        {options.map(o => <option key={o.value} value={o.value}>{o.text}</option>)}
      </select>
    </>
  )
}
