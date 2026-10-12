import { useCallback, useRef, useState } from 'react'
import {
  AdminAuthError,
  AdminRequestError,
  clearAdminToken,
  getAdminToken,
  getInbox,
  importInbox,
  setAdminToken,
  startIngest,
  uploadPdf,
} from '../api/admin'
import type { AdminMode, IfExists, InboxImportResponse, InboxResponse } from '../api/admin'
import { collectPdfFiles, pdfsFromFileList } from '../utils/pdfFiles'

type Phase = 'uploading' | 'deciding' | 'queued' | 'skipped' | 'error'

interface Item {
  id: number
  name: string
  phase: Phase
  progress: number
  message: string
  uploadId?: string
}

const PHASE_STYLE: Record<Phase, string> = {
  uploading: 'text-blue-700',
  deciding: 'text-amber-700',
  queued: 'text-green-700',
  skipped: 'text-gray-600',
  error: 'text-red-700',
}

let nextId = 1

interface Props {
  mode: AdminMode
  /** Called after something was queued, so the job list can refresh at once. */
  onStarted: () => void
  /** Called when the saved code changed (entered or rejected), so the job list can start or stop asking. */
  onCodeChanged: () => void
  /** The server rejected the saved code on a read (the job list). */
  codeRejected?: boolean
}

export default function AddDocuments({ mode, onStarted, onCodeChanged, codeRejected = false }: Props) {
  const [items, setItems] = useState<Item[]>([])
  const [dragging, setDragging] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const [codeInput, setCodeInput] = useState('')
  const [promptReason, setPromptReason] = useState<string | null>(null)
  const [justSaved, setJustSaved] = useState(false) // a code was entered here and has not been refused yet: the job list's older "rejected" answer no longer applies
  const [alsoQuestions, setAlsoQuestions] = useState(false)
  const alsoQuestionsRef = useRef(false) // read when a request is made, so a file still uploading follows the box as it stands when it is queued
  const held = useRef<File[]>([])
  const filesInput = useRef<HTMLInputElement>(null)
  const folderInput = useRef<HTMLInputElement>(null)

  const [inbox, setInbox] = useState<InboxResponse | null>(null)
  const [inboxResult, setInboxResult] = useState<InboxImportResponse | null>(null)
  const [inboxError, setInboxError] = useState<string | null>(null)
  const [inboxBusy, setInboxBusy] = useState(false)

  const update = useCallback((id: number, patch: Partial<Item>) => {
    setItems(prev => prev.map(i => (i.id === id ? { ...i, ...patch } : i)))
  }, [])

  const rejected = codeRejected && !justSaved
  const needsCode = mode === 'code' && (!getAdminToken() || rejected)

  const begin = useCallback(
    async (file: File, id: number): Promise<boolean> => {
      update(id, { phase: 'uploading', progress: 0, message: '' })
      try {
        const up = await uploadPdf(file, f => update(id, { progress: f }))
        const where = up.library
        if (where.status === 'new') {
          const r = await startIngest(up.upload_id, 'ask', alsoQuestionsRef.current)
          update(id, r.result === 'queued'
            ? { phase: 'queued', message: 'Queued. It will start when the machine is free.' }
            : { phase: 'skipped', message: r.message ?? 'Nothing to do.' })
          onStarted()
        } else if (where.status === 'same_name_different_content') {
          update(id, { phase: 'deciding', uploadId: up.upload_id, message: `${up.stem} is already in the library with different content.` })
        } else if (where.status === 'same_content') {
          update(id, { phase: 'skipped', message: 'The same file is already in the library.' })
        } else if (where.status === 'same_content_other_name') {
          update(id, { phase: 'skipped', message: `The same file is already in the library as ${where.document ?? 'another name'}.` })
        } else {
          update(id, { phase: 'skipped', message: 'This name is already queued.' })
        }
        return true
      } catch (e) {
        if (e instanceof AdminAuthError) {
          clearAdminToken()
          setJustSaved(false)
          onCodeChanged()
          update(id, { phase: 'error', message: 'The access code was not accepted.' })
          return false
        }
        update(id, { phase: 'error', message: e instanceof Error ? e.message : 'The upload failed.' })
        return true
      }
    },
    [onCodeChanged, onStarted, update],
  )

  const run = useCallback(
    async (files: File[], codeJustEntered = false) => {
      setNotice(null)
      if (files.length === 0) {
        setNotice('No PDF files were found in what you chose.')
        return
      }
      if (!codeJustEntered && mode === 'code' && (!getAdminToken() || codeRejected)) {
        held.current = [...held.current, ...files]
        setPromptReason(codeRejected ? 'The saved code was not accepted. Paste the current one.' : null)
        setNotice(`${files.length} file${files.length === 1 ? '' : 's'} will be added as soon as you enter the access code.`)
        return
      }
      const fresh = files.map(f => ({ file: f, id: nextId++ }))
      setItems(prev => [...fresh.map(({ file, id }) => ({ id, name: file.name, phase: 'uploading' as Phase, progress: 0, message: '' })), ...prev])
      for (const { file, id } of fresh) {
        const ok = await begin(file, id)
        if (!ok) {
          setPromptReason('The access code was not accepted. Paste the current one.')
          held.current = [...held.current, ...fresh.slice(fresh.findIndex(f => f.id === id)).map(f => f.file)] // the refused file too: it is tried again with the new code
          break
        }
      }
    },
    [begin, codeRejected, mode],
  )

  async function saveCode() {
    if (!codeInput.trim()) return
    setAdminToken(codeInput)
    setCodeInput('')
    setPromptReason(null)
    setJustSaved(true)
    onCodeChanged()
    const waiting = held.current
    held.current = []
    setNotice(null)
    if (waiting.length) await run(waiting, true) // the code was just stored: do not hold them again because the job list has not been asked yet
  }

  async function decide(item: Item, ifExists: IfExists) {
    if (!item.uploadId) return
    update(item.id, { phase: 'uploading', progress: 1, message: '' })
    try {
      const r = await startIngest(item.uploadId, ifExists, alsoQuestionsRef.current)
      update(item.id, r.result === 'queued'
        ? { phase: 'queued', message: ifExists === 'replace' ? 'Queued to replace the library copy.' : `Queued as ${r.document ?? 'a second copy'}.` }
        : { phase: 'skipped', message: r.message ?? 'Nothing to do.' })
      onStarted()
    } catch (e) {
      update(item.id, { phase: 'error', message: e instanceof AdminRequestError || e instanceof Error ? e.message : 'That did not work.' })
    }
  }

  async function onDrop(e: React.DragEvent) {
    e.preventDefault()
    setDragging(false)
    await run(await collectPdfFiles(e.dataTransfer))
  }

  async function loadInbox() {
    setInboxBusy(true)
    setInboxError(null)
    setInboxResult(null)
    try {
      setInbox(await getInbox())
    } catch (e) {
      if (e instanceof AdminAuthError) {
        clearAdminToken()
        onCodeChanged()
        setPromptReason('The access code was not accepted. Paste the current one.')
      }
      setInboxError(e instanceof Error ? e.message : 'Could not read the inbox')
    } finally {
      setInboxBusy(false)
    }
  }

  async function runInboxImport(files: string[] | null, ifExists: IfExists) {
    setInboxBusy(true)
    setInboxError(null)
    try {
      setInboxResult(await importInbox(files, ifExists, alsoQuestionsRef.current))
      setInbox(await getInbox())
      onStarted()
    } catch (e) {
      setInboxError(e instanceof Error ? e.message : 'The import failed')
    } finally {
      setInboxBusy(false)
    }
  }

  if (mode === 'unconfigured') {
    return (
      <div className="border border-gray-200 bg-gray-50 rounded-lg p-4 text-sm text-gray-700">
        <p className="font-medium text-gray-900">Adding documents from the browser is switched off on this server.</p>
        <p className="mt-1">
          To turn it on, run <code className="bg-white border border-gray-200 rounded px-1">reqbot token</code> on the server (this page then asks for the code), or{' '}
          <code className="bg-white border border-gray-200 rounded px-1">reqbot token --open</code> on a network you trust (no code is asked for).
        </p>
      </div>
    )
  }

  const showPrompt = needsCode || promptReason !== null

  return (
    <div>
      {showPrompt && (
        <div className="border border-amber-200 bg-amber-50 rounded-lg p-4 mb-3">
          <p className="text-sm text-amber-900">
            {promptReason ?? 'Adding documents needs the admin access code. Paste it once; this browser remembers it.'}
          </p>
          <form
            className="flex gap-2 mt-2"
            onSubmit={e => {
              e.preventDefault()
              void saveCode()
            }}
          >
            <input
              type="password"
              autoComplete="off"
              value={codeInput}
              onChange={e => setCodeInput(e.target.value)}
              placeholder="Access code"
              aria-label="Access code"
              className="flex-1 border border-gray-300 rounded px-3 py-1.5 text-sm"
            />
            <button type="submit" className="text-sm bg-blue-600 text-white rounded px-3 py-1.5 hover:bg-blue-700">
              Use this code
            </button>
          </form>
          <p className="text-xs text-amber-800 mt-2">
            Run <code className="bg-white border border-amber-200 rounded px-1">reqbot token</code> on the server to see it.
          </p>
        </div>
      )}

      <div
        data-testid="dropzone"
        onDragOver={e => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={`border-2 border-dashed rounded-lg p-4 text-center text-sm transition-colors ${
          dragging ? 'border-blue-500 bg-blue-50' : 'border-gray-300 bg-white'
        }`}
      >
        <p className="text-gray-700">Drop PDFs or a whole folder here</p>
        <label className="mt-3 flex items-center justify-center gap-2 text-xs text-gray-700">
          <input
            type="checkbox"
            checked={alsoQuestions}
            onChange={e => {
              alsoQuestionsRef.current = e.target.checked
              setAlsoQuestions(e.target.checked)
            }}
          />
          Also write draft audit questions when each document is done (takes longer; you can do it later from the checklist page)
        </label>
        <div className="mt-3 flex flex-wrap items-center justify-center gap-2">
          <button onClick={() => filesInput.current?.click()} className="text-sm text-blue-700 border border-blue-300 rounded px-3 py-1.5 hover:bg-blue-50">
            Choose files
          </button>
          <button onClick={() => folderInput.current?.click()} className="text-sm text-blue-700 border border-blue-300 rounded px-3 py-1.5 hover:bg-blue-50">
            Choose a folder
          </button>
          <button onClick={loadInbox} disabled={inboxBusy} className="text-sm text-gray-700 border border-gray-300 rounded px-3 py-1.5 hover:bg-gray-50 disabled:opacity-50">
            Import from inbox
          </button>
        </div>
        <input
          ref={filesInput}
          type="file"
          accept=".pdf,application/pdf"
          multiple
          hidden
          aria-label="Choose PDF files"
          onChange={e => {
            void run(pdfsFromFileList(e.target.files))
            e.target.value = ''
          }}
        />
        <input
          ref={folderInput}
          type="file"
          hidden
          aria-label="Choose a folder of PDFs"
          {...({ webkitdirectory: '', directory: '' } as Record<string, string>)}
          onChange={e => {
            void run(pdfsFromFileList(e.target.files))
            e.target.value = ''
          }}
        />
      </div>

      {notice && <p className="text-sm text-gray-600 mt-2">{notice}</p>}

      {items.length > 0 && (
        <ul className="mt-3 space-y-2">
          {items.map(item => (
            <li key={item.id} className="bg-white border border-gray-200 rounded-lg p-3 text-sm">
              <div className="flex items-center justify-between gap-3">
                <span className="truncate text-gray-900">{item.name}</span>
                <span className={`shrink-0 text-xs ${PHASE_STYLE[item.phase]}`}>
                  {item.phase === 'uploading' ? `Uploading ${Math.round(item.progress * 100)}%` : item.phase === 'deciding' ? 'Needs a decision' : item.phase === 'queued' ? 'Queued' : item.phase === 'skipped' ? 'Skipped' : 'Not added'}
                </span>
              </div>
              {item.message && <p className={`text-xs mt-1 ${PHASE_STYLE[item.phase]}`}>{item.message}</p>}
              {item.phase === 'deciding' && (
                <div className="flex gap-2 mt-2">
                  <button onClick={() => decide(item, 'replace')} className="text-xs bg-blue-600 text-white rounded px-2 py-1 hover:bg-blue-700">
                    Replace it
                  </button>
                  <button onClick={() => decide(item, 'keep_both')} className="text-xs text-blue-700 border border-blue-300 rounded px-2 py-1 hover:bg-blue-50">
                    Keep both
                  </button>
                  <button onClick={() => update(item.id, { phase: 'skipped', message: 'Left out; nothing changed.' })} className="text-xs text-gray-600 border border-gray-300 rounded px-2 py-1 hover:bg-gray-50">
                    Skip it
                  </button>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}

      {(inbox || inboxError) && (
        <div className="mt-3 bg-white border border-gray-200 rounded-lg p-3 text-sm">
          {inboxError && <p className="text-red-700">{inboxError}</p>}
          {inbox && !inbox.exists && <p className="text-gray-600">The inbox folder does not exist yet: {inbox.folder}</p>}
          {inbox && inbox.exists && (
            <>
              <p className="text-gray-700">
                Inbox <span className="text-gray-400">({inbox.folder})</span>: {inbox.files.length} PDF{inbox.files.length === 1 ? '' : 's'}
                {inbox.truncated ? ' (list cut short)' : ''}
              </p>
              {inbox.files.length > 0 && (
                <ul className="mt-2 space-y-1">
                  {inbox.files.map(f => (
                    <li key={f.name} className="flex items-center justify-between gap-3 text-xs">
                      <span className="truncate">{f.name}</span>
                      <span className="shrink-0 text-gray-500">
                        {f.status === 'new' ? 'New' : f.status === 'same_content' ? 'Already in the library' : f.status === 'same_content_other_name' ? `Same as ${f.document ?? 'another document'}` : f.status === 'queued' ? 'Already queued' : 'Changed since it was added'}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
              {inbox.files.some(f => f.status === 'new') && (
                <button onClick={() => runInboxImport(null, 'ask')} disabled={inboxBusy} className="mt-3 text-sm bg-blue-600 text-white rounded px-3 py-1.5 hover:bg-blue-700 disabled:opacity-50">
                  Import the new ones
                </button>
              )}
            </>
          )}
          {inboxResult && (
            <ul className="mt-3 space-y-1 border-t border-gray-100 pt-2">
              {inboxResult.results.map(r => (
                <li key={r.file} className="text-xs flex items-center justify-between gap-3">
                  <span className="truncate">{r.file}</span>
                  <span className="shrink-0 text-gray-600">
                    {r.result === 'queued' ? 'Queued' : r.result === 'skipped' ? 'Skipped' : r.result === 'needs_decision' ? 'Same name, different content' : (r.message ?? 'Not added')}
                  </span>
                  {r.result === 'needs_decision' && (
                    <span className="shrink-0 flex gap-1">
                      <button onClick={() => runInboxImport([r.file], 'replace')} className="text-blue-700 underline">Replace</button>
                      <button onClick={() => runInboxImport([r.file], 'keep_both')} className="text-blue-700 underline">Keep both</button>
                    </span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
