import { useMemo } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Avatar, DropdownMenu } from '../ui'

type HeaderProps = {
  title?: string
}

function humanize(segment: string): string {
  if (!segment) {
    return 'Home'
  }
  return segment
    .split('-')
    .filter(Boolean)
    .map((part) => part[0]?.toUpperCase() + part.slice(1))
    .join(' ')
}

export function Header({ title }: HeaderProps) {
  const location = useLocation()

  const breadcrumbs = useMemo(() => {
    const segments = location.pathname.split('/').filter(Boolean)
    const crumbs = [{ label: 'Home', path: '/' }]
    let currentPath = ''
    for (const segment of segments) {
      currentPath += `/${segment}`
      crumbs.push({ label: humanize(segment), path: currentPath })
    }
    return crumbs
  }, [location.pathname])

  const effectiveTitle = title ?? breadcrumbs[breadcrumbs.length - 1]?.label ?? 'Home'

  return (
    <header className="border-b border-border bg-surface/95 px-4 py-3 backdrop-blur sm:px-6 lg:px-8">
      <div className="flex items-center justify-between gap-4">
        <div>
          <nav className="flex items-center gap-2 text-xs text-fg/60" aria-label="Breadcrumb">
            {breadcrumbs.map((crumb, index) => (
              <span key={crumb.path} className="inline-flex items-center gap-2">
                {index > 0 ? <span>/</span> : null}
                <Link to={crumb.path} className="hover:text-fg">
                  {crumb.label}
                </Link>
              </span>
            ))}
          </nav>
          <h1 className="mt-1 text-xl font-semibold text-fg">{effectiveTitle}</h1>
        </div>

        <DropdownMenu
          trigger={
            <span className="inline-flex items-center gap-2 rounded-md border border-border bg-surface px-2 py-1.5">
              <Avatar name="SpecGen User" size="sm" />
              <span className="text-sm text-fg">User</span>
            </span>
          }
          items={[
            { id: 'profile', label: 'Profile', onSelect: () => console.info('Profile selected') },
            { id: 'workspace', label: 'Workspace Settings', onSelect: () => console.info('Workspace selected') },
            { id: 'logout', label: 'Logout', onSelect: () => console.info('Logout selected') },
          ]}
        />
      </div>
    </header>
  )
}
