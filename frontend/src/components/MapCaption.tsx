/** Fixed caption under every map: geometry version · applied dates · path label · display note.
 *  Every text comes from the API response as sent. */
export function MapCaption({ geometryVersion, appliedStart, appliedEnd, pathLabel, displayNote }: {
  geometryVersion: string; appliedStart: string; appliedEnd: string; pathLabel: string; displayNote?: string
}) {
  return (
    <p className="border-t border-rule px-4 py-2 text-xs text-ink-2">
      <span className="font-semibold text-ink">Geometry version {geometryVersion}</span>
      <span aria-hidden> · </span>applied {appliedStart} to {appliedEnd}
      <span aria-hidden> · </span>{pathLabel}
      {displayNote && <><span aria-hidden> · </span>{displayNote}</>}
    </p>
  )
}
