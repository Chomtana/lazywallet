import { createBrowserRouter, Navigate, RouterProvider } from 'react-router'
import { Toaster } from '@/components/ui/sonner'
import { GuardedLayout } from '@/routes/GuardedLayout'
import Create from '@/routes/Create'
import Import from '@/routes/Import'
import Unlock from '@/routes/Unlock'
import WalletPage from '@/routes/WalletPage'
import Welcome from '@/routes/Welcome'
import { WalletProvider } from '@/state/WalletProvider'

const router = createBrowserRouter([
  {
    element: <GuardedLayout />,
    children: [
      { path: '/', element: <WalletPage /> },
      { path: '/welcome', element: <Welcome /> },
      { path: '/unlock', element: <Unlock /> },
      { path: '/create', element: <Create /> },
      { path: '/import', element: <Import /> },
    ],
  },
  { path: '*', element: <Navigate to="/" replace /> },
])

export default function App() {
  return (
    <WalletProvider>
      <RouterProvider router={router} />
      <Toaster theme="dark" position="top-center" />
    </WalletProvider>
  )
}
