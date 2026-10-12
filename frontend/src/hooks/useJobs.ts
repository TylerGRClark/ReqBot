import { useCallback, useEffect, useRef, useState } from 'react'
import { AdminAuthError, AdminDisabledError, listJobs } from '../api/admin'
import type { JobsResponse } from '../api/admin'

const FAST_MS = 3000
const SLOW_MS = 15000

/**
 * The job list, kept fresh while the page is open: every few seconds while something is queued or running, slowly otherwise.
 * `enabled` is false until the person is allowed to see jobs (a code is set or not needed), so nothing is requested before then.
 * `refresh()` asks now (after starting or cancelling something). A failed request keeps the last list and reports the error.
 */
export function useJobs(enabled: boolean) {
  const [data, setData] = useState<JobsResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [authNeeded, setAuthNeeded] = useState(false)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const alive = useRef(true)

  const load = useCallback(async () => {
    try {
      const res = await listJobs()
      if (!alive.current) return null
      setData(res)
      setError(null)
      setAuthNeeded(false)
      return res
    } catch (e) {
      if (!alive.current) return null
      if (e instanceof AdminAuthError) setAuthNeeded(true)
      else if (e instanceof AdminDisabledError) setError(e.message)
      else setError(e instanceof Error ? e.message : 'Could not load jobs')
      return null
    }
  }, [])

  useEffect(() => {
    alive.current = true
    if (!enabled) return () => { alive.current = false }
    const tick = async () => {
      const res = await load()
      if (!alive.current) return
      const busy = !!res && (res.running !== null || res.queued > 0)
      timer.current = setTimeout(tick, busy ? FAST_MS : SLOW_MS)
    }
    void tick()
    return () => {
      alive.current = false
      if (timer.current) clearTimeout(timer.current)
    }
  }, [enabled, load])

  const refresh = useCallback(() => { void load() }, [load])
  return { data, error, authNeeded, refresh }
}
