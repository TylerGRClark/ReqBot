import { useState } from 'react'
import { setAdminToken } from '../api/admin'

/**
 * The one place a person pastes the admin access code. It is kept in this browser (localStorage) after "Use this code"; the caller is told so
 * it can carry on with whatever needed the code. `reason` replaces the default explanation (for example "the saved code was not accepted").
 */
export default function CodePrompt({ onSaved, reason }: { onSaved: () => void; reason?: string | null }) {
  const [value, setValue] = useState('')
  return (
    <div className="border border-amber-200 bg-amber-50 rounded-lg p-4">
      <p className="text-sm text-amber-900">{reason ?? 'This needs the admin access code. Paste it once; this browser remembers it.'}</p>
      <form
        className="flex gap-2 mt-2"
        onSubmit={e => {
          e.preventDefault()
          if (!value.trim()) return
          setAdminToken(value)
          setValue('')
          onSaved()
        }}
      >
        <input
          type="password"
          autoComplete="off"
          value={value}
          onChange={e => setValue(e.target.value)}
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
  )
}
