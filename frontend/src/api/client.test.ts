import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError, buildUrl, errorMessage } from './client'

afterEach(() => vi.unstubAllGlobals())

/** Replace fetch with a stub that records URLs and answers with `body` / `status`. */
function stubFetch(body: unknown = {}, status = 200) {
  const urls: string[] = []
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    urls.push(url)
    return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
  }))
  return urls
}

describe('buildUrl', () => {
  it('adds cutoff and data_version only when set', () => {
    expect(buildUrl('/api/routes')).toBe('/api/routes')
    expect(buildUrl('/api/routes', {}, { cutoff: null })).toBe('/api/routes')
    expect(buildUrl('/api/routes', {}, { cutoff: '2026-05-31' })).toBe('/api/routes?cutoff=2026-05-31')
    expect(buildUrl('/api/x', { a: 1 }, { cutoff: '2026-05-31', dataVersion: 'v1' })).toBe('/api/x?a=1&cutoff=2026-05-31&data_version=v1')
  })
  it('leaves out null, undefined and empty params, keeps 0 and false', () => {
    expect(buildUrl('/api/x', { a: null, b: undefined, c: '', d: 0, e: false })).toBe('/api/x?d=0&e=false')
  })
})

// every endpoint function, called once without and once with a cutoff
const CALLS: [string, (o?: { cutoff?: string }) => Promise<unknown>][] = [
  ['coverage', o => api.coverage(o)],
  ['routes', o => api.routes({}, o)],
  ['history', o => api.history('22', {}, o)],
  ['rankings', o => api.rankings({ metric: 'rides_per_scheduled_hour', daytype: 'W' }, o)],
  ['overlap', o => api.overlap({}, o)],
  ['compare', o => api.compare(['49', 'X49'], { daytype: 'W' }, o)],
  ['groups', o => api.groups(o)],
  ['trend', o => api.trend({}, o)],
  ['mapLines', o => api.mapLines({}, o)],
  ['models', o => api.models(o)],
]

describe('every endpoint forwards the cutoff (for Stage 7 replay) and only when it is set', () => {
  it.each(CALLS)('%s', async (_name, call) => {
    const urls = stubFetch()
    await call()
    await call({ cutoff: '2026-05-31' })
    expect(urls[0]).not.toContain('cutoff')
    expect(urls[1]).toContain('cutoff=2026-05-31')
    expect(urls.every(u => u.startsWith('/api/'))).toBe(true)   // same origin: Vite proxies it, no CORS
  })
})

describe('endpoint details', () => {
  it('history asks for historical mode; compare and map join routes with commas', async () => {
    const urls = stubFetch()
    await api.history('X49')
    await api.compare(['49', 'X49'], { daytype: 'A', period: 'development' })
    await api.mapLines({ routes: ['22'], simplify_m: 0 })
    expect(urls[0]).toBe('/api/routes/X49/history?mode=historical')
    expect(urls[1]).toBe('/api/routes/compare?routes=49%2CX49&daytype=A&period=development')
    expect(urls[2]).toBe('/api/map/lines?routes=22&simplify_m=0')   // exact lines: 0 is sent, not dropped
  })
})

describe('errors carry the API message', () => {
  it('string detail (e.g. 422 compare)', async () => {
    stubFetch({ detail: 'compare needs 2 to 8 routes, got 1' }, 422)
    await expect(api.compare(['22'], { daytype: 'W' })).rejects.toMatchObject({ status: 422, message: 'compare needs 2 to 8 routes, got 1' })
  })
  it('validation list detail', () => {
    expect(errorMessage({ detail: [{ loc: ['query', 'daytype'], msg: "Input should be 'W', 'A' or 'U'" }] }, 422))
      .toBe("daytype: Input should be 'W', 'A' or 'U'")
  })
  it('a request cancelled while its body is read stays a cancellation, never a "successful" null', async () => {
    const res = new Response('{}', { status: 200 })
    vi.spyOn(res, 'json').mockRejectedValue(new DOMException('aborted', 'AbortError'))
    vi.stubGlobal('fetch', vi.fn(async () => res))
    await expect(api.coverage()).rejects.toMatchObject({ name: 'AbortError' })
  })
  it('a 200 answer that is not JSON, or is empty, is an error, not data', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('<html>', { status: 200 })))
    await expect(api.coverage()).rejects.toBeInstanceOf(ApiError)
    vi.stubGlobal('fetch', vi.fn(async () => new Response('null', { status: 200 })))
    await expect(api.coverage()).rejects.toMatchObject({ message: 'the API answered with no data' })
  })
  it('an error with a plain-text body keeps its status message', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('Bad Gateway', { status: 502 })))
    await expect(api.coverage()).rejects.toMatchObject({ status: 502, message: expect.stringContaining('not reachable') })
  })
  it('API not running', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new TypeError('Failed to fetch') }))
    const e = await api.coverage().catch(x => x)
    expect(e).toBeInstanceOf(ApiError)
    expect(e.message).toContain('not reachable')
  })
})
