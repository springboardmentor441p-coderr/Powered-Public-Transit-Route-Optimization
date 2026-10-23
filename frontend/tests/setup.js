import '@testing-library/jest-dom/vitest'
const real = globalThis.fetch
globalThis.fetch = (u, o) => real(String(u).startsWith('/') ? `http://127.0.0.1:8000${u}` : u, o)
window.matchMedia = window.matchMedia || (() => ({ matches: false, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {} }))
globalThis.ResizeObserver = globalThis.ResizeObserver || class { observe() {} unobserve() {} disconnect() {} }
// jsdom has no SVG geometry support; Leaflet feature-detects createSVGRect to choose its SVG renderer
if (typeof SVGSVGElement !== 'undefined' && !SVGSVGElement.prototype.createSVGRect) SVGSVGElement.prototype.createSVGRect = () => ({})
