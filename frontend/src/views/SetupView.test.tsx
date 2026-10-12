import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import SetupView from './SetupView'
import * as client from '../api/client'
import * as setup from '../api/setup'
import * as admin from '../api/admin'
import type { ConfigResponse } from '../api/types'

vi.mock('../components/AppShell', () => ({ default: ({ children }: { children: React.ReactNode }) => <div>{children}</div> }))
vi.mock('../api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('../api/client')>()
  return { ...actual, getConfig: vi.fn(), updateConfig: vi.fn() }
})
vi.mock('../api/setup', async importOriginal => {
  const actual = await importOriginal<typeof import('../api/setup')>()
  return { ...actual, checkSetup: vi.fn() }
})
vi.mock('../api/admin', async importOriginal => {
  const actual = await importOriginal<typeof import('../api/admin')>()
  return { ...actual, getAccess: vi.fn() }
})

const getConfig = vi.mocked(client.getConfig)
const updateConfig = vi.mocked(client.updateConfig)
const checkSetup = vi.mocked(setup.checkSetup)
const getAccess = vi.mocked(admin.getAccess)

function config(over: Partial<ConfigResponse['config']> = {}, env: string[] = []): ConfigResponse {
  return {
    config: {
      ollama_url: 'http://ollama:11434', qdrant_url: 'http://qdrant:6333', default_model: 'llama3.1:8b-instruct-q4_K_M', extraction_model: 'llama3.1:8b-instruct-q4_K_M',
      enrichment_model: 'llama3.1:8b-instruct-q4_K_M', rewrite_model: 'llama3.1:8b-instruct-q4_K_M', synthesis_model: 'llama3.1:8b-instruct-q4_K_M', embedding_model: 'nomic-embed-text',
      top_k: 20, min_score: 0, processed_dir: '/data/processed', authority_registry: null, synthesis_backend: 'local', remote_provider: 'anthropic', remote_model: 'claude-sonnet-4-6',
      api_key_env: 'ANTHROPIC_API_KEY', authority: {}, ...over,
    },
    env_overridden: env,
  }
}

function checked(over: Partial<setup.SetupCheck> = {}): setup.SetupCheck {
  return {
    ollama: { url: 'http://ollama:11434', ok: true, message: 'OK (2 models found)', models: ['a', 'b'] },
    qdrant: { url: 'http://qdrant:6333', ok: true, message: 'OK (1 collection)' },
    models: [
      { role: 'embedding', name: 'nomic-embed-text', needed_for: 'searching and adding documents', required: true, installed: true },
      { role: 'extraction', name: 'llama3.1:8b-instruct-q4_K_M', needed_for: 'finding the requirements when a document is added', required: true, installed: true },
      { role: 'questions', name: 'qwen2.5:14b', needed_for: 'writing draft audit questions', required: false, installed: false },
    ],
    folder: { path: '/data/processed', exists: true, writable: true, message: 'OK' },
    ready: true,
    ...over,
  }
}

function show() {
  render(<MemoryRouter><SetupView /></MemoryRouter>)
}

async function goTo(step: string) {
  fireEvent.click(await screen.findByRole('button', { name: new RegExp(step) }))
}

beforeEach(() => {
  vi.clearAllMocks()
  getConfig.mockResolvedValue(config())
  checkSetup.mockResolvedValue(checked())
  getAccess.mockResolvedValue('code')
})
afterEach(cleanup)

describe('SetupView', () => {
  it('tests the saved addresses on opening and says in words what answered', async () => {
    show()
    await screen.findByText(/Ollama: OK \(2 models found\)/)
    expect(screen.getByText(/Qdrant: OK \(1 collection\)/)).toBeInTheDocument()
    expect(checkSetup).toHaveBeenCalledWith(expect.objectContaining({ ollama_url: 'http://ollama:11434', qdrant_url: 'http://qdrant:6333' }))
  })

  it('tests what was typed, not what is saved, and shows a service that does not answer', async () => {
    show()
    const input = await screen.findByLabelText('Qdrant address')
    checkSetup.mockResolvedValue(checked({ qdrant: { url: 'http://elsewhere:6333', ok: false, message: 'Could not reach Qdrant there: connection refused' }, ready: false }))
    fireEvent.change(input, { target: { value: 'http://elsewhere:6333' } })
    fireEvent.click(screen.getByText('Test these addresses'))
    await screen.findByText(/Could not reach Qdrant there: connection refused/)
    expect(checkSetup).toHaveBeenLastCalledWith(expect.objectContaining({ qdrant_url: 'http://elsewhere:6333' }))
  })

  it('names each model, what it is for, and the exact command to install a missing one', async () => {
    show()
    await goTo('2. Models')
    const list = await screen.findByLabelText('Model checks')
    expect(within(list).getByText('Draft audit questions')).toBeInTheDocument()
    expect(within(list).getByText(/not installed · optional for writing draft audit questions/)).toBeInTheDocument()
    expect(within(list).getByText('ollama pull qwen2.5:14b')).toBeInTheDocument()
    expect(within(list).queryByText('ollama pull nomic-embed-text')).not.toBeInTheDocument() // installed ones get no command
  })

  it('says a model is unknown, not missing, when Ollama could not be asked', async () => {
    checkSetup.mockResolvedValue(checked({
      ollama: { url: 'http://ollama:11434', ok: false, message: 'Could not reach Ollama there', models: [] },
      models: [{ role: 'embedding', name: 'nomic-embed-text', needed_for: 'searching and adding documents', required: true, installed: null }],
      ready: false,
    }))
    show()
    await goTo('2. Models')
    await screen.findByText(/not known: Ollama did not answer/)
    expect(screen.queryByText(/ollama pull/)).not.toBeInTheDocument()
  })

  it('warns that a changed search model needs the library rebuilt', async () => {
    show()
    await goTo('2. Models')
    fireEvent.change(await screen.findByLabelText('Search (embedding) model'), { target: { value: 'mxbai-embed-large' } })
    await screen.findByText(/rebuild the library/i)
  })

  it('shows the remote fields only when remote answers are chosen, and never asks for the key itself', async () => {
    show()
    await goTo('3. Answers')
    expect(screen.queryByLabelText('Remote model')).not.toBeInTheDocument()
    fireEvent.click(await screen.findByLabelText(/Written by a remote service/))
    expect(screen.getByLabelText('Remote model')).toBeInTheDocument()
    expect(screen.getByLabelText('Name of the key variable')).toBeInTheDocument()
    expect(screen.getByText(/The key itself is never typed here/)).toBeInTheDocument()
  })

  it('saves only what changed', async () => {
    updateConfig.mockResolvedValue(config({ qdrant_url: 'http://elsewhere:6333' }))
    show()
    fireEvent.change(await screen.findByLabelText('Qdrant address'), { target: { value: 'http://elsewhere:6333' } })
    await goTo('5. Review')
    const changes = await screen.findByLabelText('Changes')
    expect(within(changes).getAllByRole('listitem')).toHaveLength(1)
    fireEvent.click(screen.getByText('Save these settings'))
    await waitFor(() => expect(updateConfig).toHaveBeenCalledWith({ qdrant_url: 'http://elsewhere:6333' }))
    await screen.findByText(/Saved\. Next:/)
  })

  it('has nothing to save when nothing changed', async () => {
    show()
    await goTo('5. Review')
    await screen.findByText(/Nothing has been changed/)
    expect(screen.getByText('Save these settings')).toBeDisabled()
    expect(updateConfig).not.toHaveBeenCalled()
  })

  it('shows what the server said when the save is refused', async () => {
    updateConfig.mockRejectedValue(new Error('POST /config is restricted to localhost'))
    show()
    fireEvent.change(await screen.findByLabelText('Ollama address'), { target: { value: 'http://other:11434' } })
    await goTo('5. Review')
    fireEvent.click(await screen.findByText('Save these settings'))
    await screen.findByText(/restricted to localhost/)
    expect(screen.queryByText(/Saved\. Next:/)).not.toBeInTheDocument()
  })

  it('leaves a value set by an environment variable alone', async () => {
    getConfig.mockResolvedValue(config({}, ['qdrant_url']))
    show()
    const input = await screen.findByLabelText('Qdrant address')
    expect(input).toBeDisabled()
    expect(screen.getByText(/REQBOT_QDRANT_URL environment variable/)).toBeInTheDocument()
  })

  it('shows the folder and gives the command for each admin protection state, without a way to change it from the page', async () => {
    getAccess.mockResolvedValue('unconfigured')
    show()
    await goTo('4. Folder and protection')
    await screen.findByText('/data/processed')
    expect(screen.getByText('reqbot token')).toBeInTheDocument()
    expect(screen.getByText('reqbot token --open')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /turn on|enable|switch/i })).not.toBeInTheDocument()
    getAccess.mockResolvedValue('open')
    fireEvent.click(screen.getByText('Check again'))
    await screen.findByText('reqbot token --require')
  })

  it('says setup is for the server machine when the check is refused', async () => {
    checkSetup.mockRejectedValue(new Error('Setup can only be changed from the server machine itself. Open this page on the machine that runs ReqBot.'))
    show()
    await screen.findByText(/only be changed from the server machine itself/)
  })
})
