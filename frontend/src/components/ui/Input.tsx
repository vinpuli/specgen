import { forwardRef, type InputHTMLAttributes } from 'react'

type InputState = 'default' | 'error' | 'success'

export type InputProps = InputHTMLAttributes<HTMLInputElement> & {
  label?: string
  helperText?: string
  state?: InputState
}

const stateClasses: Record<InputState, string> = {
  default: 'border-border focus:ring-primary/40',
  error: 'border-danger focus:ring-danger/30',
  success: 'border-success focus:ring-success/30',
}

const helperClasses: Record<InputState, string> = {
  default: 'text-fg/60',
  error: 'text-danger',
  success: 'text-success',
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { label, helperText, state = 'default', className = '', id, ...props },
  ref,
) {
  const resolvedId = id ?? props.name
  return (
    <label className="flex w-full flex-col gap-1.5 text-sm" htmlFor={resolvedId}>
      {label ? <span className="font-medium text-fg">{label}</span> : null}
      <input
        ref={ref}
        id={resolvedId}
        className={[
          'h-10 w-full rounded-md bg-surface px-3 text-fg outline-none ring-offset-bg transition',
          'focus:ring-2',
          stateClasses[state],
          className,
        ].join(' ')}
        {...props}
      />
      {helperText ? <span className={["text-xs", helperClasses[state]].join(' ')}>{helperText}</span> : null}
    </label>
  )
})
