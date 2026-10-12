import { useCallback, useEffect, useRef, useState } from 'react'
import { getAccess, getAdminToken } from '../api/admin'
import type { AdminMode } from '../api/admin'
import { useJobs } from './useJobs'

/**
 * What the Library page needs to know about adding documents (docs/WEB_UI_PARITY_PLAN.md, section 8): which way admin actions are protected on this server
 * (`mode`, null until the server has answered), whether this browser may use them (`enabled`), and the job list while it may.
 * `onLibraryChanged` is called when the job that was running has finished, so the document list can reload.
 */
export function useAdmin(onLibraryChanged: () => void) {
  const [mode, setMode] = useState<AdminMode | null>(null)
  const [asked, setAsked] = useState(false)
  const [, setCodeVersion] = useState(0)
  const hasCode = getAdminToken() !== ''
  const enabled = mode === 'open' || (mode === 'code' && hasCode)
  const jobs = useJobs(enabled)

  useEffect(() => {
    let alive = true
    getAccess()
      .then(m => { if (alive) setMode(m) })
      .catch(() => { if (alive) setMode(null) })
      .finally(() => { if (alive) setAsked(true) })
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

  const refreshJobs = jobs.refresh
  const codeChanged = useCallback(() => {
    setCodeVersion(v => v + 1)
    refreshJobs() // ask again at once with the new code, rather than at the next poll
  }, [refreshJobs])
  const afterStart = useCallback(() => { refreshJobs() }, [refreshJobs])

  return {
    mode,
    /** The server has been asked (it may have failed to answer: `mode` is then still null). */
    asked,
    enabled,
    jobs,
    codeChanged,
    afterStart,
    /** The server turned down the code this browser saved. */
    codeRejected: mode === 'code' && jobs.authNeeded && hasCode,
  }
}

export type AdminState = ReturnType<typeof useAdmin>
