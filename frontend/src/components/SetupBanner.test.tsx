import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import SetupBanner from './SetupBanner'
import * as setup from '../api/setup'

vi.mock('../api/setup', async importOriginal => {
  const actual = await importOriginal<typeof import('../api/setup')>()
  return { ...actual, getSetupState: vi.fn() }
})
const getSetupState = vi.mocked(setup.getSetupState)

function show(path = '/search') {
  render(<MemoryRouter initialEntries={[path]}><SetupBanner /></MemoryRouter>)
}

beforeEach(() => vi.clearAllMocks())
afterEach(cleanup)

describe('SetupBanner', () => {
  it('points to the setup until a configuration has been saved', async () => {
    getSetupState.mockResolvedValue({ config_file: false, needs_setup: true, questions_model: 'qwen2.5:14b' })
    show()
    const link = await screen.findByText('Start the setup')
    expect(link.closest('a')).toHaveAttribute('href', '/setup')
  })

  it('shows nothing once it has been set up', async () => {
    getSetupState.mockResolvedValue({ config_file: true, needs_setup: false, questions_model: 'qwen2.5:14b' })
    const { container } = render(<MemoryRouter><SetupBanner /></MemoryRouter>)
    await waitFor(() => expect(getSetupState).toHaveBeenCalled())
    expect(container).toBeEmptyDOMElement()
  })

  it('shows nothing on the setup page itself, or when the server cannot be asked', async () => {
    getSetupState.mockResolvedValue({ config_file: false, needs_setup: true, questions_model: 'q' })
    show('/setup')
    await waitFor(() => expect(getSetupState).toHaveBeenCalled())
    expect(screen.queryByText('Start the setup')).not.toBeInTheDocument()
    cleanup()
    getSetupState.mockRejectedValue(new Error('down'))
    show()
    await waitFor(() => expect(getSetupState).toHaveBeenCalled())
    expect(screen.queryByText('Start the setup')).not.toBeInTheDocument()
  })
})
