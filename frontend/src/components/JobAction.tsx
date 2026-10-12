import { useCallback, useEffect, useRef, useState } from 'react'
import { AdminAuthError, cancelJob, clearAdminToken, getAccess, getAdminToken } from '../api/admin'
import type { AdminMode, JobSummary, QueueResponse } from '../api/admin'
import { useJobs } from '../hooks/useJobs'
import { canCancel, shortTime, stepLabel, stepPercent } from '../utils/jobText'
import CodePrompt from './CodePrompt'

interface Props {
  /** The button's words, e.g. "Write draft audit questions". */
  label: string
  /** Which of the jobs (newest first) is this action's: for example the questions job of this document. */
  pick: (jobs: JobSummary[]) => JobSummary | undefined
  /** Queue the job. */
  start: () => Promise<QueueResponse>
  /** When set, a click first shows this text with Start and Not now: for an action that takes a while. */
  confirm?: string
  /** Called once when the job this panel was watching finishes successfully (the page can reload what it shows). */
  onSucceeded?: () => void
}

/**
 * One admin action that runs as a job: a button, the job's progress in plain words, what went wrong if it did, and Cancel. It asks the
 * server which way admin actions are protected and shows nothing when they are switched off (the Corpus page explains how to turn them
 * on), so a reader's screen is not cluttered. Used for "Write draft audit questions" and "Rebuild the library".
 */
export default function JobAction({ label, pick, start, confirm, onSucceeded }: Props) {
  const [mode, setMode] = useState<AdminMode | null>(null)
  const [, bump] = useState(0)
  const [asking, setAsking] = useState(false)
  const [needCode, setNeedCode] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [problem, setProblem] = useState<string | null>(null)
  const hasCode = getAdminToken() !== ''
  const enabled = mode === 'open' || (mode === 'code' && hasCode)
  const jobs = useJobs(enabled)

  useEffect(() => {
    let alive = true
    getAccess().then(m => { if (alive) setMode(m) }).catch(() => { if (alive) setMode(null) })
    return () => { alive = false }
  }, [])

  const mine = pick(jobs.data?.jobs ?? [])

  // Tell the page once when the job it was watching finishes well. A job this panel started counts even if polling never caught it
  // queued or running (a short run can go from queued to done between two polls).
  const lastState = useRef<string | null>(null)
  const started = useRef<string | null>(null)
  useEffect(() => {
    const now = mine?.state ?? null
    const wasLive = lastState.current === 'queued' || lastState.current === 'running'
    const isStarted = !!mine && mine.id === started.current
    if (now === 'succeeded' && (wasLive || isStarted)) {
      started.current = null
      onSucceeded?.()
    }
    lastState.current = now
  }, [mine?.id, mine?.state, onSucceeded])

  const go = useCallback(async () => {
    setBusy(true)
    setProblem(null)
    setAsking(false)
    try {
      const r = await start()
      if (r.result === 'skipped') setProblem(r.message ?? 'That is already queued or running.')
      else started.current = r.job?.id ?? r.job_id ?? null
      jobs.refresh()
    } catch (e) {
      if (e instanceof AdminAuthError) {
        clearAdminToken()
        bump(v => v + 1)
        setNeedCode('The access code was not accepted. Paste the current one.')
      } else {
        setProblem(e instanceof Error ? e.message : 'That did not work.')
      }
    } finally {
      setBusy(false)
    }
  }, [start, jobs])

  function click() {
    setProblem(null)
    if (mode === 'code' && !getAdminToken()) {
      setNeedCode('')
      return
    }
    if (confirm) setAsking(true)
    else void go()
  }

  if (mode === null || mode === 'unconfigured') return null

  const live = mine && (mine.state === 'queued' || mine.state === 'running')
  const pct = stepPercent(mine?.progress)

  return (
    <div className="inline-block max-w-xl align-top" data-testid="job-action">
      {needCode !== null && (
        <div className="mb-2">
          <CodePrompt
            reason={needCode || undefined}
            onSaved={() => {
              setNeedCode(null)
              bump(v => v + 1)
              jobs.refresh()
              if (confirm) setAsking(true)
              else void go()
            }}
          />
        </div>
      )}

      {!live && !asking && needCode === null && (
        <button onClick={click} disabled={busy} className="text-sm bg-white border border-gray-300 text-gray-700 rounded-lg px-3 py-1.5 hover:bg-gray-50 disabled:opacity-50">
          {busy ? 'Starting…' : label}
        </button>
      )}

      {asking && (
        <div className="border border-gray-200 bg-white rounded-lg p-3 text-sm text-gray-700">
          <p>{confirm}</p>
          <div className="flex gap-2 mt-2">
            <button onClick={() => void go()} className="text-sm bg-blue-600 text-white rounded px-3 py-1.5 hover:bg-blue-700">Start</button>
            <button onClick={() => setAsking(false)} className="text-sm text-gray-600 border border-gray-300 rounded px-3 py-1.5 hover:bg-gray-50">Not now</button>
          </div>
        </div>
      )}

      {live && mine && (
        <div role="status" className="border border-blue-200 bg-blue-50 rounded-lg p-3 text-sm">
          <div className="flex items-center justify-between gap-3">
            <span className="text-blue-900">{mine.state === 'queued' ? 'Waiting for its turn' : stepLabel(mine.progress)}</span>
            {canCancel(mine.state) && (
              <button
                onClick={async () => {
                  try { await cancelJob(mine.id) } catch (e) { setProblem(e instanceof Error ? e.message : 'Could not cancel') }
                  jobs.refresh()
                }}
                className="text-xs text-gray-600 border border-gray-300 rounded px-2 py-1 hover:bg-white"
              >
                Cancel
              </button>
            )}
          </div>
          {mine.state === 'running' && (
            <div className="mt-2 h-2 bg-blue-100 rounded" aria-hidden>
              <div className="h-2 bg-blue-500 rounded transition-all" style={{ width: `${pct ?? 5}%` }} />
            </div>
          )}
        </div>
      )}

      {!live && mine && mine.state === 'succeeded' && (
        <p className="text-xs text-gray-500 mt-1">Last run finished {shortTime(mine.finished_at)}.</p>
      )}
      {!live && mine && (mine.state === 'failed' || mine.state === 'interrupted') && (
        <p className="text-xs text-red-700 mt-1">{mine.error || 'The last run did not finish.'} You can start it again.</p>
      )}
      {problem && <p className="text-xs text-red-700 mt-1">{problem}</p>}
    </div>
  )
}
