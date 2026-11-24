import { Link, Route, Routes } from 'react-router-dom'
import { api } from './api/client'
import { useApi } from './api/useApi'
import { AsyncBlock } from './components/AsyncBlock'
import { ProvenanceProvider } from './components/Provenance'
import { SourcesPanel } from './components/SourcesPanel'
import { Empty } from './components/States'
import { TopBar } from './components/TopBar'
import { AlikePage } from './screens/AlikePage'
import { CloserLookPage } from './screens/CloserLookPage'
import { ComparePage } from './screens/ComparePage'
import { DataPage } from './screens/DataPage'
import { ReplayPage } from './screens/ReplayPage'
import { OneRoutePage } from './screens/OneRoutePage'
import { SharedStopsPage } from './screens/SharedStopsPage'
import { StartPage } from './screens/StartPage'
import { StylePage } from './screens/StylePage'
import { fmtDate } from './lib/dates'

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
  const through = coverage.status === 'ok' ? coverage.data.cutoff.permitted_through : null
  const dataThrough = coverage.status === 'ok' ? (through ? fmtDate(through) : <span className="text-xs font-normal">unavailable – no cutoff reported</span>)
    : coverage.status === 'loading' ? '…' : <span className="text-xs font-normal">unavailable – API not reachable</span>
  return (
    <ProvenanceProvider>
      <Routes>
        <Route element={
          <TopBar modeLabel={coverage.status === 'ok' ? coverage.data.mode_label : 'Historical analysis'}
                  dataThrough={dataThrough}
                  sources={<AsyncBlock state={coverage} retry={coverage.retry} label="Loading sources">{c => <SourcesPanel c={c} />}</AsyncBlock>} />
        }>
          <Route path="/" element={<StartPage />} />
          <Route path="/closer-look" element={<CloserLookPage />} />
          <Route path="/route" element={<OneRoutePage />} />
          <Route path="/route/:route" element={<OneRoutePage />} />
          <Route path="/alike" element={<AlikePage />} />
          <Route path="/shared-stops" element={<SharedStopsPage />} />
          <Route path="/compare" element={<ComparePage />} />
          <Route path="/replay" element={<ReplayPage />} />
          <Route path="/data" element={<DataPage />} />
          <Route path="/style" element={<StylePage />} />
          <Route path="*" element={<NotBuilt />} />
        </Route>
      </Routes>
    </ProvenanceProvider>
  )
}
