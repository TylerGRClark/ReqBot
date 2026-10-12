import { BrowserRouter, Routes, Route, Navigate, useParams } from 'react-router-dom'
import SearchView from './views/SearchView'
import TraceView from './views/TraceView'
import CompareView from './views/CompareView'
import EvidenceView from './views/EvidenceView'
import LibraryView from './views/LibraryView'
import LibraryDetailView from './views/LibraryDetailView'
import SystemView from './views/SystemView'
import SettingsView from './views/SettingsView'
import SetupView from './views/SetupView'
import ChecklistsView from './views/ChecklistsView'
import ChecklistPreviewView from './views/ChecklistPreviewView'
import NotFoundView from './views/NotFoundView'

/** The old `/corpus/<document>` address (bookmarks, links in saved notes) goes to the document's page in the Library. */
function CorpusDocRedirect() {
  const { docId = '' } = useParams<{ docId: string }>()
  return <Navigate to={`/library/${encodeURIComponent(docId)}`} replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/search" replace />} />
        <Route path="/search" element={<SearchView />} />
        <Route path="/compare" element={<CompareView />} />
        <Route path="/evidence" element={<EvidenceView />} />
        <Route path="/library" element={<LibraryView />} />
        <Route path="/library/:docId" element={<LibraryDetailView />} />
        {/* The Library used to be called the Corpus: keep those addresses working */}
        <Route path="/corpus" element={<Navigate to="/library" replace />} />
        <Route path="/corpus/:docId" element={<CorpusDocRedirect />} />
        <Route path="/system" element={<SystemView />} />
        <Route path="/settings" element={<SettingsView />} />
        <Route path="/setup" element={<SetupView />} />
        <Route path="/checklists" element={<ChecklistsView />} />
        <Route path="/checklists/:docId" element={<ChecklistPreviewView />} />
        {/* Redirect legacy /docs bookmarks to /library */}
        <Route path="/docs" element={<Navigate to="/library" replace />} />
        <Route path="/trace/:reqId" element={<TraceView />} />
        <Route path="*" element={<NotFoundView />} />
      </Routes>
    </BrowserRouter>
  )
}
