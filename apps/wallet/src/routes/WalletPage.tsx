import { useEffect, useRef, useState } from 'react'
import { BookUser, QrCode, Zap } from 'lucide-react'
import { ChatView } from '@/chat/ChatView'
import { InputBar } from '@/chat/InputBar'
import { useChat } from '@/chat/useChat'
import { AddressBookSheet } from '@/components/AddressBookSheet'
import { ConnectedBar } from '@/components/ConnectedBar'
import { DeleteWalletDialog } from '@/components/DeleteWalletDialog'
import { QrSheet } from '@/components/QrSheet'
import { ShowSeedDialog } from '@/components/ShowSeedDialog'
import { TasksSheet } from '@/components/TasksSheet'
import { TopBar } from '@/components/TopBar'
import { Button } from '@/components/ui/button'
import { WalletMenu } from '@/components/WalletMenu'
import { KEYS } from '@/lib/storage'
import { useStored } from '@/lib/useStored'
import { say, simulateTrigger } from '@/mock/agent'
import { DEFAULT_CONTACTS } from '@/mock/fixtures'
import { dappRequest } from '@/mock/walletconnect'
import { useWallet } from '@/state/wallet-context'
import type { Contact, DappInfo, Task } from '@/types'

type Panel = 'qr' | 'contacts' | 'tasks' | 'seed' | 'delete' | null

const DAPP_REQUEST_DELAY_MS = 3000
// Matches the wallet selector pill in the centre of the top bar.
const TOPBAR_BUTTON = 'size-9 rounded-full border-border hover:bg-secondary'

export default function WalletPage() {
  const { active } = useWallet()
  const [contacts, setContacts] = useStored<Contact[]>(KEYS.contacts, DEFAULT_CONTACTS)
  const [tasks, setTasks] = useStored<Task[]>(KEYS.tasks, [])
  const [speakEnabled, setSpeakEnabled] = useStored<boolean>(KEYS.speak, true)
  const [panel, setPanel] = useState<Panel>(null)
  const [session, setSession] = useState<DappInfo | null>(null)
  const requestTimer = useRef<number | undefined>(undefined)
  const chat = useChat({ contacts, speakEnabled, onTask: (t) => setTasks((prev) => [...prev, t]) })
  const activeTasks = tasks.filter((t) => t.status === 'active').length
  const panelProps = (p: Exclude<Panel, null>) => ({
    open: panel === p,
    onOpenChange: (v: boolean) => setPanel(v ? p : null),
  })

  useEffect(() => () => window.clearTimeout(requestTimer.current), [])

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

  if (!active) return null

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
          onPick={(t) => chat.send(t)}
          onApprove={chat.approve}
          onReject={chat.reject}
          onSimulate={(t) => chat.deliver(simulateTrigger(t))}
        />
      </main>
      <div className="mx-auto w-full max-w-[720px] space-y-2 px-4 pb-4">
        {session && <ConnectedBar dapp={session} onDisconnect={disconnect} />}
        <InputBar onSend={chat.send} speakEnabled={speakEnabled} onToggleSpeak={() => setSpeakEnabled((v) => !v)} />
      </div>
      <QrSheet {...panelProps('qr')} address={active.address} onConnect={connect} />
      <AddressBookSheet {...panelProps('contacts')} contacts={contacts} onChange={setContacts} />
      <TasksSheet {...panelProps('tasks')} tasks={tasks} onChange={setTasks} />
      <ShowSeedDialog {...panelProps('seed')} />
      <DeleteWalletDialog {...panelProps('delete')} />
    </div>
  )
}
