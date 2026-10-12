import type { JobState, JobSummary } from '../api/admin'

/** Plain words for what the pipeline is doing, from the progress line the job runner keeps. */
export function stepLabel(progress: JobSummary['progress']): string {
  if (!progress) return 'Starting'
  const { step, done, total } = progress
  switch (step) {
    case 'reading': return 'Reading the PDF'
    case 'chunking': return 'Splitting it into sections'
    case 'finding':
      return total ? `Finding requirements, section ${Math.min((done ?? 0) + 1, total)} of ${total}` : 'Finding requirements'
    case 'checking': return 'Checking what was found'
    case 'totals': return 'Writing the totals'
    case 'indexing': return total ? `Adding to search, ${done ?? 0} of ${total}` : 'Adding to search'
    case 'indexing-context': return total ? `Adding the source text to search, ${done ?? 0} of ${total}` : 'Adding the source text to search'
    case 'done': return 'Finished'
    default: return step
  }
}

/** 0 to 100 when the step reports a total, else null. */
export function stepPercent(progress: JobSummary['progress']): number | null {
  if (!progress || !progress.total) return null
  return Math.max(0, Math.min(100, Math.round(((progress.done ?? 0) / progress.total) * 100)))
}

export const STATE_LABEL: Record<JobState, string> = {
  queued: 'Waiting',
  running: 'Running',
  succeeded: 'Done',
  failed: 'Failed',
  cancelled: 'Cancelled',
  interrupted: 'Interrupted',
}

export function canCancel(state: JobState): boolean {
  return state === 'queued' || state === 'running'
}

export function canRetry(state: JobState): boolean {
  return state === 'failed' || state === 'cancelled' || state === 'interrupted'
}

/** "12 Oct, 02:46" from an ISO time; the raw text when it cannot be read. */
export function shortTime(iso: string | null | undefined): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString(undefined, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
}
