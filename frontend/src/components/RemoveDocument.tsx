import { useEffect, useState } from 'react'
import { AdminAuthError, clearAdminToken, getAccess, getAdminToken, removeDocument } from '../api/admin'
import type { AdminMode } from '../api/admin'
import CodePrompt from './CodePrompt'

/**
 * "Remove this document" for an admin, never in one click: a panel says what will happen and the person types the document's key to confirm.
 * The document's saved runs go to a trash folder on the server (nothing is deleted) and its rows leave search. Shows nothing when admin
 * actions are switched off on the server.
 */
export default function RemoveDocument({ docKey, onRemoved }: { docKey: string; onRemoved: () => void }) {
  const [mode, setMode] = useState<AdminMode | null>(null)
  const [open, setOpen] = useState(false)
  const [typed, setTyped] = useState('')
  const [busy, setBusy] = useState(false)
  const [problem, setProblem] = useState<string | null>(null)
  const [needCode, setNeedCode] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    getAccess().then(m => { if (alive) setMode(m) }).catch(() => { if (alive) setMode(null) })
    return () => { alive = false }
  }, [])

  async function remove() {
    setBusy(true)
    setProblem(null)
    try {
      await removeDocument(docKey, typed)
      onRemoved()
    } catch (e) {
      if (e instanceof AdminAuthError) {
        clearAdminToken()
        setNeedCode('The access code was not accepted. Paste the current one.')
      } else {
        setProblem(e instanceof Error ? e.message : 'The removal did not work.')
      }
    } finally {
      setBusy(false)
    }
  }

  if (mode === null || mode === 'unconfigured') return null

  if (!open) {
    return (
      <div className="pt-4 border-t border-gray-100">
        <button
          onClick={() => {
            if (mode === 'code' && !getAdminToken()) setNeedCode('')
            else setOpen(true)
          }}
          className="text-sm text-red-700 border border-red-200 rounded-lg px-3 py-1.5 hover:bg-red-50"
        >
          Remove this document…
        </button>
        {needCode !== null && (
          <div className="mt-3">
            <CodePrompt reason={needCode || undefined} onSaved={() => { setNeedCode(null); setOpen(true) }} />
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="pt-4 border-t border-gray-100">
      <div className="border border-red-200 bg-red-50 rounded-lg p-4 text-sm text-gray-800 space-y-3">
        <p>
          This takes <span className="font-mono">{docKey}</span> out of search and out of the library. Its saved runs are moved to a trash folder on the server, not
          deleted, so it can be put back by moving them out again and rebuilding the library.
        </p>
        <label className="block">
          <span className="text-xs text-gray-600">Type the document&rsquo;s name to confirm</span>
          <input
            value={typed}
            onChange={e => setTyped(e.target.value)}
            aria-label="Type the document's name to confirm"
            className="mt-1 w-full border border-gray-300 rounded px-3 py-1.5 text-sm font-mono"
          />
        </label>
        <div className="flex gap-2">
          <button
            onClick={() => void remove()}
            disabled={busy || typed !== docKey}
            className="text-sm bg-red-600 text-white rounded px-3 py-1.5 hover:bg-red-700 disabled:opacity-40"
          >
            {busy ? 'Removing…' : 'Remove it'}
          </button>
          <button
            onClick={() => { setOpen(false); setTyped(''); setProblem(null) }}
            disabled={busy}
            className="text-sm text-gray-700 border border-gray-300 bg-white rounded px-3 py-1.5 hover:bg-gray-50"
          >
            Keep it
          </button>
        </div>
        {problem && <p className="text-xs text-red-700">{problem}</p>}
        {needCode !== null && <CodePrompt reason={needCode || undefined} onSaved={() => setNeedCode(null)} />}
      </div>
    </div>
  )
}
