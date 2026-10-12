import { useEffect, useRef, useState } from 'react'
import type { AdminState } from '../hooks/useAdmin'
import AddDocuments from './AddDocuments'
import JobsPanel from './JobsPanel'

const FIRST_PAGE = 3
const SECOND_PAGE = 10
const MORE = 20

interface Props {
  admin: AdminState
  /** False keeps the panel on the page but hidden, so work started in it (an upload, a pending decision) survives closing it. */
  open: boolean
  onClose: () => void
  /** Goes up each time "History" is chosen: the panel then shows more of the activity list and scrolls to it. */
  historyAsked: number
}

/**
 * The side panel of the Library page: drop PDFs, choose files or a folder, import from the inbox, and below that the latest activity
 * (the last few jobs; more on request, scrolling inside the panel so the document list never moves).
 */
export default function AddPanel({ admin, open, onClose, historyAsked }: Props) {
  const { mode, asked, enabled, jobs, afterStart, codeChanged, codeRejected } = admin
  const [limit, setLimit] = useState(FIRST_PAGE)
  const activity = useRef<HTMLDivElement>(null)
  const panel = useRef<HTMLElement>(null)

  // when it opens: bring it into view (below the whole list on a narrow screen it would be off-screen) and put the keyboard focus in it, so Escape closes it
  useEffect(() => {
    if (!open) return
    panel.current?.focus({ preventScroll: true })
    panel.current?.scrollIntoView?.({ block: 'nearest' })
  }, [open])

  useEffect(() => {
    if (historyAsked === 0 || !open) return
    setLimit(l => Math.max(l, SECOND_PAGE))
    activity.current?.scrollIntoView?.({ block: 'start' })
  }, [historyAsked, open])

  return (
    <aside
      ref={panel}
      id="add-documents-panel"
      aria-label="Add documents"
      hidden={!open}
      tabIndex={-1}
      onKeyDown={e => { if (e.key === 'Escape') onClose() }}
      className="w-full lg:w-[380px] shrink-0 bg-white border-t lg:border-t-0 lg:border-l border-gray-200 p-6 space-y-5 lg:sticky lg:top-0 lg:max-h-screen lg:overflow-y-auto focus:outline-none"
    >
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="text-base font-bold text-gray-900">Add documents</h2>
        <button onClick={onClose} className="text-sm text-blue-700 hover:underline">Close</button>
      </div>

      {mode === null ? (
        <p className="text-sm text-gray-600">
          {asked ? 'The server did not say whether adding documents is switched on. Reload the page to try again.' : 'Checking…'}
        </p>
      ) : (
        <AddDocuments mode={mode} onStarted={afterStart} onCodeChanged={codeChanged} codeRejected={codeRejected} />
      )}

      {enabled && jobs.error && <p className="text-xs text-red-700">{jobs.error}</p>}
      {enabled && (
        <div ref={activity}>
          <JobsPanel
            data={jobs.data}
            onChanged={jobs.refresh}
            banner={false}
            heading="Recent activity"
            limit={limit}
            onShowMore={() => setLimit(l => (l < SECOND_PAGE ? SECOND_PAGE : l + MORE))}
          />
        </div>
      )}
    </aside>
  )
}
