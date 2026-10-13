import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import JobsPanel from './JobsPanel'
import * as admin from '../api/admin'

vi.mock('../api/admin', async importOriginal => {
  const actual = await importOriginal<typeof import('../api/admin')>()
  return { ...actual, cancelJob: vi.fn(), retryJob: vi.fn(), getJob: vi.fn() }
})

const cancelJob = vi.mocked(admin.cancelJob)
const retryJob = vi.mocked(admin.retryJob)
const getJob = vi.mocked(admin.getJob)

function job(over: Partial<admin.JobSummary>): admin.JobSummary {
  return { id: 'JOB-20261012-010101-aaaaaa', kind: 'ingest', title: 'Ingest afi99-1.pdf', state: 'queued', progress: null, ...over }
}

beforeEach(() => vi.clearAllMocks())
afterEach(cleanup)

describe('JobsPanel', () => {
  it('shows nothing until the list has loaded', () => {
    const { container } = render(<JobsPanel data={null} onChanged={() => {}} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('shows a banner for the running job with its step and how many wait', () => {
    const running = job({ id: 'JOB-r', title: 'Ingest afi17-203.pdf', state: 'running', progress: { step: 'finding', done: 120, total: 427 } })
    render(<JobsPanel data={{ jobs: [running, job({ id: 'JOB-q' })], running: 'JOB-r', queued: 1 }} onChanged={() => {}} />)
    const banner = screen.getByRole('status')
    expect(banner).toHaveTextContent('Ingest afi17-203.pdf')
    expect(banner).toHaveTextContent('Finding requirements: 120 of 427 sections done')
    expect(banner).toHaveTextContent('1 waiting')
  })

  it('says so when there are no jobs', () => {
    render(<JobsPanel data={{ jobs: [], running: null, queued: 0 }} onChanged={() => {}} />)
    expect(screen.getByText(/No jobs yet/i)).toBeInTheDocument()
  })

  it('cancels a queued job and tells the page to refresh', async () => {
    cancelJob.mockResolvedValue(job({ state: 'cancelled' }))
    const onChanged = vi.fn()
    render(<JobsPanel data={{ jobs: [job({})], running: null, queued: 1 }} onChanged={onChanged} />)
    fireEvent.click(screen.getByText('Cancel'))
    await waitFor(() => expect(cancelJob).toHaveBeenCalledWith('JOB-20261012-010101-aaaaaa'))
    await waitFor(() => expect(onChanged).toHaveBeenCalled())
  })

  it('offers Retry only on a job that ended badly, and shows why it failed', async () => {
    retryJob.mockResolvedValue(job({}))
    const failed = job({ id: 'JOB-f', state: 'failed', error: 'Qdrant (the search index) did not answer at http://q:6333.' })
    const done = job({ id: 'JOB-d', state: 'succeeded', title: 'Ingest done.pdf' })
    render(<JobsPanel data={{ jobs: [failed, done], running: null, queued: 0 }} onChanged={() => {}} />)
    expect(screen.getByText(/Qdrant \(the search index\) did not answer/)).toBeInTheDocument()
    expect(screen.getAllByText('Retry')).toHaveLength(1)
    fireEvent.click(screen.getByText('Retry'))
    await waitFor(() => expect(retryJob).toHaveBeenCalledWith('JOB-f'))
  })

  it('opens the end of the log when a job is clicked', async () => {
    getJob.mockResolvedValue({ ...job({ state: 'failed' }), log_tail: 'line one\nline two' } as admin.JobDetail)
    render(<JobsPanel data={{ jobs: [job({ state: 'failed' })], running: null, queued: 0 }} onChanged={() => {}} />)
    fireEvent.click(screen.getByText('Ingest afi99-1.pdf'))
    await screen.findByText(/line two/)
  })

  it('shows a problem from cancel instead of failing silently', async () => {
    cancelJob.mockRejectedValue(new Error('No such job'))
    render(<JobsPanel data={{ jobs: [job({})], running: null, queued: 1 }} onChanged={() => {}} />)
    fireEvent.click(screen.getByText('Cancel'))
    await screen.findByText('No such job')
  })

  it('can leave the running-job banner to the page, and list only the newest few with a way to see older ones', () => {
    const onShowMore = vi.fn()
    const jobs = [1, 2, 3, 4].map(n => job({ id: `JOB-${n}`, title: `Ingest doc-${n}.pdf`, state: n === 1 ? 'running' : 'succeeded' }))
    render(<JobsPanel data={{ jobs, running: 'JOB-1', queued: 0 }} onChanged={() => {}} banner={false} limit={2} heading="Recent activity" onShowMore={onShowMore} />)
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Recent activity' })).toBeInTheDocument()
    expect(screen.getByText('Ingest doc-2.pdf')).toBeInTheDocument()
    expect(screen.queryByText('Ingest doc-3.pdf')).not.toBeInTheDocument()
    fireEvent.click(screen.getByText('Show older (2)'))
    expect(onShowMore).toHaveBeenCalled()
  })

  it('shows the whole title on its own line under the status and time, not cut short beside them', () => {
    const long = 'Ingest test-policy-99-1.pdf, then write draft questions'
    render(<JobsPanel data={{ jobs: [job({ title: long, state: 'succeeded', finished_at: '2026-10-12T19:26:00+00:00' })], running: null, queued: 0 }} onChanged={() => {}} />)
    const title = screen.getByText(long)
    expect(title.tagName).toBe('BUTTON')
    expect(title.className).not.toContain('truncate')
    expect(title.className).toContain('break-words')
    expect(screen.getByText('Done')).toBeInTheDocument()
  })
})
