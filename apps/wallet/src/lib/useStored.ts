import { useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'
import { readJSON, writeJSON } from './storage'

export function useStored<T>(key: string, initial: T) {
  const [value, setValue] = useState<T>(() => readJSON(key, initial))
  const warned = useRef(false)
  useEffect(() => {
    if (writeJSON(key, value) || warned.current) return
    warned.current = true
    toast.error("Couldn't save your changes — browser storage is unavailable. They'll be lost on reload.")
  }, [key, value])
  return [value, setValue] as const
}
