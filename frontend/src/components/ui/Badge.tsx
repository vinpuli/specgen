import type { ReactNode } from 'react'

type BadgeVariant = 'default' | 'success' | 'warning' | 'danger' | 'outline'

type BadgeProps = {
  children: ReactNode
  variant?: BadgeVariant
}

const variantClass: Record<BadgeVariant, string> = {
  default: 'bg-primary/15 text-primary border-transparent',
  success: 'bg-success/15 text-success border-transparent',
  warning: 'bg-warning/20 text-warning border-transparent',
  danger: 'bg-danger/15 text-danger border-transparent',
  outline: 'bg-transparent text-fg border-border',
}

export function Badge({ children, variant = 'default' }: BadgeProps) {
  return (
    <span
      className={[
        'inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold tracking-wide',
        variantClass[variant],
      ].join(' ')}
    >
      {children}
    </span>
  )
}
