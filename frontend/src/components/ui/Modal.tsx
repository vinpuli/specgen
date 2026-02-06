import { useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { Button } from './Button'

type ModalProps = {
  open: boolean
  title: string
  children: React.ReactNode
  onClose: () => void
  onConfirm?: () => void
  confirmLabel?: string
}

export function Modal({
  open,
  title,
  children,
  onClose,
  onConfirm,
  confirmLabel = 'Confirm',
}: ModalProps) {
  const previousActiveElement = useRef<Element | null>(null)
  const modalContentRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (!open) {
      if (previousActiveElement.current && previousActiveElement.current instanceof HTMLElement) {
        previousActiveElement.current.focus()
      }
      return
    }

    previousActiveElement.current = document.activeElement

    function onEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        onClose()
      }
    }

    const modal = modalContentRef.current
    if (modal) {
      setTimeout(() => {
        const focusableElements = modal.querySelectorAll(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        )
        if (focusableElements.length > 0) {
          ;(focusableElements[focusableElements.length - 1] as HTMLElement).focus()
        }
      }, 0)
    }

    document.addEventListener('keydown', onEscape)
    return () => document.removeEventListener('keydown', onEscape)
  }, [open, onClose])

  if (!open) {
    return null
  }

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-fg/40 p-4"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
    >
      <div
        ref={modalContentRef}
        className="w-full max-w-lg rounded-lg border border-border bg-surface p-6 shadow-card animate-[fadeIn_.18s_ease-out]"
        onClick={(event) => event.stopPropagation()}
      >
        <h2 id="modal-title" className="text-xl font-semibold text-fg">{title}</h2>
        <div className="mt-3 text-sm text-fg/80">{children}</div>
        <div className="mt-6 flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          {onConfirm ? <Button onClick={onConfirm}>{confirmLabel}</Button> : null}
        </div>
      </div>
    </div>,
    document.body,
  )
}
