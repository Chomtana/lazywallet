import { useEffect, useRef, useState } from 'react'
import { BookUser, QrCode, Zap } from 'lucide-react'
import { needsFunds } from '@/chain/portfolio'
import { usePortfolioUsd } from '@/chain/usePortfolioUsd'
import { ChatView } from '@/chat/ChatView'
import { FUND_PROMPT, GetFundsButton } from '@/chat/GetFundsButton'
import { InputBar } from '@/chat/InputBar'
import { QuickActionBar } from '@/chat/QuickActionBar'
import { useAgentChat } from '@/agent/useAgentChat'
import { AddressBookSheet } from '@/components/AddressBookSheet'
import { ConnectedBar } from '@/components/ConnectedBar'
import { DeleteWalletDialog } from '@/components/DeleteWalletDialog'
import { QrSheet } from '@/components/QrSheet'
import { ShowSeedDialog } from '@/components/ShowSeedDialog'
import { orderStatus } from '@/chain/scheduler'
import { useScheduledOrders } from '@/chain/useScheduledOrders'
import { TasksSheet } from '@/components/TasksSheet'
import { TopBar } from '@/components/TopBar'
import { Button } from '@/components/ui/button'
import { WalletMenu } from '@/components/WalletMenu'
import { KEYS } from '@/lib/storage'
import { formatUsd, uid } from '@/lib/format'
import { useStored } from '@/lib/useStored'
import { say } from '@/mock/agent'
import { DEFAULT_CONTACTS } from '@/mock/fixtures'
import { dappRequest } from '@/mock/walletconnect'
import { playChime } from '@/premium/chime'
import { PlanSheet } from '@/premium/PlanSheet'
import { planOf, type PlanId, type Subscription } from '@/premium/plans'
import { PremiumPane } from '@/premium/PremiumPane'
import { ResultsSheet } from '@/premium/ResultsSheet'
import { useWallet } from '@/state/wallet-context'
import type { Contact, DappInfo } from '@/types'

type Panel = 'qr' | 'contacts' | 'tasks' | 'seed' | 'delete' | 'plans' | 'results' | null

const DAPP_REQUEST_DELAY_MS = 3000
// Matches the wallet selector pill in the centre of the top bar.
const TOPBAR_BUTTON = 'size-9 rounded-full border-border hover:bg-secondary'

export default function WalletPage() {
  const { active } = useWallet()
  const [contacts, setContacts] = useStored<Contact[]>(KEYS.contacts, DEFAULT_CONTACTS)
  const [speakEnabled, setSpeakEnabled] = useStored<boolean>(KEYS.speak, true)
  const [subscription, setSubscription] = useStored<Subscription | null>(KEYS.premium, null)
  const [panel, setPanel] = useState<Panel>(null)
  const [session, setSession] = useState<DappInfo | null>(null)
  const requestTimer = useRef<number | undefined>(undefined)
  const chat = useAgentChat({ address: active?.address, mnemonic: active?.mnemonic, contacts, speakEnabled })
  const portfolio = usePortfolioUsd(active?.address)
  const refreshBalance = portfolio.refresh
  const { data: orders = [], isLoading: ordersLoading } = useScheduledOrders(active?.address)
  const nowSec = Math.floor(Date.now() / 1000)
  const activeTasks = orders.filter((o) => orderStatus(o, nowSec).state === 'active').length
  const panelProps = (p: Exclude<Panel, null>) => ({
    open: panel === p,
    onOpenChange: (v: boolean) => setPanel(v ? p : null),
  })

  useEffect(() => () => window.clearTimeout(requestTimer.current), [])

  // Re-read the balance on load, on wallet switch, and after every agent turn (transfers, swaps, faucet).
  useEffect(() => {
    if (!chat.busy) void refreshBalance()
  }, [chat.busy, refreshBalance])

  function connect(dapp: DappInfo) {
    setSession(dapp)
    chat.deliver({ messages: [say(`Connected to ${dapp.name}. I'll explain anything it asks you to sign.`)] })
    window.clearTimeout(requestTimer.current)
    requestTimer.current = window.setTimeout(() => chat.deliver(dappRequest(dapp)), DAPP_REQUEST_DELAY_MS)
  }

  function disconnect() {
    window.clearTimeout(requestTimer.current)
    if (session) chat.deliver({ messages: [say(`Disconnected from ${session.name}.`)] })
    setSession(null)
  }

  // Demo only: nothing is charged on chain — the card and the chime show the flow.
  function subscribe(plan: PlanId) {
    const p = planOf(plan)
    const now = new Date()
    const renews = new Date(now.getFullYear(), now.getMonth() + 1, now.getDate())
    setSubscription({ plan, since: now.toISOString() })
    playChime()
    chat.deliver({
      messages: [
        {
          id: uid(),
          role: 'assistant',
          kind: 'subscription',
          plan,
          chargedUsd: p.priceUsd,
          renews: renews.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }),
        },
        say(`You're on ${p.name}. I paid the first month, ${formatUsd(p.priceUsd)}, and started hunting. Tap Hunting Results any time to see how it's going.`),
      ],
    })
  }

  if (!active) return null

  const offerFunds = needsFunds(portfolio.usd)

  return (
    <div className="flex h-dvh flex-col">
      <TopBar
        left={
          <Button variant="ghost" size="icon" className={TOPBAR_BUTTON} aria-label="Receive or connect dApp" onClick={() => setPanel('qr')}>
            <QrCode />
          </Button>
        }
        center={
          <WalletMenu
            onOpenTasks={() => setPanel('tasks')}
            onShowSeed={() => setPanel('seed')}
            onDelete={() => setPanel('delete')}
          />
        }
        right={
          <>
            <Button
              variant="ghost"
              size="icon"
              className={`relative ${TOPBAR_BUTTON}`}
              aria-label={`Scheduled tasks (${activeTasks} active)`}
              onClick={() => setPanel('tasks')}
            >
              <Zap />
              {activeTasks > 0 && (
                <span className="absolute -top-1 -right-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-primary px-1 text-[10px] font-semibold text-primary-foreground">
                  {activeTasks}
                </span>
              )}
            </Button>
            <Button variant="ghost" size="icon" className={TOPBAR_BUTTON} aria-label="Address book" onClick={() => setPanel('contacts')}>
              <BookUser />
            </Button>
          </>
        }
      />
      <main className="flex-1 overflow-y-auto">
        <ChatView
          messages={chat.messages}
          progress={chat.progress}
          queue={chat.queue}
          onPick={(t) => chat.send(t)}
          onApprove={chat.approve}
          onReject={chat.reject}
          onChoose={chat.choose}
          onBuy={chat.buy}
          choicesEnabled={chat.online && !chat.busy}
        />
      </main>
      <div className="mx-auto w-full max-w-[720px] space-y-2 px-4 pb-4">
        {session && <ConnectedBar dapp={session} onDisconnect={disconnect} />}
        {offerFunds && (
          <GetFundsButton address={active.address} onFunded={refreshBalance} className="w-full" agentOnline={chat.online} onAsk={(t) => chat.send(t)} />
        )}
        <QuickActionBar onPick={(t) => chat.send(t)} disabled={!chat.online} />
        <InputBar onSend={chat.send} speakEnabled={speakEnabled} onToggleSpeak={() => setSpeakEnabled((v) => !v)} />
        <PremiumPane subscription={subscription} onChoosePlan={() => setPanel('plans')} onResults={() => setPanel('results')} />
      </div>
      <QrSheet {...panelProps('qr')} address={active.address} onConnect={connect} onAddFunds={chat.online ? () => chat.send(FUND_PROMPT) : undefined} />
      <AddressBookSheet {...panelProps('contacts')} contacts={contacts} onChange={setContacts} />
      <TasksSheet {...panelProps('tasks')} orders={orders} loading={ordersLoading} />
      <ShowSeedDialog {...panelProps('seed')} />
      <DeleteWalletDialog {...panelProps('delete')} />
      <PlanSheet {...panelProps('plans')} current={subscription?.plan ?? null} onSubscribe={subscribe} />
      {subscription && <ResultsSheet {...panelProps('results')} plan={subscription.plan} speakEnabled={speakEnabled} />}
    </div>
  )
}
