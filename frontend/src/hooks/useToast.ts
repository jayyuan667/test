import { useCallback, useRef, useState } from 'react'

export interface Toast {
  id: number
  message: string
  type: 'error' | 'success' | 'info'
}

export function useToast() {
  const [toasts, setToasts] = useState<Toast[]>([])
  const nextId = useRef(0)

  const show = useCallback((message: string, type: Toast['type'] = 'error') => {
    const id = nextId.current++
    setToasts(prev => [...prev, { id, message, type }])
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id))
    }, 4000)
  }, [])

  return { toasts, show }
}
