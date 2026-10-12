import { useState, useEffect, useMemo, useCallback } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import * as api from '../api/client'
import type { DocsEntry, DocsResponse } from '../api/types'
import AppShell from '../components/AppShell'
import AddPanel from '../components/AddPanel'
import WorkingStrip from '../components/WorkingStrip'
import LoadingSpinner from '../components/LoadingSpinner'
import ErrorBanner from '../components/ErrorBanner'
import { useAdmin } from '../hooks/useAdmin'
import { docValue } from '../utils/ui'

// ── Types ─────────────────────────────────────────────────────────────────────

type SortKey = 'name' | 'count' | 'date'

// ── Sub-components ────────────────────────────────────────────────────────────

function DocRow({ entry }: { entry: DocsEntry }) {
  const navigate = useNavigate()
  const displayName = entry.source_pdf || entry.doc_key
  const detailPath = `/library/${encodeURIComponent(entry.doc_key)}`

  return (
    <div
      className="bg-white border border-gray-200 rounded-lg p-4 cursor-pointer hover:border-blue-300 hover:shadow-sm transition-all"
      onClick={() => navigate(detailPath)}
    >
      <div className="flex items-center justify-between gap-4">
        <div className="min-w-0">
          <Link
            to={detailPath}
            onClick={e => e.stopPropagation()}
            className="text-sm font-medium text-gray-900 hover:text-blue-700 hover:underline truncate block"
          >
            {displayName}
          </Link>
          <p className="text-xs text-gray-400 mt-1">
            {entry.count.toLocaleString()} requirement{entry.count !== 1 ? 's' : ''}
            {' · '}
            {entry.profile || 'cybersecurity'}
            {' · '}
            {entry.mode}
            {' · '}
            {entry.run_date}
          </p>
        </div>
        <Link
          to={`/search?doc=${encodeURIComponent(docValue(entry))}`}
          onClick={e => e.stopPropagation()}
          className="shrink-0 text-sm text-blue-600 hover:underline whitespace-nowrap"
        >
          Search ↗
        </Link>
      </div>
    </div>
  )
}

// ── Sort button ───────────────────────────────────────────────────────────────

function SortBtn({
  label,
  sortKey,
  active,
  asc,
  onClick,
}: {
  label: string
  sortKey: SortKey
  active: boolean
  asc: boolean
  onClick: (k: SortKey) => void
}) {
  return (
    <button
      onClick={() => onClick(sortKey)}
      className={`px-2 py-1 rounded text-xs ${
        active
          ? 'bg-blue-100 text-blue-700 font-medium'
          : 'text-gray-500 hover:bg-gray-100'
      }`}
    >
      {label}
      {active && (asc ? ' ↑' : ' ↓')}
    </button>
  )
}

// ── Main view ─────────────────────────────────────────────────────────────────

export default function LibraryView() {
  const [data, setData] = useState<DocsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [filter, setFilter] = useState('')
  const [sortKey, setSortKey] = useState<SortKey>('name')
  const [sortAsc, setSortAsc] = useState(true)

  // the "add documents" panel: closed until asked for (or until a link says `?add=1`, as the setup page's "add your first document" does)
  const [params] = useSearchParams()
  const [panelOpen, setPanelOpen] = useState(params.get('add') === '1')
  const [historyAsked, setHistoryAsked] = useState(0)

  const loadDocs = useCallback(() => {
    api
      .docs()
      .then(res => { setData(res); setError(null) })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : 'Failed to load documents')
      })
      .finally(() => { setLoading(false) })
  }, [])

  useEffect(() => { loadDocs() }, [loadDocs])

  // asks the server how adding is protected and keeps the job list fresh; reloads the list when a job finishes
  const admin = useAdmin(loadDocs)

  const filtered = useMemo<DocsEntry[]>(() => {
    if (!data) return []
    const q = filter.trim().toLowerCase()
    if (!q) return data.docs
    return data.docs.filter(d => {
      const haystack = `${d.source_pdf} ${d.doc_key}`.toLowerCase()
      return haystack.includes(q)
    })
  }, [data, filter])

  const sorted = useMemo<DocsEntry[]>(() => {
    const mult = sortAsc ? 1 : -1
    return [...filtered].sort((a, b) => {
      if (sortKey === 'count') return mult * (a.count - b.count)
      if (sortKey === 'date') return mult * a.run_date.localeCompare(b.run_date)
      return mult * (a.source_pdf || a.doc_key).localeCompare(b.source_pdf || b.doc_key)
    })
  }, [filtered, sortKey, sortAsc])

  function handleSort(key: SortKey) {
    if (key === sortKey) {
      setSortAsc(prev => !prev)
    } else {
      setSortKey(key)
      setSortAsc(true)
    }
  }

  return (
    <AppShell>
      {/* while something is being read, rebuilt or written: what it is and how far along (nothing when idle) */}
      <WorkingStrip data={admin.enabled ? admin.jobs.data : null} onHistory={() => { setPanelOpen(true); setHistoryAsked(n => n + 1) }} />

      <div className="flex flex-col lg:flex-row lg:items-start">
        <main className="flex-1 min-w-0 w-full max-w-4xl mx-auto px-6 py-8">
          <div className="flex flex-wrap items-end justify-between gap-4 mb-6">
            <div>
              <h1 className="text-xl font-bold text-gray-900">Library</h1>
              {!loading && !error && data && (
                <p className="text-sm text-gray-500 mt-1">
                  {data.total_docs} document{data.total_docs !== 1 ? 's' : ''}
                  {' · '}
                  {data.total_reqs.toLocaleString()} requirement{data.total_reqs !== 1 ? 's' : ''}
                </p>
              )}
            </div>
            <button
              onClick={() => setPanelOpen(open => !open)}
              aria-expanded={panelOpen}
              aria-controls="add-documents-panel"
              className="bg-blue-600 text-white text-sm font-semibold rounded px-4 py-2 hover:bg-blue-700"
            >
              Add documents
            </button>
          </div>

          {/* Loading */}
          {loading && <LoadingSpinner />}

          {/* Error */}
          {!loading && error && <ErrorBanner message={error} />}

          {/* Results */}
          {!loading && !error && data && (
            <>
              {/* Filter + sort */}
              <div className="flex items-center gap-3 mb-3">
                <input
                  type="text"
                  value={filter}
                  onChange={e => setFilter(e.target.value)}
                  placeholder="Filter by name…"
                  aria-label="Filter by name"
                  className="flex-1 min-w-0 border border-gray-300 rounded px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <div className="flex items-center gap-1 shrink-0">
                  <span className="text-xs text-gray-400 mr-1">Sort:</span>
                  <SortBtn label="Name" sortKey="name" active={sortKey === 'name'} asc={sortAsc} onClick={handleSort} />
                  <SortBtn label="Count" sortKey="count" active={sortKey === 'count'} asc={sortAsc} onClick={handleSort} />
                  <SortBtn label="Date" sortKey="date" active={sortKey === 'date'} asc={sortAsc} onClick={handleSort} />
                </div>
              </div>

              {/* Row count */}
              <p className="text-xs text-gray-400 mb-3">
                {sorted.length} of {data.total_docs} document{data.total_docs !== 1 ? 's' : ''}
                {filter.trim() ? ` matching "${filter.trim()}"` : ''}
              </p>

              {/* Document list */}
              {sorted.length === 0 && data.total_docs > 0 ? (
                <p className="text-sm text-gray-500">
                  No documents match &ldquo;{filter}&rdquo;.
                </p>
              ) : (
                <div className="space-y-2">
                  {sorted.map(entry => (
                    <DocRow key={entry.doc_key} entry={entry} />
                  ))}
                </div>
              )}
            </>
          )}

          {/* Empty library */}
          {!loading && !error && data && data.total_docs === 0 && (
            <p className="text-sm text-gray-500">
              Nothing is in the library yet. Choose <strong className="font-medium text-gray-700">Add documents</strong>, or ingest a PDF with the command line.
            </p>
          )}
        </main>

        {panelOpen && <AddPanel admin={admin} onClose={() => setPanelOpen(false)} historyAsked={historyAsked} />}
      </div>
    </AppShell>
  )
}
