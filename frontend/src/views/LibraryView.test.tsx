import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import LibraryView from './LibraryView'
import * as client from '../api/client'
import * as admin from '../api/admin'
import * as setup from '../api/setup'

vi.mock('../api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('../api/client')>()
  return { ...actual, docs: vi.fn(), status: vi.fn() }
})
vi.mock('../api/admin', async importOriginal => {
  const actual = await importOriginal<typeof import('../api/admin')>()
  return { ...actual, getAccess: vi.fn(), listJobs: vi.fn(), getInbox: vi.fn() }
})
vi.mock('../api/setup', async importOriginal => {
  const actual = await importOriginal<typeof import('../api/setup')>()
  return { ...actual, getSetupState: vi.fn() }
})

const docs = vi.mocked(client.docs)
const status = vi.mocked(client.status)
const getAccess = vi.mocked(admin.getAccess)
const listJobs = vi.mocked(admin.listJobs)
const getSetupState = vi.mocked(setup.getSetupState)

function entry(key: string, count: number) {
  return { doc_key: key, source_pdf: `${key}.pdf`, path: `/p/${key}`, count, mode: 'docling', run_date: '2026-10-12', profile: 'cybersecurity', skip_sections_applied: null }
}
function job(over: Partial<admin.JobSummary>): admin.JobSummary {
  return { id: 'JOB-1', kind: 'ingest', title: 'Ingest test-policy-99-1.pdf', state: 'succeeded', progress: null, ...over }
}

function show(path = '/library') {
  return render(<MemoryRouter initialEntries={[path]}><LibraryView /></MemoryRouter>)
}

beforeEach(() => {
  vi.clearAllMocks()
  docs.mockResolvedValue({ docs: [entry('test-policy-99-1', 8), entry('test-policy-99-2', 3)], total_reqs: 11, total_docs: 2 } as never)
  status.mockResolvedValue({ ollama: { reachable: true, models: [] }, qdrant: { reachable: true, collections: [] } } as never)
  getAccess.mockResolvedValue('open')
  listJobs.mockResolvedValue({ jobs: [], running: null, queued: 0 })
  getSetupState.mockResolvedValue({ config_file: true, needs_setup: false, questions_model: 'qwen2.5:14b' })
})
afterEach(cleanup)

describe('Library page', () => {
  it('is the whole library: a heading, the totals and every document, with the add panel closed', async () => {
    show()
    expect(await screen.findByRole('heading', { name: 'Library' })).toBeInTheDocument()
    expect(await screen.findByText('test-policy-99-1.pdf')).toBeInTheDocument()
    expect(screen.getByText('test-policy-99-2.pdf')).toBeInTheDocument()
    expect(screen.getByText(/2 documents · 11 requirements/)).toBeInTheDocument()
    expect(screen.queryByRole('complementary', { name: 'Add documents' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Add documents' })).toHaveAttribute('aria-expanded', 'false')
    // document pages live under /library
    expect(screen.getByText('test-policy-99-1.pdf').closest('a')).toHaveAttribute('href', '/library/test-policy-99-1')
  })

  it('opens the add panel from the button and closes it again, without reloading the list', async () => {
    show()
    await screen.findByText('test-policy-99-1.pdf')
    fireEvent.click(screen.getByRole('button', { name: 'Add documents' }))
    const panel = await screen.findByRole('complementary', { name: 'Add documents' })
    expect(within(panel).getByTestId('dropzone')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Add documents', expanded: true })).toBeInTheDocument()
    expect(screen.getByText('test-policy-99-1.pdf')).toBeInTheDocument() // the list stays where it is
    fireEvent.click(within(panel).getByText('Close'))
    expect(screen.queryByRole('complementary', { name: 'Add documents' })).not.toBeInTheDocument()
    expect(docs).toHaveBeenCalledTimes(1)
  })

  it('opens with the panel showing when the address says ?add=1 (the setup page links there)', async () => {
    show('/library?add=1')
    expect(await screen.findByRole('complementary', { name: 'Add documents' })).toBeInTheDocument()
  })

  it('closes the panel with the Escape key', async () => {
    show('/library?add=1')
    const panel = await screen.findByRole('complementary', { name: 'Add documents' })
    fireEvent.keyDown(within(panel).getByText('Close'), { key: 'Escape' })
    expect(screen.queryByRole('complementary', { name: 'Add documents' })).not.toBeInTheDocument()
  })

  it('says how to turn adding on when the server has it switched off', async () => {
    getAccess.mockResolvedValue('unconfigured')
    show('/library?add=1')
    expect(await screen.findByText(/switched off on this server/)).toBeInTheDocument()
  })

  it('shows nothing across the top while the queue is idle', async () => {
    show()
    await screen.findByText('test-policy-99-1.pdf')
    await waitFor(() => expect(listJobs).toHaveBeenCalled())
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('shows a strip while a job runs, and History opens the panel with the activity list', async () => {
    listJobs.mockResolvedValue({
      jobs: [job({ id: 'JOB-r', title: 'Ingest afi17-203.pdf', state: 'running', progress: { step: 'finding', done: 120, total: 427 } }), job({ id: 'JOB-q', state: 'queued', title: 'Ingest b.pdf' })],
      running: 'JOB-r',
      queued: 1,
    })
    show()
    const strip = await screen.findByRole('status')
    expect(strip).toHaveTextContent('Working')
    expect(strip).toHaveTextContent('Ingest afi17-203.pdf: Finding requirements: 120 of 427 sections done')
    expect(strip).toHaveTextContent('1 waiting')
    expect(screen.queryByRole('complementary', { name: 'Add documents' })).not.toBeInTheDocument()

    fireEvent.click(within(strip).getByText('History'))
    const panel = await screen.findByRole('complementary', { name: 'Add documents' })
    expect(await within(panel).findByRole('heading', { name: 'Recent activity' })).toBeInTheDocument()
    expect(within(panel).getByText('Ingest b.pdf')).toBeInTheDocument()
    // the running job is the strip's business: the panel does not repeat it as a second banner
    expect(screen.getAllByRole('status')).toHaveLength(1)
  })

  it('lists the latest few jobs in the panel and shows older ones on request', async () => {
    listJobs.mockResolvedValue({
      jobs: [1, 2, 3, 4, 5].map(n => job({ id: `JOB-${n}`, title: `Ingest doc-${n}.pdf` })),
      running: null,
      queued: 0,
    })
    show('/library?add=1')
    const panel = await screen.findByRole('complementary', { name: 'Add documents' })
    expect(await within(panel).findByText('Ingest doc-3.pdf')).toBeInTheDocument()
    expect(within(panel).queryByText('Ingest doc-4.pdf')).not.toBeInTheDocument()
    fireEvent.click(within(panel).getByText('Show older (2)'))
    expect(within(panel).getByText('Ingest doc-5.pdf')).toBeInTheDocument()
    expect(within(panel).queryByText(/Show older/)).not.toBeInTheDocument()
  })

  it('reloads the document list when the job that was running has finished', async () => {
    const running = job({ id: 'JOB-r', state: 'running', progress: { step: 'finding', done: 1, total: 4 } })
    listJobs.mockResolvedValueOnce({ jobs: [running], running: 'JOB-r', queued: 0 })
    listJobs.mockResolvedValue({ jobs: [{ ...running, state: 'succeeded' }], running: null, queued: 0 })
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      show()
      await screen.findByRole('status')
      expect(docs).toHaveBeenCalledTimes(1)
      await vi.advanceTimersByTimeAsync(3500) // the list is asked again every few seconds while a job runs
      await waitFor(() => expect(docs).toHaveBeenCalledTimes(2))
      expect(screen.queryByRole('status')).not.toBeInTheDocument()
    } finally {
      vi.useRealTimers()
    }
  })

  it('says what to do when the library is empty', async () => {
    docs.mockResolvedValue({ docs: [], total_reqs: 0, total_docs: 0 } as never)
    show()
    expect(await screen.findByText(/Nothing is in the library yet/)).toBeInTheDocument()
  })
})
