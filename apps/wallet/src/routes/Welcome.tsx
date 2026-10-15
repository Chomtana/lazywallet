import { useNavigate } from 'react-router'
import { AuthLayout } from '@/components/AuthLayout'
import { Button } from '@/components/ui/button'

export default function Welcome() {
  const navigate = useNavigate()
  return (
    <AuthLayout>
      <div className="space-y-2 text-center">
        <h1 className="text-3xl font-semibold tracking-tight">Just say it.</h1>
        <p className="text-muted-foreground">
          Your voice-powered AI wallet. Talk to check balances, send, swap and automate trades.
        </p>
      </div>
      <div className="grid gap-3">
        <Button size="lg" onClick={() => navigate('/create')}>
          Create new wallet
        </Button>
        <Button size="lg" variant="secondary" onClick={() => navigate('/import')}>
          Import seed phrase
        </Button>
      </div>
    </AuthLayout>
  )
}
