import { Check, ChevronDown, Download, KeyRound, ListTodo, Lock, Plus, Trash2 } from 'lucide-react'
import { useNavigate } from 'react-router'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { formatUsd, shortAddress } from '@/lib/format'
import { PORTFOLIO_USD } from '@/mock/fixtures'
import { useWallet } from '@/state/wallet-context'

type Props = { onOpenTasks: () => void; onShowSeed: () => void; onDelete: () => void }

export function WalletMenu({ onOpenTasks, onShowSeed, onDelete }: Props) {
  const { wallets, active, setActive, lock } = useWallet()
  const navigate = useNavigate()
  if (!active) return null

  return (
    <DropdownMenu modal={false}>
      <DropdownMenuTrigger className="flex min-w-0 items-center gap-2 rounded-full border px-3 py-1.5 text-sm hover:bg-secondary">
        <span className="truncate font-medium">{active.name}</span>
        <span className="font-mono text-xs text-muted-foreground">{shortAddress(active.address)}</span>
        <ChevronDown className="size-4 text-muted-foreground" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="center" className="w-72">
        <DropdownMenuLabel>Wallets</DropdownMenuLabel>
        {wallets.map((w) => (
          <DropdownMenuItem key={w.id} onSelect={() => setActive(w.id)}>
            <div className="min-w-0 flex-1">
              <p className="truncate">{w.name}</p>
              <p className="font-mono text-xs text-muted-foreground">
                {shortAddress(w.address)} · {formatUsd(PORTFOLIO_USD)}
              </p>
            </div>
            {w.id === active.id && <Check className="size-4 text-primary" />}
          </DropdownMenuItem>
        ))}
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => navigate('/create')}>
          <Plus /> Add new wallet
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => navigate('/import')}>
          <Download /> Import seed phrase
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={onOpenTasks}>
          <ListTodo /> Scheduled tasks
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={onShowSeed}>
          <KeyRound /> Show seed phrase
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={lock}>
          <Lock /> Lock
        </DropdownMenuItem>
        <DropdownMenuItem variant="destructive" onSelect={onDelete}>
          <Trash2 /> Delete wallet
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
