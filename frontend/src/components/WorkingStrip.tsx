import type { JobsResponse } from '../api/admin'
import { stepLabel, stepPercent } from '../utils/jobText'

/**
 * The slim strip across the top of the Library page while something is being read, rebuilt or written: what it is, which step, and how many wait.
 * Shows nothing when the queue is idle. `onHistory` opens the activity list.
 */
export default function WorkingStrip({ data, onHistory }: { data: JobsResponse | null; onHistory: () => void }) {
  if (!data) return null
  const running = data.jobs.find(j => j.id === data.running) ?? data.jobs.find(j => j.state === 'running')
  if (!running && data.queued === 0) return null

  const pct = running ? stepPercent(running.progress) : null
  return (
    <div role="status" className="flex flex-wrap items-center gap-x-4 gap-y-1 bg-blue-50 border-b border-blue-200 px-6 py-2.5 text-sm text-blue-900">
      <span className="font-semibold">{running ? 'Working' : 'Waiting to start'}</span>
      {running && <span className="min-w-0 truncate">{running.title}: {stepLabel(running.progress)}</span>}
      {running && (
        <span className="h-1.5 w-32 bg-blue-100 rounded" aria-hidden>
          <span className="block h-1.5 bg-blue-500 rounded transition-all" style={{ width: `${pct ?? 5}%` }} />
        </span>
      )}
      {data.queued > 0 && <span className="text-xs text-blue-800">{data.queued} waiting</span>}
      <button onClick={onHistory} className="ml-auto text-sm text-blue-700 underline hover:text-blue-900">
        History
      </button>
    </div>
  )
}
