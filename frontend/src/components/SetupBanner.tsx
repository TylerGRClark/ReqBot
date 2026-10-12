import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { getSetupState } from '../api/setup'

/** A one-line prompt at the top of every page until a configuration has been saved. Shows nothing when the server cannot be asked. */
export default function SetupBanner() {
  const [needs, setNeeds] = useState(false)
  const { pathname } = useLocation()

  useEffect(() => {
    let alive = true
    getSetupState().then(s => { if (alive) setNeeds(s.needs_setup) }).catch(() => { if (alive) setNeeds(false) })
    return () => { alive = false }
  }, [])

  if (!needs || pathname === '/setup') return null
  return (
    <div role="status" className="bg-amber-50 border-b border-amber-200 px-6 py-2 text-sm text-amber-900">
      ReqBot has not been set up on this server yet.{' '}
      <Link to="/setup" className="font-medium underline">Start the setup</Link>
    </div>
  )
}
