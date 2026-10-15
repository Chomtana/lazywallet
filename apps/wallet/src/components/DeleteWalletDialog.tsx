import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { useWallet } from '@/state/wallet-context'

export function DeleteWalletDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  const { active, wallets, deleteWallet } = useWallet()
  const isLast = wallets.length === 1

  async function confirmDelete() {
    if (active) await deleteWallet(active.id)
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Delete “{active?.name}”?</DialogTitle>
          <DialogDescription>
            {isLast
              ? "This is your only wallet, so LazyWallet will reset. You'll need the seed phrase to get it back."
              : "It will be removed from this device. You'll need the seed phrase to get it back."}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button variant="destructive" onClick={confirmDelete}>
            Delete
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
