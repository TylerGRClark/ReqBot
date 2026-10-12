import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import * as api from '../api/client'
import type { ConfigResponse, ConfigUpdateRequest } from '../api/types'
import { getAccess } from '../api/admin'
import type { AdminMode } from '../api/admin'
import { checkSetup } from '../api/setup'
import type { SetupCheck, SetupValues } from '../api/setup'
import AppShell from '../components/AppShell'
import LoadingSpinner from '../components/LoadingSpinner'
import ErrorBanner from '../components/ErrorBanner'

type Backend = 'local' | 'remote' | 'none'
type Provider = 'anthropic' | 'openai'

interface Form {
  ollama_url: string
  qdrant_url: string
  embedding_model: string
  default_model: string
  synthesis_backend: Backend
  synthesis_model: string
  remote_provider: Provider
  remote_model: string
  api_key_env: string
}

const STEPS = ['Services', 'Models', 'Answers', 'Folder and protection', 'Review'] as const

function toForm(cfg: ConfigResponse['config']): Form {
  return {
    ollama_url: cfg.ollama_url,
    qdrant_url: cfg.qdrant_url,
    embedding_model: cfg.embedding_model,
    default_model: cfg.default_model,
    synthesis_backend: (['local', 'remote', 'none'] as const).find(b => b === cfg.synthesis_backend) ?? 'local',
    synthesis_model: cfg.synthesis_model,
    remote_provider: cfg.remote_provider === 'openai' ? 'openai' : 'anthropic',
    remote_model: cfg.remote_model,
    api_key_env: cfg.api_key_env,
  }
}

const LABELS: Record<keyof Form, string> = {
  ollama_url: 'Ollama address',
  qdrant_url: 'Qdrant address',
  embedding_model: 'Search (embedding) model',
  default_model: 'Main model',
  synthesis_backend: 'Written answers',
  synthesis_model: 'Answer-writing model',
  remote_provider: 'Remote provider',
  remote_model: 'Remote model',
  api_key_env: 'Name of the key variable',
}

const ROLE_LABELS: Record<string, string> = {
  embedding: 'Search',
  extraction: 'Finding requirements',
  rewrite: 'Understanding questions',
  questions: 'Draft audit questions',
  synthesis: 'Written answers',
}

const BACKEND_WORDS: Record<Backend, string> = {
  local: 'Written by Ollama on your own machine',
  remote: 'Written by a remote service (Claude or GPT)',
  none: 'Retrieval only: passages and citations, no written answer',
}

function diff(form: Form, baseline: Form): ConfigUpdateRequest {
  const out: ConfigUpdateRequest = {}
  for (const key of Object.keys(form) as (keyof Form)[]) {
    if (form[key] !== baseline[key]) (out as Record<string, string>)[key] = form[key]
  }
  return out
}

function Mark({ ok }: { ok: boolean | null }) {
  if (ok === null) return <span className="text-gray-400" aria-label="unknown">?</span>
  return ok ? <span className="text-green-700" aria-label="ok">✓</span> : <span className="text-red-700" aria-label="problem">✗</span>
}

function Command({ children }: { children: string }) {
  return <code className="block mt-1 bg-gray-100 border border-gray-200 rounded px-2 py-1 text-xs font-mono text-gray-800 select-all">{children}</code>
}

export default function SetupView() {
  const [baseline, setBaseline] = useState<Form | null>(null)
  const [form, setForm] = useState<Form | null>(null)
  const [envOverridden, setEnvOverridden] = useState<string[]>([])
  const [loadError, setLoadError] = useState<string | null>(null)
  const [step, setStep] = useState(0)
  const [check, setCheck] = useState<SetupCheck | null>(null)
  const [checking, setChecking] = useState(false)
  const [checkError, setCheckError] = useState<string | null>(null)
  const [access, setAccess] = useState<AdminMode | null>(null)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  const values = useCallback((f: Form): SetupValues => ({
    ollama_url: f.ollama_url,
    qdrant_url: f.qdrant_url,
    embedding_model: f.embedding_model,
    default_model: f.default_model,
    synthesis_model: f.synthesis_model,
    synthesis_backend: f.synthesis_backend,
  }), [])

  const runCheck = useCallback(async (f: Form) => {
    setChecking(true)
    setCheckError(null)
    try {
      setCheck(await checkSetup(values(f)))
    } catch (e) {
      setCheck(null)
      setCheckError(e instanceof Error ? e.message : 'The check did not work.')
    } finally {
      setChecking(false)
    }
  }, [values])

  useEffect(() => {
    let alive = true
    api.getConfig()
      .then(res => {
        if (!alive) return
        const f = toForm(res.config)
        setBaseline(f)
        setForm(f)
        setEnvOverridden(res.env_overridden)
        void runCheck(f)
      })
      .catch((e: unknown) => { if (alive) setLoadError(e instanceof Error ? e.message : 'Could not load the configuration') })
    getAccess().then(m => { if (alive) setAccess(m) }).catch(() => { if (alive) setAccess(null) })
    return () => { alive = false }
  }, [runCheck])

  const changes = useMemo(() => (form && baseline ? diff(form, baseline) : {}), [form, baseline])
  const changedKeys = Object.keys(changes) as (keyof Form)[]

  function set<K extends keyof Form>(key: K, value: Form[K]) {
    setForm(prev => (prev ? { ...prev, [key]: value } : prev))
    setSaved(false)
  }

  async function save() {
    if (!form || !baseline) return
    setSaving(true)
    setSaveError(null)
    try {
      const res = await api.updateConfig(changes)
      const f = toForm(res.config)
      setBaseline(f)
      setForm(f)
      setEnvOverridden(res.env_overridden)
      setSaved(true)
      void runCheck(f)
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : 'The settings were not saved.')
    } finally {
      setSaving(false)
    }
  }

  function field(key: keyof Form, opts: { mono?: boolean } = {}) {
    if (!form) return null
    const fromEnv = envOverridden.includes(key)
    return (
      <label className="block">
        <span className="text-sm font-medium text-gray-700">{LABELS[key]}</span>
        <input
          value={form[key]}
          onChange={e => set(key, e.target.value as never)}
          disabled={fromEnv}
          aria-label={LABELS[key]}
          className={`mt-1 w-full border border-gray-300 rounded px-3 py-1.5 text-sm ${opts.mono ? 'font-mono' : ''} disabled:bg-gray-100 disabled:text-gray-500`}
        />
        {fromEnv && <span className="text-xs text-gray-500">Set by the REQBOT_{key.toUpperCase()} environment variable on the server, so it cannot be changed here.</span>}
      </label>
    )
  }

  if (loadError) return <AppShell><main className="max-w-2xl mx-auto px-6 py-8"><ErrorBanner message={loadError} /></main></AppShell>
  if (!form || !baseline) return <AppShell><main className="max-w-2xl mx-auto px-6 py-8"><LoadingSpinner /></main></AppShell>

  const embeddingChanged = form.embedding_model !== baseline.embedding_model

  return (
    <AppShell>
      <main className="max-w-2xl mx-auto px-6 py-8 space-y-6">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Set up ReqBot</h1>
          <p className="text-sm text-gray-600 mt-1">
            Five short steps. Nothing is changed until the last one, and you can run this again any time. It does the same job as <span className="font-mono">reqbot init</span> on the command line.
          </p>
        </div>

        <ol className="flex flex-wrap gap-2 text-xs" aria-label="Steps">
          {STEPS.map((title, i) => (
            <li key={title}>
              <button
                onClick={() => setStep(i)}
                aria-current={i === step ? 'step' : undefined}
                className={`px-2.5 py-1 rounded-full border ${i === step ? 'bg-blue-600 border-blue-600 text-white' : 'bg-white border-gray-300 text-gray-700 hover:bg-gray-50'}`}
              >
                {i + 1}. {title}
              </button>
            </li>
          ))}
        </ol>

        {checkError && <ErrorBanner message={checkError} />}

        {step === 0 && (
          <section aria-label="Services" className="space-y-4">
            <p className="text-sm text-gray-700">
              ReqBot needs two services that are already running somewhere it can reach: <strong>Ollama</strong> (runs the language models) and <strong>Qdrant</strong> (the
              search database). It does not install or start them.
            </p>
            {field('ollama_url', { mono: true })}
            {field('qdrant_url', { mono: true })}
            <button onClick={() => void runCheck(form)} disabled={checking} className="text-sm bg-white border border-gray-300 text-gray-700 rounded-lg px-3 py-1.5 hover:bg-gray-50 disabled:opacity-50">
              {checking ? 'Testing…' : 'Test these addresses'}
            </button>
            {check && (
              <ul className="space-y-1 text-sm">
                <li><Mark ok={check.ollama.ok} /> Ollama: {check.ollama.message}</li>
                <li><Mark ok={check.qdrant.ok} /> Qdrant: {check.qdrant.message}</li>
              </ul>
            )}
          </section>
        )}

        {step === 1 && (
          <section aria-label="Models" className="space-y-4">
            <p className="text-sm text-gray-700">These are the models ReqBot will ask Ollama for. A model that is not installed is installed on the machine that runs Ollama.</p>
            {field('embedding_model', { mono: true })}
            {embeddingChanged && (
              <p className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded px-3 py-2">
                The library was built with <span className="font-mono">{baseline.embedding_model}</span>. After saving, rebuild the library (System page) so searches use the new one.
              </p>
            )}
            {field('default_model', { mono: true })}
            <button onClick={() => void runCheck(form)} disabled={checking} className="text-sm bg-white border border-gray-300 text-gray-700 rounded-lg px-3 py-1.5 hover:bg-gray-50 disabled:opacity-50">
              {checking ? 'Checking…' : 'Check the models'}
            </button>
            {check && (
              <ul className="space-y-3 text-sm" aria-label="Model checks">
                {check.models.map(m => (
                  <li key={m.role}>
                    <div>
                      <Mark ok={m.installed} /> <span className="font-medium">{ROLE_LABELS[m.role] ?? m.role}</span>:{' '}
                      <span className="font-mono">{m.name || '(not set)'}</span>{' '}
                      <span className="text-xs text-gray-500">
                        {m.installed === true ? 'installed' : m.installed === false ? 'not installed' : 'not known: Ollama did not answer'} · {m.required ? 'needed' : 'optional'} for {m.needed_for}
                      </span>
                    </div>
                    {m.installed === false && m.name && (
                      <div className="ml-5 text-xs text-gray-600">
                        On the machine that runs Ollama:
                        <Command>{`ollama pull ${m.name}`}</Command>
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </section>
        )}

        {step === 2 && (
          <section aria-label="Answers" className="space-y-4">
            <p className="text-sm text-gray-700">
              Search, checklists and evidence always work. This only decides who writes the sentence-style answer in Ask. A remote service is sent only your question and the
              retrieved passages, never whole documents.
            </p>
            <fieldset className="space-y-2">
              <legend className="text-sm font-medium text-gray-700">{LABELS.synthesis_backend}</legend>
              {(['local', 'remote', 'none'] as const).map(b => (
                <label key={b} className="flex items-start gap-2 text-sm text-gray-800">
                  <input type="radio" name="backend" checked={form.synthesis_backend === b} onChange={() => set('synthesis_backend', b)} disabled={envOverridden.includes('synthesis_backend')} />
                  <span>{BACKEND_WORDS[b]}</span>
                </label>
              ))}
            </fieldset>
            {form.synthesis_backend === 'local' && field('synthesis_model', { mono: true })}
            {form.synthesis_backend === 'remote' && (
              <div className="space-y-3">
                <label className="block">
                  <span className="text-sm font-medium text-gray-700">{LABELS.remote_provider}</span>
                  <select
                    value={form.remote_provider}
                    onChange={e => set('remote_provider', e.target.value === 'openai' ? 'openai' : 'anthropic')}
                    aria-label={LABELS.remote_provider}
                    className="mt-1 w-full border border-gray-300 rounded px-3 py-1.5 text-sm"
                  >
                    <option value="anthropic">Anthropic (Claude)</option>
                    <option value="openai">OpenAI (GPT)</option>
                  </select>
                </label>
                {field('remote_model', { mono: true })}
                {field('api_key_env', { mono: true })}
                <p className="text-xs text-gray-600">The key itself is never typed here. Set that environment variable on the server before starting ReqBot.</p>
              </div>
            )}
          </section>
        )}

        {step === 3 && (
          <section aria-label="Folder and protection" className="space-y-5">
            <div className="space-y-1">
              <h2 className="text-sm font-semibold text-gray-800">Where documents are kept</h2>
              {check ? (
                <>
                  <p className="text-sm"><Mark ok={check.folder.writable} /> <span className="font-mono">{check.folder.path}</span></p>
                  <p className="text-xs text-gray-600">{check.folder.message}</p>
                </>
              ) : (
                <p className="text-xs text-gray-600">Not checked yet.</p>
              )}
              <p className="text-xs text-gray-500">To use a different folder, set <span className="font-mono">REQBOT_PROCESSED_DIR</span> on the server or run <span className="font-mono">reqbot init</span>. This page does not change it, on purpose.</p>
            </div>

            <div className="space-y-1">
              <h2 className="text-sm font-semibold text-gray-800">Who can add and remove documents</h2>
              {access === null && <p className="text-xs text-gray-600">The server did not say.</p>}
              {access === 'unconfigured' && (
                <>
                  <p className="text-sm text-gray-700">Adding documents from this page is switched off. Choose one, on the server:</p>
                  <p className="text-xs text-gray-600 mt-2">An access code that admins paste once (recommended; the command prints the code):</p>
                  <Command>reqbot token</Command>
                  <p className="text-xs text-gray-600 mt-2">Or trusted network: anyone who can reach this server may add documents, and no code is asked for:</p>
                  <Command>reqbot token --open</Command>
                </>
              )}
              {access === 'code' && (
                <>
                  <p className="text-sm text-gray-700"><Mark ok /> An access code is required. To see it, on the server:</p>
                  <Command>reqbot token</Command>
                </>
              )}
              {access === 'open' && (
                <>
                  <p className="text-sm text-gray-700"><Mark ok /> Trusted-network mode is on: no code is asked for. To require a code again, on the server:</p>
                  <Command>reqbot token --require</Command>
                </>
              )}
              <p className="text-xs text-gray-500">This is only ever switched on the server itself, never from a web page.</p>
              <button onClick={() => void getAccess().then(setAccess).catch(() => setAccess(null))} className="text-xs text-blue-700 underline">Check again</button>
            </div>
          </section>
        )}

        {step === 4 && (
          <section aria-label="Review" className="space-y-4">
            {changedKeys.length === 0 && !saved && <p className="text-sm text-gray-700">Nothing has been changed. The saved settings stay as they are.</p>}
            {changedKeys.length > 0 && (
              <ul className="text-sm space-y-1" aria-label="Changes">
                {changedKeys.map(k => (
                  <li key={k}>
                    <span className="font-medium">{LABELS[k]}</span>: <span className="font-mono text-gray-500">{baseline[k]}</span> → <span className="font-mono">{form[k]}</span>
                  </li>
                ))}
              </ul>
            )}
            {check && (
              <p className="text-sm">
                <Mark ok={check.ready} /> {check.ready ? 'Everything ReqBot needs is in place.' : 'Not everything is in place yet (see the steps above). You can still save and come back.'}
              </p>
            )}
            {saveError && <ErrorBanner message={saveError} />}
            {saved && (
              <p role="status" className="text-sm text-green-800 bg-green-50 border border-green-200 rounded px-3 py-2">
                Saved. Next: <Link to="/corpus" className="underline">add your first document</Link> or <Link to="/search" className="underline">try a search</Link>.
              </p>
            )}
            <button onClick={() => void save()} disabled={saving || changedKeys.length === 0} className="text-sm bg-blue-600 text-white rounded-lg px-4 py-2 hover:bg-blue-700 disabled:opacity-50">
              {saving ? 'Saving…' : 'Save these settings'}
            </button>
          </section>
        )}

        <div className="flex justify-between pt-2 border-t border-gray-100">
          <button onClick={() => setStep(s => Math.max(0, s - 1))} disabled={step === 0} className="text-sm text-gray-700 border border-gray-300 rounded px-3 py-1.5 hover:bg-gray-50 disabled:opacity-40">Back</button>
          <button
            onClick={() => {
              setStep(s => Math.min(STEPS.length - 1, s + 1))
              if (step === 2) void runCheck(form) // the folder step shows what the saved folder looks like; the review shows whether it is all ready
            }}
            disabled={step === STEPS.length - 1}
            className="text-sm bg-blue-600 text-white rounded px-3 py-1.5 hover:bg-blue-700 disabled:opacity-40"
          >
            Next
          </button>
        </div>
      </main>
    </AppShell>
  )
}
