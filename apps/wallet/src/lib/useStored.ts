import { useEffect, useState } from 'react'
import { readJSON, writeJSON } from './storage'

export function useStored<T>(key: string, initial: T) {
  const [value, setValue] = useState<T>(() => readJSON(key, initial))
  useEffect(() => {
    writeJSON(key, value)
  }, [key, value])
  return [value, setValue] as const
}
