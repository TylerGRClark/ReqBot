import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, waitFor } from '@testing-library/react'
import App from './App'
import * as client from './api/client'
import * as admin from './api/admin'
import * as setup from './api/setup'

vi.mock('./api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('./api/client')>()
  return { ...actual, docs: vi.fn(), status: vi.fn() }
})
vi.mock('./api/admin', async importOriginal => {
  const actual = await importOriginal<typeof import('./api/admin')>()
  return { ...actual, getAccess: vi.fn(), listJobs: vi.fn() }
})
vi.mock('./api/setup', async importOriginal => {
  const actual = await importOriginal<typeof import('./api/setup')>()
  return { ...actual, getSetupState: vi.fn() }
})

beforeEach(() => {
  vi.mocked(client.docs).mockResolvedValue({ docs: [], total_reqs: 0, total_docs: 0 } as never)
  vi.mocked(client.status).mockResolvedValue({ ollama: { reachable: true, models: [] }, qdrant: { reachable: true, collections: [] } } as never)
  vi.mocked(admin.getAccess).mockResolvedValue('unconfigured')
  vi.mocked(admin.listJobs).mockResolvedValue({ jobs: [], running: null, queued: 0 })
  vi.mocked(setup.getSetupState).mockResolvedValue({ config_file: true, needs_setup: false, questions_model: 'q' })
})
afterEach(() => {
  cleanup()
  window.history.pushState({}, '', '/')
})

describe('the Library used to be the Corpus', () => {
  it('sends an old /corpus address to /library', async () => {
    window.history.pushState({}, '', '/corpus')
    render(<App />)
    await waitFor(() => expect(window.location.pathname).toBe('/library'))
  })

  it('sends an old document address to the same document under /library', async () => {
    window.history.pushState({}, '', '/corpus/test-policy-99-1')
    render(<App />)
    await waitFor(() => expect(window.location.pathname).toBe('/library/test-policy-99-1'))
  })

  it('sends the older /docs bookmark to /library', async () => {
    window.history.pushState({}, '', '/docs')
    render(<App />)
    await waitFor(() => expect(window.location.pathname).toBe('/library'))
  })
})
