import { forwardRef, type ButtonHTMLAttributes } from 'react'

type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'ghost'
type ButtonSize = 'sm' | 'md' | 'lg'

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant
  size?: ButtonSize
  fullWidth?: boolean
}

const variantClasses: Record<ButtonVariant, string> = {
  primary: 'bg-primary text-primary-foreground hover:opacity-95',
  secondary: 'bg-secondary text-fg hover:bg-secondary/80',
  danger: 'bg-danger text-primary-foreground hover:opacity-95',
  ghost: 'bg-transparent text-fg hover:bg-secondary',
}

const sizeClasses: Record<ButtonSize, string> = {
  sm: 'h-8 px-3 text-sm',
  md: 'h-10 px-4 text-sm',
  lg: 'h-12 px-5 text-base',
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { className = '', variant = 'primary', size = 'md', fullWidth = false, disabled, ...props },
  ref,
) {
  const disabledClasses = disabled ? 'cursor-not-allowed opacity-60' : ''
  return (
    <button
      ref={ref}
      disabled={disabled}
      className={[
        'inline-flex items-center justify-center rounded-md font-medium transition',
        'focus:outline-none focus:ring-2 focus:ring-primary/40 focus:ring-offset-2 focus:ring-offset-bg',
        variantClasses[variant],
        sizeClasses[size],
        fullWidth ? 'w-full' : '',
        disabledClasses,
        className,
      ].join(' ')}
      {...props}
    />
  )
})
