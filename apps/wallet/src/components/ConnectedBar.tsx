import { Check, ChevronDown } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { hostOf } from '@/lib/format'
import type { DappInfo } from '@/types'

export function ConnectedBar({ dapp, onDisconnect }: { dapp: DappInfo; onDisconnect: () => void }) {
  return (
    <div className="flex items-center gap-3 rounded-2xl border bg-card px-3 py-2 text-sm">
      <span className="relative flex size-8 shrink-0 items-center justify-center rounded-full bg-secondary">
        {dapp.icon}
        <span className="absolute -right-0.5 -bottom-0.5 size-2.5 rounded-full bg-primary ring-2 ring-card" />
      </span>
      <div className="min-w-0 flex-1">
        <p className="font-medium">Connected to {dapp.name}</p>
        <p className="truncate text-xs text-muted-foreground">{hostOf(dapp.url)}</p>
      </div>
      <DropdownMenu modal={false}>
        <DropdownMenuTrigger className="flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs">
          Sandbox <ChevronDown className="size-3" />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuLabel>Network</DropdownMenuLabel>
          <DropdownMenuItem>
            Sandbox (Ethereum fork)
            <Check className="ml-auto size-4 text-primary" />
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <Button variant="ghost" size="sm" onClick={onDisconnect}>
        Disconnect
      </Button>
    </div>
  )
}
