import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import RemoveDocument from './RemoveDocument'
import * as admin from '../api/admin'

vi.mock('../api/admin', async importOriginal => {
  const actual = await importOriginal<typeof import('../api/admin')>()
  return { ...actual, getAccess: vi.fn(), removeDocument: vi.fn() }
})

const getAccess = vi.mocked(admin.getAccess)
const removeDocument = vi.mocked(admin.removeDocument)

beforeEach(() => {
  window.localStorage.clear()
  vi.clearAllMocks()
})
afterEach(cleanup)

describe('RemoveDocument', () => {
  it('shows nothing when admin actions are switched off', async () => {
    getAccess.mockResolvedValue('unconfigured')
    const { container } = render(<RemoveDocument docKey="afi99-1" onRemoved={() => {}} />)
    await waitFor(() => expect(getAccess).toHaveBeenCalled())
    expect(container).toBeEmptyDOMElement()
  })

  it('is never one click: the document\'s name has to be typed before Remove it is enabled', async () => {
    getAccess.mockResolvedValue('open')
    removeDocument.mockResolvedValue({ document: 'afi99-1', run_folders_moved: ['afi99-1_20261001_120000'], trash: '/p/.trash/x', points_removed: { requirements: 3, context: 2 } })
    const onRemoved = vi.fn()
    render(<RemoveDocument docKey="afi99-1" onRemoved={onRemoved} />)
    fireEvent.click(await screen.findByText('Remove this document…'))
    expect(screen.getByText(/moved to a trash folder on the server, not deleted/i)).toBeInTheDocument()
    const confirm = screen.getByText('Remove it') as HTMLButtonElement
    expect(confirm).toBeDisabled()
    fireEvent.change(screen.getByLabelText("Type the document's name to confirm"), { target: { value: 'afi99' } })
    expect(confirm).toBeDisabled()
    fireEvent.change(screen.getByLabelText("Type the document's name to confirm"), { target: { value: 'afi99-1' } })
    expect(confirm).toBeEnabled()
    fireEvent.click(confirm)
    await waitFor(() => expect(removeDocument).toHaveBeenCalledWith('afi99-1', 'afi99-1'))
    await waitFor(() => expect(onRemoved).toHaveBeenCalled())
  })

  it('"Keep it" closes the panel and removes nothing', async () => {
    getAccess.mockResolvedValue('open')
    render(<RemoveDocument docKey="afi99-1" onRemoved={() => {}} />)
    fireEvent.click(await screen.findByText('Remove this document…'))
    fireEvent.click(screen.getByText('Keep it'))
    expect(removeDocument).not.toHaveBeenCalled()
    expect(screen.getByText('Remove this document…')).toBeInTheDocument()
  })

  it('shows why a removal was refused, such as a job still running', async () => {
    getAccess.mockResolvedValue('open')
    removeDocument.mockRejectedValue(new admin.AdminRequestError('A job for this document is queued or running; cancel it or wait for it first.', 409, 'jobs_active'))
    const onRemoved = vi.fn()
    render(<RemoveDocument docKey="afi99-1" onRemoved={onRemoved} />)
    fireEvent.click(await screen.findByText('Remove this document…'))
    fireEvent.change(screen.getByLabelText("Type the document's name to confirm"), { target: { value: 'afi99-1' } })
    fireEvent.click(screen.getByText('Remove it'))
    await screen.findByText(/queued or running; cancel it or wait/)
    expect(onRemoved).not.toHaveBeenCalled()
  })

  it('asks for the access code first when one is needed', async () => {
    getAccess.mockResolvedValue('code')
    render(<RemoveDocument docKey="afi99-1" onRemoved={() => {}} />)
    fireEvent.click(await screen.findByText('Remove this document…'))
    expect(screen.getByLabelText('Access code')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Access code'), { target: { value: 'my-code' } })
    fireEvent.click(screen.getByText('Use this code'))
    await screen.findByText('Remove it')
    expect(admin.getAdminToken()).toBe('my-code')
    expect(removeDocument).not.toHaveBeenCalled()
  })
})
