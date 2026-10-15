import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router'
import { toast } from 'sonner'
import { AuthLayout } from '@/components/AuthLayout'
import { NameForm } from '@/components/NameForm'
import { PasswordStep } from '@/components/PasswordStep'
import { StepHeader } from '@/components/StepHeader'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { addressFromMnemonic, isValidMnemonic, normalizeMnemonic } from '@/lib/vault'
import { useWallet } from '@/state/wallet-context'

type Step = 'name' | 'phrase' | 'password'

export default function Import() {
  const { status, wallets, addWallet } = useWallet()
  const navigate = useNavigate()
  const needsPassword = status !== 'unlocked'
  const steps: Step[] = needsPassword ? ['name', 'phrase', 'password'] : ['name', 'phrase']
  const [step, setStep] = useState<Step>('name')
  const [name, setName] = useState('')
  const [phrase, setPhrase] = useState('')
  const [phraseError, setPhraseError] = useState<string | null>(null)
  const [mnemonic, setMnemonic] = useState('')
  const [busy, setBusy] = useState(false)
  const stepNo = steps.indexOf(step) + 1

  function back() {
    const i = steps.indexOf(step)
    if (i > 0) setStep(steps[i - 1])
    else navigate(status === 'unlocked' ? '/' : '/welcome')
  }

  async function save(m: string, password?: string) {
    setBusy(true)
    const ok = await addWallet(name, m, password)
    setBusy(false)
    if (ok) navigate('/')
    else toast.error("Couldn't save the wallet — browser storage is unavailable.")
  }

  function submitPhrase(e: FormEvent) {
    e.preventDefault()
    const m = normalizeMnemonic(phrase)
    if (!isValidMnemonic(m)) {
      setPhraseError("That doesn't look like a valid 12 or 24-word seed phrase. Check the spelling and word order.")
      return
    }
    const address = addressFromMnemonic(m)
    if (wallets.some((w) => w.address === address)) {
      setPhraseError('This wallet is already in LazyWallet.')
      return
    }
    setPhraseError(null)
    setMnemonic(m)
    if (needsPassword) setStep('password')
    else void save(m)
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
              setStep('phrase')
            }}
          />
        </>
      )}
      {step === 'phrase' && (
        <>
          <StepHeader step={stepNo} total={steps.length} title="Enter your seed phrase" subtitle="12 or 24 words, separated by spaces." />
          <form onSubmit={submitPhrase} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="phrase">Seed phrase</Label>
              <Textarea
                id="phrase"
                autoFocus
                rows={4}
                spellCheck={false}
                autoComplete="off"
                className="font-mono"
                value={phrase}
                onChange={(e) => setPhrase(e.target.value)}
              />
            </div>
            {phraseError && <p className="text-sm text-destructive">{phraseError}</p>}
            <Button type="submit" size="lg" className="w-full" disabled={!phrase.trim() || busy}>
              Continue
            </Button>
          </form>
        </>
      )}
      {step === 'password' && (
        <>
          <StepHeader step={stepNo} total={steps.length} title="Set a password" subtitle="You'll use it to unlock LazyWallet on this device." />
          <PasswordStep busy={busy} onSubmit={(pw) => void save(mnemonic, pw)} />
        </>
      )}
      <Button variant="ghost" className="w-full" onClick={back}>
        Back
      </Button>
    </AuthLayout>
  )
}
