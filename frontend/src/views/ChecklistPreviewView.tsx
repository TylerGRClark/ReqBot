import { useState, useEffect } from 'react'
import { useParams, useSearchParams, Link } from 'react-router-dom'
import * as api from '../api/client'
import { startQuestions } from '../api/admin'
import type { ChecklistEnvelope, ChecklistItem } from '../api/types'
import AppShell from '../components/AppShell'
import LoadingSpinner from '../components/LoadingSpinner'
import ErrorBanner from '../components/ErrorBanner'
import ChecklistTable, { needsAttention } from '../components/ChecklistTable'
import ExportButtonGroup from '../components/ExportButtonGroup'
import JobAction from '../components/JobAction'

export default function ChecklistPreviewView() {
  const { docId } = useParams<{ docId: string }>()
  const [searchParams] = useSearchParams()
  const profile = searchParams.get('profile') ?? 'cybersecurity'

  const [data, setData] = useState<ChecklistEnvelope | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [flaggedOnly, setFlaggedOnly] = useState(false)
  const [reloadTick, setReloadTick] = useState(0) // bumped when draft questions finish, so the table shows them

  useEffect(() => {
    if (!docId) return
    setFlaggedOnly(false)
    setLoading(true)
    setError(null)
    setData(null)
    api
      .checklist({ doc_key: docId, profile })
      .then(setData)
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : 'Failed to load checklist')
      })
      .finally(() => setLoading(false))
  }, [docId, profile, reloadTick])

  const items: ChecklistItem[] = data?.items ?? []
  const missed: ChecklistItem[] = data?.possible_missed ?? []
  const displayItems = flaggedOnly ? items.filter(needsAttention) : items
  const flaggedCount = items.filter(needsAttention).length

  return (
    <AppShell>
      <main className="max-w-full px-6 py-8 space-y-4">
        <div>
          <Link to="/checklists" className="text-sm text-blue-600 hover:underline">
            ← Back to generate
          </Link>
        </div>

        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-xl font-bold text-gray-900">Checklist</h1>
            <p className="mt-1 text-xs text-gray-400 font-mono">
              {docId} · {profile}
            </p>
          </div>

          {data && docId && (
            <div className="flex flex-wrap items-start gap-3">
              <JobAction
                label="Write draft audit questions"
                confirm="This asks the model to write a draft question for each row that has none yet. It can take several minutes for a long document, and rows that have not changed are reused. The questions are drafts to check before use."
                pick={jobs => jobs.find(j => j.kind === 'questions' && j.params?.doc_key === docId)}
                start={() => startQuestions(docId)}
                onSucceeded={() => setReloadTick(t => t + 1)}
              />
              <ExportButtonGroup docKey={docId} profile={profile} />
            </div>
          )}
        </div>

        {loading && <LoadingSpinner />}

        {!loading && error && <ErrorBanner message={error} />}

        {!loading && !error && data && (
          <>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-sm text-gray-500">
                {data.summary.total_items} item{data.summary.total_items !== 1 ? 's' : ''}
                {flaggedCount > 0 && (
                  <span className="ml-2 text-amber-700">
                    · {flaggedCount} with a hint to check
                  </span>
                )}
              </p>

              {flaggedCount > 0 && (
                <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={flaggedOnly}
                    onChange={e => setFlaggedOnly(e.target.checked)}
                    className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  />
                  Hints only
                </label>
              )}
            </div>

            {items.length === 0 ? (
              <p className="text-sm text-gray-500 py-8 text-center">
                No requirements had sufficient provenance to generate checklist items.
              </p>
            ) : displayItems.length === 0 ? (
              <p className="text-sm text-gray-500 py-8 text-center">
                No flagged items in this checklist.
              </p>
            ) : (
              <ChecklistTable items={displayItems} />
            )}

            {missed.length > 0 && (
              <section className="space-y-2 pt-4" aria-label="Possible missed requirements">
                <h2 className="text-base font-semibold text-gray-900">
                  Possible missed requirements ({missed.length})
                </h2>
                <p className="text-sm text-gray-500">
                  These passages look like obligations but were not extracted (found by a text scan). Confirm each one;
                  they are not counted above.
                </p>
                <ChecklistTable items={missed} />
              </section>
            )}
          </>
        )}
      </main>
    </AppShell>
  )
}
