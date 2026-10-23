const BASE = (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_BASE) || ''

const qs = (p) => {
  const u = new URLSearchParams()
  Object.entries(p || {}).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== '') u.set(k, v) })
  return u.toString()
}
async function handle(r) {
  if (!r.ok) {
    let msg = r.statusText
    try { const j = await r.json(); msg = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail) } catch { /* ignore */ }
    throw new Error(msg)
  }
  return r.json()
}
export const get = (path, params, signal) => fetch(`${BASE}/api${path}?${qs(params)}`, { signal }).then(handle)
export const post = (path, body) => fetch(`${BASE}/api${path}`, {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }).then(handle)
export const upload = (path, form) => fetch(`${BASE}/api${path}`, { method: 'POST', body: form }).then(handle)
export const url = (path, params) => `${BASE}/api${path}?${qs(params)}`
