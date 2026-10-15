import { useState, type FormEvent } from 'react'
import { Camera, ClipboardPaste, Copy } from 'lucide-react'
import { QRCodeSVG } from 'qrcode.react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { hostOf } from '@/lib/format'
import { isWcUri, mockProposal, type Proposal } from '@/mock/walletconnect'
import type { Address, DappInfo } from '@/types'

type Props = {
  open: boolean
  onOpenChange: (v: boolean) => void
  address: Address
  onConnect: (dapp: DappInfo) => void
}

export function QrSheet({ open, onOpenChange, address, onConnect }: Props) {
  const [uri, setUri] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [proposal, setProposal] = useState<Proposal | null>(null)

  async function copyAddress() {
    try {
      await navigator.clipboard.writeText(address)
      toast.success('Address copied')
    } catch {
      toast.error('Copy failed')
    }
  }

  async function paste() {
    try {
      setUri(await navigator.clipboard.readText())
    } catch {
      toast.error('Clipboard access was blocked — paste manually')
    }
  }

  function connect(e: FormEvent) {
    e.preventDefault()
    if (!isWcUri(uri)) {
      setError("That isn't a WalletConnect link — it should start with wc:")
      return
    }
    setError(null)
    setProposal(mockProposal())
  }

  function approve() {
    if (proposal) onConnect(proposal.dapp)
    setProposal(null)
    setUri('')
    onOpenChange(false)
  }

  return (
    <>
      <Sheet open={open} onOpenChange={onOpenChange}>
        <SheetContent side="left" className="w-full sm:max-w-md">
          <SheetHeader>
            <SheetTitle>Receive or connect</SheetTitle>
          </SheetHeader>
          <Tabs defaultValue="receive" className="px-4 pb-4">
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger value="receive">Receive</TabsTrigger>
              <TabsTrigger value="connect">Connect dApp</TabsTrigger>
            </TabsList>
            <TabsContent value="receive" className="space-y-4 pt-4">
              <div className="mx-auto w-fit rounded-2xl bg-white p-4">
                <QRCodeSVG value={address} size={200} />
              </div>
              <p className="break-all text-center font-mono text-sm">{address}</p>
              <Button variant="secondary" className="w-full" onClick={copyAddress}>
                <Copy /> Copy address
              </Button>
              <p className="text-center text-xs text-muted-foreground">
                Sandbox · Ethereum mainnet fork. Don't send real funds here.
              </p>
            </TabsContent>
            <TabsContent value="connect" className="space-y-4 pt-4">
              <p className="text-sm text-muted-foreground">
                On the dApp, choose WalletConnect, copy its link, and paste it here.
              </p>
              <form onSubmit={connect} className="space-y-3">
                <Label htmlFor="wc-uri">WalletConnect link</Label>
                <div className="flex gap-2">
                  <Input
                    id="wc-uri"
                    className="font-mono"
                    placeholder="wc:…"
                    value={uri}
                    onChange={(e) => setUri(e.target.value)}
                  />
                  <Button type="button" variant="secondary" size="icon" aria-label="Paste" onClick={paste}>
                    <ClipboardPaste />
                  </Button>
                </div>
                {error && <p className="text-sm text-destructive">{error}</p>}
                <Button type="submit" className="w-full" disabled={!uri.trim()}>
                  Connect
                </Button>
              </form>
              <Button variant="ghost" className="w-full" disabled>
                <Camera /> Scan QR — coming soon
              </Button>
            </TabsContent>
          </Tabs>
        </SheetContent>
      </Sheet>
      <Dialog open={proposal !== null} onOpenChange={(v) => !v && setProposal(null)}>
        <DialogContent>
          {proposal && (
            <>
              <DialogHeader>
                <div className="flex items-center gap-3">
                  <span className="flex size-10 items-center justify-center rounded-full bg-secondary text-xl">
                    {proposal.dapp.icon}
                  </span>
                  <div>
                    <DialogTitle>{proposal.dapp.name} wants to connect</DialogTitle>
                    <DialogDescription>{hostOf(proposal.dapp.url)}</DialogDescription>
                  </div>
                </div>
              </DialogHeader>
              <dl className="space-y-2 text-sm">
                <div className="flex justify-between gap-4">
                  <dt className="text-muted-foreground">Network</dt>
                  <dd>{proposal.chain}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-muted-foreground">Can request</dt>
                  <dd className="text-right font-mono">{proposal.methods.join(', ')}</dd>
                </div>
              </dl>
              <p className="text-xs text-muted-foreground">
                It can only ask. Every request shows up in your chat for you to approve.
              </p>
              <DialogFooter>
                <Button variant="secondary" onClick={() => setProposal(null)}>
                  Reject
                </Button>
                <Button onClick={approve}>Approve</Button>
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>
    </>
  )
}
