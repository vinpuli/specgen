import type { ReactNode } from 'react'

type CardProps = {
  children: ReactNode
  className?: string
}

export function Card({ children, className = '' }: CardProps) {
  return <article className={['rounded-lg border border-border bg-surface shadow-card', className].join(' ')}>{children}</article>
}

export function CardHeader({ children, className = '' }: CardProps) {
  return <header className={['border-b border-border px-5 py-4', className].join(' ')}>{children}</header>
}

export function CardContent({ children, className = '' }: CardProps) {
  return <div className={['px-5 py-4', className].join(' ')}>{children}</div>
}

export function CardFooter({ children, className = '' }: CardProps) {
  return <footer className={['border-t border-border px-5 py-4', className].join(' ')}>{children}</footer>
}
