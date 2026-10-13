/**
 * The admin side of the API (docs/WEB_UI_PARITY_PLAN.md, stage 4): which way admin actions are protected, uploads, the inbox, ingest jobs.
 *
 * Every call here except getAccess() goes to a route that needs the admin access code (or none, when the server was put in
 * trusted-network mode). The code lives in this browser's localStorage after the person pastes it once; it is never sent anywhere
 * but as an Authorization header to this server, and no API route ever returns it. Storage can be blocked (private windows), so
 * every read and write is wrapped and the page works without it (the code is then asked for each session).
 */
import { z } from 'zod'

const BASE = '/api'
const TOKEN_KEY = 'reqbot.adminToken'

export type AdminMode = 'unconfigured' | 'code' | 'open'
export type IfExists = 'ask' | 'replace' | 'keep_both'
export type JobState = 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled' | 'interrupted'

/** The server says admin actions are switched off (no code configured and not in trusted-network mode). */
export class AdminDisabledError extends Error {
  constructor(message = 'Adding documents from the browser is switched off on this server.') {
    super(message)
    this.name = 'AdminDisabledError'
  }
}

/** The admin access code is missing or wrong. */
export class AdminAuthError extends Error {
  constructor(message = 'The admin access code is required.') {
    super(message)
    this.name = 'AdminAuthError'
  }
}

/** The server refused or failed a request; `code` is the stable machine name when it sent one (not_pdf, too_large, ...). */
export class AdminRequestError extends Error {
  status: number
  code: string
  constructor(message: string, status: number, code = '') {
    super(message)
    this.name = 'AdminRequestError'
    this.status = status
    this.code = code
  }
}

// ── The code, kept in this browser ───────────────────────────────────────────

export function getAdminToken(): string {
  try {
    return window.localStorage.getItem(TOKEN_KEY) ?? ''
  } catch {
    return ''
  }
}

export function setAdminToken(token: string): void {
  try {
    window.localStorage.setItem(TOKEN_KEY, token.trim())
  } catch {
    /* storage blocked: the code is asked for again next time */
  }
}

export function clearAdminToken(): void {
  try {
    window.localStorage.removeItem(TOKEN_KEY)
  } catch {
    /* nothing to clear */
  }
}

function authHeaders(): Record<string, string> {
  const token = getAdminToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

// ── Shapes (checked at runtime, like the evidence and config responses) ───────────

const accessSchema = z.object({ admin: z.enum(['unconfigured', 'code', 'open']) })

const progressSchema = z
  .object({ step: z.string(), done: z.number().optional(), total: z.number().optional(), at: z.string().optional() })
  .nullable()

export const jobSummarySchema = z.object({
  id: z.string(),
  kind: z.string(),
  title: z.string(),
  state: z.enum(['queued', 'running', 'succeeded', 'failed', 'cancelled', 'interrupted']),
  attempt: z.number().nullish(),
  command: z.string().nullish(),
  created_at: z.string().nullish(),
  started_at: z.string().nullish(),
  finished_at: z.string().nullish(),
  progress: progressSchema.nullish(),
  error: z.string().nullish(),
  exit_code: z.number().nullish(),
  run_dir: z.string().nullish(),
  requested_by: z.string().nullish(),
  retry_of: z.string().nullish(),
  cancel_requested: z.boolean().nullish(),
  /** What a screen matches a job to its document by (`doc_key` for draft questions, `requirements_only` for a rebuild). */
  params: z.record(z.string(), z.unknown()).nullish(),
})

const jobsSchema = z.object({
  jobs: z.array(jobSummarySchema),
  running: z.string().nullable(),
  queued: z.number(),
})

const jobDetailSchema = jobSummarySchema.extend({ log_tail: z.string() })

const librarySchema = z.object({
  status: z.enum(['new', 'same_content', 'same_content_other_name', 'same_name_different_content', 'queued']),
  document: z.string().nullish(),
  job_id: z.string().nullish(),
})

const uploadSchema = z.object({
  upload_id: z.string(),
  filename: z.string(),
  stem: z.string(),
  size: z.number(),
  pages: z.number(),
  sha256: z.string(),
  library: librarySchema,
})

const startSchema = z.object({
  result: z.enum(['queued', 'skipped']),
  document: z.string().nullish(),
  reason: z.string().nullish(),
  message: z.string().nullish(),
  job_id: z.string().nullish(),
  job: jobSummarySchema.nullish(),
})

const queueSchema = z.object({
  result: z.enum(['queued', 'skipped']),
  job: jobSummarySchema.nullish(),
  reason: z.string().nullish(),
  job_id: z.string().nullish(),
  message: z.string().nullish(),
})

const removedSchema = z.object({
  document: z.string(),
  run_folders_moved: z.array(z.string()),
  files_moved: z.number().nullish(),
  trash: z.string(),
  points_removed: z.object({ requirements: z.number(), context: z.number() }),
})

const inboxSchema = z.object({
  folder: z.string(),
  exists: z.boolean(),
  truncated: z.boolean(),
  files: z.array(
    z.object({
      name: z.string(),
      size: z.number(),
      status: z.enum(['new', 'same_content', 'same_content_other_name', 'same_name_different_content', 'queued']),
      document: z.string().nullish(),
    }),
  ),
})

const inboxImportSchema = z.object({
  queued: z.number(),
  results: z.array(
    z.object({
      file: z.string(),
      result: z.enum(['queued', 'skipped', 'needs_decision', 'refused']),
      reason: z.string().nullish(),
      code: z.string().nullish(),
      message: z.string().nullish(),
      document: z.string().nullish(),
    }),
  ),
})

export type JobSummary = z.infer<typeof jobSummarySchema>
export type JobDetail = z.infer<typeof jobDetailSchema>
export type JobsResponse = z.infer<typeof jobsSchema>
export type UploadResponse = z.infer<typeof uploadSchema>
export type StartResponse = z.infer<typeof startSchema>
export type QueueResponse = z.infer<typeof queueSchema>
export type RemovedResponse = z.infer<typeof removedSchema>
export type InboxResponse = z.infer<typeof inboxSchema>
export type InboxImportResponse = z.infer<typeof inboxImportSchema>
export type LibraryStanding = z.infer<typeof librarySchema>

// ── Requests ─────────────────────────────────────────────────────────────

/** `detail` is a string, or {code, message} from the intake routes, or a list from a validation error. */
export function describeError(status: number, body: unknown, fallback: string): { message: string; code: string } {
  const detail = (body as { detail?: unknown } | null)?.detail
  if (typeof detail === 'string' && detail) return { message: detail, code: '' }
  if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
    const d = detail as { code?: unknown; message?: unknown }
    return { message: typeof d.message === 'string' && d.message ? d.message : fallback, code: typeof d.code === 'string' ? d.code : '' }
  }
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as { msg?: unknown }
    return { message: typeof first?.msg === 'string' ? first.msg : fallback, code: '' }
  }
  return { message: `${fallback} (${status})`, code: '' }
}

function raise(status: number, body: unknown, label: string): never {
  const { message, code } = describeError(status, body, `${label} failed`)
  if (status === 401) throw new AdminAuthError(message)
  if (status === 403 && /access code/i.test(message)) throw new AdminDisabledError(message)
  throw new AdminRequestError(message, status, code)
}

async function request<T>(schema: z.ZodType<T>, label: string, path: string, init: RequestInit = {}): Promise<{ status: number; data: T }> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { ...(init.body ? { 'Content-Type': 'application/json' } : {}), ...authHeaders(), ...(init.headers as Record<string, string> | undefined) },
  })
  const body: unknown = await res.json().catch(() => null)
  if (!res.ok) raise(res.status, body, label)
  const parsed = schema.safeParse(body)
  if (!parsed.success) {
    console.warn(`${label} response failed schema validation`, parsed.error)
    throw new Error(`${label} response did not match the expected shape — see console for details`)
  }
  return { status: res.status, data: parsed.data }
}

export async function getAccess(): Promise<AdminMode> {
  const res = await fetch(`${BASE}/access`)
  if (!res.ok) throw new Error(`access failed: ${res.status} ${res.statusText}`)
  const parsed = accessSchema.safeParse(await res.json())
  if (!parsed.success) throw new Error('access response did not match the expected shape')
  return parsed.data.admin
}

/**
 * How many of the newest jobs the page asks for (the server's most is 200; its default is 50). A folder of PDFs queues one job each, and the rows in the add panel that
 * follow those jobs have to find theirs.
 */
export const JOB_WINDOW = 200

export async function listJobs(limit: number = JOB_WINDOW): Promise<JobsResponse> {
  return (await request(jobsSchema, 'jobs', `/jobs?limit=${limit}`)).data
}

export async function getJob(id: string): Promise<JobDetail> {
  return (await request(jobDetailSchema, 'job', `/jobs/${encodeURIComponent(id)}`)).data
}

export async function cancelJob(id: string): Promise<JobSummary> {
  return (await request(jobSummarySchema, 'cancel', `/jobs/${encodeURIComponent(id)}/cancel`, { method: 'POST' })).data
}

export async function retryJob(id: string): Promise<JobSummary> {
  return (await request(jobSummarySchema, 'retry', `/jobs/${encodeURIComponent(id)}/retry`, { method: 'POST' })).data
}

/** Write draft audit questions for one document, as a job. `skipped` means one is already queued or running for it. */
export async function startQuestions(docKey: string, profile = 'cybersecurity'): Promise<QueueResponse> {
  return (await request(queueSchema, 'questions', '/jobs/questions', { method: 'POST', body: JSON.stringify({ doc_key: docKey, profile }) })).data
}

/** Rebuild the search library from the saved documents, as a job. `skipped` means a rebuild is already queued or running. */
export async function startReindex(requirementsOnly = false): Promise<QueueResponse> {
  return (await request(queueSchema, 'rebuild', '/jobs/reindex', { method: 'POST', body: JSON.stringify({ requirements_only: requirementsOnly }) })).data
}

/** Take a document out of the library. The server refuses unless `confirmName` repeats the document's exact key; its run folders go to a trash folder, nothing is deleted. */
export async function removeDocument(docKey: string, confirmName: string): Promise<RemovedResponse> {
  const body = { doc_key: docKey, confirm: true, confirm_name: confirmName }
  return (await request(removedSchema, 'removal', '/documents/remove', { method: 'POST', body: JSON.stringify(body) })).data
}

export async function getInbox(): Promise<InboxResponse> {
  return (await request(inboxSchema, 'inbox', '/inbox')).data
}

/** Start one ingest per PDF in the inbox (all of them when `files` is null). */
export async function importInbox(files: string[] | null, ifExists: IfExists = 'ask', thenQuestions = false): Promise<InboxImportResponse> {
  const body = { files, if_exists: ifExists, then_questions: thenQuestions }
  return (await request(inboxImportSchema, 'inbox import', '/jobs/inbox', { method: 'POST', body: JSON.stringify(body) })).data
}

/**
 * Start the pipeline for an uploaded PDF. Resolves with the result, or rejects with an AdminRequestError whose code is
 * `same_name_different_content` (status 409) when the name is already in the library with other content and `ifExists` is 'ask'.
 */
export async function startIngest(uploadId: string, ifExists: IfExists = 'ask', thenQuestions = false): Promise<StartResponse> {
  const body = { upload_id: uploadId, if_exists: ifExists, then_questions: thenQuestions }
  return (await request(startSchema, 'start', '/jobs/ingest', { method: 'POST', body: JSON.stringify(body) })).data
}

/**
 * Send one PDF as the raw request body. XMLHttpRequest rather than fetch because only it reports upload progress.
 * `onProgress` gets a fraction from 0 to 1.
 */
export function uploadPdf(file: File, onProgress?: (fraction: number) => void): Promise<UploadResponse> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', `${BASE}/uploads?filename=${encodeURIComponent(file.name)}`)
    xhr.setRequestHeader('Content-Type', 'application/pdf')
    const token = getAdminToken()
    if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`)
    xhr.upload.onprogress = e => {
      if (onProgress && e.lengthComputable && e.total > 0) onProgress(e.loaded / e.total)
    }
    xhr.onerror = () => reject(new Error('The upload could not reach the server.'))
    xhr.onload = () => {
      let body: unknown = null
      try {
        body = JSON.parse(xhr.responseText)
      } catch {
        body = null
      }
      if (xhr.status < 200 || xhr.status >= 300) {
        try {
          raise(xhr.status, body, 'upload')
        } catch (e) {
          reject(e)
        }
        return
      }
      const parsed = uploadSchema.safeParse(body)
      if (!parsed.success) {
        reject(new Error('upload response did not match the expected shape'))
        return
      }
      resolve(parsed.data)
    }
    xhr.send(file)
  })
}
