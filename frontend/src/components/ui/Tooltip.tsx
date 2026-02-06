import { useId, useState, type ReactNode } from 'react'

type TooltipProps = {
  content: ReactNode
  children: ReactNode
}

export function Tooltip({ content, children }: TooltipProps) {
  const [open, setOpen] = useState(false)
  const tooltipId = useId()

  const handleKeyDown = (event: React.KeyboardEvent<HTMLSpanElement>) => {
    if (event.key === 'Escape') {
      setOpen(false)
    } else if (event.key === 'Enter' || event.key === ' ') {
      setOpen((prev) => !prev)
    }
  }

  return (
    <span className="relative inline-flex" onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}>
      <span
        tabIndex={0}
        role="button"
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onKeyDown={handleKeyDown}
        aria-describedby={open ? tooltipId : undefined}
      >
        {children}
      </span>
      {open ? (
        <span
          id={tooltipId}
          role="tooltip"
          className="absolute left-1/2 top-full z-30 mt-2 -translate-x-1/2 whitespace-nowrap rounded-md bg-fg px-2.5 py-1 text-xs text-bg shadow-card"
        >
          {content}
        </span>
      ) : null}
    </span>
  )
}
