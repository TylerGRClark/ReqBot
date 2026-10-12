/**
 * Picking the PDFs out of what a person dropped: files, or a whole folder (walked recursively, subfolders included).
 *
 * A dropped folder is only visible through the non-standard but universally supported `webkitGetAsEntry()`; everything is
 * read in the browser and nothing is sent until the caller uploads each file. Anything that is not a `.pdf`, and any hidden
 * file or folder (a name starting with a dot), is left out.
 */
export function isPdfName(name: string): boolean {
  return /\.pdf$/i.test(name) && !name.startsWith('.')
}

export function pdfsFromFileList(list: FileList | File[] | null | undefined): File[] {
  return Array.from(list ?? []).filter(f => isPdfName(f.name))
}

interface EntryLike {
  isFile: boolean
  isDirectory: boolean
  name: string
  file?: (ok: (f: File) => void, fail?: (e: unknown) => void) => void
  createReader?: () => { readEntries: (ok: (entries: EntryLike[]) => void, fail?: (e: unknown) => void) => void }
}

function readAll(reader: ReturnType<NonNullable<EntryLike['createReader']>>): Promise<EntryLike[]> {
  // readEntries returns the entries in batches (about 100 at a time) until it returns an empty one
  return new Promise((resolve, reject) => {
    const all: EntryLike[] = []
    const next = () =>
      reader.readEntries(batch => {
        if (batch.length === 0) resolve(all)
        else {
          all.push(...batch)
          next()
        }
      }, reject)
    next()
  })
}

async function walk(entry: EntryLike, out: File[], depth: number): Promise<void> {
  if (entry.name.startsWith('.') || depth > 20) return
  if (entry.isFile && entry.file && isPdfName(entry.name)) {
    out.push(await new Promise<File>((ok, fail) => entry.file!(ok, fail)))
  } else if (entry.isDirectory && entry.createReader) {
    for (const child of await readAll(entry.createReader())) await walk(child, out, depth + 1)
  }
}

/** The PDFs in a drop, files and folders alike, in the order the browser listed them. */
export async function collectPdfFiles(dt: DataTransfer | null | undefined): Promise<File[]> {
  if (!dt) return []
  const items = Array.from(dt.items ?? [])
  const entries = items
    .map(i => (typeof i.webkitGetAsEntry === 'function' ? (i.webkitGetAsEntry() as unknown as EntryLike | null) : null))
    .filter((e): e is EntryLike => e !== null)
  if (entries.length === 0) return pdfsFromFileList(dt.files)
  const out: File[] = []
  for (const entry of entries) await walk(entry, out, 0)
  return out
}
