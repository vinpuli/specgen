import { forwardRef, type SelectHTMLAttributes } from 'react'

export type SelectOption = {
  value: string
  label: string
}

export type SelectProps = SelectHTMLAttributes<HTMLSelectElement> & {
  label?: string
  helperText?: string
  options: SelectOption[]
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { label, helperText, options, className = '', id, ...props },
  ref,
) {
  const resolvedId = id ?? props.name
  return (
    <label className="flex w-full flex-col gap-1.5 text-sm" htmlFor={resolvedId}>
      {label ? <span className="font-medium text-fg">{label}</span> : null}
      <select
        ref={ref}
        id={resolvedId}
        className={[
          'h-10 w-full rounded-md border border-border bg-surface px-3 text-fg outline-none transition',
          'focus:ring-2 focus:ring-primary/40',
          className,
        ].join(' ')}
        {...props}
      >
        {options.map((option, index) => (
          <option key={`${option.value}-${index}`} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      {helperText ? <span className="text-xs text-fg/60">{helperText}</span> : null}
    </label>
  )
})
