import { spawn } from 'node:child_process'
import { setTimeout as delay } from 'node:timers/promises'
import { access, mkdtemp, readFile, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const projectRoot = resolve(frontendRoot, '..')
const apiBase = process.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api/v1'
const apiOrigin = apiBase.replace(/\/api\/v1\/?$/, '')
const appUrl = 'http://127.0.0.1:5173'
const failureAppUrl = 'http://127.0.0.1:5174'
const chromeCandidates = [
  process.env.CHROME_PATH,
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
].filter(Boolean)
let chromePath
for (const candidate of chromeCandidates) {
  try { await access(candidate); chromePath = candidate; break } catch { /* Try next installed browser. */ }
}

if (!chromePath) throw new Error('Set CHROME_PATH to Chrome or Edge to run the E2E smoke tests.')
await fetch(`${apiOrigin}/health`).then((response) => {
  if (!response.ok) throw new Error(`API health request failed with ${response.status}`)
}).catch((error) => { throw new Error(`Start the FastAPI service at ${apiOrigin} first: ${error.message}`) })

const profileDir = await mkdtemp(join(tmpdir(), 'routeranker-e2e-'))
const vite = spawn(process.execPath, [join(frontendRoot, 'node_modules/vite/bin/vite.js'), '--host', '127.0.0.1', '--port', '5173', '--strictPort'], {
  cwd: frontendRoot,
  env: { ...process.env, VITE_API_BASE_URL: apiBase },
  stdio: 'ignore',
})
const chrome = spawn(chromePath, [
  '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
  '--disable-background-networking', '--no-sandbox', '--remote-debugging-port=0',
  `--user-data-dir=${profileDir}`, 'about:blank',
], { stdio: 'ignore' })

class DevTools {
  constructor(socket) {
    this.socket = socket
    this.nextId = 0
    this.pending = new Map()
    this.exceptions = []
    socket.addEventListener('message', (event) => {
      const message = JSON.parse(event.data)
      if (message.method === 'Runtime.exceptionThrown') this.exceptions.push(message.params.exceptionDetails.text)
      if (message.id && this.pending.has(message.id)) {
        const { resolve: resolveCall, reject } = this.pending.get(message.id)
        this.pending.delete(message.id)
        if (message.error) reject(new Error(message.error.message))
        else resolveCall(message.result)
      }
    })
  }

  send(method, params = {}) {
    const id = ++this.nextId
    return new Promise((resolveCall, reject) => {
      this.pending.set(id, { resolve: resolveCall, reject })
      this.socket.send(JSON.stringify({ id, method, params }))
      setTimeout(() => {
        if (this.pending.has(id)) {
          this.pending.delete(id)
          reject(new Error(`Timed out waiting for Chrome command ${method}`))
        }
      }, 10_000).unref()
    })
  }

  async evaluate(expression) {
    const response = await this.send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true, userGesture: true })
    if (response.exceptionDetails) throw new Error(response.exceptionDetails.text)
    return response.result?.value
  }

  async waitFor(expression, label, timeout = 25_000) {
    const start = Date.now()
    while (Date.now() - start < timeout) {
      if (chrome.exitCode !== null) throw new Error('Chrome exited while waiting for page content.')
      const result = await this.evaluate(expression)
      if (result) return result
      await delay(200)
    }
    const body = await this.evaluate("document.body?.innerText.slice(0, 500)")
    throw new Error(`Timed out waiting for ${label}; page text: ${body}`)
  }

  async click(selector, label = selector) {
    const clicked = await this.evaluate(`(() => { const node = document.querySelector(${JSON.stringify(selector)}); if (!node) return false; node.click(); return true; })()`)
    if (!clicked) throw new Error(`Could not find clickable control: ${label}`)
  }

  async clickText(selector, text, label = text) {
    const clicked = await this.evaluate(`(() => { const node = [...document.querySelectorAll(${JSON.stringify(selector)})].find((item) => item.textContent.trim().includes(${JSON.stringify(text)})); if (!node) return false; node.click(); return true; })()`)
    if (!clicked) throw new Error(`Could not find clickable control: ${label}`)
  }

  async setInput(selector, value) {
    const found = await this.evaluate(`(() => { const node = document.querySelector(${JSON.stringify(selector)}); if (!node) return false; node.focus(); const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; setter.call(node, ${JSON.stringify(value)}); node.dispatchEvent(new Event('input', { bubbles: true })); node.dispatchEvent(new Event('change', { bubbles: true })); return true; })()`)
    if (!found) throw new Error(`Could not find input: ${selector}`)
  }
}

let devtools
let failureVite
let passed = 0
function pass(name) { passed += 1; process.stdout.write(`PASS ${name}\n`) }

try {
  await waitForServer(appUrl, vite)
  const portFile = join(profileDir, 'DevToolsActivePort')
  let portInfo = ''
  for (let attempt = 0; attempt < 100; attempt += 1) {
    try { portInfo = await readFile(portFile, 'utf8'); break } catch { await delay(100) }
  }
  if (!portInfo) throw new Error('Chrome did not expose a DevTools port.')
  const debugPort = portInfo.split(/\r?\n/)[0]
  const targetResponse = await fetch(`http://127.0.0.1:${debugPort}/json/new?about:blank`, { method: 'PUT' })
  if (!targetResponse.ok) throw new Error(`Chrome target creation failed: ${targetResponse.status}`)
  const target = await targetResponse.json()
  const socket = new WebSocket(target.webSocketDebuggerUrl)
  await new Promise((resolveCall, reject) => {
    socket.addEventListener('open', resolveCall, { once: true })
    socket.addEventListener('error', reject, { once: true })
  })
  devtools = new DevTools(socket)
  await devtools.send('Page.enable')
  await devtools.send('Runtime.enable')
  await devtools.send('Network.enable')
  await devtools.send('Page.navigate', { url: appUrl })

  await devtools.waitFor("document.querySelector('h1')?.textContent.includes('Good morning, Chennai')", 'overview dashboard')
  await devtools.waitFor("document.body.innerText.includes('Scheduled trip records')", 'overview metrics')
  pass('overview loads real API summaries')

  await devtools.click('a[href="/routes"]')
  await devtools.waitFor("document.querySelector('h1')?.textContent.includes('Route explorer')", 'route explorer')
  await devtools.waitFor("document.querySelectorAll('tbody tr').length > 0", 'route results')
  await devtools.setInput('input[placeholder="Search route ID or name"]', '29A')
  await devtools.waitFor("document.querySelectorAll('tbody tr').length > 0 && [...document.querySelectorAll('tbody tr')].some((row) => row.innerText.includes('29A'))", 'filtered route results')
  await devtools.clickText('tbody button', 'Details')
  await devtools.waitFor("document.body.innerText.includes('Saved cluster assignments')", 'route profile and clusters')
  await devtools.click('button[aria-label="Close route details"]')
  pass('route search, filtering, and details work')

  await devtools.setInput('input[placeholder="Search route ID or name"]', 'routeranker-no-such-route')
  await devtools.waitFor("document.body.innerText.includes('No routes match these filters')", 'empty route search state')
  pass('empty route search state renders')
  await devtools.clickText('button', 'Clear filters')
  await devtools.waitFor("document.querySelectorAll('tbody tr').length >= 2", 'multiple routes')
  await devtools.evaluate("[...document.querySelectorAll('input[aria-label^=\"Select route\"]')].slice(0,2).forEach((node) => node.click())")
  await devtools.clickText('button', 'Compare selected')
  await devtools.waitFor("document.querySelector('h1')?.textContent.includes('Route comparison')", 'comparison page')
  await devtools.clickText('button', 'Compare routes')
  await devtools.waitFor("document.body.innerText.includes('Comparison details')", 'route comparison results')
  pass('route selection and side-by-side comparison work')

  await devtools.click('a[href="/stops"]')
  await devtools.waitFor("document.querySelector('h1')?.textContent.includes('Stop explorer')", 'stop explorer')
  await devtools.waitFor("document.querySelectorAll('main button').length > 0", 'stop results')
  await devtools.click('main button')
  await devtools.waitFor("document.body.innerText.includes('Routes serving this stop')", 'stop route membership')
  pass('stop search and serving routes work')

  await devtools.click('a[href="/insights"]')
  await devtools.waitFor("document.querySelector('h1')?.textContent.includes('Machine learning insights')", 'ML insights')
  await devtools.waitFor("document.body.innerText.includes('Cluster profiles') && document.querySelectorAll('tbody tr').length > 0", 'cluster profiles')
  pass('K-Means and DBSCAN profiles and scores render')

  await devtools.click('a[href="/map"]')
  await devtools.waitFor("document.querySelector('h1')?.textContent.includes('Transit network map')", 'network map')
  await devtools.waitFor("document.querySelector('.leaflet-overlay-pane canvas') && document.body.innerText.match(/[0-9,]+ plotted stops with valid coordinates/)", 'GTFS coordinate canvas and stop count', 45_000)
  if (!(await devtools.evaluate("document.body.innerText.includes('shapes.txt')"))) throw new Error('Map geometry limitation is not disclosed.')
  pass('network map plots actual stop points and explains missing shapes')

  failureVite = spawn(process.execPath, [join(frontendRoot, 'node_modules/vite/bin/vite.js'), '--host', '127.0.0.1', '--port', '5174', '--strictPort'], {
    cwd: frontendRoot,
    env: { ...process.env, VITE_API_BASE_URL: 'http://127.0.0.1:65530/api/v1' },
    stdio: 'ignore',
  })
  await waitForServer(failureAppUrl, failureVite)
  await devtools.send('Page.navigate', { url: failureAppUrl })
  await devtools.waitFor("document.body.innerText.includes('API unavailable')", 'backend connection error state')
  await devtools.waitFor("document.body.innerText.includes('Data could not be loaded')", 'API request error state')
  pass('backend connection failure is shown to users')

  if (devtools.exceptions.length) throw new Error(`Browser runtime exceptions: ${devtools.exceptions.join('; ')}`)
  process.stdout.write(`\n${passed} E2E workflows passed.\n`)
} finally {
  devtools?.socket.close()
  failureVite?.kill()
  chrome.kill()
  vite.kill()
  await new Promise((resolveCall) => setTimeout(resolveCall, 300))
  const absoluteProfile = resolve(profileDir)
  const absoluteTemp = resolve(tmpdir())
  if (!absoluteProfile.startsWith(`${absoluteTemp}\\`) || !absoluteProfile.includes('routeranker-e2e-')) {
    throw new Error('Refusing to remove an unexpected Chrome profile path.')
  }
  await rm(absoluteProfile, { recursive: true, force: true })
}

async function waitForServer(url, processHandle) {
  for (let attempt = 0; attempt < 100; attempt += 1) {
    if (processHandle.exitCode !== null) throw new Error(`Vite exited with code ${processHandle.exitCode}`)
    try {
      const response = await fetch(url)
      if (response.ok) return
    } catch { /* Vite is still starting. */ }
    await delay(200)
  }
  throw new Error(`Vite did not start at ${url}`)
}
