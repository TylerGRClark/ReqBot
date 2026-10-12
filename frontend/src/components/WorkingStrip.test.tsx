import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import WorkingStrip from './WorkingStrip'
import type { JobSummary } from '../api/admin'

afterEach(cleanup)

function job(over: Partial<JobSummary>): JobSummary {
  return { id: 'JOB-1', kind: 'ingest', title: 'Ingest afi99-1.pdf', state: 'running', progress: null, ...over }
}

describe('WorkingStrip', () => {
  it('shows nothing before the list has loaded or when nothing is running or waiting', () => {
    const a = render(<WorkingStrip data={null} onHistory={() => {}} />)
    expect(a.container).toBeEmptyDOMElement()
    cleanup()
    const b = render(<WorkingStrip data={{ jobs: [job({ state: 'succeeded' })], running: null, queued: 0 }} onHistory={() => {}} />)
    expect(b.container).toBeEmptyDOMElement()
  })

  it('names the running job and its step, and opens the history', () => {
    const onHistory = vi.fn()
    render(<WorkingStrip data={{ jobs: [job({ progress: { step: 'reindex', done: 2, total: 5 }, title: 'Rebuild the search library' })], running: 'JOB-1', queued: 0 }} onHistory={onHistory} />)
    expect(screen.getByRole('status')).toHaveTextContent('Rebuild the search library: Rebuilding the library: 2 of 5 documents done')
    expect(screen.queryByText(/waiting/)).not.toBeInTheDocument()
    fireEvent.click(screen.getByText('History'))
    expect(onHistory).toHaveBeenCalled()
  })

  it('says so when jobs are queued but none has started', () => {
    render(<WorkingStrip data={{ jobs: [job({ state: 'queued' })], running: null, queued: 1 }} onHistory={() => {}} />)
    expect(screen.getByRole('status')).toHaveTextContent('Waiting to start')
    expect(screen.getByRole('status')).toHaveTextContent('1 waiting')
  })
})
