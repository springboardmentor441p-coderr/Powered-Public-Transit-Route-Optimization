import type { ReactNode } from 'react'
import type { ApiState } from '../api/useApi'
import { Empty, ErrorState, Loading } from './States'

/** Every data block goes through this: loading -> skeleton, error -> message + Retry, empty -> a plain sentence,
 *  otherwise the content. `isEmpty` decides what "nothing to show" means for this block. */
export function AsyncBlock<T>({ state, retry, isEmpty, emptyMessage = 'Nothing to show for these choices.', label, children }: {
  state: ApiState<T>; retry: () => void; isEmpty?: (d: T) => boolean; emptyMessage?: string | ((d: T) => string)
  label?: string; children: (data: T) => ReactNode
}) {
  if (state.status === 'loading') return <Loading label={label} />
  if (state.status === 'error') return <ErrorState message={state.message} onRetry={retry} />
  if (isEmpty?.(state.data)) {
    return <Empty message={typeof emptyMessage === 'function' ? emptyMessage(state.data) : emptyMessage} />
  }
  return <>{children(state.data)}</>
}
