import { Bell, Repeat, Zap, type LucideIcon } from 'lucide-react'
import type { TaskKind } from '@/types'

export const TASK_ICONS: Record<TaskKind, LucideIcon> = { dca: Repeat, alert: Bell, conditional: Zap }
