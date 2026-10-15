import { useState } from 'react'
import { useNavigate } from 'react-router'
import { toast } from 'sonner'
import { AuthLayout } from '@/components/AuthLayout'
import { NameForm } from '@/components/NameForm'
import { PasswordStep } from '@/components/PasswordStep'
import { SeedPhrase } from '@/components/SeedPhrase'
import { StepHeader } from '@/components/StepHeader'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { newMnemonic } from '@/lib/vault'
import { useWallet } from '@/state/wallet-context'

type Step = 'name' | 'password' | 'seed'

export default function Create() {
  const { status, addWallet } = useWallet()
  const navigate = useNavigate()
  const needsPassword = status !== 'unlocked'
  const steps: Step[] = needsPassword ? ['name', 'password', 'seed'] : ['name', 'seed']
  const [step, setStep] = useState<Step>('name')
  const [name, setName] = useState('')
  const [password, setPassword] = useState('')
  const [mnemonic] = useState(() => newMnemonic())
  const [savedIt, setSavedIt] = useState(false)
  const [busy, setBusy] = useState(false)
  const stepNo = steps.indexOf(step) + 1

  function back() {
    const i = steps.indexOf(step)
    if (i > 0) setStep(steps[i - 1])
    else navigate(status === 'unlocked' ? '/' : '/welcome')
  }

  async function finish() {
    setBusy(true)
    const ok = await addWallet(name, mnemonic, password || undefined)
    setBusy(false)
    if (ok) navigate('/')
    else toast.error("Couldn't save the wallet — browser storage is unavailable.")
  }

  return (
    <AuthLayout>
      {step === 'name' && (
        <>
          <StepHeader step={stepNo} total={steps.length} title="Name your wallet" subtitle="Only you see this name." />
          <NameForm
            initial={name}
            onSubmit={(v) => {
              setName(v)
              setStep(needsPassword ? 'password' : 'seed')
            }}
          />
        </>
      )}
      {step === 'password' && (
        <>
          <StepHeader step={stepNo} total={steps.length} title="Set a password" subtitle="You'll use it to unlock LazyWallet on this device." />
          <PasswordStep
            onSubmit={(pw) => {
              setPassword(pw)
              setStep('seed')
            }}
          />
        </>
      )}
      {step === 'seed' && (
        <>
          <StepHeader
            step={stepNo}
            total={steps.length}
            title="Write down your seed phrase"
            subtitle="These 12 words are the only way to recover your wallet. Never share them."
          />
          <SeedPhrase mnemonic={mnemonic} />
          <label className="flex items-center gap-3 text-sm">
            <Checkbox checked={savedIt} onCheckedChange={(v) => setSavedIt(v === true)} />
            I've written it down somewhere safe
          </label>
          <Button size="lg" className="w-full" disabled={!savedIt || busy} onClick={finish}>
            {busy ? 'Saving…' : 'Open my wallet'}
          </Button>
        </>
      )}
      <Button variant="ghost" className="w-full" onClick={back}>
        Back
      </Button>
    </AuthLayout>
  )
}
