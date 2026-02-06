import { createContext, useCallback, useContext, useMemo, useState, useRef, useEffect, type ReactNode } from 'react'

type ToastVariant = 'info' | 'success' | 'warning' | 'error'

type ToastItem = {
  id: string
  message: string
  variant: ToastVariant
}

type ToastContextValue = {
  pushToast: (message: string, variant?: ToastVariant) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

const variantClass: Record<ToastVariant, string> = {
  info: 'border-primary/30 bg-primary/10 text-fg',
  success: 'border-success/30 bg-success/10 text-fg',
  warning: 'border-warning/30 bg-warning/10 text-fg',
  error: 'border-danger/30 bg-danger/10 text-fg',
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [queue, setQueue] = useState<ToastItem[]>([])
  const timeoutIdsRef = useRef<Map<string, NodeJS.Timeout>>(new Map())

  const removeToast = useCallback((id: string) => {
    const timeoutId = timeoutIdsRef.current.get(id)
    if (timeoutId) {
      clearTimeout(timeoutId)
      timeoutIdsRef.current.delete(id)
    }
    setQueue((prev) => prev.filter((item) => item.id !== id))
  }, [])

  const pushToast = useCallback((message: string, variant: ToastVariant = 'info') => {
    const id = `${Date.now()}-${Math.random().toString(16).slice(2)}`
    setQueue((prev) => [...prev, { id, message, variant }])
    const timeoutId = window.setTimeout(() => removeToast(id), 3500)
    timeoutIdsRef.current.set(id, timeoutId)
  }, [removeToast])

  useEffect(() => {
    return () => {
      timeoutIdsRef.current.forEach((timeoutId) => {
        clearTimeout(timeoutId)
      })
      timeoutIdsRef.current.clear()
    }
  }, [])

  const value = useMemo<ToastContextValue>(() => ({ pushToast }), [pushToast])

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed bottom-4 right-4 z-[70] flex w-full max-w-sm flex-col gap-2">
        {queue.map((toast) => (
          <div
            key={toast.id}
            className={[
              'pointer-events-auto rounded-md border px-4 py-3 text-sm shadow-card',
              variantClass[toast.variant],
            ].join(' ')}
            role="alert"
            aria-live="assertive"
            aria-atomic="true"
          >
            <div className="flex items-start justify-between gap-3">
              <p>{toast.message}</p>
              <button
                type="button"
                onClick={() => removeToast(toast.id)}
                className="text-xs font-semibold text-fg/70 hover:text-fg"
                aria-label={`Close ${toast.variant}: ${toast.message}`}
              >
                CLOSE
              </button>
            </div>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const context = useContext(ToastContext)
  if (!context) {
    throw new Error('useToast must be used within ToastProvider')
  }
  return context
}
