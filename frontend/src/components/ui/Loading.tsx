import type { HTMLAttributes } from 'react'

type SpinnerProps = {
  size?: 'sm' | 'md' | 'lg'
}

const sizeClass = {
  sm: 'h-4 w-4 border-2',
  md: 'h-6 w-6 border-2',
  lg: 'h-8 w-8 border-[3px]',
}

export function LoadingSpinner({ size = 'md' }: SpinnerProps) {
  return <span className={[sizeClass[size], 'inline-block animate-spin rounded-full border-primary border-t-transparent'].join(' ')} aria-label="Loading" />
}

export function Skeleton({ className = '', ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={['animate-pulse rounded-md bg-secondary', className].join(' ')} {...props} />
}
