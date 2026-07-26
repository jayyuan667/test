import { createContext, useContext, useState, useCallback, useRef, type ReactNode } from 'react'

export interface Toast {
  id: number
  message: string
  type: 'error' | 'success' | 'info'
}

interface ToastContextValue {
  toasts: Toast[]
  show: (message: string, type?: Toast['type']) => void
}

const ToastCtx = createContext<ToastContextValue | null>(null)

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const nextId = useRef(0)

  const show = useCallback((message: string, type: Toast['type'] = 'error') => {
    const id = nextId.current++
    setToasts(prev => [...prev, { id, message, type }])
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id))
    }, 4000)
  }, [])

  return (
    <ToastCtx.Provider value={{ toasts, show }}>
      {children}
    </ToastCtx.Provider>
  )
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastCtx)
  if (!ctx) throw new Error('useToast must be used within ToastProvider')
  return ctx
}
