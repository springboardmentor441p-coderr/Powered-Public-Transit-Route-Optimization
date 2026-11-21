import { Link, Route, Routes } from 'react-router-dom'
import { api } from './api/client'
import { useApi } from './api/useApi'
import { AsyncBlock } from './components/AsyncBlock'
import { ProvenanceProvider } from './components/Provenance'
import { SourcesPanel } from './components/SourcesPanel'
import { Empty } from './components/States'
import { TopBar } from './components/TopBar'
import { StylePage } from './screens/StylePage'

function NotBuilt() {
  return (
    <div>
      <Empty message="This screen is not built yet." />
      <Link to="/style" className="text-sm">Open the style reference</Link>
    </div>
  )
}

export default function App() {
  // The data status in the top bar comes from the API, once per page load (and again if the cutoff changes).
  const coverage = useApi(o => api.coverage(o), 'coverage')
  const dataThrough = coverage.status === 'ok' ? coverage.data.cutoff.permitted_through
    : coverage.status === 'loading' ? '…' : <span className="text-xs font-normal">unavailable – API not reachable</span>
  return (
    <ProvenanceProvider>
      <Routes>
        <Route element={
          <TopBar modeLabel={coverage.status === 'ok' ? coverage.data.mode_label : 'Historical analysis'}
                  dataThrough={dataThrough}
                  sources={<AsyncBlock state={coverage} retry={coverage.retry} label="Loading sources">{c => <SourcesPanel c={c} />}</AsyncBlock>} />
        }>
          <Route path="/style" element={<StylePage />} />
          <Route path="*" element={<NotBuilt />} />
        </Route>
      </Routes>
    </ProvenanceProvider>
  )
}
