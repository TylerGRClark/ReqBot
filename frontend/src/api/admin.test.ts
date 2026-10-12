import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  AdminAuthError,
  AdminDisabledError,
  AdminRequestError,
  clearAdminToken,
  describeError,
  getAccess,
  getAdminToken,
  listJobs,
  setAdminToken,
  startIngest,
} from './admin'

function reply(status: number, body: unknown) {
  return Promise.resolve({ ok: status >= 200 && status < 300, status, statusText: '', json: () => Promise.resolve(body) } as Response)
}

beforeEach(() => {
  window.localStorage.clear()
})
afterEach(() => {
  vi.restoreAllMocks()
})

describe('the saved code', () => {
  it('is kept trimmed, read back, and cleared', () => {
    expect(getAdminToken()).toBe('')
    setAdminToken('  abc123  ')
    expect(getAdminToken()).toBe('abc123')
    clearAdminToken()
    expect(getAdminToken()).toBe('')
  })

  it('does not break when storage is blocked', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('blocked') })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('blocked') })
    expect(getAdminToken()).toBe('')
    expect(() => setAdminToken('x')).not.toThrow()
  })
})

describe('describeError', () => {
  it('reads a string, a {code, message} object, a validation list, and falls back', () => {
    expect(describeError(401, { detail: 'An admin access code is required.' }, 'x')).toEqual({ message: 'An admin access code is required.', code: '' })
    expect(describeError(415, { detail: { code: 'not_pdf', message: 'Not a PDF' } }, 'x')).toEqual({ message: 'Not a PDF', code: 'not_pdf' })
    expect(describeError(422, { detail: [{ msg: 'field required' }] }, 'x').message).toBe('field required')
    expect(describeError(500, null, 'jobs failed').message).toBe('jobs failed (500)')
  })
})

describe('requests', () => {
  it('sends the saved code as a bearer header and checks the shape of the answer', async () => {
    setAdminToken('secret-code')
    const spy = vi.spyOn(globalThis, 'fetch').mockImplementation(() => reply(200, { jobs: [], running: null, queued: 0 }))
    await expect(listJobs()).resolves.toEqual({ jobs: [], running: null, queued: 0 })
    const init = spy.mock.calls[0][1] as RequestInit
    expect((init.headers as Record<string, string>).Authorization).toBe('Bearer secret-code')
  })

  it('sends no header when no code is saved (trusted-network mode)', async () => {
    const spy = vi.spyOn(globalThis, 'fetch').mockImplementation(() => reply(200, { jobs: [], running: null, queued: 0 }))
    await listJobs()
    expect((spy.mock.calls[0][1] as RequestInit).headers as Record<string, string>).not.toHaveProperty('Authorization')
  })

  it('maps 401 to a code problem and a 403 about the code to "switched off"', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => reply(401, { detail: 'The admin access code is not correct.' }))
    await expect(listJobs()).rejects.toBeInstanceOf(AdminAuthError)
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => reply(403, { detail: 'No admin access code is configured on this server. Run `reqbot token`.' }))
    await expect(listJobs()).rejects.toBeInstanceOf(AdminDisabledError)
  })

  it('keeps the stable code of a refusal, such as the same-name question', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(() =>
      reply(409, { detail: { code: 'same_name_different_content', message: 'Replace it, or keep both?', options: ['replace', 'keep_both'] } }))
    const err = await startIngest('UP-20261012-010101-abcdef').catch(e => e)
    expect(err).toBeInstanceOf(AdminRequestError)
    expect(err.status).toBe(409)
    expect(err.code).toBe('same_name_different_content')
  })

  it('fails closed on an answer of the wrong shape', async () => {
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => reply(200, { jobs: 'nope' }))
    await expect(listJobs()).rejects.toThrow(/did not match/)
  })

  it('reads the access mode from the public route', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => reply(200, { admin: 'open' }))
    await expect(getAccess()).resolves.toBe('open')
  })
})
