import { Button } from '@/components/ui/button'
import type { Task } from '@/types'
import { TASK_ICONS } from './task-icons'

export function TaskCard({ task, onSimulate }: { task: Task; onSimulate?: (task: Task) => void }) {
  const Icon = TASK_ICONS[task.kind]
  return (
    <div className="rounded-2xl border bg-card p-4">
      <div className="flex items-start gap-3">
        <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-primary/15 text-primary">
          <Icon className="size-4" />
        </span>
        <div className="min-w-0">
          <p className="font-medium">{task.description}</p>
          <p className="text-sm text-muted-foreground">{task.schedule}</p>
        </div>
      </div>
      {task.trigger && onSimulate && (
        <Button variant="secondary" size="sm" className="mt-3" onClick={() => onSimulate(task)}>
          Simulate trigger
        </Button>
      )}
    </div>
  )
}
