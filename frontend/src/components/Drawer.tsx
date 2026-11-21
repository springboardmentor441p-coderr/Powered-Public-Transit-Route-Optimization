import { useEffect, useRef, type ReactNode } from 'react'

/** Right-side panel that slides over the page edge. Esc or the Close button closes it; focus moves to its
 *  heading when it opens, so keyboard users land in it. `inline` renders the same panel in the page flow
 *  (used on /style to show one open). */
export function Drawer({ title, eyebrow, onClose, inline = false, children }: {
  title: string; eyebrow?: string; onClose?: () => void; inline?: boolean; children: ReactNode
}) {
  const heading = useRef<HTMLHeadingElement>(null)
  const close = useRef(onClose)
  useEffect(() => { close.current = onClose })
  useEffect(() => {  // runs once per opening: focus the heading, listen for Esc
    if (inline) return
    heading.current?.focus()
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') close.current?.() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [inline])

  const box = inline
    ? 'border border-rule bg-panel'
    : 'fixed inset-y-0 right-0 z-[1200] w-[min(400px,100vw)] overflow-y-auto border-l border-rule-strong bg-panel'
  return (
    <aside role={inline ? undefined : 'dialog'} aria-labelledby="drawer-title" className={box}>
      <div className="flex items-start justify-between gap-3 border-b border-rule px-5 py-3">
        <div>
          {eyebrow && <div className="eyebrow">{eyebrow}</div>}
          <h2 id={inline ? undefined : 'drawer-title'} ref={heading} tabIndex={-1} className="text-md font-semibold">{title}</h2>
        </div>
        {onClose && <button type="button" className="btn-secondary h-7" onClick={onClose}>Close</button>}
      </div>
      <div className="px-5 py-4">{children}</div>
    </aside>
  )
}
