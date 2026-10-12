import { describe, expect, it } from 'vitest'
import { canCancel, canRetry, stepLabel, stepPercent } from './jobText'

describe('stepLabel', () => {
  it('says what the pipeline is doing in plain words', () => {
    expect(stepLabel(null)).toBe('Starting')
    expect(stepLabel({ step: 'reading' })).toBe('Reading the PDF')
    expect(stepLabel({ step: 'finding', done: 120, total: 427 })).toBe('Finding requirements: 120 of 427 sections done')
    expect(stepLabel({ step: 'finding', done: 427, total: 427 })).toBe('Finding requirements: 427 of 427 sections done')
    expect(stepLabel({ step: 'indexing', done: 50, total: 200 })).toBe('Adding to search, 50 of 200')
    expect(stepLabel({ step: 'questions', done: 40, total: 133 })).toBe('Writing questions: 40 of 133 rows done')
    expect(stepLabel({ step: 'reindex', done: 0, total: 13 })).toBe('Rebuilding the library: 0 of 13 documents done')
    expect(stepLabel({ step: 'reindex-context', done: 12, total: 13 })).toBe('Rebuilding the source text: 12 of 13 documents done')
    expect(stepLabel({ step: 'something-new' })).toBe('something-new')
  })
})

describe('stepPercent and the buttons', () => {
  it('gives a percentage only when there is a total', () => {
    expect(stepPercent({ step: 'finding', done: 1, total: 4 })).toBe(25)
    expect(stepPercent({ step: 'reading' })).toBeNull()
    expect(stepPercent(null)).toBeNull()
  })
  it('offers Cancel on live jobs and Retry on ended ones that can be retried', () => {
    expect(canCancel('queued') && canCancel('running')).toBe(true)
    expect(canCancel('succeeded')).toBe(false)
    expect(canRetry('failed') && canRetry('cancelled') && canRetry('interrupted')).toBe(true)
    expect(canRetry('succeeded') || canRetry('running') || canRetry('queued')).toBe(false)
  })
})
