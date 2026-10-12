import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import AddDocuments from './AddDocuments'
import * as admin from '../api/admin'

vi.mock('../api/admin', async importOriginal => {
  const actual = await importOriginal<typeof import('../api/admin')>()
  return { ...actual, uploadPdf: vi.fn(), startIngest: vi.fn(), getInbox: vi.fn(), importInbox: vi.fn() }
})

const uploadPdf = vi.mocked(admin.uploadPdf)
const startIngest = vi.mocked(admin.startIngest)
const getInbox = vi.mocked(admin.getInbox)
const importInbox = vi.mocked(admin.importInbox)

function pdf(name = 'afi99-1.pdf') {
  return new File(['%PDF-1.4'], name, { type: 'application/pdf' })
}

function uploaded(status: admin.LibraryStanding['status'], extra: Partial<admin.UploadResponse> = {}, document: string | null = null): admin.UploadResponse {
  return { upload_id: 'UP-20261012-010101-abcdef', filename: 'afi99-1.pdf', stem: 'afi99-1', size: 8, pages: 1, sha256: 'x', library: { status, document }, ...extra }
}

function choose(files: File[]) {
  fireEvent.change(screen.getByLabelText('Choose PDF files'), { target: { files } })
}

function setup(mode: admin.AdminMode, props: Partial<React.ComponentProps<typeof AddDocuments>> = {}) {
  const onStarted = vi.fn()
  const onCodeChanged = vi.fn()
  render(<AddDocuments mode={mode} onStarted={onStarted} onCodeChanged={onCodeChanged} {...props} />)
  return { onStarted, onCodeChanged }
}

beforeEach(() => {
  window.localStorage.clear()
  vi.clearAllMocks()
})
afterEach(cleanup)

describe('AddDocuments', () => {
  it('says adding is switched off when the server has no code and is not in trusted-network mode', () => {
    setup('unconfigured')
    expect(screen.getByText(/switched off on this server/i)).toBeInTheDocument()
    expect(screen.queryByTestId('dropzone')).not.toBeInTheDocument()
    expect(screen.getByText('reqbot token --open')).toBeInTheDocument()
  })

  it('uploads and starts a new file at once when no code is needed', async () => {
    uploadPdf.mockResolvedValue(uploaded('new'))
    startIngest.mockResolvedValue({ result: 'queued', document: 'afi99-1', job: null })
    const { onStarted } = setup('open')
    choose([pdf()])
    await screen.findByText('Queued')
    expect(startIngest).toHaveBeenCalledWith('UP-20261012-010101-abcdef', 'ask')
    expect(onStarted).toHaveBeenCalled()
  })

  it('leaves out files that are not PDFs and says so when nothing is left', async () => {
    setup('open')
    choose([new File(['x'], 'notes.txt')])
    await screen.findByText(/No PDF files were found/i)
    expect(uploadPdf).not.toHaveBeenCalled()
  })

  it('holds the files and asks for the code when one is needed, then adds them once it is entered', async () => {
    uploadPdf.mockResolvedValue(uploaded('new'))
    startIngest.mockResolvedValue({ result: 'queued', document: 'afi99-1', job: null })
    const { onCodeChanged } = setup('code')
    expect(screen.getByLabelText('Access code')).toBeInTheDocument()
    choose([pdf()])
    await screen.findByText(/will be added as soon as you enter the access code/i)
    expect(uploadPdf).not.toHaveBeenCalled()
    fireEvent.change(screen.getByLabelText('Access code'), { target: { value: ' my-code ' } })
    fireEvent.click(screen.getByText('Use this code'))
    await screen.findByText('Queued')
    expect(admin.getAdminToken()).toBe('my-code')
    expect(onCodeChanged).toHaveBeenCalled()
    expect(uploadPdf).toHaveBeenCalledTimes(1)
  })

  it('does not ask for the code again once it is saved', () => {
    admin.setAdminToken('saved')
    setup('code')
    expect(screen.queryByLabelText('Access code')).not.toBeInTheDocument()
  })

  it('forgets a code the server refuses and asks again', async () => {
    admin.setAdminToken('stale')
    uploadPdf.mockRejectedValue(new admin.AdminAuthError('The admin access code is not correct.'))
    const { onCodeChanged } = setup('code')
    choose([pdf()])
    await screen.findByText('The access code was not accepted.')
    expect(admin.getAdminToken()).toBe('')
    expect(onCodeChanged).toHaveBeenCalled()
    expect(await screen.findByText(/was not accepted\. Paste the current one/i)).toBeInTheDocument()
    // the refused file is tried again as soon as a new code is entered
    uploadPdf.mockResolvedValue(uploaded('new'))
    startIngest.mockResolvedValue({ result: 'queued', document: 'afi99-1', job: null })
    fireEvent.change(screen.getByLabelText('Access code'), { target: { value: 'fresh-code' } })
    fireEvent.click(screen.getByText('Use this code'))
    await screen.findByText('Queued')
    expect(uploadPdf).toHaveBeenCalledTimes(2)
  })

  it('asks what to do when the name is in the library with different content, and never starts it silently', async () => {
    uploadPdf.mockResolvedValue(uploaded('same_name_different_content'))
    startIngest.mockResolvedValue({ result: 'queued', document: 'afi99-1_2', job: null })
    setup('open')
    choose([pdf()])
    await screen.findByText('Needs a decision')
    expect(startIngest).not.toHaveBeenCalled()
    fireEvent.click(screen.getByText('Keep both'))
    await screen.findByText('Queued as afi99-1_2.')
    expect(startIngest).toHaveBeenCalledWith('UP-20261012-010101-abcdef', 'keep_both')
  })

  it('can replace, and can leave a file out', async () => {
    uploadPdf.mockResolvedValue(uploaded('same_name_different_content'))
    startIngest.mockResolvedValue({ result: 'queued', document: 'afi99-1', job: null })
    setup('open')
    choose([pdf()])
    fireEvent.click(await screen.findByText('Replace it'))
    await screen.findByText('Queued to replace the library copy.')
    expect(startIngest).toHaveBeenCalledWith('UP-20261012-010101-abcdef', 'replace')
    cleanup()
    vi.clearAllMocks()
    uploadPdf.mockResolvedValue(uploaded('same_name_different_content'))
    setup('open')
    choose([pdf()])
    fireEvent.click(await screen.findByText('Skip it'))
    await screen.findByText('Left out; nothing changed.')
    expect(startIngest).not.toHaveBeenCalled()
  })

  it('skips a file whose content is already in the library without starting anything', async () => {
    uploadPdf.mockResolvedValue(uploaded('same_content_other_name', {}, 'afi17-203'))
    setup('open')
    choose([pdf()])
    await screen.findByText('The same file is already in the library as afi17-203.')
    expect(startIngest).not.toHaveBeenCalled()
  })

  it('shows what the server said when a file is refused', async () => {
    uploadPdf.mockRejectedValue(new admin.AdminRequestError('The file is larger than the 100 MB limit.', 413, 'too_large'))
    setup('open')
    choose([pdf()])
    await screen.findByText('The file is larger than the 100 MB limit.')
    expect(screen.getByText('Not added')).toBeInTheDocument()
  })

  it('lists the inbox and imports the new files', async () => {
    getInbox.mockResolvedValue({
      folder: '/data/inbox', exists: true, truncated: false,
      files: [{ name: 'new-one.pdf', size: 10, status: 'new' }, { name: 'have-it.pdf', size: 10, status: 'same_content' }],
    })
    importInbox.mockResolvedValue({ queued: 1, results: [{ file: 'new-one.pdf', result: 'queued' }] })
    const { onStarted } = setup('open')
    fireEvent.click(screen.getByText('Import from inbox'))
    await screen.findByText('new-one.pdf')
    expect(screen.getByText('Already in the library')).toBeInTheDocument()
    fireEvent.click(screen.getByText('Import the new ones'))
    await waitFor(() => expect(importInbox).toHaveBeenCalledWith(null, 'ask'))
    expect(onStarted).toHaveBeenCalled()
  })

  it('uploads the held files at once when a replacement code is entered, even while the job list still says the old code was rejected', async () => {
    admin.setAdminToken('stale')
    uploadPdf.mockResolvedValue(uploaded('new'))
    startIngest.mockResolvedValue({ result: 'queued', document: 'afi99-1', job: null })
    setup('code', { codeRejected: true })
    expect(screen.getByLabelText('Access code')).toBeInTheDocument()
    choose([pdf()])
    await screen.findByText(/will be added as soon as you enter the access code/i)
    expect(uploadPdf).not.toHaveBeenCalled()
    fireEvent.change(screen.getByLabelText('Access code'), { target: { value: 'replacement' } })
    fireEvent.click(screen.getByText('Use this code'))
    await screen.findByText('Queued')
    expect(uploadPdf).toHaveBeenCalledTimes(1)
    expect(screen.queryByLabelText('Access code')).not.toBeInTheDocument()
  })
})
