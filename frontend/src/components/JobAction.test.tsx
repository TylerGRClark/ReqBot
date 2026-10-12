import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import JobAction from './JobAction'
import * as admin from '../api/admin'

vi.mock('../api/admin', async importOriginal => {
  const actual = await importOriginal<typeof import('../api/admin')>()
  return { ...actual, getAccess: vi.fn(), listJobs: vi.fn(), cancelJob: vi.fn() }
})

const getAccess = vi.mocked(admin.getAccess)
const listJobs = vi.mocked(admin.listJobs)
const cancelJob = vi.mocked(admin.cancelJob)

function job(over: Partial<admin.JobSummary> = {}): admin.JobSummary {
  return { id: 'JOB-20261012-010101-aaaaaa', kind: 'questions', title: 'Draft questions for afi99-1', state: 'queued', progress: null, params: { doc_key: 'afi99-1' }, ...over }
}

function jobs(list: admin.JobSummary[]): admin.JobsResponse {
  const running = list.find(j => j.state === 'running')
  return { jobs: list, running: running?.id ?? null, queued: list.filter(j => j.state === 'queued').length }
}

const pick = (list: admin.JobSummary[]) => list.find(j => j.kind === 'questions' && j.params?.doc_key === 'afi99-1')

function show(props: Partial<React.ComponentProps<typeof JobAction>> = {}) {
  const start = vi.fn().mockResolvedValue({ result: 'queued', job: job() })
  const onSucceeded = vi.fn()
  render(<JobAction label="Write draft audit questions" pick={pick} start={start} onSucceeded={onSucceeded} {...props} />)
  return { start, onSucceeded }
}

beforeEach(() => {
  window.localStorage.clear()
  vi.clearAllMocks()
  listJobs.mockResolvedValue(jobs([]))
})
afterEach(() => {
  cleanup()
  vi.useRealTimers()
})

describe('JobAction', () => {
  it('shows nothing until the server says admin actions are possible', async () => {
    getAccess.mockResolvedValue('unconfigured')
    const { container } = render(<JobAction label="Go" pick={pick} start={vi.fn()} />)
    await waitFor(() => expect(getAccess).toHaveBeenCalled())
    expect(container).toBeEmptyDOMElement()
  })

  it('starts the job on a click when no code is needed and shows its progress in plain words', async () => {
    getAccess.mockResolvedValue('open')
    // the first read finds nothing running; the read right after the start finds the job running
    listJobs.mockResolvedValueOnce(jobs([])).mockResolvedValue(jobs([job({ state: 'running', progress: { step: 'questions', done: 40, total: 133 } })]))
    const { start } = show()
    fireEvent.click(await screen.findByText('Write draft audit questions'))
    await waitFor(() => expect(start).toHaveBeenCalledTimes(1))
    await screen.findByText('Writing questions: 40 of 133 rows done')
    expect(screen.queryByText('Write draft audit questions')).not.toBeInTheDocument() // no second start while it runs
  })

  it('asks first when it takes a while, and does nothing on "Not now"', async () => {
    getAccess.mockResolvedValue('open')
    const { start } = show({ confirm: 'This can take several minutes.' })
    fireEvent.click(await screen.findByText('Write draft audit questions'))
    expect(screen.getByText('This can take several minutes.')).toBeInTheDocument()
    fireEvent.click(screen.getByText('Not now'))
    expect(start).not.toHaveBeenCalled()
    fireEvent.click(screen.getByText('Write draft audit questions'))
    fireEvent.click(screen.getByText('Start'))
    await waitFor(() => expect(start).toHaveBeenCalledTimes(1))
  })

  it('asks for the access code before starting when one is needed, then starts', async () => {
    getAccess.mockResolvedValue('code')
    const { start } = show()
    fireEvent.click(await screen.findByText('Write draft audit questions'))
    expect(start).not.toHaveBeenCalled()
    fireEvent.change(screen.getByLabelText('Access code'), { target: { value: 'my-code' } })
    fireEvent.click(screen.getByText('Use this code'))
    await waitFor(() => expect(start).toHaveBeenCalledTimes(1))
    expect(admin.getAdminToken()).toBe('my-code')
  })

  it('forgets a code the server refuses and asks again', async () => {
    admin.setAdminToken('stale')
    getAccess.mockResolvedValue('code')
    const start = vi.fn().mockRejectedValue(new admin.AdminAuthError('The admin access code is not correct.'))
    show({ start })
    fireEvent.click(await screen.findByText('Write draft audit questions'))
    await screen.findByText(/was not accepted\. Paste the current one/i)
    expect(admin.getAdminToken()).toBe('')
  })

  it('shows why the last run failed and lets it be started again', async () => {
    getAccess.mockResolvedValue('open')
    listJobs.mockResolvedValue(jobs([job({ state: 'failed', error: 'The model machine (Ollama) did not answer at http://m:11434.' })]))
    show()
    await screen.findByText(/The model machine \(Ollama\) did not answer/)
    expect(screen.getByText('Write draft audit questions')).toBeInTheDocument()
  })

  it('says a duplicate is already queued instead of starting a second one', async () => {
    getAccess.mockResolvedValue('open')
    const start = vi.fn().mockResolvedValue({ result: 'skipped', message: 'That is already queued or running.' })
    show({ start })
    fireEvent.click(await screen.findByText('Write draft audit questions'))
    await screen.findByText('That is already queued or running.')
  })

  it('offers Cancel on a running job', async () => {
    getAccess.mockResolvedValue('open')
    listJobs.mockResolvedValue(jobs([job({ state: 'running', progress: { step: 'questions', done: 1, total: 9 } })]))
    cancelJob.mockResolvedValue(job({ state: 'cancelled' }))
    show()
    fireEvent.click(await screen.findByText('Cancel'))
    await waitFor(() => expect(cancelJob).toHaveBeenCalledWith('JOB-20261012-010101-aaaaaa'))
  })

  it('tells the page once when the job it was watching finishes well', async () => {
    getAccess.mockResolvedValue('open')
    listJobs.mockResolvedValue(jobs([job({ state: 'running', progress: { step: 'questions', done: 1, total: 2 } })]))
    const { onSucceeded } = show()
    await screen.findByText('Writing questions: 1 of 2 rows done')
    listJobs.mockResolvedValue(jobs([job({ state: 'succeeded', finished_at: '2026-10-12T05:00:00Z' })]))
    await act(async () => { await new Promise(r => setTimeout(r, 3300)) }) // the list is read again every 3 seconds while a job runs
    await waitFor(() => expect(onSucceeded).toHaveBeenCalledTimes(1))
    expect(screen.getByText(/Last run finished/)).toBeInTheDocument()
  }, 10000)

  it('tells the page when a job it started finished between two reads, never seen running', async () => {
    getAccess.mockResolvedValue('open')
    const done = job({ id: 'JOB-20261012-020202-bbbbbb', state: 'succeeded', finished_at: '2026-10-12T05:00:00Z' })
    // the list read before the click is empty; the first read after the click already shows the job finished
    listJobs.mockResolvedValueOnce(jobs([])).mockResolvedValue(jobs([done]))
    const { start, onSucceeded } = show()
    start.mockResolvedValue({ result: 'queued', job: done })
    fireEvent.click(await screen.findByText('Write draft audit questions'))
    await waitFor(() => expect(onSucceeded).toHaveBeenCalledTimes(1))
  })
})
