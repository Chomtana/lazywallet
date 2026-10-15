import { ChatView } from '@/chat/ChatView'
import { InputBar } from '@/chat/InputBar'
import { useChat } from '@/chat/useChat'
import { TopBar } from '@/components/TopBar'
import { Badge } from '@/components/ui/badge'
import { KEYS } from '@/lib/storage'
import { useStored } from '@/lib/useStored'
import { simulateTrigger } from '@/mock/agent'
import { DEFAULT_CONTACTS } from '@/mock/fixtures'
import { useWallet } from '@/state/wallet-context'
import type { Contact, Task } from '@/types'

export default function WalletPage() {
  const { active } = useWallet()
  const [contacts] = useStored<Contact[]>(KEYS.contacts, DEFAULT_CONTACTS)
  const [, setTasks] = useStored<Task[]>(KEYS.tasks, [])
  const [speakEnabled, setSpeakEnabled] = useStored<boolean>(KEYS.speak, true)
  const chat = useChat({ contacts, speakEnabled, onTask: (t) => setTasks((prev) => [...prev, t]) })

  if (!active) return null

  return (
    <div className="flex h-dvh flex-col">
      <TopBar
        center={
          <div className="flex items-center gap-2">
            <span className="font-medium">{active.name}</span>
            <Badge variant="secondary">Sandbox</Badge>
          </div>
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
      <div className="mx-auto w-full max-w-[720px] px-4 pb-4">
        <InputBar onSend={chat.send} speakEnabled={speakEnabled} onToggleSpeak={() => setSpeakEnabled((v) => !v)} />
      </div>
    </div>
  )
}
