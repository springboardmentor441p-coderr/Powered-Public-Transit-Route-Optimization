import { groupColour } from '../design/tokens'

type Size = 'sm' | 'md' | 'lg'
const SIZES: Record<Size, string> = {
  sm: 'h-5 min-w-8 pl-[7px] pr-1.5 text-xs',
  md: 'h-6 min-w-10 pl-2 pr-2 text-sm',
  lg: 'h-9 min-w-14 pl-3 pr-3 text-lg',
}

/** A route number drawn as a small bus-stop sign plate: white, ink border, bold number,
 *  with a stripe in the route's group colour down the left edge (grey when ungrouped). */
export function RouteSign({ route, groupId, groupName, size = 'md' }: {
  route: string; groupId?: number | null; groupName?: string | null; size?: Size
}) {
  const label = `Route ${route}${groupName ? `, ${groupName}` : groupId == null ? ', ungrouped' : ''}`
  return (
    <span
      aria-label={label}
      title={label}
      className={`relative inline-flex shrink-0 items-center justify-center overflow-hidden rounded-[3px]
                  border-[1.5px] border-ink bg-panel font-bold tracking-tight text-ink num ${SIZES[size]}`}
    >
      <span aria-hidden className="absolute inset-y-0 left-0 w-1" style={{ background: groupColour(groupId) }} />
      {route}
    </span>
  )
}
