import { Mic } from 'lucide-react'
import type { AssistantMessage, ChoiceOption, Message, Task } from '@/types'
import { AirdropCard } from './cards/AirdropCard'
import { BalanceCard } from './cards/BalanceCard'
import { BalanceChangeCard } from './cards/BalanceChangeCard'
import { ChoiceCard } from './cards/ChoiceCard'
import { ConfirmCard } from './cards/ConfirmCard'
import { StatusCard } from './cards/StatusCard'
import { SubscriptionCard } from './cards/SubscriptionCard'
import { TaskCard } from './cards/TaskCard'
import { TextBubble } from './cards/TextBubble'
import { TokenListCard } from './cards/TokenListCard'
import { UnlockListCard } from './cards/UnlockListCard'

export type MessageActions = {
  onApprove: (id: string) => void
  onReject: (id: string) => void
  onSimulate?: (task: Task) => void
  onChoose?: (id: string, option: ChoiceOption) => void
  onBuy?: (text: string) => void // sends a card chip's message (token Buy, airdrop Farm/Buy) as the user
  choicesEnabled?: boolean // choice and Buy buttons (off while the agent is busy or offline)
}

function AssistantBody({ message, onApprove, onReject, onSimulate, onChoose, onBuy, choicesEnabled = true }: { message: AssistantMessage } & MessageActions) {
  switch (message.kind) {
    case 'text':
      return <TextBubble text={message.text} />
    case 'balance':
      return <BalanceCard holdings={message.holdings} />
    case 'balance_change':
      return <BalanceChangeCard changes={message.changes} />
    case 'tokens':
      return <TokenListCard title={message.title} items={message.items} enabled={choicesEnabled} onBuy={(text) => onBuy?.(text)} />
    case 'confirm':
      return (
        <ConfirmCard
          tx={message.tx}
          state={message.state}
          onApprove={() => onApprove(message.id)}
          onReject={() => onReject(message.id)}
        />
      )
    case 'status':
      return <StatusCard state={message.state} text={message.text} hash={message.hash} />
    case 'task':
      return <TaskCard task={message.task} onSimulate={onSimulate} />
    case 'choice':
      return (
        <ChoiceCard
          question={message.question}
          options={message.options}
          chosen={message.chosen}
          closed={message.closed}
          enabled={choicesEnabled}
          onChoose={(o) => onChoose?.(message.id, o)}
        />
      )
    case 'airdrops':
      return <AirdropCard title={message.title} items={message.items} enabled={choicesEnabled} onSend={(text) => onBuy?.(text)} />
    case 'unlocks':
      return <UnlockListCard title={message.title} items={message.items} enabled={choicesEnabled} onBuy={(text) => onBuy?.(text)} />
    case 'subscription':
      return <SubscriptionCard plan={message.plan} chargedUsd={message.chargedUsd} renews={message.renews} />
  }
}

// queued: typed or spoken while the agent was busy; sent after the current turn.
export function MessageItem({ message, queued, ...actions }: { message: Message; queued?: boolean } & MessageActions) {
  if (message.role === 'user') {
    const tag = queued ? 'Queued' : message.unsent ? 'Not sent' : null
    return (
      <div className="flex flex-col items-end gap-1">
        <div
          className={`max-w-[85%] min-w-0 rounded-2xl rounded-br-md bg-primary px-4 py-2.5 wrap-anywhere text-primary-foreground ${tag ? 'opacity-50' : ''}`}
        >
          {message.spoken && <Mic className="mr-1.5 inline size-3.5 align-[-2px]" />}
          {message.text}
        </div>
        {tag && <span className={`px-1 text-xs ${message.unsent ? 'text-destructive' : 'text-muted-foreground'}`}>{tag}</span>}
      </div>
    )
  }
  return (
    <div className="flex justify-start">
      <div className="w-full min-w-0 max-w-[85%]">
        <AssistantBody message={message} {...actions} />
      </div>
    </div>
  )
}
