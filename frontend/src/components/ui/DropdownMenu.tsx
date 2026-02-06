import { useEffect, useRef, useState, type ReactNode } from 'react'

type MenuItem = {
  id: string
  label: string
  onSelect: () => void
  icon?: ReactNode
  disabled?: boolean
}

type DropdownMenuProps = {
  trigger: ReactNode
  items: MenuItem[]
  align?: 'left' | 'right'
}

export function DropdownMenu({ trigger, items, align = 'right' }: DropdownMenuProps) {
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement | null>(null)
  const triggerRef = useRef<HTMLButtonElement | null>(null)
  const menuRef = useRef<HTMLDivElement | null>(null)
  const itemRefs = useRef<(HTMLButtonElement | null)[]>([])

  useEffect(() => {
    function handleOutsideClick(event: MouseEvent) {
      if (!containerRef.current?.contains(event.target as Node)) {
        setOpen(false)
      }
    }

    document.addEventListener('mousedown', handleOutsideClick)
    return () => document.removeEventListener('mousedown', handleOutsideClick)
  }, [])

  useEffect(() => {
    if (open) {
      const firstNonDisabledIndex = items.findIndex((item) => !item.disabled)
      if (firstNonDisabledIndex >= 0 && itemRefs.current[firstNonDisabledIndex]) {
        itemRefs.current[firstNonDisabledIndex]?.focus()
      }
    } else {
      triggerRef.current?.focus()
    }
  }, [open, items])

  const handleMenuKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Escape') {
      setOpen(false)
      triggerRef.current?.focus()
      return
    }

    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault()
      const currentIndex = itemRefs.current.findIndex(
        (ref) => ref === document.activeElement
      )
      const direction = event.key === 'ArrowDown' ? 1 : -1
      let nextIndex = currentIndex + direction

      while (nextIndex >= 0 && nextIndex < items.length) {
        if (!items[nextIndex].disabled && itemRefs.current[nextIndex]) {
          itemRefs.current[nextIndex]?.focus()
          return
        }
        nextIndex += direction
      }
    }

    if (event.key === 'Enter' || event.key === ' ') {
      const currentIndex = itemRefs.current.findIndex(
        (ref) => ref === document.activeElement
      )
      if (currentIndex >= 0 && items[currentIndex]) {
        event.preventDefault()
        items[currentIndex].onSelect()
        setOpen(false)
      }
    }
  }

  return (
    <div ref={containerRef} className="relative inline-flex">
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className="inline-flex"
        aria-haspopup="menu"
        aria-expanded={open}
      >
        {trigger}
      </button>
      {open ? (
        <div
          ref={menuRef}
          className={[
            'absolute top-full z-20 mt-2 min-w-44 rounded-md border border-border bg-surface p-1 shadow-card',
            align === 'right' ? 'right-0' : 'left-0',
          ].join(' ')}
          role="menu"
          onKeyDown={handleMenuKeyDown}
        >
          {items.map((item, index) => (
            <button
              ref={(el) => {
                itemRefs.current[index] = el
              }}
              key={item.id}
              type="button"
              disabled={item.disabled}
              onClick={() => {
                if (item.disabled) {
                  return
                }
                item.onSelect()
                setOpen(false)
              }}
              className={[
                'flex w-full items-center gap-2 rounded px-3 py-2 text-sm text-left text-fg',
                item.disabled ? 'cursor-not-allowed opacity-50' : 'hover:bg-secondary',
              ].join(' ')}
              role="menuitem"
            >
              {item.icon}
              {item.label}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  )
}
