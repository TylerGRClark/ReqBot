/**
 * First-run setup calls (docs/WEB_UI_PARITY_PLAN.md, section 9a). Both are read-only: saving what the wizard collects goes through `updateConfig` in client.ts, and
 * admin protection is switched with `reqbot token` on the server, never from the page.
 */
import { z } from 'zod'

const BASE = '/api'

const stateSchema = z.object({
  config_file: z.boolean(),
  needs_setup: z.boolean(),
  questions_model: z.string(),
})

const modelSchema = z.object({
  role: z.string(),
  name: z.string(),
  needed_for: z.string(),
  required: z.boolean(),
  installed: z.boolean().nullable(), // null: the model machine could not be asked
})

const checkSchema = z.object({
  ollama: z.object({ url: z.string(), ok: z.boolean(), message: z.string(), models: z.array(z.string()) }),
  qdrant: z.object({ url: z.string(), ok: z.boolean(), message: z.string() }),
  models: z.array(modelSchema),
  folder: z.object({ path: z.string(), exists: z.boolean(), writable: z.boolean(), message: z.string() }),
  ready: z.boolean(),
})

export type SetupState = z.infer<typeof stateSchema>
export type SetupCheck = z.infer<typeof checkSchema>
export type SetupModel = z.infer<typeof modelSchema>

/** The values the wizard tests; anything left out is taken from the saved configuration. */
export interface SetupValues {
  ollama_url?: string
  qdrant_url?: string
  embedding_model?: string
  default_model?: string
  synthesis_model?: string
  synthesis_backend?: 'local' | 'remote' | 'none'
}

function parse<T>(schema: z.ZodType<T>, data: unknown, label: string): T {
  const r = schema.safeParse(data)
  if (!r.success) {
    console.warn(`${label} response failed schema validation`, r.error)
    throw new Error(`${label} response did not match the expected shape — see console for details`)
  }
  return r.data
}

export async function getSetupState(): Promise<SetupState> {
  const res = await fetch(`${BASE}/setup`)
  if (!res.ok) throw new Error(`setup state failed: ${res.status} ${res.statusText}`)
  return parse(stateSchema, await res.json(), 'setup state')
}

export async function checkSetup(values: SetupValues): Promise<SetupCheck> {
  const res = await fetch(`${BASE}/setup/check`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(values),
  })
  if (res.status === 403) throw new Error('Setup can only be changed from the server machine itself. Open this page on the machine that runs ReqBot.')
  if (!res.ok) throw new Error(`setup check failed: ${res.status} ${res.statusText}`)
  return parse(checkSchema, await res.json(), 'setup check')
}
