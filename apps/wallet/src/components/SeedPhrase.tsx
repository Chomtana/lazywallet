import { useState } from 'react'
import { Copy, Eye } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export function SeedPhrase({ mnemonic }: { mnemonic: string }) {
  const [revealed, setRevealed] = useState(false)
  const words = mnemonic.split(' ')

  async function copy() {
    try {
      await navigator.clipboard.writeText(mnemonic)
      toast.success('Seed phrase copied')
    } catch {
      toast.error('Copy failed — write it down instead')
    }
  }

  return (
    <div className="space-y-3">
      <div className="relative">
        <ol className={cn('grid grid-cols-2 gap-2 sm:grid-cols-3', !revealed && 'select-none blur-md')}>
          {words.map((word, i) => (
            <li key={i} className="flex items-center gap-2 rounded-lg bg-secondary px-3 py-2 font-mono text-sm">
              <span className="w-5 text-right text-muted-foreground">{i + 1}</span>
              {word}
            </li>
          ))}
        </ol>
        {!revealed && (
          <button
            type="button"
            onClick={() => setRevealed(true)}
            className="absolute inset-0 flex items-center justify-center gap-2 rounded-lg text-sm font-medium"
          >
            <Eye className="size-4" />
            Tap to reveal
          </button>
        )}
      </div>
      <Button type="button" variant="secondary" className="w-full" onClick={copy} disabled={!revealed}>
        <Copy className="size-4" />
        Copy
      </Button>
    </div>
  )
}
