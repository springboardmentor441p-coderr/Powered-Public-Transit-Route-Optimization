import { describe, expect, it, vi } from 'vitest'
import { settle, type ApiState } from './useApi'

describe('settle: only the current request may change the screen', () => {
  it('a live request sets ok with its data', async () => {
    const set = vi.fn<(s: ApiState<number>) => void>()
    await settle(Promise.resolve(7), new AbortController().signal, set)
    expect(set).toHaveBeenCalledWith({ status: 'ok', data: 7 })
  })
  it('a late answer after cleanup is dropped (success or failure)', async () => {
    const ctrl = new AbortController()
    const set = vi.fn()
    let resolve!: (v: unknown) => void
    const p = new Promise(r => { resolve = r })
    const done = settle(p, ctrl.signal, set)
    ctrl.abort()                       // the effect was cleaned up: the screen moved on
    resolve(null)                      // ...and only then the old answer arrives
    await done
    await settle(Promise.reject(new Error('boom')), ctrl.signal, set)
    expect(set).not.toHaveBeenCalled()
  })
  it('a real failure of a live request becomes an error; a cancellation does not', async () => {
    const set = vi.fn()
    await settle(Promise.reject(new Error('the API is not reachable')), new AbortController().signal, set)
    expect(set).toHaveBeenCalledWith({ status: 'error', message: 'the API is not reachable' })
    set.mockClear()
    await settle(Promise.reject(new DOMException('aborted', 'AbortError')), new AbortController().signal, set)
    expect(set).not.toHaveBeenCalled()
  })
})
