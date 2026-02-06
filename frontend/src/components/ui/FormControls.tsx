import { useId, useState, type InputHTMLAttributes } from 'react'

export function Checkbox({ label, ...props }: InputHTMLAttributes<HTMLInputElement> & { label: string }) {
  const id = useId()
  return (
    <label htmlFor={id} className="inline-flex items-center gap-2 text-sm text-fg">
      <input type="checkbox" className="h-4 w-4 rounded border-border text-primary focus:ring-primary/40" {...props} id={id} />
      <span>{label}</span>
    </label>
  )
}

export type RadioOption = { value: string; label: string }

type RadioGroupProps = {
  name: string
  options: RadioOption[]
  value: string
  onChange: (value: string) => void
}

export function RadioGroup({ name, options, value, onChange }: RadioGroupProps) {
  return (
    <div className="flex flex-col gap-2">
      {options.map((option) => (
        <label key={option.value} className="inline-flex items-center gap-2 text-sm text-fg">
          <input
            type="radio"
            name={name}
            value={option.value}
            checked={value === option.value}
            onChange={() => onChange(option.value)}
            className="h-4 w-4 border-border text-primary focus:ring-primary/40"
          />
          <span>{option.label}</span>
        </label>
      ))}
    </div>
  )
}

type ToggleProps = {
  enabled: boolean
  onChange: (enabled: boolean) => void
  label?: string
  ariaLabel?: string
}

export function Toggle({ enabled, onChange, label, ariaLabel }: ToggleProps) {
  return (
    <label className="inline-flex items-center gap-3 text-sm text-fg">
      {label ? <span>{label}</span> : null}
      <button
        type="button"
        onClick={() => onChange(!enabled)}
        className={[
          'relative inline-flex h-6 w-11 items-center rounded-full transition',
          enabled ? 'bg-primary' : 'bg-secondary',
        ].join(' ')}
        role="switch"
        aria-checked={enabled}
        aria-label={label ? undefined : ariaLabel}
      >
        <span
          className={[
            'inline-block h-4 w-4 transform rounded-full bg-white transition',
            enabled ? 'translate-x-6' : 'translate-x-1',
          ].join(' ')}
        />
      </button>
    </label>
  )
}

type ProgressProps = {
  value: number
  max?: number
  label?: string
}

export function Progress({ value, max = 100, label }: ProgressProps) {
  const ratio = max <= 0 ? 0 : Math.max(0, Math.min(100, Math.round((value / max) * 100)))
  const clampedValue = Math.max(0, Math.min(max || 0, value))
  return (
    <div className="w-full">
      <div className="mb-1 flex items-center justify-between text-xs text-fg/70">
        <span>{label ?? 'Progress'}</span>
        <span>{ratio}%</span>
      </div>
      <div className="h-2 w-full rounded-full bg-secondary" role="progressbar" aria-valuemin={0} aria-valuemax={max} aria-valuenow={clampedValue}>
        <div className="h-2 rounded-full bg-primary transition-all" style={{ width: `${ratio}%` }} />
      </div>
    </div>
  )
}

export function useToggle(initial = false) {
  const [enabled, setEnabled] = useState(initial)
  return { enabled, setEnabled }
}
