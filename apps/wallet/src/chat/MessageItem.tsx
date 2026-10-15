import { Mic } from 'lucide-react'
import type { AssistantMessage, Message, Task } from '@/types'
import { BalanceCard } from './cards/BalanceCard'
import { ConfirmCard } from './cards/ConfirmCard'
import { StatusCard } from './cards/StatusCard'
import { TaskCard } from './cards/TaskCard'
import { TextBubble } from './cards/TextBubble'

export type MessageActions = {
  onApprove: (id: string) => void
  onReject: (id: string) => void
  onSimulate: (task: Task) => void
}

function AssistantBody({ message, onApprove, onReject, onSimulate }: { message: AssistantMessage } & MessageActions) {
  switch (message.kind) {
    case 'text':
      return <TextBubble text={message.text} />
    case 'balance':
      return <BalanceCard holdings={message.holdings} />
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
  }
}

export function MessageItem({ message, ...actions }: { message: Message } & MessageActions) {
  if (message.role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-br-md bg-primary px-4 py-2.5 text-primary-foreground">
          {message.spoken && <Mic className="mr-1.5 inline size-3.5 align-[-2px]" />}
          {message.text}
        </div>
      </div>
    )
  }
  return (
    <div className="flex justify-start">
      <div className="w-full max-w-[85%]">
        <AssistantBody message={message} {...actions} />
      </div>
    </div>
  )
}
