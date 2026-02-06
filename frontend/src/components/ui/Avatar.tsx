type AvatarProps = {
  src?: string
  alt?: string
  name?: string
  size?: 'sm' | 'md' | 'lg'
}

const sizeClass = {
  sm: 'h-8 w-8 text-xs',
  md: 'h-10 w-10 text-sm',
  lg: 'h-14 w-14 text-base',
}

function initialsFromName(name?: string): string {
  const trimmedName = (name || '').trim()
  if (!trimmedName) {
    return '?'
  }
  const parts = trimmedName.split(/\s+/).filter(Boolean)
  if (parts.length === 1) {
    return parts[0].slice(0, 2).toUpperCase()
  }
  return `${parts[0][0] ?? ''}${parts[1][0] ?? ''}`.toUpperCase()
}

export function Avatar({ src, alt = 'Avatar', name, size = 'md' }: AvatarProps) {
  if (src) {
    return (
      <img
        src={src}
        alt={alt}
        className={[sizeClass[size], 'rounded-full border border-border object-cover'].join(' ')}
      />
    )
  }

  return (
    <div
      aria-label={alt}
      className={[
        sizeClass[size],
        'inline-flex items-center justify-center rounded-full border border-border bg-primary/10 font-semibold text-primary',
      ].join(' ')}
    >
      {initialsFromName(name)}
    </div>
  )
}
