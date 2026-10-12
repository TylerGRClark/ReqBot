import { describe, expect, it } from 'vitest'
import { collectPdfFiles, isPdfName, pdfsFromFileList } from './pdfFiles'

function file(name: string): File {
  return new File(['%PDF-1.4'], name, { type: 'application/pdf' })
}

type FakeEntry = {
  isFile: boolean
  isDirectory: boolean
  name: string
  file?: (ok: (f: File) => void) => void
  createReader?: () => { readEntries: (ok: (e: FakeEntry[]) => void) => void }
}

function fileEntry(name: string): FakeEntry {
  return { isFile: true, isDirectory: false, name, file: ok => ok(file(name)) }
}

function dirEntry(name: string, children: FakeEntry[], batch = 2): FakeEntry {
  return {
    isFile: false,
    isDirectory: true,
    name,
    createReader: () => {
      let at = 0
      return {
        readEntries: ok => {
          const part = children.slice(at, at + batch) // the browser hands entries over in batches, then an empty one
          at += batch
          ok(part)
        },
      }
    },
  }
}

function transfer(entries: FakeEntry[], files: File[] = []): DataTransfer {
  return {
    items: entries.map(e => ({ webkitGetAsEntry: () => e })),
    files,
  } as unknown as DataTransfer
}

describe('isPdfName', () => {
  it('accepts a .pdf name in any case and refuses the rest', () => {
    expect(isPdfName('AFI17-203.PDF')).toBe(true)
    expect(isPdfName('notes.txt')).toBe(false)
    expect(isPdfName('.hidden.pdf')).toBe(false)
    expect(isPdfName('doc.pdf.exe')).toBe(false)
  })
})

describe('pdfsFromFileList', () => {
  it('keeps only the PDFs', () => {
    expect(pdfsFromFileList([file('a.pdf'), file('b.txt'), file('c.PDF')]).map(f => f.name)).toEqual(['a.pdf', 'c.PDF'])
    expect(pdfsFromFileList(null)).toEqual([])
  })
})

describe('collectPdfFiles', () => {
  it('walks a dropped folder, its sub-folders and every batch of entries', async () => {
    const tree = dirEntry('afis', [
      fileEntry('one.pdf'),
      fileEntry('two.pdf'),
      fileEntry('readme.txt'),
      dirEntry('older', [fileEntry('three.pdf'), fileEntry('.DS_Store'), fileEntry('four.pdf'), fileEntry('five.pdf')]),
      dirEntry('.git', [fileEntry('hidden.pdf')]),
    ])
    const names = (await collectPdfFiles(transfer([tree]))).map(f => f.name)
    expect(names).toEqual(['one.pdf', 'two.pdf', 'three.pdf', 'four.pdf', 'five.pdf'])
  })

  it('takes loose files and folders dropped together', async () => {
    const names = (await collectPdfFiles(transfer([fileEntry('solo.pdf'), dirEntry('d', [fileEntry('in-d.pdf')])]))).map(f => f.name)
    expect(names).toEqual(['solo.pdf', 'in-d.pdf'])
  })

  it('falls back to the plain file list when the browser gives no entries', async () => {
    const dt = { items: [], files: [file('a.pdf'), file('b.docx')] } as unknown as DataTransfer
    expect((await collectPdfFiles(dt)).map(f => f.name)).toEqual(['a.pdf'])
    expect(await collectPdfFiles(null)).toEqual([])
  })
})
