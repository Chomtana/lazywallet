import { useState } from 'react'
import { BookUser, Zap } from 'lucide-react'
import { ChatView } from '@/chat/ChatView'
import { InputBar } from '@/chat/InputBar'
import { useChat } from '@/chat/useChat'
import { AddressBookSheet } from '@/components/AddressBookSheet'
import { DeleteWalletDialog } from '@/components/DeleteWalletDialog'
import { ShowSeedDialog } from '@/components/ShowSeedDialog'
import { TasksSheet } from '@/components/TasksSheet'
import { TopBar } from '@/components/TopBar'
import { Button } from '@/components/ui/button'
import { WalletMenu } from '@/components/WalletMenu'
import { KEYS } from '@/lib/storage'
import { useStored } from '@/lib/useStored'
import { simulateTrigger } from '@/mock/agent'
import { DEFAULT_CONTACTS } from '@/mock/fixtures'
import { useWallet } from '@/state/wallet-context'
import type { Contact, Task } from '@/types'

type Panel = 'contacts' | 'tasks' | 'seed' | 'delete' | null

export default function WalletPage() {
  const { active } = useWallet()
  const [contacts, setContacts] = useStored<Contact[]>(KEYS.contacts, DEFAULT_CONTACTS)
  const [tasks, setTasks] = useStored<Task[]>(KEYS.tasks, [])
  const [speakEnabled, setSpeakEnabled] = useStored<boolean>(KEYS.speak, true)
  const [panel, setPanel] = useState<Panel>(null)
  const chat = useChat({ contacts, speakEnabled, onTask: (t) => setTasks((prev) => [...prev, t]) })
  const activeTasks = tasks.filter((t) => t.status === 'active').length
  const panelProps = (p: Exclude<Panel, null>) => ({
    open: panel === p,
    onOpenChange: (v: boolean) => setPanel(v ? p : null),
  })

  if (!active) return null

  return (
    <div className="flex h-dvh flex-col">
      <TopBar
        center={
          <WalletMenu
            onOpenTasks={() => setPanel('tasks')}
            onShowSeed={() => setPanel('seed')}
            onDelete={() => setPanel('delete')}
          />
        }
        right={
          <Button variant="ghost" size="icon" aria-label="Address book" onClick={() => setPanel('contacts')}>
            <BookUser />
          </Button>
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
        {activeTasks > 0 && (
          <button
            type="button"
            onClick={() => setPanel('tasks')}
            className="flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs text-muted-foreground hover:text-foreground"
          >
            <Zap className="size-3.5 text-primary" />
            {activeTasks} active {activeTasks === 1 ? 'task' : 'tasks'}
          </button>
        )}
        <InputBar onSend={chat.send} speakEnabled={speakEnabled} onToggleSpeak={() => setSpeakEnabled((v) => !v)} />
      </div>
      <AddressBookSheet {...panelProps('contacts')} contacts={contacts} onChange={setContacts} />
      <TasksSheet {...panelProps('tasks')} tasks={tasks} onChange={setTasks} />
      <ShowSeedDialog {...panelProps('seed')} />
      <DeleteWalletDialog {...panelProps('delete')} />
    </div>
  )
}
