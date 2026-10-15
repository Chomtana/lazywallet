import { Pause, Play, Trash2 } from 'lucide-react'
import { TASK_ICONS } from '@/chat/cards/task-icons'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import type { Task } from '@/types'

type Props = { open: boolean; onOpenChange: (v: boolean) => void; tasks: Task[]; onChange: (tasks: Task[]) => void }

export function TasksSheet({ open, onOpenChange, tasks, onChange }: Props) {
  const toggle = (id: string) =>
    onChange(tasks.map((t) => (t.id === id ? { ...t, status: t.status === 'active' ? 'paused' : 'active' } : t)))

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full sm:max-w-md">
        <SheetHeader>
          <SheetTitle>Scheduled tasks</SheetTitle>
          <SheetDescription>Tasks run only while this tab is open. You approve every transaction.</SheetDescription>
        </SheetHeader>
        <div className="flex-1 overflow-y-auto px-4 pb-4">
          {tasks.length === 0 ? (
            <p className="py-10 text-center text-sm text-muted-foreground">
              No tasks yet. Try “Alert me if ETH drops below 3000”.
            </p>
          ) : (
            <ul className="divide-y">
              {tasks.map((t) => {
                const Icon = TASK_ICONS[t.kind]
                return (
                  <li key={t.id} className="flex items-center gap-3 py-3">
                    <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-primary/15 text-primary">
                      <Icon className="size-4" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="font-medium">{t.description}</p>
                      <p className="text-xs text-muted-foreground">{t.schedule}</p>
                      {t.status === 'paused' && (
                        <Badge variant="secondary" className="mt-1">
                          Paused
                        </Badge>
                      )}
                    </div>
                    <Button
                      size="icon"
                      variant="ghost"
                      aria-label={t.status === 'active' ? 'Pause task' : 'Resume task'}
                      onClick={() => toggle(t.id)}
                    >
                      {t.status === 'active' ? <Pause /> : <Play />}
                    </Button>
                    <Button
                      size="icon"
                      variant="ghost"
                      aria-label="Delete task"
                      onClick={() => onChange(tasks.filter((x) => x.id !== t.id))}
                    >
                      <Trash2 />
                    </Button>
                  </li>
                )
              })}
            </ul>
          )}
        </div>
      </SheetContent>
    </Sheet>
  )
}
