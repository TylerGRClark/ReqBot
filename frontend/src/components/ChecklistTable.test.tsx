import { afterEach, describe, expect, it } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import ChecklistTable, { needsAttention } from './ChecklistTable'
import type { ChecklistItem } from '../api/types'

afterEach(cleanup)

const base: ChecklistItem = {
  checklist_item_id: 'CHK-1',
  requirement_ids: ['REQ-1'],
  source_quote: 'Provide a representative to the working group when requested.',
  source_ref: '2.9.2',
  section_title_path: ['ROLES AND RESPONSIBILITIES', '2.9. AF/A4'],
  page_refs: [11],
  domain_tags: [],
  confidence: 0.6,
  audit_question: '',
  status: 'not-started',
  assessor_notes: '',
  requires_human_review: true,
  review_reasons: ['low-confidence'],
}

describe('needsAttention', () => {
  it('ignores low confidence alone', () => {
    expect(needsAttention(base)).toBe(false)
  })
  it('is true for a specific hint or a reason other than low confidence', () => {
    expect(needsAttention({ ...base, item_flags: ['table_fragment'] })).toBe(true)
    expect(needsAttention({ ...base, review_reasons: ['low-confidence', 'missing-source-ref'] })).toBe(true)
  })
})

describe('ChecklistTable audit layout', () => {
  it('shows the applies-to heading, the passage and the hints, with no Flag column', () => {
    render(
      <ChecklistTable
        items={[{ ...base, applies_to: 'AF/A4', passage: 'Lead-in:\n>> Provide a representative <<', item_flags: ['no_stated_actor'] }]}
      />,
    )
    expect(screen.getAllByText('AF/A4').length).toBeGreaterThan(0)
    expect(screen.getByText('Show passage')).toBeTruthy()
    expect(screen.getByText('no_stated_actor')).toBeTruthy()
    expect(screen.queryByText('Flag')).toBeNull()
    expect(screen.queryByText('low-confidence')).toBeNull()
  })

  it('renders an item with a null confidence and without the new fields', () => {
    render(<ChecklistTable items={[{ ...base, confidence: null }]} />)
    expect(screen.getByText('2.9.2')).toBeTruthy()
    expect(screen.getAllByText('—').length).toBeGreaterThan(0)
  })
})
