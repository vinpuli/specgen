import type { ReactNode } from 'react'

type AlertVariant = 'info' | 'success' | 'warning' | 'danger'

type AlertProps = {
  title?: string
  children: ReactNode
  variant?: AlertVariant
}

const styleMap: Record<AlertVariant, string> = {
  info: 'border-primary/30 bg-primary/10 text-fg',
  success: 'border-success/30 bg-success/10 text-fg',
  warning: 'border-warning/30 bg-warning/10 text-fg',
  danger: 'border-danger/30 bg-danger/10 text-fg',
}

export function Alert({ title, children, variant = 'info' }: AlertProps) {
  return (
    <div className={['rounded-md border px-4 py-3', styleMap[variant]].join(' ')} role="alert">
      {title ? <h3 className="text-sm font-semibold">{title}</h3> : null}
      <div className={title ? 'mt-1 text-sm' : 'text-sm'}>{children}</div>
    </div>
  )
}
