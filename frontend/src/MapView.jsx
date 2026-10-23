import React, { useEffect } from 'react'
import { MapContainer, TileLayer, CircleMarker, Polyline, Tooltip, useMap } from 'react-leaflet'

function Fit({ pts }) {
  const map = useMap()
  const sig = pts.length ? `${pts.length}|${pts[0]}|${pts[pts.length - 1]}` : ''
  useEffect(() => { if (pts.length) map.fitBounds(pts, { padding: [24, 24], maxZoom: 14 }) }, [sig])   // eslint-disable-line
  return null
}

/** stops: [{lat,lon,w,name}] drawn as demand-sized circles; line: [{stop_lat,stop_lon}] drawn as a route. */
export default function MapView({ stops = [], line = [] }) {
  const pts = (line.length ? line.map((p) => [p.stop_lat, p.stop_lon]) : stops.map((s) => [s.lat, s.lon]))
  const maxw = Math.max(...stops.map((s) => s.w || 0), 1)
  if (!pts.length) return <div className="map muted">No coordinates</div>
  return (
    <MapContainer className="map" center={pts[0]} zoom={11} scrollWheelZoom={false}>
      <TileLayer attribution="&copy; OpenStreetMap contributors" url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" />
      <Fit pts={pts} />
      {stops.map((s, i) => (
        <CircleMarker key={i} center={[s.lat, s.lon]} radius={3 + 11 * Math.sqrt((s.w || 0) / maxw)}
          pathOptions={{ color: '#e45756', weight: 0, fillOpacity: 0.35 }}><Tooltip>{s.name}: ~{Math.round(s.w || 0)} boardings/day</Tooltip></CircleMarker>))}
      {line.length > 0 && <>
        <Polyline positions={pts} pathOptions={{ color: '#4c78a8', weight: 4 }} />
        {pts.map((p, i) => <CircleMarker key={i} center={p} radius={4} pathOptions={{ color: '#fff', weight: 1, fillColor: '#e45756', fillOpacity: 1 }} />)}
      </>}
    </MapContainer>
  )
}
