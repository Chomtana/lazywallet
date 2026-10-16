import { useNavigate } from 'react-router'
import { AuthLayout } from '@/components/AuthLayout'
import { Button } from '@/components/ui/button'

export default function Welcome() {
  const navigate = useNavigate()
  return (
    <AuthLayout>
      <div className="space-y-2 text-center">
        <h1 className="text-2xl font-semibold tracking-tight">
          Hunt <span className="text-primary">AIRDROP</span> while <span className="text-primary">SLEEP</span>
        </h1>
        <p className="text-lg text-muted-foreground">
          Let AI agents hunt <span className="font-semibold text-primary">AIRDROPS</span>
          <br />
          and <span className="font-semibold text-primary">TRADE</span> while you{' '}
          <span className="font-semibold text-primary">SLEEP</span>
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
