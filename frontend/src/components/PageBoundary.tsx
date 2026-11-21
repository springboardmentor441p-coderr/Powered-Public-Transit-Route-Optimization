import { Component, type ReactNode } from 'react'
import { ErrorState } from './States'

/** If a screen fails while rendering, show what went wrong and a Reload button instead of a blank page. The top
 *  bar stays usable, and the boundary is keyed by the page address (in TopBar), so moving to another screen
 *  starts clean. */
export class PageBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state: { error: Error | null } = { error: null }

  static getDerivedStateFromError(error: Error) {
    return { error }
  }

  render() {
    if (this.state.error) {
      return <ErrorState message={`This screen stopped: ${this.state.error.message}`} onRetry={() => window.location.reload()} />
    }
    return this.props.children
  }
}
