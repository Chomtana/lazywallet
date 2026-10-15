import { Navigate, Outlet, useLocation } from 'react-router'
import { useWallet } from '@/state/wallet-context'
import { redirectFor } from './redirect'

export function GuardedLayout() {
  const { status } = useWallet()
  const { pathname } = useLocation()
  const to = redirectFor(status, pathname)
  return to ? <Navigate to={to} replace /> : <Outlet />
}
