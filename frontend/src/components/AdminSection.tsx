import { useCallback, useEffect, useRef, useState } from 'react'
import { getAccess, getAdminToken } from '../api/admin'
import type { AdminMode } from '../api/admin'
import { useJobs } from '../hooks/useJobs'
import AddDocuments from './AddDocuments'
import JobsPanel from './JobsPanel'

/**
 * The admin part of the Corpus page: add documents, and see the jobs they start (docs/WEB_UI_PARITY_PLAN.md, section 8).
 * It asks the server which way admin actions are protected, and shows nothing at all until that is known. `onLibraryChanged`
 * is called when a job finishes, so the document list can reload.
 */
export default function AdminSection({ onLibraryChanged }: { onLibraryChanged: () => void }) {
  const [mode, setMode] = useState<AdminMode | null>(null)
  const [, setCodeVersion] = useState(0)
  const hasCode = getAdminToken() !== ''
  const enabled = mode === 'open' || (mode === 'code' && hasCode)
  const jobs = useJobs(enabled)

  useEffect(() => {
    let alive = true
    getAccess()
      .then(m => { if (alive) setMode(m) })
      .catch(() => { if (alive) setMode(null) })
    return () => { alive = false }
  }, [])

  // reload the document list when the job that was running is done
  const lastRunning = useRef<string | null>(null)
  useEffect(() => {
    const now = jobs.data?.running ?? null
    if (lastRunning.current && now !== lastRunning.current) {
      const finished = jobs.data?.jobs.find(j => j.id === lastRunning.current)
      if (!finished || finished.state === 'succeeded') onLibraryChanged()
    }
    lastRunning.current = now
  }, [jobs.data, onLibraryChanged])

  const codeChanged = useCallback(() => setCodeVersion(v => v + 1), [])
  const afterStart = useCallback(() => { jobs.refresh() }, [jobs])

  if (mode === null) return null
  return (
    <>
      <AddDocuments mode={mode} onStarted={afterStart} onCodeChanged={codeChanged} codeRejected={mode === 'code' && jobs.authNeeded && hasCode} />
      {enabled && <JobsPanel data={jobs.data} onChanged={jobs.refresh} />}
      {enabled && jobs.error && <p className="text-xs text-red-700 mb-4">{jobs.error}</p>}
    </>
  )
}
