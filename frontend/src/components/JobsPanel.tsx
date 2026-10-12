import { useState } from 'react'
import { cancelJob, getJob, retryJob } from '../api/admin'
import type { JobsResponse, JobSummary } from '../api/admin'
import { STATE_LABEL, canCancel, canRetry, shortTime, stepLabel, stepPercent } from '../utils/jobText'

const BADGE: Record<string, string> = {
  queued: 'bg-gray-100 text-gray-700',
  running: 'bg-blue-100 text-blue-700',
  succeeded: 'bg-green-100 text-green-700',
  failed: 'bg-red-100 text-red-700',
  cancelled: 'bg-gray-100 text-gray-500',
  interrupted: 'bg-amber-100 text-amber-700',
}

function Banner({ job, waiting }: { job: JobSummary; waiting: number }) {
  const pct = stepPercent(job.progress)
  return (
    <div role="status" className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-3">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm font-medium text-blue-900 truncate">{job.title}</p>
        <p className="text-xs text-blue-700 shrink-0">
          {waiting > 0 ? `${waiting} waiting` : 'Nothing else waiting'}
        </p>
      </div>
      <p className="text-sm text-blue-800 mt-1">{stepLabel(job.progress)}</p>
      <div className="mt-2 h-2 bg-blue-100 rounded" aria-hidden>
        <div className="h-2 bg-blue-500 rounded transition-all" style={{ width: `${pct ?? 5}%` }} />
      </div>
    </div>
  )
}

function JobRow({ job, onChanged }: { job: JobSummary; onChanged: () => void }) {
  const [open, setOpen] = useState(false)
  const [log, setLog] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [problem, setProblem] = useState<string | null>(null)

  async function toggle() {
    const next = !open
    setOpen(next)
    if (next) {
      try {
        setLog((await getJob(job.id)).log_tail)
      } catch (e) {
        setLog(e instanceof Error ? e.message : 'Could not load the log')
      }
    }
  }

  async function act(fn: (id: string) => Promise<unknown>) {
    setBusy(true)
    setProblem(null)
    try {
      await fn(job.id)
      onChanged()
    } catch (e) {
      setProblem(e instanceof Error ? e.message : 'That did not work')
    } finally {
      setBusy(false)
    }
  }

  return (
    <li className="bg-white border border-gray-200 rounded-lg p-3">
      <div className="flex items-center gap-3">
        <span className={`text-xs px-2 py-0.5 rounded shrink-0 ${BADGE[job.state] ?? BADGE.queued}`}>{STATE_LABEL[job.state]}</span>
        <button onClick={toggle} className="text-sm text-gray-900 truncate text-left hover:underline min-w-0 flex-1" aria-expanded={open}>
          {job.title}
        </button>
        <span className="text-xs text-gray-400 shrink-0">{shortTime(job.finished_at ?? job.started_at ?? job.created_at)}</span>
        {canCancel(job.state) && (
          <button disabled={busy} onClick={() => act(cancelJob)} className="text-xs text-gray-600 border border-gray-300 rounded px-2 py-1 hover:bg-gray-50 disabled:opacity-50">
            Cancel
          </button>
        )}
        {canRetry(job.state) && (
          <button disabled={busy} onClick={() => act(retryJob)} className="text-xs text-blue-700 border border-blue-300 rounded px-2 py-1 hover:bg-blue-50 disabled:opacity-50">
            Retry
          </button>
        )}
      </div>
      {job.state === 'running' && job.cancel_requested && <p className="text-xs text-gray-500 mt-1">Stopping…</p>}
      {job.error && (job.state === 'failed' || job.state === 'interrupted') && <p className="text-xs text-red-700 mt-2">{job.error}</p>}
      {problem && <p className="text-xs text-red-700 mt-2">{problem}</p>}
      {open && (
        <pre className="mt-2 max-h-56 overflow-auto bg-gray-50 border border-gray-200 rounded p-2 text-[11px] leading-snug whitespace-pre-wrap">
          {log === null ? 'Loading…' : log.trim() || 'No log yet.'}
        </pre>
      )}
    </li>
  )
}

interface PanelProps {
  data: JobsResponse | null
  onChanged: () => void
  /** Show the banner for the running job above the list (the Library page shows it as a strip across the top instead). */
  banner?: boolean
  /** How many of the newest jobs to list. */
  limit?: number
  heading?: string
  /** When given, and there are more jobs than `limit`, a button asks for more. */
  onShowMore?: () => void
}

export default function JobsPanel({ data, onChanged, banner = true, limit = 10, heading = 'Jobs', onShowMore }: PanelProps) {
  if (!data) return null
  const running = data.jobs.find(j => j.id === data.running) ?? data.jobs.find(j => j.state === 'running')
  const rest = data.jobs.slice(0, limit)
  const older = data.jobs.length - rest.length
  return (
    <section aria-label={heading}>
      {banner && running && <Banner job={running} waiting={data.queued} />}
      <h2 className="text-xs uppercase tracking-wide text-gray-400 mb-2">{heading}</h2>
      {rest.length === 0 ? (
        <p className="text-sm text-gray-500">No jobs yet. Drop a PDF above to start one.</p>
      ) : (
        <ul className="space-y-2">
          {rest.map(j => (
            <JobRow key={j.id} job={j} onChanged={onChanged} />
          ))}
        </ul>
      )}
      {older > 0 && onShowMore && (
        <button onClick={onShowMore} className="mt-3 text-sm text-blue-700 hover:underline">
          Show older ({older})
        </button>
      )}
    </section>
  )
}
